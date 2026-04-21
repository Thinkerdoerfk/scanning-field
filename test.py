import time
import numpy as np
import matplotlib.pyplot as plt
import pypicosdk.pypicosdk as psdk


def main():
    scope = psdk.ps5000a()
    scope.open_unit()

    try:
        print("Connected:", scope.get_unit_serial())

        # 1) fixed 8-bit
        scope.set_device_resolution(psdk.RESOLUTION.BIT_8)

        # 2) turn all channels off first
        scope.set_all_channels_off()

        # 3) channel A: trigger reference input
        scope.set_channel(
            channel=psdk.CHANNEL.A,
            coupling=psdk.COUPLING.DC,
            range=psdk.RANGE.V2,
            enabled=True,
            offset=0.0,
            probe_scale=1.0,
        )

        # 4) channel B: captured signal
        scope.set_channel(
            channel=psdk.CHANNEL.B,
            coupling=psdk.COUPLING.DC,
            range=psdk.RANGE.V2,
            enabled=True,
            offset=0.0,
            probe_scale=1.0,
        )

        # 5) trigger on A
        scope.set_simple_trigger(
            channel=psdk.CHANNEL.A,
            threshold=100.0,   # mV
            threshold_unit="mv",
            enable=True,
            direction=psdk.TRIGGER_DIR.RISING,
            delay=0,
            auto_trigger=0,
        )

        # 6) sampling setup
        sample_rate_mhz = 62.5
        total_window_us = 50.0
        timebase = 4
        pre_trig_percent = 0.0

        fs_hz = sample_rate_mhz * 1e6
        dt_s = 1.0 / fs_hz
        samples = int(round(total_window_us * 1e-6 / dt_s))

        print("sample_rate_mhz =", sample_rate_mhz)
        print("timebase =", timebase)
        print("samples =", samples)

        # 7) IMPORTANT: allocate buffers for BOTH enabled channels
        buf_a = scope.set_data_buffer(
            channel=psdk.CHANNEL.A,
            samples=samples,
            segment=0,
        )
        buf_b = scope.set_data_buffer(
            channel=psdk.CHANNEL.B,
            samples=samples,
            segment=0,
        )

        # 8) arm block capture
        print("Arming capture: trigger=A, capture=B ...")
        busy_ms = scope.run_block_capture(
            timebase=timebase,
            samples=samples,
            pre_trig_percent=pre_trig_percent,
            segment=0,
        )
        print("run_block_capture returned busy_ms =", busy_ms)

        # In your wrapper path, do not rely on is_ready()
        # For continuous input on A, trigger should occur quickly
        time.sleep(0.2)

        # 9) fetch values
        print("Fetching values for A and B...")
        scope.get_values(
            samples=samples,
            start_index=0,
            segment=0,
            ratio=0,
        )

        raw_a = np.asarray(buf_a)
        raw_b = np.asarray(buf_b)

        volts_a = np.asarray(scope.adc_to_volts(raw_a, channel=psdk.CHANNEL.A), dtype=float)
        volts_b = np.asarray(scope.adc_to_volts(raw_b, channel=psdk.CHANNEL.B), dtype=float)

        t_us = np.arange(len(volts_b), dtype=float) * dt_s * 1e6

        print("A min/max V =", volts_a.min(), volts_a.max())
        print("B min/max V =", volts_b.min(), volts_b.max())

        # plot B only
        plt.figure()
        plt.plot(t_us, volts_b, label="Channel B")
        plt.xlabel("Time (us)")
        plt.ylabel("Voltage (V)")
        plt.title("Trigger on A, Capture on B")
        plt.grid(True)
        plt.legend()
        plt.show()

    finally:
        try:
            scope.close_unit()
        except Exception:
            pass


if __name__ == "__main__":
    main()