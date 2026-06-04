import glob
import os
import time

import numpy as np


def _none_if_nan(value):
    if value is None:
        return None
    value = float(value)
    if np.isnan(value):
        return None
    return value


def _build_frequency_list_hz(freq_count, freq_start_mhz, freq_stop_mhz, freq_step_khz):
    freq_count = int(freq_count)
    start_hz = float(freq_start_mhz) * 1e6
    stop_hz = float(freq_stop_mhz) * 1e6
    step_hz = float(freq_step_khz) * 1e3

    if freq_count <= 0:
        raise ValueError("freq_count must be positive")
    if start_hz <= 0 or stop_hz <= 0:
        raise ValueError("frequency range must be positive")
    if stop_hz < start_hz:
        raise ValueError("frequency stop must be >= start")

    if step_hz > 0:
        freqs = np.arange(start_hz, stop_hz + step_hz * 1e-9, step_hz, dtype=float)
        if len(freqs) == freq_count:
            return freqs

    return np.linspace(start_hz, stop_hz, freq_count, dtype=float)


def _as_meta_dict(value):
    try:
        arr = np.asarray(value, dtype=object)
        if arr.shape == ():
            item = arr.item()
            return item if isinstance(item, dict) else {}
    except Exception:
        pass
    return {}


def _load_npz_file(path):
    with np.load(path, allow_pickle=True) as d:
        return {key: d[key] for key in d.files}


def _get_scalar(data, key, default=np.nan):
    if key in data:
        try:
            return float(np.asarray(data[key]).reshape(-1)[0])
        except Exception:
            return default

    meta = _as_meta_dict(data.get("meta"))
    if key in meta:
        try:
            return float(np.asarray(meta[key]).reshape(-1)[0])
        except Exception:
            return default
    return default


def _get_file_frequency_list_hz(data, configured_frequencies_hz):
    for key in ("excitation_frequencies_hz", "frequencies_hz"):
        if key in data:
            values = np.asarray(data[key], dtype=float).reshape(-1)
            if len(values) > 0:
                return values

    meta = _as_meta_dict(data.get("meta"))
    for key in ("excitation_frequencies_hz", "frequencies_hz"):
        if key in meta:
            values = np.asarray(meta[key], dtype=float).reshape(-1)
            if len(values) > 0:
                return values

    return np.asarray(configured_frequencies_hz, dtype=float).reshape(-1)


def _get_time_axis(data):
    if "time_s" not in data:
        raise RuntimeError("NPZ does not contain time_s")
    return np.asarray(data["time_s"], dtype=float).reshape(-1)


def _get_signal(data):
    if "signal" not in data:
        raise RuntimeError("NPZ does not contain signal")
    return np.asarray(data["signal"], dtype=float)


def _split_multifrequency_signals(signal, time_s, freq_count):
    signal = np.asarray(signal, dtype=float)
    time_s = np.asarray(time_s, dtype=float).reshape(-1)
    freq_count = int(freq_count)

    if signal.ndim == 2:
        if signal.shape[0] != freq_count:
            raise RuntimeError(
                f"Signal has {signal.shape[0]} frequency rows, expected {freq_count}"
            )
        return signal, time_s

    flat = signal.reshape(-1)
    if len(flat) == len(time_s):
        if freq_count == 1:
            return flat.reshape(1, -1), time_s
        raise RuntimeError("1D signal cannot be split into multiple frequencies")

    if len(flat) % freq_count != 0:
        raise RuntimeError("1D signal length is not divisible by frequency count")

    samples = len(flat) // freq_count
    if len(time_s) != samples:
        raise RuntimeError("Time axis length does not match split signal length")
    return flat.reshape(freq_count, samples), time_s


