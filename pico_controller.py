# pico_controller.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

import numpy as np
import pypicosdk as psdk


@dataclass
class PicoCaptureResult:
    time_s: np.ndarray
    signal_v: np.ndarray
    meta: Dict[str, Any]


class PicoController:
    """
    Minimal PicoScope 5442D controller using pyPicoSDK / ps5000a backend.

    Current target:
    - single-channel test capture on Channel A
    - block capture
    - return waveform for GUI display
    """

    def __init__(self):
        self.scope = None
        self.channel_name = "A"
        self.channel_range = "mV100"
        self.coupling = "DC"
        self.last_result: Optional[PicoCaptureResult] = None

    def connect(self):
        if self.scope is not None:
            return

        self.scope = psdk.ps5000a()
        self.scope.open_unit()

    def is_connected(self) -> bool:
        return self.scope is not None

    def identify(self) -> str:
        if self.scope is None:
            raise RuntimeError("PicoScope not connected")
        try:
            return str(self.scope.get_unit_serial())
        except Exception:
            return "Connected (serial unavailable)"

    def close(self):
        if self.scope is not None:
            try:
                self.scope.close_unit()
            finally:
                self.scope = None

    def _require_scope(self):
        if self.scope is None:
            raise RuntimeError("PicoScope not connected")

    def _normalize_channel_name(self, channel: str) -> str:
        ch = channel.strip().lower()
        mapping = {
            "a": "channel_a",
            "b": "channel_b",
            "c": "channel_c",
            "d": "channel_d",
            "channel_a": "channel_a",
            "channel_b": "channel_b",
            "channel_c": "channel_c",
            "channel_d": "channel_d",
        }
        if ch not in mapping:
            raise ValueError(
                f"Unsupported channel: {channel}. Use A/B/C/D or channel_a/channel_b/channel_c/channel_d"
            )
        return mapping[ch]

    def _normalize_range_name(self, vrange: str) -> str:
        """
        Convert user-friendly forms to pyPicoSDK RANGE names.

        Accepted user inputs:
            10mV, 20mV, 50mV, 100mV, 200mV, 500mV
            1V, 2V, 5V, 10V, 20V
        Converted to:
            mV10, mV20, mV50, mV100, mV200, mV500
            V1, V2, V5, V10, V20
        """
        s = vrange.strip()
        key = s.lower()

        mapping = {
            "10mv": "mV10",
            "20mv": "mV20",
            "50mv": "mV50",
            "100mv": "mV100",
            "200mv": "mV200",
            "500mv": "mV500",
            "1v": "V1",
            "2v": "V2",
            "5v": "V5",
            "10v": "V10",
            "20v": "V20",
            # already-correct enum-like names
            "mv10": "mV10",
            "mv20": "mV20",
            "mv50": "mV50",
            "mv100": "mV100",
            "mv200": "mV200",
            "mv500": "mV500",
            "v1": "V1",
            "v2": "V2",
            "v5": "V5",
            "v10": "V10",
            "v20": "V20",
        }

        if key in mapping:
            return mapping[key]

        raise ValueError(
            f"Unsupported range: {vrange}. "
            f"Use one of: 10mV, 20mV, 50mV, 100mV, 200mV, 500mV, 1V, 2V, 5V, 10V, 20V"
        )

    def _get_range_enum(self, range_name: str):
        """
        Turn a normalized range name like 'mV100' or 'V1' into psdk.RANGE.<name>.
        """
        if hasattr(psdk, "RANGE") and hasattr(psdk.RANGE, range_name):
            return getattr(psdk.RANGE, range_name)
        raise ValueError(f"pyPicoSDK RANGE enum not found for: {range_name}")

    def _normalize_coupling(self, coupling: str):
        name = coupling.strip().upper()

        candidates = [name, f"AC_{name}" if name in ("AC", "DC") else name]
        for cand in candidates:
            if hasattr(psdk.COUPLING, cand):
                return getattr(psdk.COUPLING, cand)

        if name == "DC" and hasattr(psdk.COUPLING, "DC"):
            return getattr(psdk.COUPLING, "DC")
        if name == "AC" and hasattr(psdk.COUPLING, "AC"):
            return getattr(psdk.COUPLING, "AC")

        raise ValueError(f"Unsupported coupling: {coupling}")

    def configure_channel(
        self,
        channel: str = "A",
        vrange: str = "100mV",
        coupling: str = "DC",
        offset: float = 0.0,
        probe_scale: float = 1.0,
    ):
        self._require_scope()

        sdk_channel = self._normalize_channel_name(channel)
        sdk_range_name = self._normalize_range_name(vrange)
        sdk_range = self._get_range_enum(sdk_range_name)

        self.channel_name = channel
        self.channel_range = sdk_range_name
        self.coupling = coupling

        self.scope.set_all_channels_off()

        self.scope.set_channel(
            channel=sdk_channel,
            range=sdk_range,
            enabled=True,
            coupling=self._normalize_coupling(coupling),
            offset=offset,
            probe_scale=probe_scale,
        )

    def capture_block(
        self,
        channel: str = "A",
        vrange: str = "100mV",
        coupling: str = "DC",
        timebase: int = 3,
        samples: int = 5000,
        pre_trigger_percent: int = 20,
        trigger_threshold_mv: float = 0.0,
        auto_trigger_us: int = 1000,
    ) -> PicoCaptureResult:
        self._require_scope()

        sdk_channel = self._normalize_channel_name(channel)
        sdk_range_name = self._normalize_range_name(vrange)

        self.configure_channel(
            channel=channel,
            vrange=sdk_range_name,
            coupling=coupling,
        )

        self.scope.set_simple_trigger(
            channel=sdk_channel,
            threshold=float(trigger_threshold_mv),
            threshold_unit="mv",
            enable=True,
            direction=psdk.TRIGGER_DIR.RISING,
            delay=0,
            auto_trigger=int(auto_trigger_us),
        )

        buffers, time_axis = self.scope.run_simple_block_capture(
            timebase=int(timebase),
            samples=int(samples),
            output_unit="v",
            time_unit="ns",
            pre_trig_percent=int(pre_trigger_percent),
        )

        signal = None

        if sdk_channel in buffers:
            signal = buffers[sdk_channel]

        if signal is None:
            for key, value in buffers.items():
                if str(key).strip().lower() == sdk_channel.lower():
                    signal = value
                    break

        if signal is None:
            first_key = next(iter(buffers.keys()))
            signal = buffers[first_key]

        time_s = np.asarray(time_axis, dtype=float) * 1e-9
        signal_v = np.asarray(signal, dtype=float)

        result = PicoCaptureResult(
            time_s=time_s,
            signal_v=signal_v,
            meta={
                "channel": channel,
                "sdk_channel": sdk_channel,
                "range": sdk_range_name,
                "coupling": coupling,
                "timebase": int(timebase),
                "samples": int(samples),
                "pre_trigger_percent": int(pre_trigger_percent),
                "trigger_threshold_mv": float(trigger_threshold_mv),
                "auto_trigger_us": int(auto_trigger_us),
            },
        )

        self.last_result = result
        return result

    def get_last_result(self) -> Optional[PicoCaptureResult]:
        return self.last_result