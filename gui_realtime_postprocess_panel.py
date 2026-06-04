import multiprocessing as mp
import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from realtime_multifrequency_postprocess import run_realtime_multifrequency_postprocess


class RealtimePostprocessPanel(ttk.LabelFrame):
    def __init__(self, parent, ctx, log_func=None):
        super().__init__(parent, text="🌈 Realtime Multifrequency Maps", padding=8)
        self.ctx = ctx
        self.log = log_func if log_func is not None else print

        self.process = None
        self.stop_event = None
        self.status_queue = None
        self.current_npz_path = ""
        self.current_data = None

        self._build_vars()
        self._build_layout()
        self._build_plot()
        self._poll_worker()
        self._poll_output_file()

    def _build_vars(self):
        self.var_input_folder = tk.StringVar(value="")
        self.var_output_folder = tk.StringVar(value="")
        self.var_channel = tk.StringVar(value="D")
        self.var_scan_mode = tk.StringVar(value="Sweep frequency")
        self.var_freq_count = tk.StringVar(value="21")
        self.var_freq_start_mhz = tk.StringVar(value="2.0")
        self.var_freq_stop_mhz = tk.StringVar(value="2.1")
        self.var_freq_step_khz = tk.StringVar(value="5")
        self.var_voltage_list_vpp = tk.StringVar(value="0.1")
        self.var_sens = tk.StringVar(value="0.05")
        self.var_gate_t1_us = tk.StringVar(value="400")
        self.var_gate_t2_us = tk.StringVar(value="500")
        self.var_field = tk.StringVar(value="pressure")
        self.var_freq_index = tk.StringVar(value="all")
        self.var_status = tk.StringVar(value="Stopped")
        self.var_processed = tk.StringVar(value="Files: 0 | Points: 0")

    def _build_layout(self):
        self.columnconfigure(1, weight=1)

        r = 0
        ttk.Label(self, text="Input").grid(row=r, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.var_input_folder, width=34).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(self, text="Use Save", command=self.use_current_save_folder).grid(row=r, column=2, sticky="ew")

        r += 1
        ttk.Label(self, text="Output").grid(row=r, column=0, sticky="w")
        ttk.Entry(self, textvariable=self.var_output_folder, width=34).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(self, text="Default", command=self.use_default_output_folder).grid(row=r, column=2, sticky="ew")

        r += 1
        rowf = ttk.Frame(self)
        rowf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(rowf, text="Ch").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_channel, width=4).pack(side="left", padx=(3, 8))
        ttk.Label(rowf, text="Mode").pack(side="left")
        ttk.Combobox(
            rowf,
            textvariable=self.var_scan_mode,
            values=["Sweep frequency", "Sweep voltage"],
            width=16,
            state="readonly",
        ).pack(side="left", padx=(3, 8))
        ttk.Label(rowf, text="Count").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_freq_count, width=5).pack(side="left", padx=(3, 8))
        ttk.Label(rowf, text="MHz").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_freq_start_mhz, width=6).pack(side="left", padx=(3, 2))
        ttk.Label(rowf, text="to").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_freq_stop_mhz, width=6).pack(side="left", padx=(3, 8))
        ttk.Label(rowf, text="kHz").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_freq_step_khz, width=5).pack(side="left", padx=(3, 0))

        r += 1
        rowf = ttk.Frame(self)
        rowf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(rowf, text="Sweep voltage").pack(side="left")
        ttk.Label(rowf, text="Fixed MHz").pack(side="left", padx=(8, 3))
        ttk.Entry(rowf, textvariable=self.var_freq_start_mhz, width=6).pack(side="left")
        ttk.Label(rowf, text="Vpp list").pack(side="left", padx=(8, 3))
        ttk.Entry(rowf, textvariable=self.var_voltage_list_vpp, width=28).pack(side="left", fill="x", expand=True)

        r += 1
        rowf = ttk.Frame(self)
        rowf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(rowf, text="Sens V/MPa").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_sens, width=7).pack(side="left", padx=(3, 8))
        ttk.Label(rowf, text="Gate us").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_gate_t1_us, width=6).pack(side="left", padx=(3, 2))
        ttk.Label(rowf, text="to").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_gate_t2_us, width=6).pack(side="left", padx=(3, 8))
        ttk.Button(rowf, text="▶ Start", command=self.start_worker).pack(side="left", padx=(0, 4))
        ttk.Button(rowf, text="■ Stop", command=self.stop_worker).pack(side="left")

        r += 1
        rowf = ttk.Frame(self)
        rowf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        ttk.Label(rowf, textvariable=self.var_status).pack(side="left")
        ttk.Label(rowf, textvariable=self.var_processed).pack(side="right")

        r += 1
        rowf = ttk.Frame(self)
        rowf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(6, 2))
        ttk.Label(rowf, text="Field").pack(side="left")
        ttk.Combobox(
            rowf,
            textvariable=self.var_field,
            values=["pressure", "phase", "voltage"],
            width=9,
            state="readonly",
        ).pack(side="left", padx=(3, 8))
        ttk.Label(rowf, text="Map #").pack(side="left")
        ttk.Entry(rowf, textvariable=self.var_freq_index, width=5).pack(side="left", padx=(3, 8))
        ttk.Button(rowf, text="Update", command=self.update_plot).pack(side="left")

        self.plot_frame = ttk.Frame(self)
        self.plot_frame.grid(row=r + 1, column=0, columnspan=3, sticky="nsew")
        self.rowconfigure(r + 1, weight=1)

    def _build_plot(self):
        self.fig = Figure(figsize=(4.4, 3.4), dpi=100, facecolor="#f8fafc")
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_empty("No realtime map yet")

    def _draw_empty(self, text):
        self.ax.clear()
        self.ax.set_facecolor("#ffffff")
        self.ax.text(0.5, 0.5, text, ha="center", va="center", transform=self.ax.transAxes)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.canvas.draw_idle()

    def _float_or_none_us(self, text):
        text = str(text).strip()
        if not text:
            return None
        return float(text) * 1e-6

    def _parse_voltage_list_vpp(self):
        text = self.var_voltage_list_vpp.get().strip()
        if not text:
            raise RuntimeError("Vpp list is empty.")
        parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
        try:
            values = np.asarray([float(part) for part in parts], dtype=float)
        except Exception:
            raise RuntimeError("Invalid Vpp list. Use values like 0.5,0.52,0.54")
        if len(values) == 0:
            raise RuntimeError("Vpp list is empty.")
        if np.any(values <= 0):
            raise RuntimeError("All Vpp values must be positive.")
        return values

    def use_current_save_folder(self):
        try:
            save_dir = getattr(self.ctx.pico, "save_dir", "") if self.ctx.pico is not None else ""
            if not save_dir:
                raise RuntimeError("No Pico save folder selected.")
            ch = self.var_channel.get().strip().upper()
            input_folder = os.path.join(save_dir, ch)
            self.var_input_folder.set(input_folder)
            if not self.var_output_folder.get().strip():
                self.use_default_output_folder()
        except Exception as e:
            messagebox.showerror("Realtime Postprocess", str(e))

    def use_default_output_folder(self):
        base = ""
        if self.var_input_folder.get().strip():
            base = os.path.dirname(self.var_input_folder.get().strip())
        elif self.ctx.pico is not None:
            base = getattr(self.ctx.pico, "save_dir", "") or ""
        if not base:
            base = os.getcwd()
        self.var_output_folder.set(os.path.join(base, "realtime_multifrequency_postprocess"))

    def _build_config(self):
        input_folder = self.var_input_folder.get().strip()
        output_folder = self.var_output_folder.get().strip()
        channel = self.var_channel.get().strip().upper()
        if not input_folder:
            raise RuntimeError("Input folder is empty.")
        if not output_folder:
            raise RuntimeError("Output folder is empty.")
        os.makedirs(output_folder, exist_ok=True)
        scan_mode = self.var_scan_mode.get().strip()
        voltage_mode = scan_mode == "Sweep voltage"
        output_stem = "realtime_voltage_sweep_fft" if voltage_mode else "realtime_multifrequency_fft"
        output_path = os.path.join(output_folder, f"{output_stem}_{channel}.npz")
        self.current_npz_path = output_path
        freq_start_mhz = float(self.var_freq_start_mhz.get())
        if voltage_mode:
            amplitudes_vpp = self._parse_voltage_list_vpp()
            freq_count = int(len(amplitudes_vpp))
            freq_stop_mhz = freq_start_mhz
            freq_step_khz = 1.0
        else:
            amplitudes_vpp = None
            freq_count = int(self.var_freq_count.get())
            freq_stop_mhz = float(self.var_freq_stop_mhz.get())
            freq_step_khz = float(self.var_freq_step_khz.get())
        return {
            "input_folder": input_folder,
            "output_path": output_path,
            "channel_name": channel,
            "scan_mode": "voltage_sweep" if voltage_mode else "frequency_sweep",
            "freq_count": freq_count,
            "freq_start_mhz": freq_start_mhz,
            "freq_stop_mhz": freq_stop_mhz,
            "freq_step_khz": freq_step_khz,
            "excitation_amplitudes_vpp": amplitudes_vpp,
            "sens_v_per_mpa": float(self.var_sens.get()),
            "gate_t1": self._float_or_none_us(self.var_gate_t1_us.get()),
            "gate_t2": self._float_or_none_us(self.var_gate_t2_us.get()),
            "poll_interval_s": 1.0,
            "save_every_s": 30.0,
        }

    def start_worker(self):
        try:
            if self.process is not None and self.process.is_alive():
                raise RuntimeError("Realtime postprocess is already running.")
            config = self._build_config()
            self.current_data = None
            self._draw_empty("Processing existing files")
            self.status_queue = mp.Queue()
            self.stop_event = mp.Event()
            self.process = mp.Process(
                target=run_realtime_multifrequency_postprocess,
                args=(config, self.status_queue, self.stop_event),
                daemon=True,
            )
            self.process.start()
            self.var_status.set("Starting realtime postprocess...")
            self.log(f"[POST] Started realtime postprocess: {self.current_npz_path}")
        except Exception as e:
            self.log(f"[POST] Start failed: {e}")
            messagebox.showerror("Realtime Postprocess", str(e))

    def stop_worker(self):
        try:
            if self.stop_event is not None:
                self.stop_event.set()
            if self.process is not None:
                self.process.join(timeout=2.0)
                if self.process.is_alive():
                    self.process.terminate()
            self.var_status.set("Stopped")
        except Exception as e:
            self.log(f"[POST] Stop failed: {e}")

    def _poll_worker(self):
        try:
            if self.status_queue is not None:
                while True:
                    try:
                        msg = self.status_queue.get_nowait()
                    except queue.Empty:
                        break
                    self.var_status.set(str(msg.get("message", msg.get("status", ""))))
                    self.var_processed.set(
                        f"Files: {msg.get('processed_files', 0)} | Points: {msg.get('processed_points', 0)}"
                    )
                    if msg.get("type") == "error":
                        self.log(f"[POST] {msg.get('message')}")
        finally:
            self.after(500, self._poll_worker)

    def _poll_output_file(self):
        try:
            if self.current_npz_path and os.path.exists(self.current_npz_path):
                self._load_current_npz()
                self.update_plot()
        except Exception as e:
            self.var_status.set(f"Plot update failed: {e}")
        finally:
            self.after(30000, self._poll_output_file)

    def _load_current_npz(self):
        with np.load(self.current_npz_path, allow_pickle=True) as d:
            self.current_data = {k: d[k] for k in d.files}

    def update_plot(self):
        if self.current_data is None:
            self._draw_empty("Waiting for processed file")
            return
        field = self.var_field.get().strip().lower()
        key = {
            "pressure": "pressure_amp_maps",
            "phase": "phase_maps",
            "voltage": "voltage_amp_maps",
        }.get(field)
        if key is None or key not in self.current_data:
            self._draw_empty("No map data")
            return

        maps = np.asarray(self.current_data[key], dtype=float)
        if maps.ndim != 3:
            self._draw_empty("Invalid map shape")
            return
        freq_text = self.var_freq_index.get().strip().lower()
        if freq_text in ("all", "*"):
            self._draw_all_frequency_maps(field, maps)
            return

        idx = int(freq_text) - 1
        idx = max(0, min(idx, maps.shape[0] - 1))
        self.var_freq_index.set(str(idx + 1))

        field_map = maps[idx]
        freqs_mhz = np.asarray(self.current_data.get("excitation_frequencies_mhz", []), dtype=float).reshape(-1)
        amplitudes_vpp = np.asarray(self.current_data.get("excitation_amplitudes_vpp", []), dtype=float).reshape(-1)
        scan_mode = str(np.asarray(self.current_data.get("scan_mode", "frequency_sweep")).reshape(-1)[0])
        if scan_mode == "voltage_sweep" and idx < len(amplitudes_vpp):
            base_freq = f"{freqs_mhz[idx]:.3f} MHz, " if idx < len(freqs_mhz) else ""
            freq_label = f"{base_freq}{amplitudes_vpp[idx]:.6g} Vpp"
        else:
            freq_label = f"{freqs_mhz[idx]:.3f} MHz" if idx < len(freqs_mhz) else f"#{idx + 1}"
        x_unique = np.asarray(self.current_data.get("x_unique", []), dtype=float).reshape(-1)
        y_unique = np.asarray(self.current_data.get("y_unique", []), dtype=float).reshape(-1)
        extent = None
        if len(x_unique) > 0 and len(y_unique) > 0:
            extent = [
                float(np.nanmin(x_unique)),
                float(np.nanmax(x_unique)),
                float(np.nanmin(y_unique)),
                float(np.nanmax(y_unique)),
            ]

        self.fig.clear()
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.set_facecolor("#ffffff")
        if np.all(np.isnan(field_map)):
            self._draw_empty(f"No data at {freq_label}")
            return

        if field == "phase":
            vmin, vmax = -np.pi, np.pi
            label = "Phase (rad)"
        elif field == "voltage":
            vmin = vmax = None
            label = "Voltage amplitude (V)"
        else:
            vmin = vmax = None
            label = "Pressure amplitude (MPa)"

        image = self.ax.imshow(
            field_map,
            origin="lower",
            aspect="equal",
            cmap="jet",
            interpolation="nearest",
            extent=extent,
            vmin=vmin,
            vmax=vmax,
        )
        self.ax.set_title(f"{field.title()} at {freq_label}")
        self.ax.set_xlabel("X (mm)" if extent is not None else "X index")
        self.ax.set_ylabel("Y (mm)" if extent is not None else "Y index")
        cb = self.fig.colorbar(image, ax=self.ax, fraction=0.046, pad=0.04)
        cb.set_label(label)
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def _draw_all_frequency_maps(self, field, maps):
        freq_count = int(maps.shape[0])
        if freq_count <= 0:
            self._draw_empty("No map data")
            return

        freqs_mhz = np.asarray(self.current_data.get("excitation_frequencies_mhz", []), dtype=float).reshape(-1)
        amplitudes_vpp = np.asarray(self.current_data.get("excitation_amplitudes_vpp", []), dtype=float).reshape(-1)
        scan_mode = str(np.asarray(self.current_data.get("scan_mode", "frequency_sweep")).reshape(-1)[0])
        x_unique = np.asarray(self.current_data.get("x_unique", []), dtype=float).reshape(-1)
        y_unique = np.asarray(self.current_data.get("y_unique", []), dtype=float).reshape(-1)
        extent = None
        if len(x_unique) > 0 and len(y_unique) > 0:
            extent = [
                float(np.nanmin(x_unique)),
                float(np.nanmax(x_unique)),
                float(np.nanmin(y_unique)),
                float(np.nanmax(y_unique)),
            ]

        cols = int(np.ceil(np.sqrt(freq_count)))
        rows = int(np.ceil(freq_count / cols))
        self.fig.clear()
        axes = self.fig.subplots(rows, cols, squeeze=False)

        finite_values = maps[np.isfinite(maps)]
        if field == "phase":
            vmin, vmax = -np.pi, np.pi
            cmap = "twilight"
        else:
            vmin = float(np.nanmin(finite_values)) if finite_values.size else None
            vmax = float(np.nanmax(finite_values)) if finite_values.size else None
            cmap = "jet"

        last_image = None
        for i, ax in enumerate(axes.flat):
            ax.set_facecolor("#ffffff")
            if i >= freq_count:
                ax.axis("off")
                continue

            field_map = maps[i]
            if np.all(np.isnan(field_map)):
                ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes, fontsize=7)
            else:
                last_image = ax.imshow(
                    field_map,
                    origin="lower",
                    aspect="equal",
                    cmap=cmap,
                    interpolation="nearest",
                    extent=extent,
                    vmin=vmin,
                    vmax=vmax,
                )

            if scan_mode == "voltage_sweep" and i < len(amplitudes_vpp):
                title = f"{amplitudes_vpp[i]:.6g} Vpp"
            else:
                title = f"{freqs_mhz[i]:.3f} MHz" if i < len(freqs_mhz) else f"#{i + 1}"
            ax.set_title(title, fontsize=7)
            ax.set_xticks([])
            ax.set_yticks([])

        if last_image is not None:
            if field == "phase":
                label = "Phase (rad)"
            elif field == "voltage":
                label = "Voltage amplitude (V)"
            else:
                label = "Pressure amplitude (MPa)"
            self.fig.colorbar(last_image, ax=axes.ravel().tolist(), fraction=0.025, pad=0.01).set_label(label)

        title_suffix = "All Voltages" if scan_mode == "voltage_sweep" else "All Frequencies"
        self.fig.suptitle(f"{field.title()} Maps: {title_suffix}", fontsize=10)
        self.canvas.draw_idle()

    def destroy(self):
        self.stop_worker()
        super().destroy()