def _apply_gate_to_blocks(signal_blocks, time_s, gate_t1=None, gate_t2=None):
    signal_blocks = np.asarray(signal_blocks, dtype=float)
    time_s = np.asarray(time_s, dtype=float).reshape(-1)

    mask = np.ones(time_s.shape, dtype=bool)
    if gate_t1 is not None:
        mask &= time_s >= float(gate_t1)
    if gate_t2 is not None:
        mask &= time_s <= float(gate_t2)
    if np.count_nonzero(mask) < 2:
        raise RuntimeError("Gate contains fewer than 2 samples")
    return signal_blocks[:, mask], time_s[mask]


def _fft_complex_amp_at_target_freq(signal, time_s, target_freq_hz, remove_dc=True):
    y = np.asarray(signal, dtype=float).reshape(-1)
    t = np.asarray(time_s, dtype=float).reshape(-1)
    if len(y) != len(t) or len(y) < 2:
        raise RuntimeError("Signal and time axis are not compatible")

    if remove_dc:
        y = y - float(np.mean(y))

    target_freq_hz = float(target_freq_hz)
    kernel = np.exp(-2j * np.pi * target_freq_hz * (t - t[0]))
    complex_amp = (2.0 / len(y)) * np.sum(y * kernel)

    dt = float(np.median(np.diff(t)))
    fft_freqs = np.fft.rfftfreq(len(y), d=dt)
    fft_index = int(np.argmin(np.abs(fft_freqs - target_freq_hz)))
    freq_found_hz = float(fft_freqs[fft_index])
    return complex_amp, freq_found_hz, fft_index


def _voltage_amp_to_pressure_amp_mpa(voltage_amp_v, sens_v_per_mpa):
    sens = float(sens_v_per_mpa)
    if sens <= 0:
        raise ValueError("sens_v_per_mpa must be positive")
    return float(voltage_amp_v) / sens


def _make_maps(rows, freq_count):
    if not rows:
        return None

    x_unique = np.unique(np.round([r["x_mm"] for r in rows], 9)).astype(np.float32)
    y_unique = np.unique(np.round([r["y_mm"] for r in rows], 9)).astype(np.float32)
    nx = len(x_unique)
    ny = len(y_unique)

    voltage_amp_maps = np.full((freq_count, ny, nx), np.nan, dtype=np.float32)
    pressure_amp_maps = np.full((freq_count, ny, nx), np.nan, dtype=np.float32)
    phase_maps = np.full((freq_count, ny, nx), np.nan, dtype=np.float32)
    freq_found_maps = np.full((freq_count, ny, nx), np.nan, dtype=np.float32)

    for r in rows:
        ix = np.where(np.abs(x_unique - np.float32(r["x_mm"])) < 1e-6)[0]
        iy = np.where(np.abs(y_unique - np.float32(r["y_mm"])) < 1e-6)[0]
        if len(ix) == 0 or len(iy) == 0:
            continue
        freq_i = int(r["frequency_index"]) - 1
        if freq_i < 0 or freq_i >= freq_count:
            continue
        voltage_amp_maps[freq_i, iy[0], ix[0]] = np.float32(r["voltage_amp_V"])
        pressure_amp_maps[freq_i, iy[0], ix[0]] = np.float32(r["pressure_amp_MPa"])
        phase_maps[freq_i, iy[0], ix[0]] = np.float32(r["phase_rad"])
        freq_found_maps[freq_i, iy[0], ix[0]] = np.float32(r["freq_found_Hz"])

    point_keys = sorted({(r["point_index"], r["file_name"]) for r in rows})
    return {
        "x_unique": x_unique,
        "y_unique": y_unique,
        "voltage_amp_maps": voltage_amp_maps,
        "pressure_amp_maps": pressure_amp_maps,
        "phase_maps": phase_maps,
        "freq_found_maps": freq_found_maps,
        "processed_points": len(point_keys),
    }


