import ctypes
import time
import numpy as np

from picosdk.ps5000a import ps5000a as ps
from picosdk.functions import adc2mV, assert_pico_ok


class PicoScope5442D:
    def __init__(self):
        self.chandle = ctypes.c_int16()
        self.status = {}

        self.connected = False
        self.max_adc = ctypes.c_int16()

        self.channel = "A"
        self.channel_enum = ps.PS5000A_CHANNEL["PS5000A_CHANNEL_A"]
        self.range_name = "PS5000A_5V"
        self.range_enum = ps.PS5000A_RANGE[self.range_name]
        self.coupling_enum = ps.PS5000A_COUPLING["PS5000A_DC"]

        self.trigger_enabled = True
        self.trigger_threshold_mv = 500
        self.trigger_direction = ps.PS5000A_THRESHOLD_DIRECTION["PS5000A_RISING"]
        self.trigger_delay = 0
        self.auto_trigger_ms = 1000

        self.pre_trigger_samples = 500
        self.post_trigger_samples = 1500
        self.timebase = 4

        self.buffer_max = None
        self.buffer_min = None
        self.time_interval_ns = None

    def connect(self):
        resolution = ps.PS5000A_DEVICE_RESOLUTION["PS5000A_DR_8BIT"]

        self.status["openunit"] = ps.ps5000aOpenUnit(
            ctypes.byref(self.chandle),
            None,
            resolution
        )
        assert_pico_ok(self.status["openunit"])

        self.status["maximumValue"] = ps.ps5000aMaximumValue(
            self.chandle,
            ctypes.byref(self.max_adc)
        )
        assert_pico_ok(self.status["maximumValue"])

        self.connected = True
        return "PicoScope 5442D connected"

    def close(self):
        if self.connected:
            self.status["close"] = ps.ps5000aCloseUnit(self.chandle)
            self.connected = False

    def configure_channel(
        self,
        channel="A",
        vrange="PS5000A_5V",
        coupling="PS5000A_DC",
        offset_v=0.0,
        enabled=True
    ):
        if not self.connected:
            raise RuntimeError("PicoScope not connected")

        channel_map = {
            "A": "PS5000A_CHANNEL_A",
            "B": "PS5000A_CHANNEL_B",
            "C": "PS5000A_CHANNEL_C",
            "D": "PS5000A_CHANNEL_D",
        }

        self.channel = channel
        self.channel_enum = ps.PS5000A_CHANNEL[channel_map[channel]]
        self.range_name = vrange
        self.range_enum = ps.PS5000A_RANGE[vrange]
        self.coupling_enum = ps.PS5000A_COUPLING[coupling]

        self.status[f"setCh{channel}"] = ps.ps5000aSetChannel(
            self.chandle,
            self.channel_enum,
            int(enabled),
            self.coupling_enum,
            self.range_enum,
            ctypes.c_float(offset_v)
        )
        assert_pico_ok(self.status[f"setCh{channel}"])

    def configure_trigger(
        self,
        threshold_mv=500,
        direction="RISING",
        auto_trigger_ms=1000,
        enabled=True
    ):
        if not self.connected:
            raise RuntimeError("PicoScope not connected")

        self.trigger_enabled = enabled
        self.trigger_threshold_mv = threshold_mv
        self.auto_trigger_ms = auto_trigger_ms

        direction_map = {
            "RISING": "PS5000A_RISING",
            "FALLING": "PS5000A_FALLING",
        }
        self.trigger_direction = ps.PS5000A_THRESHOLD_DIRECTION[direction_map[direction]]

        # 这里先按模拟通道触发骨架写。
        # 你后面如果走真正 EXT 口触发，需要再切到 EXT 对应枚举和阈值。
        threshold_adc = int(threshold_mv * self.max_adc.value / 5000)

        self.status["trigger"] = ps.ps5000aSetSimpleTrigger(
            self.chandle,
            int(enabled),
            self.channel_enum,
            threshold_adc,
            self.trigger_direction,
            self.trigger_delay,
            self.auto_trigger_ms
        )
        assert_pico_ok(self.status["trigger"])

    def configure_block(
        self,
        pre_trigger_samples=500,
        post_trigger_samples=1500,
        timebase=4
    ):
        if not self.connected:
            raise RuntimeError("PicoScope not connected")

        self.pre_trigger_samples = pre_trigger_samples
        self.post_trigger_samples = post_trigger_samples
        self.timebase = timebase

        total_samples = pre_trigger_samples + post_trigger_samples

        self.buffer_max = (ctypes.c_int16 * total_samples)()
        self.buffer_min = (ctypes.c_int16 * total_samples)()

        segment_index = 0

        self.status["setDataBuffers"] = ps.ps5000aSetDataBuffers(
            self.chandle,
            self.channel_enum,
            ctypes.byref(self.buffer_max),
            ctypes.byref(self.buffer_min),
            total_samples,
            segment_index,
            ps.PS5000A_RATIO_MODE["PS5000A_RATIO_MODE_NONE"]
        )
        assert_pico_ok(self.status["setDataBuffers"])

        time_interval_ns = ctypes.c_float()
        returned_max_samples = ctypes.c_int32()

        self.status["getTimebase2"] = ps.ps5000aGetTimebase2(
            self.chandle,
            self.timebase,
            total_samples,
            ctypes.byref(time_interval_ns),
            ctypes.byref(returned_max_samples),
            0
        )
        assert_pico_ok(self.status["getTimebase2"])

        self.time_interval_ns = time_interval_ns.value

    def arm(self):
        if not self.connected:
            raise RuntimeError("PicoScope not connected")

        time_indisposed_ms = ctypes.c_int32()

        self.status["runBlock"] = ps.ps5000aRunBlock(
            self.chandle,
            self.pre_trigger_samples,
            self.post_trigger_samples,
            self.timebase,
            ctypes.byref(time_indisposed_ms),
            0,
            None,
            None
        )
        assert_pico_ok(self.status["runBlock"])

    def wait_until_ready(self, timeout=5.0, poll_interval=0.01):
        if not self.connected:
            raise RuntimeError("PicoScope not connected")

        ready = ctypes.c_int16(0)
        t0 = time.time()

        while ready.value == 0:
            self.status["isReady"] = ps.ps5000aIsReady(
                self.chandle,
                ctypes.byref(ready)
            )

            if time.time() - t0 > timeout:
                raise TimeoutError("PicoScope acquisition timeout")

            time.sleep(poll_interval)

    def read_data(self):
        if not self.connected:
            raise RuntimeError("PicoScope not connected")

        total_samples = self.pre_trigger_samples + self.post_trigger_samples
        c_total_samples = ctypes.c_int32(total_samples)
        overflow = ctypes.c_int16()

        self.status["getValues"] = ps.ps5000aGetValues(
            self.chandle,
            0,
            ctypes.byref(c_total_samples),
            1,
            ps.PS5000A_RATIO_MODE["PS5000A_RATIO_MODE_NONE"],
            0,
            ctypes.byref(overflow)
        )
        assert_pico_ok(self.status["getValues"])

        data_mv = adc2mV(self.buffer_max, self.range_enum, self.max_adc)
        data_mv = np.array(data_mv[:c_total_samples.value], dtype=np.float64)

        t = np.arange(c_total_samples.value) * self.time_interval_ns * 1e-9
        return t, data_mv