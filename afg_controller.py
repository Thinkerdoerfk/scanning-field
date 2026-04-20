from __future__ import annotations

from typing import Optional
import pyvisa


class AFGController:
    """
    Tektronix AFG3022B controller

    Notes:
    - This version automatically switch trigger source to External.
    - Trigger source must be selected manually by GUI or explicit method calls.
    """

    def __init__(
        self,
        resource_name: str = "GPIB0::11::INSTR",
        timeout_ms: int = 5000,
        channel: int = 1,
    ):
        self.resource_name = resource_name
        self.timeout_ms = timeout_ms
        self.channel = channel

        self.rm: Optional[pyvisa.ResourceManager] = None
        self.inst = None

    # -------------------------
    # Basic connection
    # -------------------------
    def connect(self):
        if self.inst is not None:
            return

        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.resource_name)
        self.inst.timeout = self.timeout_ms
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"

        self.write("*CLS")
        _ = self.identify()

    def is_connected(self) -> bool:
        return self.inst is not None

    def close(self):
        if self.inst is not None:
            try:
                self.inst.close()
            finally:
                self.inst = None

        if self.rm is not None:
            try:
                self.rm.close()
            finally:
                self.rm = None

    def _require_connected(self):
        if self.inst is None:
            raise RuntimeError("AFG not connected")

    def write(self, cmd: str):
        self._require_connected()
        self.inst.write(cmd)

    def query(self, cmd: str) -> str:
        self._require_connected()
        return self.inst.query(cmd).strip()

    def identify(self) -> str:
        return self.query("*IDN?")

    # -------------------------
    # Channel / output
    # -------------------------
    def set_channel(self, channel: int):
        if channel not in (1, 2):
            raise ValueError("channel must be 1 or 2")
        self.channel = channel

    def output_on(self):
        self.write(f"OUTPut{self.channel}:STATe ON")

    def output_off(self):
        self.write(f"OUTPut{self.channel}:STATe OFF")

    def get_output_state(self) -> str:
        return self.query(f"OUTPut{self.channel}:STATe?")

    # -------------------------
    # Waveform
    # -------------------------
    def set_sine(self, frequency_hz: float, amplitude_vpp: float, offset_v: float = 0.0):
        ch = self.channel
        self.write(f"SOURce{ch}:FUNCtion SINusoid")
        self.write(f"SOURce{ch}:FREQuency:FIXed {frequency_hz}")
        self.write(f"SOURce{ch}:VOLTage:UNIT VPP")
        self.write(f"SOURce{ch}:VOLTage:LEVel:IMMediate:AMPLitude {amplitude_vpp}")
        self.write(f"SOURce{ch}:VOLTage:LEVel:IMMediate:OFFSet {offset_v}")

    def configure_2mhz_100mvpp(self):
        self.set_sine(frequency_hz=2e6, amplitude_vpp=0.1, offset_v=0.0)

    # -------------------------
    # Trigger output mode
    # -------------------------
    def set_trigger_out_mode(self, mode: str):
        """
        mode: 'TRIG' or 'SYNC'
        """
        mode = mode.strip().upper()
        if mode not in ("TRIG", "SYNC"):
            raise ValueError("trigger out mode must be TRIG or SYNC")
        self.write(f"OUTPut:TRIGger:MODE {mode}")

    def get_trigger_out_mode(self) -> str:
        return self.query("OUTPut:TRIGger:MODE?")

    # -------------------------
    # Burst setup
    # -------------------------
    def set_burst_enabled(self, enabled: bool):
        ch = self.channel
        self.write(f"SOURce{ch}:BURSt:STATe {'ON' if enabled else 'OFF'}")

    def disable_burst(self):
        self.set_burst_enabled(False)

    def set_burst_mode(self, mode: str):
        """
        mode: 'TRIG' or 'GAT'
        """
        mode = mode.strip().upper()
        if mode not in ("TRIG", "GAT"):
            raise ValueError("burst mode must be TRIG or GAT")
        ch = self.channel
        self.write(f"SOURce{ch}:BURSt:MODE {mode}")

    def get_burst_mode(self) -> str:
        ch = self.channel
        return self.query(f"SOURce{ch}:BURSt:MODE?")

    def set_burst_cycles(self, cycles: int):
        if cycles <= 0:
            raise ValueError("cycles must be > 0")
        ch = self.channel
        self.write(f"SOURce{ch}:BURSt:NCYCles {int(cycles)}")

    def get_burst_cycles(self) -> str:
        ch = self.channel
        return self.query(f"SOURce{ch}:BURSt:NCYCles?")

    def set_burst_delay_s(self, delay_s: float):
        if delay_s < 0:
            raise ValueError("delay_s must be >= 0")
        ch = self.channel
        self.write(f"SOURce{ch}:BURSt:TDELay {delay_s}")

    def get_burst_delay_s(self) -> str:
        ch = self.channel
        return self.query(f"SOURce{ch}:BURSt:TDELay?")

    # -------------------------
    # Trigger source
    # -------------------------
    def set_trigger_source_internal(self):
        self.write("TRIGger:SEQuence:SOURce TIM")

    def set_trigger_source_external(self):
        self.write("TRIGger:SEQuence:SOURce EXT")

    def set_trigger_source_bus(self):
        self.write("TRIGger:SEQuence:SOURce BUS")

    def get_trigger_source(self) -> str:
        return self.query("TRIGger:SEQuence:SOURce?")

    def set_internal_trigger_interval_s(self, interval_s: float):
        """
        Only meaningful when trigger source = TIM/internal.
        """
        if interval_s <= 0:
            raise ValueError("interval_s must be > 0")
        self.write(f"TRIGger:SEQuence:TIMer {interval_s}")

    def get_internal_trigger_interval_s(self) -> str:
        return self.query("TRIGger:SEQuence:TIMer?")

    # -------------------------
    # Software trigger
    # -------------------------
    def send_trigger(self):
        """
        Fire one software trigger event.
        Effective when trigger source is BUS and burst mode is configured properly.
        """
        self.write("TRIGger:SEQuence:IMMediate")

    def fire_software_trigger_once(self):
        self.send_trigger()

    # -------------------------
    # High-level helpers
    # -------------------------
    def prepare_burst_waiting(
        self,
        frequency_hz: float,
        amplitude_vpp: float,
        offset_v: float = 0.0,
        cycles: int = 1000,
        trigger_out_mode: str = "TRIG",
        burst_mode: str = "TRIG",
        trigger_delay_s: float = 0.0,
        keep_output_on: bool = True,
    ):
        """
        Configure waveform/burst/output, but DO NOT change trigger source automatically.
        You must manually select BUS / EXT / TIM later.

        Typical workflow:
            1) prepare_burst_waiting(...)
            2) set_trigger_source_bus()   # manually from GUI button
            3) fire_software_trigger_once()
        """
        self.set_sine(frequency_hz, amplitude_vpp, offset_v)
        self.set_trigger_out_mode(trigger_out_mode)
        self.set_burst_mode(burst_mode)
        self.set_burst_cycles(cycles)
        self.set_burst_delay_s(trigger_delay_s)
        self.set_burst_enabled(True)

        if keep_output_on:
            self.output_on()

    def get_basic_settings(self) -> dict:
        ch = self.channel
        data = {
            "idn": self.identify(),
            "channel": ch,
            "shape": self.query(f"SOURce{ch}:FUNCtion?"),
            "freq_hz": self.query(f"SOURce{ch}:FREQuency:FIXed?"),
            "volt_unit": self.query(f"SOURce{ch}:VOLTage:UNIT?"),
            "ampl": self.query(f"SOURce{ch}:VOLTage:LEVel:IMMediate:AMPLitude?"),
            "offset": self.query(f"SOURce{ch}:VOLTage:LEVel:IMMediate:OFFSet?"),
            "output": self.query(f"OUTPut{ch}:STATe?"),
            "burst_state": self.query(f"SOURce{ch}:BURSt:STATe?"),
            "burst_mode": self.query(f"SOURce{ch}:BURSt:MODE?"),
            "burst_cycles": self.query(f"SOURce{ch}:BURSt:NCYCles?"),
            "burst_delay_s": self.query(f"SOURce{ch}:BURSt:TDELay?"),
            "trigger_source": self.query("TRIGger:SEQuence:SOURce?"),
            "trigger_timer_s": self.query("TRIGger:SEQuence:TIMer?"),
            "trigger_out_mode": self.query("OUTPut:TRIGger:MODE?"),
        }
        return data

    def safe_stop(self):
        try:
            self.disable_burst()
        except Exception:
            pass
        try:
            self.output_off()
        except Exception:
            pass