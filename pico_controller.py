from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path
import time

import numpy as np
import pypicosdk as psdk


@dataclass
class PicoCaptureResult:
    time_s: np.ndarray
    signal_v: np.ndarray
    meta: Dict[str, Any]


class PicoController:
    """
    Pico controller for scanning workflow.

    Intended workflow:
        1. connect()
        2. apply_config(...)      # only once from PicoPanel
        3. set_save_directory(...)
        4. during scan, for each point:
             arm_current_capture()
             ... AFG software trigger -> Pico EXT rising edge ...
             wait_and_fetch_current_capture()
             save_capture_npz(...)
    """

    SAMPLE_RATE_OPTIONS_MHZ = [15.625, 31.25, 62.5]
    FIXED_RESOLUTION_BITS = 16

    def __init__(self):
        self.scope = None
        self.last_result: Optional[PicoCaptureResult] = None

        self.save_dir: Optional[Path] = None

        self._configured = False
        self._armed = False

        # stored config from panel
        self.recv_channel = "A"
        self.vrange = "100mV"
        self.coupling = "DC"

        self.sample_rate_mhz = 62.5
        self.duration_us = 20.0          # total acquisition window
        self.pre_trigger_us = 0.0        # trigger前保留时间
        self.post_trigger_us = 20.0      # 自动计算 = duration - pre_trigger

        self.trigger_source = "EXT"
        self.trigger_direction = "RISING"
        self.trigger_threshold_mv = 0.0
        self.auto_trigger_us = 0

        # derived config / runtime
        self.timebase: Optional[int] = None
        self.actual_fs_hz: Optional[float] = None
        self.dt_s: Optional[float] = None
        self.samples: Optional[int] = None
        self.pre_trigger_percent: int = 0
        self.total_window_us: Optional[float] = None

        # runtime capture state
        self._capture_segment = 0
        self._capture_buffer = None
        self._capture_channel_name: Optional[str] = None
        self._last_busy_ms: Optional[int] = None

    # ------------------------------------------------------------
    # basic
    # ------------------------------------------------------------
    def connect(self):
        if self.scope is not None:
            return

        self.scope = psdk.ps5000a()
        self.scope.open_unit()
        self._set_resolution_16bit()

    def close(self):
        if self.scope is not None:
            try:
                self.scope.close_unit()
            finally:
                self.scope = None
                self._configured = False
                self._armed = False
                self._capture_buffer = None
                self._capture_channel_name = None
                self._last_busy_ms = None

    def is_connected(self) -> bool:
        return self.scope is not None

    def is_configured(self) -> bool:
        return self._configured

    def identify(self) -> str:
        self._require_scope()
        try:
            serial = str(self.scope.get_unit_serial())
        except Exception:
            serial = "serial unavailable"
        return f"{serial} | fixed 16-bit"

    def _require_scope(self):
        if self.scope is None:
            raise RuntimeError("PicoScope not connected")

    # ------------------------------------------------------------
    # normalization helpers
    # ------------------------------------------------------------
    def _normalize_channel_name(self, channel: str) -> str:
        ch = channel.strip().lower()
        mapping = {
            "a": "channel_a",
            "b": "channel_b",
            "c": "channel_c",
            "d": "channel_d",
            "ext": "external",
            "external": "external",
            "channel_a": "channel_a",
            "channel_b": "channel_b",
            "channel_c": "channel_c",
            "channel_d": "channel_d",
        }
        if ch not in mapping:
            raise ValueError("Unsupported channel. Use A/B/C/D or EXT.")
        return mapping[ch]

    def _normalize_range_enum(self, vrange: str):
        s = vrange.strip()
        mapping = {
            "10mV": psdk.RANGE.mV10,
            "20mV": psdk.RANGE.mV20,
            "50mV": psdk.RANGE.mV50,
            "100mV": psdk.RANGE.mV100,
            "200mV": psdk.RANGE.mV200,
            "500mV": psdk.RANGE.mV500,
            "1V": psdk.RANGE.V1,
            "2V": psdk.RANGE.V2,
            "5V": psdk.RANGE.V5,
            "10V": psdk.RANGE.V10,
            "20V": psdk.RANGE.V20,
        }
        if s not in mapping:
            raise ValueError(
                "Unsupported range. Use 10mV/20mV/50mV/100mV/200mV/500mV/1V/2V/5V/10V/20V"
            )
        return mapping[s]

    def _normalize_coupling(self, coupling: str):
        name = coupling.strip().upper()
        if not hasattr(psdk, "COUPLING"):
            raise RuntimeError("psdk.COUPLING not found")

        if hasattr(psdk.COUPLING, name):
            return getattr(psdk.COUPLING, name)

        raise ValueError(f"Unsupported coupling: {coupling}")

    def _normalize_trigger_direction(self, direction: str):
        name = direction.strip().upper()
        if hasattr(psdk, "TRIGGER_DIR") and hasattr(psdk.TRIGGER_DIR, name):
            return getattr(psdk.TRIGGER_DIR, name)
        raise ValueError(f"Unsupported trigger direction: {direction}")

    # ------------------------------------------------------------
    # resolution
    # ------------------------------------------------------------
    def _set_resolution_16bit(self):
        self._require_scope()

        if not hasattr(psdk, "RESOLUTION"):
            raise RuntimeError("psdk.RESOLUTION not found in this wrapper")

        if not hasattr(psdk.RESOLUTION, "BIT_16"):
            raise RuntimeError("psdk.RESOLUTION.BIT_16 not found")

        self.scope.set_device_resolution(psdk.RESOLUTION.BIT_16)

    # ------------------------------------------------------------
    # save folder
    # ------------------------------------------------------------
    def set_save_directory(self, folder: str):
        p = Path(folder).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        self.save_dir = p

    # ------------------------------------------------------------
    # config only once from panel
    # ------------------------------------------------------------
    def apply_config(
        self,
        recv_channel: str,
        vrange: str,
        coupling: str,
        sample_rate_mhz: float,
        duration_us: float,
        pre_trigger_us: float,
        trigger_source: str,
        trigger_direction: str,
        trigger_threshold_mv: float,
        auto_trigger_us: int,
    ) -> Dict[str, Any]:
        """
        Apply hardware configuration once from PicoPanel.

        Notes:
        - fixed 16-bit mode
        - duration_us = total acquisition window
        - pre_trigger_us = time before trigger inside the total window
        - post_trigger_us is auto-calculated
        """
        self._require_scope()
        self._set_resolution_16bit()

        sample_rate_mhz = float(sample_rate_mhz)
        duration_us = float(duration_us)
        pre_trigger_us = float(pre_trigger_us)
        trigger_threshold_mv = float(trigger_threshold_mv)
        auto_trigger_us = int(auto_trigger_us)

        if duration_us <= 0:
            raise ValueError("duration_us must be > 0")
        if pre_trigger_us < 0:
            raise ValueError("pre_trigger_us must be >= 0")
        if pre_trigger_us > duration_us:
            raise ValueError("pre_trigger_us cannot be greater than duration_us")
        if sample_rate_mhz <= 0:
            raise ValueError("sample_rate_mhz must be > 0")

        self.recv_channel = recv_channel.strip()
        self.vrange = vrange.strip()
        self.coupling = coupling.strip()

        self.sample_rate_mhz = sample_rate_mhz
        self.duration_us = duration_us
        self.pre_trigger_us = pre_trigger_us
        self.post_trigger_us = self.duration_us - self.pre_trigger_us

        self.trigger_source = trigger_source.strip().upper()
        self.trigger_direction = trigger_direction.strip().upper()
        self.trigger_threshold_mv = trigger_threshold_mv
        self.auto_trigger_us = auto_trigger_us

        recv_channel_name = self._normalize_channel_name(self.recv_channel)
        recv_range_name = self._normalize_range_enum(self.vrange)

        # channel setup
        self.scope.set_all_channels_off()
        self.scope.set_channel(
            channel=recv_channel_name,
            range=recv_range_name,
            enabled=True,
            coupling=self._normalize_coupling(self.coupling),
            offset=0.0,
            probe_scale=1.0,
        )

        # trigger setup
        if self.trigger_source == "EXT":
            raise RuntimeError(
                "EXT trigger is temporarily not supported in this project. "
                "Please use A/B/C/D as trigger source."
            )

        elif self.trigger_source in ("A", "B", "C", "D"):
            trigger_channel = self._normalize_channel_name(self.trigger_source)
            self.scope.set_simple_trigger(
                channel=trigger_channel,
                threshold=float(self.trigger_threshold_mv),
                threshold_unit="mv",
                enable=True,
                direction=self._normalize_trigger_direction(self.trigger_direction),
                delay=0,
                auto_trigger=int(self.auto_trigger_us),
            )

        else:
            raise ValueError("Trigger source must be A/B/C/D")

        # total acquisition window
        self.total_window_us = self.duration_us

        # requested fs -> timebase
        self.timebase = self._sample_rate_mhz_to_timebase(self.sample_rate_mhz)

        # first-pass estimate from requested fs
        requested_fs_hz = self.sample_rate_mhz * 1e6
        self.actual_fs_hz = requested_fs_hz
        self.dt_s = 1.0 / self.actual_fs_hz

        # total samples from total window
        self.samples = max(1, int(round(self.total_window_us * 1e-6 / self.dt_s)))

        # pre-trigger percentage
        if self.total_window_us > 0:
            self.pre_trigger_percent = int(round(100.0 * self.pre_trigger_us / self.total_window_us))
            self.pre_trigger_percent = max(0, min(95, self.pre_trigger_percent))
        else:
            self.pre_trigger_percent = 0

        self._configured = True
        self._armed = False
        self._capture_buffer = None
        self._capture_channel_name = None
        self._last_busy_ms = None

        return self.get_config_summary()

    def get_config_summary(self) -> Dict[str, Any]:
        return {
            "recv_channel": self.recv_channel,
            "vrange": self.vrange,
            "coupling": self.coupling,
            "trigger_source": self.trigger_source,
            "trigger_direction": self.trigger_direction,
            "trigger_threshold_mv": self.trigger_threshold_mv,
            "auto_trigger_us": self.auto_trigger_us,
            "requested_sample_rate_mhz": self.sample_rate_mhz,
            "actual_sample_rate_mhz": None if self.actual_fs_hz is None else self.actual_fs_hz / 1e6,
            "timebase": self.timebase,
            "dt_s": self.dt_s,
            "samples": self.samples,
            "duration_us": self.duration_us,
            "pre_trigger_us": self.pre_trigger_us,
            "post_trigger_us": self.post_trigger_us,
            "total_window_us": self.total_window_us,
            "pre_trigger_percent": self.pre_trigger_percent,
            "resolution_bits": self.FIXED_RESOLUTION_BITS,
        }

    def _sample_rate_mhz_to_timebase(self, sample_rate_mhz: float) -> int:
        """
        The wrapper says sample_rate_to_timebase(sample_rate, unit=<SAMPLE_RATE.MSPS>).
        Since panel uses MHz, pass the numeric MHz value directly with default unit.
        """
        if not hasattr(self.scope, "sample_rate_to_timebase"):
            raise RuntimeError("sample_rate_to_timebase not available in this wrapper")

        tb = self.scope.sample_rate_to_timebase(float(sample_rate_mhz))
        if isinstance(tb, tuple):
            tb = tb[0]
        return int(tb)

    def _refresh_actual_sampling_info_from_device(self):
        """
        Best-effort refresh of actual sampling interval / sample rate from device state.
        Safe to call after run_block_capture().
        """
        try:
            if hasattr(self.scope, "get_actual_interval"):
                dt = self.scope.get_actual_interval()
                if isinstance(dt, (int, float)) and dt > 0:
                    self.dt_s = float(dt)
                    self.actual_fs_hz = 1.0 / self.dt_s
                    return
        except Exception:
            pass

        try:
            if hasattr(self.scope, "get_actual_sample_rate"):
                fs = self.scope.get_actual_sample_rate()
                if isinstance(fs, (int, float)) and fs > 0:
                    self.actual_fs_hz = float(fs)
                    self.dt_s = 1.0 / self.actual_fs_hz
                    return
        except Exception:
            pass

        if self.actual_fs_hz is None:
            self.actual_fs_hz = self.sample_rate_mhz * 1e6
        if self.dt_s is None:
            self.dt_s = 1.0 / self.actual_fs_hz

    # ------------------------------------------------------------
    # arm / fetch / save for scan
    # ------------------------------------------------------------
    def arm_current_capture(self):
        """
        True hardware arm:
        - allocate capture buffer
        - run block capture
        - Pico enters waiting-for-trigger state
        """
        self._require_scope()

        if not self._configured:
            raise RuntimeError("Pico is not configured. Please apply config in Pico panel first.")

        recv_channel_name = self._normalize_channel_name(self.recv_channel)

        self._capture_segment = 0
        self._capture_channel_name = recv_channel_name
        self._capture_buffer = self.scope.set_data_buffer(
            channel=recv_channel_name,
            samples=int(self.samples),
            segment=int(self._capture_segment),
        )

        self._last_busy_ms = self.scope.run_block_capture(
            timebase=int(self.timebase),
            samples=int(self.samples),
            pre_trig_percent=float(self.pre_trigger_percent),
            segment=int(self._capture_segment),
        )

        self._refresh_actual_sampling_info_from_device()
        self._armed = True

    def wait_and_fetch_current_capture(self, timeout_s: float = 5.0) -> PicoCaptureResult:
        """
        Wait until current armed capture finishes, fetch data into the buffer,
        convert to volts, and build time axis.
        """
        self._require_scope()

        if not self._configured:
            raise RuntimeError("Pico is not configured.")
        if not self._armed:
            raise RuntimeError("Pico was not armed before fetch.")
        if self._capture_buffer is None:
            raise RuntimeError("Capture buffer is not allocated.")
        if self._capture_channel_name is None:
            raise RuntimeError("Capture channel is not set.")

        t0 = time.time()

        self.scope.is_ready()

        elapsed = time.time() - t0
        if elapsed > timeout_s:
            raise TimeoutError(f"Pico capture timeout after {elapsed:.3f} s")

        self.scope.get_values(
            samples=int(self.samples),
            start_index=0,
            segment=int(self._capture_segment),
            ratio=0,
        )

        raw_signal = np.asarray(self._capture_buffer)

        signal_v = self.scope.adc_to_volts(
            raw_signal,
            channel=self._capture_channel_name,
        )
        signal_v = np.asarray(signal_v, dtype=float)

        if self.dt_s is None or self.dt_s <= 0:
            self.dt_s = 1.0 / (self.sample_rate_mhz * 1e6)

        time_s = np.arange(len(signal_v), dtype=float) * float(self.dt_s)

        result = PicoCaptureResult(
            time_s=time_s,
            signal_v=signal_v,
            meta={
                "recv_channel": self.recv_channel,
                "recv_channel_sdk": self._capture_channel_name,
                "vrange": self.vrange,
                "coupling": self.coupling,
                "resolution_bits": self.FIXED_RESOLUTION_BITS,
                "requested_sample_rate_mhz": self.sample_rate_mhz,
                "actual_sample_rate_mhz": None if self.actual_fs_hz is None else self.actual_fs_hz / 1e6,
                "timebase": self.timebase,
                "dt_s": self.dt_s,
                "samples": len(signal_v),
                "duration_us": self.duration_us,
                "pre_trigger_us": self.pre_trigger_us,
                "post_trigger_us": self.post_trigger_us,
                "total_window_us": self.total_window_us,
                "pre_trigger_percent": self.pre_trigger_percent,
                "trigger_source": self.trigger_source,
                "trigger_direction": self.trigger_direction,
                "trigger_threshold_mv": self.trigger_threshold_mv,
                "auto_trigger_us": self.auto_trigger_us,
                "segment": self._capture_segment,
                "estimated_busy_ms": self._last_busy_ms,
                "fetch_wait_s": elapsed,
            },
        )

        self.last_result = result
        self._armed = False
        self._capture_buffer = None
        self._capture_channel_name = None
        return result

    def save_capture_npz(
        self,
        result: PicoCaptureResult,
        point_index: int,
        x_mm: float,
        y_mm: float,
    ) -> str:
        """
        Save one capture as compressed NumPy archive.
        Fast, compact, and easy to restore later with Python.
        """
        if self.save_dir is None:
            raise RuntimeError("Save folder is not set. Please choose it in Pico panel first.")

        filename = f"pt_{point_index:06d}_x{x_mm:+08.3f}_y{y_mm:+08.3f}.npz"
        filepath = self.save_dir / filename

        np.savez_compressed(
            filepath,
            time_s=result.time_s,
            signal_v=result.signal_v,
            point_index=int(point_index),
            x_mm=float(x_mm),
            y_mm=float(y_mm),
            meta=np.array(result.meta, dtype=object),
        )

        return str(filepath)

    def get_last_result(self) -> Optional[PicoCaptureResult]:
        return self.last_result