def _save_output(output_path, config, rows, maps, frequencies_hz):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if maps is None:
        return
    amplitudes_vpp = config.get("excitation_amplitudes_vpp")
    if amplitudes_vpp is None:
        amplitudes_vpp = []

    rows_dtype = [
        ("file_name", "U260"),
        ("point_index", "f8"),
        ("x_mm", "f8"),
        ("y_mm", "f8"),
        ("frequency_index", "i4"),
        ("excitation_frequency_Hz", "f8"),
        ("excitation_frequency_MHz", "f8"),
        ("excitation_amplitude_Vpp", "f8"),
        ("voltage_amp_V", "f8"),
        ("pressure_amp_MPa", "f8"),
        ("phase_rad", "f8"),
        ("freq_found_Hz", "f8"),
        ("fft_index", "i4"),
    ]
    row_array = np.zeros(len(rows), dtype=rows_dtype)
    for i, r in enumerate(rows):
        for name, _ in rows_dtype:
            row_array[name][i] = r[name]

    np.savez(
        output_path,
        channel_name=np.array(config["channel_name"]),
        scan_mode=np.array(str(config.get("scan_mode", "frequency_sweep"))),
        frequency_count=np.array(len(frequencies_hz), dtype=np.int32),
        excitation_frequencies_hz=np.asarray(frequencies_hz, dtype=np.float64),
        excitation_frequencies_mhz=np.asarray(frequencies_hz, dtype=np.float64) / 1e6,
        excitation_amplitudes_vpp=np.asarray(amplitudes_vpp, dtype=np.float64),
        sens_v_per_mpa=np.array(config["sens_v_per_mpa"], dtype=np.float32),
        gate_t1=np.array(np.nan if config["gate_t1"] is None else config["gate_t1"], dtype=np.float32),
        gate_t2=np.array(np.nan if config["gate_t2"] is None else config["gate_t2"], dtype=np.float32),
        x_unique=maps["x_unique"],
        y_unique=maps["y_unique"],
        rows=row_array,
        voltage_amp_maps=maps["voltage_amp_maps"],
        pressure_amp_maps=maps["pressure_amp_maps"],
        phase_maps=maps["phase_maps"],
        freq_found_maps=maps["freq_found_maps"],
        processed_points=np.array(maps["processed_points"], dtype=np.int32),
        updated_unix_time=np.array(time.time(), dtype=np.float64),
    )


