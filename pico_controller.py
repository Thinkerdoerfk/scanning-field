from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pypicosdk.pypicosdk as psdk


@dataclass
class PicoCaptureResult:
    """
    Multi-channel capture result.

    time_s:
        Shared time axis.

    signals_v:
        Dict like:
            {
                "A": np.ndarray(...),
                "B": np.ndarray(...),
            }

    meta:
        Metadata dict.
    """
    time_s: np.ndarray
    signals_v: Dict[str, np.ndarray]
    meta: Dict[str, Any]


class PicoController:
    """
    Generic PicoScope controller for block capture.

    Current stable strategy:
    - fixed 8-bit mode
    - trigger source can be A/B/C/D
    - capture channels can be one or more of A/B/C/D
    - avoid is_ready() loop
    - use sleep after arm, then get_values()
    """

    FIXED_RESOLUTION_BITS = 8

    def __init__(self):
        self.scope = None

        # state
        self._configured = False
        self._armed = False

        # current config
        self.capture_channels: List[str] = []
        self.save_channels: List[str] = []
        self.channel_ranges: Dict[str, str] = {
            "A": "V2",
            "B": "V2",
            "C": "V2",
            "D": "V2",
        }
        self.coupling: str = "DC"

        self.sample_rate_mhz: float = 62.5
        self.duration_us: float = 50.0
        self.pre_trigger_us: float = 0.0
        self.post_trigger_us: float = 50.0
        self.total_window_us: float = 50.0

        self.trigger_source: str = "A"
        self.trigger_direction: str = "RISING"
        self.trigger_threshold_mv: float = 100.0
        self.auto_trigger_us: int = 0

        # timing / derived
        self.timebase: Optional[int] = None
        self.actual_fs_hz: Optional[float] = None
        self.dt_s: Optional[float] = None
        self.samples: Optional[int] = None
        self.pre_trigger_percent: int = 0

        # runtime
        self._capture_segment: int = 0
        self._capture_buffers: Dict[str, np.ndarray] = {}
        self._channels_for_run: List[str] = []      # trigger + capture (unique)
        self._channels_to_buffer: List[str] = []    # same as _channels_for_run here

        # stable workaround
        self.sleep_after_arm_s: float = 0.2

        # save / result
        self.save_dir: Optional[str] = None
        self.last_result: Optional[PicoCaptureResult] = None

    # ------------------------------------------------------------------
    # connection
    # ------------------------------------------------------------------
    def connect(self):
        if self.scope is not None:
            return
        self.scope = psdk.ps5000a()
        self.scope.open_unit()
        self._set_resolution_8bit()

    def disconnect(self):
        if self.scope is not None:
            try:
                self.scope.close_unit()
            except Exception:
                pass
        self.scope = None
        self._configured = False
        self._armed = False
        self._capture_buffers = {}
        self._channels_for_run = []
        self._channels_to_buffer = []

    def close(self):
        self.disconnect()

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
        return f"{serial} | fixed 8-bit"

    def _require_scope(self):
        if self.scope is None:
            raise RuntimeError("PicoScope is not connected.")

    def _set_resolution_8bit(self):
        self._require_scope()
        self.scope.set_device_resolution(psdk.RESOLUTION.BIT_8)

    # ------------------------------------------------------------------
    # normalize helpers
    # ------------------------------------------------------------------
    def _normalize_channel_label(self, name: str) -> str:
        s = str(name).strip().upper()
        if s not in ("A", "B", "C", "D"):
            raise ValueError(f"Unsupported channel name: {name}")
        return s

    def _channel_enum(self, name: str):
        s = self._normalize_channel_label(name)
        mapping = {
            "A": psdk.CHANNEL.A,
            "B": psdk.CHANNEL.B,
            "C": psdk.CHANNEL.C,
            "D": psdk.CHANNEL.D,
        }
        return mapping[s]

    def _normalize_range_enum(self, vrange: str):
        s = str(vrange).strip().upper()
        mapping = {
            "10MV": psdk.RANGE.mV10,
            "20MV": psdk.RANGE.mV20,
            "50MV": psdk.RANGE.mV50,
            "100MV": psdk.RANGE.mV100,
            "200MV": psdk.RANGE.mV200,
            "500MV": psdk.RANGE.mV500,
            "1V": psdk.RANGE.V1,
            "2V": psdk.RANGE.V2,
            "5V": psdk.RANGE.V5,
            "10V": psdk.RANGE.V10,
            "20V": psdk.RANGE.V20,
            "V1": psdk.RANGE.V1,
            "V2": psdk.RANGE.V2,
            "V5": psdk.RANGE.V5,
            "V10": psdk.RANGE.V10,
            "V20": psdk.RANGE.V20,
        }
        if s not in mapping:
            raise ValueError(f"Unsupported range: {vrange}")
        return mapping[s]

    def _normalize_coupling(self, coupling: str):
        s = str(coupling).strip().upper()
        mapping = {
            "AC": psdk.COUPLING.AC,
            "DC": psdk.COUPLING.DC,
            "DC_50OHM": psdk.COUPLING.DC_50OHM,
            "DC50": psdk.COUPLING.DC_50OHM,
            "50OHM": psdk.COUPLING.DC_50OHM,
        }
        if s not in mapping:
            raise ValueError(f"Unsupported coupling: {coupling}")
        return mapping[s]

    def _normalize_trigger_direction(self, direction: str):
        s = str(direction).strip().upper()
        mapping = {
            "ABOVE": psdk.TRIGGER_DIR.ABOVE,
            "BELOW": psdk.TRIGGER_DIR.BELOW,
            "RISING": psdk.TRIGGER_DIR.RISING,
            "FALLING": psdk.TRIGGER_DIR.FALLING,
            "RISING_OR_FALLING": psdk.TRIGGER_DIR.RISING_OR_FALLING,
            "RISING/FALLING": psdk.TRIGGER_DIR.RISING_OR_FALLING,
            "BOTH": psdk.TRIGGER_DIR.RISING_OR_FALLING,
        }
        if s not in mapping:
            raise ValueError(f"Unsupported trigger direction: {direction}")
        return mapping[s]

    def _sample_rate_mhz_to_timebase(self, sample_rate_mhz: float) -> int:
        """
        Current validated mapping in your project:
        62.5 MHz -> timebase 4
        """
        fs = float(sample_rate_mhz)
        known = {
            62.5: 4,
        }
        for k, tb in known.items():
            if abs(fs - k) < 1e-9:
                return tb
        raise ValueError(
            f"Currently only sample_rate_mhz=62.5 is validated in this controller; got {sample_rate_mhz}"
        )

    def _parse_capture_channels(self, capture_channels: Any) -> List[str]:
        """
        Accept:
        - ["B", "C"]
        - "B,C"
        - "B C"
        - "B"
        """
        if isinstance(capture_channels, str):
            text = capture_channels.replace(";", ",").replace(" ", ",")
            items = [x.strip() for x in text.split(",") if x.strip()]
        elif isinstance(capture_channels, (list, tuple)):
            items = [str(x).strip() for x in capture_channels if str(x).strip()]
        else:
            raise ValueError("capture_channels must be str or list/tuple")

        if not items:
            raise ValueError("capture_channels cannot be empty")

        out = []
        seen = set()
        for ch in items:
            label = self._normalize_channel_label(ch)
            if label not in seen:
                seen.add(label)
                out.append(label)
        return out

    def _parse_channel_ranges(self, channel_ranges: Any = None, vrange: Optional[str] = None) -> Dict[str, str]:
        """
        Normalize per-channel voltage range settings.

        Accept:
        - channel_ranges=None and vrange="V2" -> all channels use V2
        - channel_ranges={"A":"V2", "B":"20mV", ...}
        """
        if channel_ranges is None:
            fallback = str(vrange).strip() if vrange is not None else None
            out: Dict[str, str] = {}
            for ch in ("A", "B", "C", "D"):
                value = fallback if fallback is not None else self.channel_ranges.get(ch, "V2")
                value = str(value).strip()
                self._normalize_range_enum(value)
                out[ch] = value
            return out

        if not isinstance(channel_ranges, dict):
            raise ValueError("channel_ranges must be a dict like {'A':'V2','B':'20mV',...}")

        out: Dict[str, str] = {}
        fallback = str(vrange).strip() if vrange is not None else None
        for ch in ("A", "B", "C", "D"):
            if ch in channel_ranges:
                value = channel_ranges[ch]
            elif fallback is not None:
                value = fallback
            else:
                value = self.channel_ranges.get(ch, "V2")
            value = str(value).strip()
            self._normalize_range_enum(value)
            out[ch] = value
        return out

    def _build_channels_for_run(self) -> List[str]:
        """
        Channels enabled for this run:
        - trigger source
        - capture channels
        Unique, ordered with trigger first.
        """
        out = []
        seen = set()

        trig = self._normalize_channel_label(self.trigger_source)
        if trig not in seen:
            seen.add(trig)
            out.append(trig)

        for ch in self.capture_channels:
            if ch not in seen:
                seen.add(ch)
                out.append(ch)

        return out

    # ------------------------------------------------------------------
    # public config
    # ------------------------------------------------------------------
    def set_save_dir(self, folder: str):
        if not folder:
            raise ValueError("folder cannot be empty")
        os.makedirs(folder, exist_ok=True)
        self.save_dir = folder
    def set_save_channels(self, save_channels: Any):
        self.save_channels = self._parse_capture_channels(save_channels)

    def get_config_summary(self) -> Dict[str, Any]:
        return {
            "capture_channels": list(self.capture_channels),
            "save_channels": list(self.save_channels),
            "channel_ranges": dict(self.channel_ranges),
            "coupling": self.coupling,
            "resolution_bits": self.FIXED_RESOLUTION_BITS,
            "sample_rate_mhz": self.sample_rate_mhz,
            "duration_us": self.duration_us,
            "pre_trigger_us": self.pre_trigger_us,
            "post_trigger_us": self.post_trigger_us,
            "total_window_us": self.total_window_us,
            "samples": self.samples,
            "timebase": self.timebase,
            "dt_s": self.dt_s,
            "trigger_source": self.trigger_source,
            "trigger_direction": self.trigger_direction,
            "trigger_threshold_mv": self.trigger_threshold_mv,
            "auto_trigger_us": self.auto_trigger_us,
            "channels_for_run": list(self._channels_for_run),
            "sleep_after_arm_s": self.sleep_after_arm_s,
            "save_dir": self.save_dir,
        }

    def apply_config(
        self,
        capture_channels: Any,
        channel_ranges: Optional[Dict[str, str]] = None,
        coupling: str,
        sample_rate_mhz: float,
        duration_us: float,
        pre_trigger_us: float,
        trigger_source: str,
        trigger_direction: str,
        trigger_threshold_mv: float,
        auto_trigger_us: int,
        vrange: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_scope()
        self._set_resolution_8bit()

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

        self.capture_channels = self._parse_capture_channels(capture_channels)
        if not self.save_channels:
            self.save_channels = list(self.capture_channels)

        self.channel_ranges = self._parse_channel_ranges(channel_ranges=channel_ranges, vrange=vrange)
        self.coupling = str(coupling).strip()

        self.sample_rate_mhz = sample_rate_mhz
        self.duration_us = duration_us
        self.pre_trigger_us = pre_trigger_us
        self.post_trigger_us = self.duration_us - self.pre_trigger_us
        self.total_window_us = self.duration_us

        self.trigger_source = self._normalize_channel_label(trigger_source)
        self.trigger_direction = str(trigger_direction).strip().upper()
        self.trigger_threshold_mv = trigger_threshold_mv
        self.auto_trigger_us = auto_trigger_us

        self.timebase = self._sample_rate_mhz_to_timebase(self.sample_rate_mhz)

        requested_fs_hz = self.sample_rate_mhz * 1e6
        self.actual_fs_hz = requested_fs_hz
        self.dt_s = 1.0 / self.actual_fs_hz

        self.samples = max(1, int(round(self.total_window_us * 1e-6 / self.dt_s)))

        if self.total_window_us > 0:
            self.pre_trigger_percent = int(round(100.0 * self.pre_trigger_us / self.total_window_us))
            self.pre_trigger_percent = max(0, min(95, self.pre_trigger_percent))
        else:
            self.pre_trigger_percent = 0

        self.scope.set_all_channels_off()

        self._channels_for_run = self._build_channels_for_run()
        self._channels_to_buffer = list(self._channels_for_run)

        coupling_enum = self._normalize_coupling(self.coupling)

        for ch in self._channels_for_run:
            ch_range = self.channel_ranges.get(ch, "V2")
            range_enum = self._normalize_range_enum(ch_range)
            self.scope.set_channel(
                channel=self._channel_enum(ch),
                range=range_enum,
                enabled=True,
                coupling=coupling_enum,
                offset=0.0,
                probe_scale=1.0,
            )

        self.scope.set_simple_trigger(
            channel=self._channel_enum(self.trigger_source),
            threshold=float(self.trigger_threshold_mv),
            threshold_unit="mv",
            enable=True,
            direction=self._normalize_trigger_direction(self.trigger_direction),
            delay=0,
            auto_trigger=int(self.auto_trigger_us),
        )

        self._configured = True
        self._armed = False
        self._capture_buffers = {}
        self.last_result = None

        return self.get_config_summary()

    # ------------------------------------------------------------------
    # arm / fetch
    # ------------------------------------------------------------------
    def arm_current_capture(self):
        self._require_scope()

        if not self._configured:
            raise RuntimeError("Pico is not configured. Please apply config first.")
        if not self.capture_channels:
            raise RuntimeError("No capture channels configured.")
        if self.samples is None:
            raise RuntimeError("samples is None. Please apply config first.")
        if self.timebase is None:
            raise RuntimeError("timebase is None. Please apply config first.")

        self._capture_segment = 0
        self._capture_buffers = {}

        for ch in self._channels_to_buffer:
            buf = self.scope.set_data_buffer(
                channel=self._channel_enum(ch),
                samples=int(self.samples),
                segment=int(self._capture_segment),
            )
            self._capture_buffers[ch] = buf

        self.scope.run_block_capture(
            timebase=int(self.timebase),
            samples=int(self.samples),
            pre_trig_percent=float(self.pre_trigger_percent),
            segment=int(self._capture_segment),
        )

        self._armed = True

    def wait_and_fetch_current_capture(self, timeout_s: float = 5.0) -> PicoCaptureResult:
        self._require_scope()

        if not self._configured:
            raise RuntimeError("Pico is not configured.")
        if not self._armed:
            raise RuntimeError("Pico was not armed before fetch.")
        if not self._capture_buffers:
            raise RuntimeError("Capture buffers are not allocated.")
        if self.samples is None:
            raise RuntimeError("samples is None.")

        sleep_s = getattr(self, "sleep_after_arm_s", 0.2)
        if sleep_s is None:
            sleep_s = 0.2
        sleep_s = float(sleep_s)
        if sleep_s < 0:
            sleep_s = 0.0

        t0 = time.time()

        if sleep_s > 0:
            time.sleep(sleep_s)

        self.scope.get_values(
            samples=int(self.samples),
            start_index=0,
            segment=int(self._capture_segment),
            ratio=0,
        )

        fetch_elapsed = time.time() - t0
        if fetch_elapsed > timeout_s:
            raise TimeoutError(f"Pico capture timeout after {fetch_elapsed:.3f} s")

        signals_v: Dict[str, np.ndarray] = {}

        for ch in self._channels_to_buffer:
            raw_signal = np.asarray(self._capture_buffers[ch])
            sig_v = self.scope.adc_to_volts(raw_signal, channel=self._channel_enum(ch))
            signals_v[ch] = np.asarray(sig_v, dtype=float)

        first_ch = self._channels_to_buffer[0]
        n = len(signals_v[first_ch])

        if self.dt_s is None or self.dt_s <= 0:
            self.dt_s = 1.0 / (self.sample_rate_mhz * 1e6)

        time_s = np.arange(n, dtype=float) * float(self.dt_s)

        result = PicoCaptureResult(
            time_s=time_s,
            signals_v=signals_v,
            meta={
                "capture_channels": list(self.capture_channels),
                "trigger_source": self.trigger_source,
                "display_channels": list(self._channels_for_run),
                "channels_for_run": list(self._channels_for_run),
                "channel_ranges": dict(self.channel_ranges),
                "coupling": self.coupling,
                "resolution_bits": self.FIXED_RESOLUTION_BITS,
                "requested_sample_rate_mhz": self.sample_rate_mhz,
                "actual_sample_rate_mhz": None if self.actual_fs_hz is None else self.actual_fs_hz / 1e6,
                "timebase": self.timebase,
                "dt_s": self.dt_s,
                "samples": n,
                "duration_us": self.duration_us,
                "pre_trigger_us": self.pre_trigger_us,
                "post_trigger_us": self.post_trigger_us,
                "total_window_us": self.total_window_us,
                "pre_trigger_percent": self.pre_trigger_percent,
                "trigger_direction": self.trigger_direction,
                "trigger_threshold_mv": self.trigger_threshold_mv,
                "auto_trigger_us": self.auto_trigger_us,
                "segment": self._capture_segment,
                "sleep_after_arm_s": sleep_s,
                "fetch_wait_s": fetch_elapsed,
            },
        )

        self.last_result = result
        self._armed = False
        self._capture_buffers = {}
        return result

    def capture_once(self, timeout_s: float = 5.0) -> PicoCaptureResult:
        self.arm_current_capture()
        return self.wait_and_fetch_current_capture(timeout_s=timeout_s)

    # ------------------------------------------------------------------
    # saving
    # ------------------------------------------------------------------
    def save_capture_npz(
        self,
        result: PicoCaptureResult,
        point_index: Optional[int] = None,
        x_mm: Optional[float] = None,
        y_mm: Optional[float] = None,
        prefix: str = "capture",
        folder: Optional[str] = None,
        save_channels: Optional[Any] = None,
    ) -> Dict[str, str]:
        save_folder = folder or self.save_dir
        if not save_folder:
            raise RuntimeError("No save folder specified.")
        os.makedirs(save_folder, exist_ok=True)

        if save_channels is None:
            channels_to_save = list(self.save_channels) if self.save_channels else list(self.capture_channels)
        else:
            channels_to_save = self._parse_capture_channels(save_channels)

        if not channels_to_save:
            raise RuntimeError("No save channels specified.")

        saved_paths: Dict[str, str] = {}

        for ch in channels_to_save:
            if ch not in result.signals_v:
                continue

            ch_folder = os.path.join(save_folder, ch)
            os.makedirs(ch_folder, exist_ok=True)

            if point_index is None:
                file_index = self._get_next_channel_file_index(ch_folder, prefix)
            else:
                file_index = int(point_index)

            filename = f"{prefix}_{file_index:06d}.npz"
            path = os.path.join(ch_folder, filename)

            payload = {
                "time_s": np.asarray(result.time_s, dtype=float),
                "signal": np.asarray(result.signals_v[ch], dtype=float),
                "channel": np.array(ch),
                "meta": np.array(result.meta, dtype=object),
            }

            if point_index is not None:
                payload["point_index"] = int(point_index)
            if x_mm is not None:
                payload["x_mm"] = float(x_mm)
            if y_mm is not None:
                payload["y_mm"] = float(y_mm)

            np.savez_compressed(path, **payload)
            saved_paths[ch] = path

        if not saved_paths:
            raise RuntimeError(
                f"None of the requested save channels {channels_to_save} were present in capture result. "
                f"Available channels: {list(result.signals_v.keys())}"
            )

        return saved_paths
