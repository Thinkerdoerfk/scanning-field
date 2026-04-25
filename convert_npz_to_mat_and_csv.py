import os
import glob
import numpy as np
import pandas as pd
from scipy.io import savemat


def load_npz_file(path: str):
    data = np.load(path, allow_pickle=True)

    out = {}
    for k in data.files:
        out[k] = data[k]

    return out


def get_scalar(d, key, default=np.nan):
    if key not in d:
        return default
    v = d[key]
    if isinstance(v, np.ndarray):
        if v.shape == ():
            return v.item()
        if v.size == 1:
            return v.reshape(-1)[0].item()
    try:
        return float(v)
    except Exception:
        return default


def get_signal(d, channel_name=None):
    # 新格式：signal
    if "signal" in d:
        return np.asarray(d["signal"]).reshape(-1)

    # 旧格式：signal_B / signal_A ...
    if channel_name is not None:
        key = f"signal_{channel_name}"
        if key in d:
            return np.asarray(d[key]).reshape(-1)

    # 兜底：找第一个 signal_*
    for k in d.keys():
        if k.startswith("signal_"):
            return np.asarray(d[k]).reshape(-1)

    raise KeyError("No signal field found in npz file.")


def get_time_axis(d, signal_len=None):
    if "time_s" not in d:
        raise KeyError("No time_s field found in npz file.")
    t = np.asarray(d["time_s"]).reshape(-1)
    if signal_len is not None and len(t) != signal_len:
        raise ValueError(f"time_s length ({len(t)}) != signal length ({signal_len})")
    return t


def metric_peak_abs(sig):
    return float(np.max(np.abs(sig)))


def metric_rms(sig):
    return float(np.sqrt(np.mean(np.square(sig))))


def metric_pp(sig):
    return float(np.max(sig) - np.min(sig))


def build_outputs(folder, channel_name="B", out_prefix=None):
    if out_prefix is None:
        out_prefix = f"reconstructed_{channel_name}"

    files = sorted(glob.glob(os.path.join(folder, "capture_*.npz")))
    if not files:
        raise RuntimeError(f"No capture_*.npz found in: {folder}")

    rows = []
    time_ref = None

    print(f"Found {len(files)} files")

    for i, f in enumerate(files, 1):
        d = load_npz_file(f)

        sig = get_signal(d, channel_name=channel_name)
        t = get_time_axis(d, signal_len=len(sig))

        if time_ref is None:
            time_ref = t.copy()
        else:
            if len(t) != len(time_ref):
                raise ValueError(f"Inconsistent sample length in file: {f}")

        row = {
            "file_name": os.path.basename(f),
            "point_index": get_scalar(d, "point_index", np.nan),
            "x_mm": get_scalar(d, "x_mm", np.nan),
            "y_mm": get_scalar(d, "y_mm", np.nan),
            "peak_abs": metric_peak_abs(sig),
            "rms": metric_rms(sig),
            "pp": metric_pp(sig),
            "signal": sig,
        }
        rows.append(row)

        if i % 100 == 0 or i == len(files):
            print(f"  loaded {i}/{len(files)}")

    # DataFrame for table/csv
    df = pd.DataFrame(
        {
            "file_name": [r["file_name"] for r in rows],
            "point_index": [r["point_index"] for r in rows],
            "x_mm": [r["x_mm"] for r in rows],
            "y_mm": [r["y_mm"] for r in rows],
            "peak_abs": [r["peak_abs"] for r in rows],
            "rms": [r["rms"] for r in rows],
            "pp": [r["pp"] for r in rows],
        }
    )

    # 尝试按 point_index 排序；如果没有就按文件名
    if df["point_index"].notna().any():
        df = df.sort_values(["point_index", "file_name"], kind="stable").reset_index(drop=True)
    else:
        df = df.sort_values(["file_name"], kind="stable").reset_index(drop=True)

    # 重新按排序后的顺序取 rows
    row_map = {r["file_name"]: r for r in rows}
    rows_sorted = [row_map[fname] for fname in df["file_name"].tolist()]

    x_all = df["x_mm"].to_numpy(dtype=float)
    y_all = df["y_mm"].to_numpy(dtype=float)
    point_all = df["point_index"].to_numpy(dtype=float)

    signals = np.vstack([r["signal"] for r in rows_sorted])  # shape: [Npoints, Nsamples]

    # 唯一坐标
    x_unique = np.unique(np.round(x_all, 9))
    y_unique = np.unique(np.round(y_all, 9))

    nx = len(x_unique)
    ny = len(y_unique)
    ns = signals.shape[1]

    peak_map = np.full((ny, nx), np.nan, dtype=float)
    rms_map = np.full((ny, nx), np.nan, dtype=float)
    pp_map = np.full((ny, nx), np.nan, dtype=float)

    # 如果网格规则完整，还同时恢复 3D 波形场： [Ny, Nx, Nsamples]
    signal_cube = np.full((ny, nx, ns), np.nan, dtype=float)

    for _, r in df.iterrows():
        x = round(float(r["x_mm"]), 9)
        y = round(float(r["y_mm"]), 9)
        ix = np.where(np.abs(x_unique - x) < 1e-12)[0]
        iy = np.where(np.abs(y_unique - y) < 1e-12)[0]
        if len(ix) == 0 or len(iy) == 0:
            continue
        ix = ix[0]
        iy = iy[0]

        peak_map[iy, ix] = float(r["peak_abs"])
        rms_map[iy, ix] = float(r["rms"])
        pp_map[iy, ix] = float(r["pp"])

        sig = row_map[r["file_name"]]["signal"]
        signal_cube[iy, ix, :] = sig

    # 输出 MAT
    mat_dict = {
        "channel_name": np.array(channel_name, dtype=object),
        "time_s": np.asarray(time_ref, dtype=float),
        "signals": np.asarray(signals, dtype=float),          # [Npoints, Nsamples]
        "x_mm": np.asarray(x_all, dtype=float),               # [Npoints]
        "y_mm": np.asarray(y_all, dtype=float),               # [Npoints]
        "point_index": np.asarray(point_all, dtype=float),    # [Npoints]
        "x_unique": np.asarray(x_unique, dtype=float),
        "y_unique": np.asarray(y_unique, dtype=float),
        "peak_abs_map": peak_map,                             # [Ny, Nx]
        "rms_map": rms_map,                                   # [Ny, Nx]
        "pp_map": pp_map,                                     # [Ny, Nx]
        "signal_cube": signal_cube,                           # [Ny, Nx, Nsamples]
        "file_names": np.array(df["file_name"].tolist(), dtype=object),
    }

    mat_path = os.path.join(folder, out_prefix + ".mat")
    savemat(mat_path, mat_dict, do_compression=True)

    # 输出 CSV
    csv_path = os.path.join(folder, out_prefix + ".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print("\nDone.")
    print("MAT saved to:", mat_path)
    print("CSV saved to:", csv_path)
    print("signals shape:", signals.shape)
    print("signal_cube shape:", signal_cube.shape)
    print("map shape:", peak_map.shape)

    return mat_path, csv_path


if __name__ == "__main__":
    # 改成你的 B 文件夹
    folder = r"C:\Users\admin\Desktop\jianqing\scanresults\20260425\test1\B"
    channel_name = "B"
    build_outputs(folder=folder, channel_name=channel_name)