def run_realtime_multifrequency_postprocess(config, status_queue, stop_event):
    input_folder = config["input_folder"]
    output_path = config["output_path"]
    poll_interval_s = float(config.get("poll_interval_s", 1.0))
    save_every_s = float(config.get("save_every_s", 5.0))

    gate_t1 = _none_if_nan(config.get("gate_t1"))
    gate_t2 = _none_if_nan(config.get("gate_t2"))
    configured_frequencies_hz = _build_frequency_list_hz(
        freq_count=int(config["freq_count"]),
        freq_start_mhz=float(config["freq_start_mhz"]),
        freq_stop_mhz=float(config["freq_stop_mhz"]),
        freq_step_khz=float(config["freq_step_khz"]),
    )
    freq_count = int(len(configured_frequencies_hz))
    configured_amplitudes = config.get("excitation_amplitudes_vpp")
    if configured_amplitudes is None:
        configured_amplitudes = []
    configured_amplitudes_vpp = np.asarray(configured_amplitudes, dtype=float).reshape(-1)
    if len(configured_amplitudes_vpp) not in (0, freq_count):
        raise ValueError("excitation_amplitudes_vpp length must match freq_count")

    rows = []
    processed_files = set()
    last_save_t = 0.0

    status_queue.put(
        {
            "type": "status",
            "status": "running",
            "message": "Realtime postprocess started",
            "output_path": output_path,
            "processed_files": 0,
            "processed_points": 0,
        }
    )

    while not stop_event.is_set():
        try:
            files = sorted(glob.glob(os.path.join(input_folder, "capture_*.npz")))
            new_files = [p for p in files if p not in processed_files]

            for path in new_files:
                if stop_event.is_set():
                    break

                data = _load_npz_file(path)
                file_frequencies_hz = _get_file_frequency_list_hz(data, configured_frequencies_hz)
                if len(file_frequencies_hz) != freq_count:
                    raise RuntimeError(
                        f"{os.path.basename(path)} has {len(file_frequencies_hz)} frequencies, expected {freq_count}"
                    )

                sig_raw = _get_signal(data)
                t_raw = _get_time_axis(data)
                sig_blocks, t = _split_multifrequency_signals(
                    sig_raw,
                    t_raw,
                    freq_count=freq_count,
                )
                sig_blocks, t_proc = _apply_gate_to_blocks(
                    sig_blocks,
                    t,
                    gate_t1=gate_t1,
                    gate_t2=gate_t2,
                )

                point_index = _get_scalar(data, "point_index", np.nan)
                x_mm = _get_scalar(data, "x_mm", np.nan)
                y_mm = _get_scalar(data, "y_mm", np.nan)

                for freq_index, (target_freq_hz, sig) in enumerate(zip(file_frequencies_hz, sig_blocks), 1):
                    amplitude_vpp = (
                        float(configured_amplitudes_vpp[freq_index - 1])
                        if len(configured_amplitudes_vpp) == freq_count
                        else np.nan
                    )
                    complex_amp, freq_found_hz, fft_index = _fft_complex_amp_at_target_freq(
                        sig,
                        t_proc,
                        target_freq_hz=target_freq_hz,
                        remove_dc=True,
                    )
                    voltage_amp_v = float(np.abs(complex_amp))
                    rows.append(
                        {
                            "file_name": os.path.basename(path),
                            "point_index": float(point_index),
                            "x_mm": float(x_mm),
                            "y_mm": float(y_mm),
                            "frequency_index": int(freq_index),
                            "excitation_frequency_Hz": float(target_freq_hz),
                            "excitation_frequency_MHz": float(target_freq_hz / 1e6),
                            "excitation_amplitude_Vpp": amplitude_vpp,
                            "voltage_amp_V": voltage_amp_v,
                            "pressure_amp_MPa": _voltage_amp_to_pressure_amp_mpa(
                                voltage_amp_v,
                                float(config["sens_v_per_mpa"]),
                            ),
                            "phase_rad": float(np.angle(complex_amp)),
                            "freq_found_Hz": float(freq_found_hz),
                            "fft_index": int(fft_index),
                        }
                    )
                processed_files.add(path)

                now = time.time()
                if rows and now - last_save_t >= save_every_s:
                    maps = _make_maps(rows, freq_count=freq_count)
                    _save_output(output_path, config, rows, maps, configured_frequencies_hz)
                    last_save_t = now
                    status_queue.put(
                        {
                            "type": "status",
                            "status": "running",
                            "message": "Updated maps",
                            "output_path": output_path,
                            "processed_files": len(processed_files),
                            "processed_points": maps["processed_points"] if maps else 0,
                        }
                    )

            now = time.time()
            if rows and (new_files or now - last_save_t >= save_every_s):
                maps = _make_maps(rows, freq_count=freq_count)
                _save_output(output_path, config, rows, maps, configured_frequencies_hz)
                last_save_t = now
                status_queue.put(
                    {
                        "type": "status",
                        "status": "running",
                        "message": "Updated maps",
                        "output_path": output_path,
                        "processed_files": len(processed_files),
                        "processed_points": maps["processed_points"] if maps else 0,
                    }
                )

            time.sleep(poll_interval_s)

        except Exception as e:
            status_queue.put({"type": "error", "status": "error", "message": str(e)})
            time.sleep(max(1.0, poll_interval_s))

    try:
        maps = _make_maps(rows, freq_count=freq_count)
        if maps is not None:
            _save_output(output_path, config, rows, maps, configured_frequencies_hz)
    finally:
        status_queue.put(
            {
                "type": "status",
                "status": "stopped",
                "message": "Realtime postprocess stopped",
                "output_path": output_path,
                "processed_files": len(processed_files),
            }
        )
