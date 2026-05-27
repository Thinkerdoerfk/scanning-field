import glob
import os
import queue
import time

import numpy as np


POSTPROCESS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "postprocessscan")
)


def _ensure_postprocess_path():
    import sys

    if POSTPROCESS_DIR not in sys.path:
        sys.path.insert(0, POSTPROCESS_DIR)


def _load_tools():
    _ensure_postprocess_path()
    from postprocess_multifrequency_pressure_fft import (
        apply_gate_to_blocks,
        build_frequency_list_hz,
        get_file_frequency_list_hz,
        split_multifrequency_signals,
    )
    from postprocess_pressure_fft import (
        fft_complex_amp_at_target_freq,
        get_scalar,
        get_signal,
        get_time_axis,
        load_npz_file,
        voltage_amp_to_pressure_amp_mpa,
    )

    return {
        "apply_gate_to_blocks": apply_gate_to_blocks,
        "build_frequency_list_hz": build_frequency_list_hz,
        "get_file_frequency_list_hz": get_file_frequency_list_hz,
        "split_multifrequency_signals": split_multifrequency_signals,
        "fft_complex_amp_at_target_freq": fft_complex_amp_at_target_freq,
        "get_scalar": get_scalar,
        "get_signal": get_signal,
        "get_time_axis": get_time_axis,
        "load_npz_file": load_npz_file,
        "voltage_amp_to_pressure_amp_mpa": voltage_amp_to_pressure_amp_mpa,
    }


def _none_if_nan(value):
    if value is None:
        return None
    value = float(value)
    if np.isnan(value):
        return None
    return value


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

    rows_dtype = [
        ("file_name", "U260"),
        ("point_index", "f8"),
        ("x_mm", "f8"),
        ("y_mm", "f8"),
        ("frequency_index", "i4"),
        ("excitation_frequency_Hz", "f8"),
        ("excitation_frequency_MHz", "f8"),
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

    np.savez_compressed(
        output_path,
        channel_name=np.array(config["channel_name"]),
        frequency_count=np.array(len(frequencies_hz), dtype=np.int32),
        excitation_frequencies_hz=np.asarray(frequencies_hz, dtype=np.float64),
        excitation_frequencies_mhz=np.asarray(frequencies_hz, dtype=np.float64) / 1e6,
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
    tools = _load_tools()
    input_folder = config["input_folder"]
    output_path = config["output_path"]
    channel_name = config["channel_name"]
    poll_interval_s = float(config.get("poll_interval_s", 1.0))
    save_every_s = float(config.get("save_every_s", 2.0))

    gate_t1 = _none_if_nan(config.get("gate_t1"))
    gate_t2 = _none_if_nan(config.get("gate_t2"))
    configured_frequencies_hz = tools["build_frequency_list_hz"](
        freq_count=int(config["freq_count"]),
        freq_start_mhz=float(config["freq_start_mhz"]),
        freq_stop_mhz=float(config["freq_stop_mhz"]),
        freq_step_khz=float(config["freq_step_khz"]),
    )
    freq_count = int(len(configured_frequencies_hz))

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

                d = tools["load_npz_file"](path)
                file_frequencies_hz = tools["get_file_frequency_list_hz"](d, configured_frequencies_hz)
                sig_raw = tools["get_signal"](d, channel_name=channel_name)
                t_raw = tools["get_time_axis"](d)
                sig_blocks, t = tools["split_multifrequency_signals"](
                    sig_raw,
                    t_raw,
                    freq_count=freq_count,
                )
                sig_blocks, t_proc = tools["apply_gate_to_blocks"](
                    sig_blocks,
                    t,
                    gate_t1=gate_t1,
                    gate_t2=gate_t2,
                )

                point_index = tools["get_scalar"](d, "point_index", np.nan)
                x_mm = tools["get_scalar"](d, "x_mm", np.nan)
                y_mm = tools["get_scalar"](d, "y_mm", np.nan)

                for freq_index, (target_freq_hz, sig) in enumerate(zip(file_frequencies_hz, sig_blocks), 1):
                    complex_amp, freq_found_hz, fft_index = tools["fft_complex_amp_at_target_freq"](
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
                            "voltage_amp_V": voltage_amp_v,
                            "pressure_amp_MPa": float(
                                tools["voltage_amp_to_pressure_amp_mpa"](
                                    voltage_amp_v,
                                    float(config["sens_v_per_mpa"]),
                                )
                            ),
                            "phase_rad": float(np.angle(complex_amp)),
                            "freq_found_Hz": float(freq_found_hz),
                            "fft_index": int(fft_index),
                        }
                    )
                processed_files.add(path)

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

