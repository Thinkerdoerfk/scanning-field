import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np

from scan_controller import ScanController


class ScanPanel:
    def __init__(self, parent, ctx, log_func):
        self.parent = parent
        self.ctx = ctx
        self.log = log_func

        self.scan_controller = None
        #self.scan_thread = None
        #self.test_scan_thread = None

        self.frame = ttk.LabelFrame(parent, text="🗺 Scan", padding=6)
        self.frame.pack(fill="x", padx=4, pady=4)

        # =========================
        # Variables
        # =========================
        self.x_start_var = tk.StringVar(value="0")
        self.x_stop_var = tk.StringVar(value="2")
        self.x_step_var = tk.StringVar(value="0.5")

        self.y_start_var = tk.StringVar(value="0")
        self.y_stop_var = tk.StringVar(value="2")
        self.y_step_var = tk.StringVar(value="0.5")

        self.dwell_var = tk.StringVar(value="0.1")
        self.freq_start_mhz_var = tk.StringVar(value="1.0")
        self.freq_stop_mhz_var = tk.StringVar(value="2.0")
        self.freq_step_khz_var = tk.StringVar(value="100")
        self.distance_hydrophone_channel_var = tk.StringVar(value="D")
        self.distance_sound_speed_var = tk.StringVar(value="1500")
        self.distance_threshold_sigma_var = tk.StringVar(value="6")
        self.distance_result_var = tk.StringVar(value="Distance: N/A")
        self.distance_button = None
        self.monitor_status_var = tk.StringVar(value="Idle")
        self.monitor_point_var = tk.StringVar(value="Point: 0 / 0")
        self.monitor_position_var = tk.StringVar(value="Position: ---, --- mm")
        self.monitor_frequency_var = tk.StringVar(value="Freq: 0 / 0")
        self.monitor_eta_var = tk.StringVar(value="ETA: --")
        self.monitor_elapsed_var = tk.StringVar(value="Elapsed: --")
        self.monitor_progress_var = tk.DoubleVar(value=0.0)
        self.readiness_var = tk.StringVar(value="Stage -- | AFG -- | Pico -- | Config -- | Save --")
        self._last_progress_update_id = -1
        # Repeated sampling at one point is temporarily disabled.
        # Keep this variable for restoring repeated captures later if needed.
        # self.trigger_count_var = tk.StringVar(value="1")

        self._build_ui()

    # ============================================================
    # UI
    # ============================================================
    def _build_ui(self):
        for c in range(8):
            self.frame.columnconfigure(c, weight=0)
        self.frame.columnconfigure(6, weight=1)
        self.frame.columnconfigure(7, weight=0, minsize=260)

        row = 0
        ttk.Label(self.frame, text="X0").grid(row=row, column=0, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.x_start_var, width=7).grid(row=row, column=1, padx=2, pady=2)
        ttk.Label(self.frame, text="X1").grid(row=row, column=2, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.x_stop_var, width=7).grid(row=row, column=3, padx=2, pady=2)
        ttk.Label(self.frame, text="dX").grid(row=row, column=4, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.x_step_var, width=7).grid(row=row, column=5, padx=2, pady=2)

        corner_frame = ttk.Frame(self.frame)
        corner_frame.grid(row=0, column=6, rowspan=3, padx=(18, 8), pady=2, sticky="nw")
        ttk.Label(corner_frame, text="🎯 Corners").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(corner_frame, text="LT", width=4, command=lambda: self.test_scan_corner("LT")).grid(row=1, column=0,
                                                                                                       padx=1, pady=1)
        ttk.Button(corner_frame, text="RT", width=4, command=lambda: self.test_scan_corner("RT")).grid(row=1, column=1,
                                                                                                       padx=1, pady=1)
        ttk.Button(corner_frame, text="LD", width=4, command=lambda: self.test_scan_corner("LD")).grid(row=2, column=0,
                                                                                                       padx=1, pady=1)
        ttk.Button(corner_frame, text="RD", width=4, command=lambda: self.test_scan_corner("RD")).grid(row=2, column=1,
                                                                                                       padx=1, pady=1)

        row += 1
        ttk.Label(self.frame, text="Y0").grid(row=row, column=0, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.y_start_var, width=7).grid(row=row, column=1, padx=2, pady=2)
        ttk.Label(self.frame, text="Y1").grid(row=row, column=2, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.y_stop_var, width=7).grid(row=row, column=3, padx=2, pady=2)
        ttk.Label(self.frame, text="dY").grid(row=row, column=4, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.y_step_var, width=7).grid(row=row, column=5, padx=2, pady=2)

        row += 1
        ttk.Label(self.frame, text="Dwell (s)").grid(row=row, column=0, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.dwell_var, width=7).grid(row=row, column=1, padx=2, pady=2)
        freq_frame = ttk.Frame(self.frame)
        freq_frame.grid(row=row, column=2, columnspan=4, padx=2, pady=2, sticky="w")
        ttk.Label(freq_frame, text="Freq MHz").pack(side="left")
        ttk.Entry(freq_frame, textvariable=self.freq_start_mhz_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(freq_frame, text="to").pack(side="left", padx=(4, 0))
        ttk.Entry(freq_frame, textvariable=self.freq_stop_mhz_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(freq_frame, text="step kHz").pack(side="left", padx=(8, 0))
        ttk.Entry(freq_frame, textvariable=self.freq_step_khz_var, width=7).pack(side="left", padx=(4, 0))
        # Repeated sampling at one point is temporarily disabled.
        # trigger_frame = ttk.Frame(self.frame)
        # trigger_frame.grid(row=row, column=2, columnspan=2, padx=2, pady=2, sticky="w")
        # ttk.Label(trigger_frame, text="Trig/point").pack(side="left")
        # ttk.Entry(trigger_frame, textvariable=self.trigger_count_var, width=7).pack(side="left", padx=(4, 0))

        row += 1
        dist_frame = ttk.Frame(self.frame)
        dist_frame.grid(row=row, column=0, columnspan=6, padx=2, pady=2, sticky="ew")
        ttk.Label(dist_frame, text="Hydro Ch").pack(side="left")
        ttk.Combobox(
            dist_frame,
            textvariable=self.distance_hydrophone_channel_var,
            values=["A", "B", "C", "D"],
            width=4,
            state="readonly",
        ).pack(side="left", padx=(4, 10))
        ttk.Label(dist_frame, text="c m/s").pack(side="left")
        ttk.Entry(dist_frame, textvariable=self.distance_sound_speed_var, width=8).pack(side="left", padx=(4, 10))
        ttk.Label(dist_frame, text="sigma").pack(side="left")
        ttk.Entry(dist_frame, textvariable=self.distance_threshold_sigma_var, width=5).pack(side="left", padx=(4, 10))
        self.distance_button = ttk.Button(
            dist_frame,
            text="⌁ Estimate Distance",
            command=self.estimate_hydrophone_distance,
            state="disabled",
        )
        self.distance_button.pack(side="left", padx=(0, 10))
        ttk.Label(dist_frame, textvariable=self.distance_result_var).pack(side="left")

        monitor_frame = ttk.LabelFrame(self.frame, text="📈 Scan Monitor", padding=6)
        monitor_frame.grid(row=0, column=7, rowspan=6, padx=(12, 2), pady=2, sticky="nsew")
        monitor_frame.columnconfigure(0, weight=1)
        ttk.Label(monitor_frame, textvariable=self.monitor_status_var).grid(row=0, column=0, sticky="w", pady=(0, 2))
        ttk.Label(monitor_frame, textvariable=self.monitor_position_var).grid(row=1, column=0, sticky="w", pady=1)
        ttk.Label(monitor_frame, textvariable=self.monitor_point_var).grid(row=2, column=0, sticky="w", pady=1)
        ttk.Label(monitor_frame, textvariable=self.monitor_frequency_var).grid(row=3, column=0, sticky="w", pady=1)
        ttk.Progressbar(
            monitor_frame,
            variable=self.monitor_progress_var,
            maximum=100.0,
            mode="determinate",
            length=220,
        ).grid(row=4, column=0, sticky="w", pady=(4, 2))
        ttk.Label(monitor_frame, textvariable=self.monitor_elapsed_var).grid(row=5, column=0, sticky="w", pady=1)
        ttk.Label(monitor_frame, textvariable=self.monitor_eta_var).grid(row=6, column=0, sticky="w", pady=1)

        assist_frame = ttk.LabelFrame(self.frame, text="✅ Readiness / XY Preview", padding=6)
        assist_frame.grid(row=3, column=6, rowspan=3, padx=(18, 8), pady=2, sticky="nsew")
        assist_frame.columnconfigure(0, weight=1)
        ttk.Label(assist_frame, textvariable=self.readiness_var).grid(row=0, column=0, sticky="w")
        ttk.Button(
            assist_frame,
            text="📂 Open Save Folder",
            command=self.open_save_folder,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 5))
        self.preview_canvas = tk.Canvas(
            assist_frame,
            width=250,
            height=92,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#b7c6d8",
        )
        self.preview_canvas.grid(row=2, column=0, sticky="ew")

        row += 1
        ttk.Button(self.frame, text="▶ Start Scan", command=self.start_scan).grid(row=row, column=2, padx=4, pady=5,
                                                                                sticky="ew")
        ttk.Button(self.frame, text="■ Stop Scan", command=self.stop_scan).grid(row=row, column=3, padx=4, pady=5,
                                                                              sticky="ew")
        ttk.Label(self.frame, text="Path: X+ / return / Y+").grid(row=row, column=4, columnspan=2, padx=4, pady=5,
                                                                  sticky="w")

        row += 1
        ttk.Label(
            self.frame,
            text="Stage must already be at (X0, Y0) before Start.",
        ).grid(row=row, column=0, columnspan=6, padx=2, pady=(2, 0), sticky="w")
        self.frame.after(500, self._refresh_scan_monitor)
        self.frame.after(800, self._refresh_scan_helpers)

    # ============================================================
    # Helpers
    # ============================================================
    def _get_float(self, var, name):
        try:
            return float(var.get().strip())
        except Exception:
            raise ValueError(f"Invalid value for {name}")

    def _get_int(self, var, name):
        text = var.get().strip()
        try:
            value = int(text)
        except Exception:
            raise ValueError(f"Invalid value for {name}: must be an integer")
        if str(value) != text:
            raise ValueError(f"Invalid value for {name}: must be an integer")
        return value

    def _build_frequency_list_hz(self):
        freq_start_mhz = self._get_float(self.freq_start_mhz_var, "Freq Start MHz")
        freq_stop_mhz = self._get_float(self.freq_stop_mhz_var, "Freq Stop MHz")
        freq_step_khz = self._get_float(self.freq_step_khz_var, "Freq Step kHz")

        if freq_start_mhz <= 0:
            raise ValueError("Freq Start must be positive.")
        if freq_stop_mhz < freq_start_mhz:
            raise ValueError("Freq Stop must be >= Freq Start.")
        if freq_step_khz <= 0:
            raise ValueError("Freq Step must be positive.")

        start_hz = freq_start_mhz * 1e6
        stop_hz = freq_stop_mhz * 1e6
        step_hz = freq_step_khz * 1e3
        frequencies_hz = np.arange(start_hz, stop_hz + step_hz * 1e-9, step_hz, dtype=float)

        if len(frequencies_hz) == 0:
            raise ValueError("Frequency list is empty.")
        return frequencies_hz

    def _format_duration(self, seconds):
        if seconds is None:
            return "--"
        try:
            seconds = max(0.0, float(seconds))
        except Exception:
            return "--"
        if seconds < 60:
            return f"{seconds:.0f} s"
        minutes, sec = divmod(int(round(seconds)), 60)
        if minutes < 60:
            return f"{minutes:d} min {sec:02d} s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours:d} h {minutes:02d} min"

    def _preview_grid_values(self):
        x_start = self._get_float(self.x_start_var, "X Start")
        x_stop = self._get_float(self.x_stop_var, "X Stop")
        x_step = self._get_float(self.x_step_var, "X Step")
        y_start = self._get_float(self.y_start_var, "Y Start")
        y_stop = self._get_float(self.y_stop_var, "Y Stop")
        y_step = self._get_float(self.y_step_var, "Y Step")
        if x_step <= 0 or y_step <= 0:
            raise ValueError("Step must be positive")
        if x_stop < x_start or y_stop < y_start:
            raise ValueError("Stop must be >= start")
        xs = np.arange(x_start, x_stop + 0.5 * x_step, x_step, dtype=float)
        ys = np.arange(y_start, y_stop + 0.5 * y_step, y_step, dtype=float)
        return xs, ys

    def _readiness_text(self):
        stage_ok = self.ctx.stage is not None and getattr(self.ctx, "stage_connected", False)
        afg_ok = self.ctx.afg is not None and getattr(self.ctx, "afg_connected", False)
        pico_ok = False
        config_ok = False
        save_ok = False
        try:
            pico_ok = self.ctx.pico is not None and self.ctx.pico.is_connected()
            config_ok = pico_ok and self.ctx.pico.is_configured()
            save_ok = pico_ok and bool(getattr(self.ctx.pico, "save_dir", None))
        except Exception:
            pass

        def mark(value):
            return "OK" if value else "--"

        return (
            f"Stage {mark(stage_ok)} | AFG {mark(afg_ok)} | Pico {mark(pico_ok)} | "
            f"Config {mark(config_ok)} | Save {mark(save_ok)}"
        )

    def _draw_preview_grid(self, xs, ys):
        canvas = self.preview_canvas
        canvas.delete("all")
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        pad = 14
        nx = len(xs)
        ny = len(ys)
        if nx == 0 or ny == 0:
            canvas.create_text(width / 2, height / 2, text="Invalid grid", fill="#536579")
            return

        progress = getattr(self.ctx, "scan_progress", {}) or {}
        current_point = int(progress.get("current_point_index", 0) or 0)
        completed_points = int(progress.get("completed_points", 0) or 0)
        status = str(progress.get("status", "idle")).lower()
        plot_w = max(1, width - 2 * pad)
        plot_h = max(1, height - 2 * pad)
        dense_grid = nx * ny > 400 or min(
            plot_w / max(1, nx),
            plot_h / max(1, ny),
        ) < 5

        for row_idx in range(ny):
            for col_idx in range(nx):
                point_index = row_idx * nx + col_idx + 1
                x_px = width / 2 if nx == 1 else pad + col_idx * (width - 2 * pad) / (nx - 1)
                y_px = height / 2 if ny == 1 else height - pad - row_idx * (height - 2 * pad) / (ny - 1)

                if dense_grid:
                    cell_w = max(1.0, plot_w / max(1, nx))
                    cell_h = max(1.0, plot_h / max(1, ny))
                    fill = "#dbe6f0"
                    outline = ""
                    if point_index <= completed_points:
                        fill = "#8fcf8a"
                    if status == "running" and point_index == current_point:
                        fill = "#f4b84a"
                        outline = "#9a6400"
                    canvas.create_rectangle(
                        x_px - cell_w * 0.45,
                        y_px - cell_h * 0.45,
                        x_px + cell_w * 0.45,
                        y_px + cell_h * 0.45,
                        fill=fill,
                        outline=outline,
                    )
                else:
                    fill = "#ffffff"
                    outline = "#8da3bb"
                    spacing = min(
                        plot_w / max(1, nx - 1) if nx > 1 else plot_w,
                        plot_h / max(1, ny - 1) if ny > 1 else plot_h,
                    )
                    radius = max(2.0, min(4.0, spacing * 0.20))
                    if point_index <= completed_points:
                        fill = "#7fbf7b"
                        outline = "#4f8f4a"
                    if status == "running" and point_index == current_point:
                        fill = "#f4b84a"
                        outline = "#b27600"
                        radius = min(5.0, radius + 1.5)
                    canvas.create_oval(
                        x_px - radius,
                        y_px - radius,
                        x_px + radius,
                        y_px + radius,
                        fill=fill,
                        outline=outline,
                    )

        canvas.create_text(
            pad,
            height - 4,
            text=f"{nx} x {ny} points",
            anchor="sw",
            fill="#536579",
            font=("Segoe UI", 8),
        )

    def _refresh_scan_helpers(self):
        try:
            self.readiness_var.set(self._readiness_text())
            xs, ys = self._preview_grid_values()
            self._draw_preview_grid(xs, ys)
        except Exception as e:
            self.readiness_var.set(self._readiness_text())
            try:
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(125, 46, text=f"Preview: {e}", fill="#9a3412")
            except Exception:
                pass
        finally:
            self.frame.after(800, self._refresh_scan_helpers)

    def open_save_folder(self):
        try:
            if self.ctx.pico is None:
                raise RuntimeError("PicoScope is not available.")
            save_dir = getattr(self.ctx.pico, "save_dir", None)
            if not save_dir:
                raise RuntimeError("No save folder selected in Pico panel.")
            if not os.path.isdir(save_dir):
                raise RuntimeError(f"Save folder does not exist: {save_dir}")
            os.startfile(save_dir)
        except Exception as e:
            self.log(f"Open save folder failed: {e}")
            try:
                messagebox.showerror("Open Save Folder", str(e))
            except Exception:
                pass

    def _refresh_scan_monitor(self):
        try:
            update_id = getattr(self.ctx, "scan_progress_update_id", 0)
            progress = getattr(self.ctx, "scan_progress", {}) or {}
            if update_id != self._last_progress_update_id:
                self._last_progress_update_id = update_id
                status = str(progress.get("status", "idle")).title()
                message = str(progress.get("message", "Idle"))
                current_x = progress.get("current_x_mm")
                current_y = progress.get("current_y_mm")
                current_point = int(progress.get("current_point_index", 0) or 0)
                completed_points = int(progress.get("completed_points", 0) or 0)
                total_points = int(progress.get("total_points", 0) or 0)
                completed_captures = int(progress.get("completed_captures", 0) or 0)
                total_captures = int(progress.get("total_captures", 0) or 0)
                freq_index = int(progress.get("current_frequency_index", 0) or 0)
                freq_count = int(progress.get("frequency_count", 0) or 0)

                if current_x is None or current_y is None:
                    self.monitor_position_var.set("Position: ---, --- mm")
                else:
                    self.monitor_position_var.set(
                        f"Position: X={float(current_x):.3f} mm, Y={float(current_y):.3f} mm"
                    )

                self.monitor_status_var.set(f"{status}: {message}")
                if total_points > 0:
                    self.monitor_point_var.set(
                        f"Point: {current_point} / {total_points}  (done {completed_points})"
                    )
                else:
                    self.monitor_point_var.set("Point: 0 / 0")
                self.monitor_frequency_var.set(f"Freq: {freq_index} / {freq_count}")
                self.monitor_elapsed_var.set(
                    f"Elapsed: {self._format_duration(progress.get('elapsed_s'))}"
                )
                self.monitor_eta_var.set(
                    f"ETA: {self._format_duration(progress.get('eta_s'))}"
                )

                percent = 0.0
                if total_captures > 0:
                    percent = 100.0 * completed_captures / total_captures
                elif total_points > 0:
                    percent = 100.0 * completed_points / total_points
                self.monitor_progress_var.set(max(0.0, min(100.0, percent)))
        except Exception as e:
            self.monitor_status_var.set(f"Monitor error: {e}")
        finally:
            self.frame.after(500, self._refresh_scan_monitor)

    def set_distance_ready(self, ready):
        if self.distance_button is not None:
            self.distance_button.configure(state="normal" if ready else "disabled")
        if not ready:
            self.distance_result_var.set("Distance: N/A")

    def _baseline_mask(self, time_s, end_s=None):
        time_s = np.asarray(time_s, dtype=float)
        if end_s is not None:
            mask = time_s < float(end_s)
            if np.count_nonzero(mask) >= 10:
                return mask

        n = len(time_s)
        count = max(10, int(0.10 * n))
        count = min(count, n)
        mask = np.zeros(n, dtype=bool)
        mask[:count] = True
        return mask

    def _robust_noise_level(self, signal, mask):
        values = np.asarray(signal, dtype=float)[mask]
        if values.size < 2:
            values = np.asarray(signal, dtype=float)
        center = float(np.median(values))
        mad = float(np.median(np.abs(values - center)))
        sigma = 1.4826 * mad
        if sigma <= 0:
            sigma = float(np.std(values))
        if sigma <= 0:
            sigma = 1e-15
        return center, sigma

    def _find_onset(self, time_s, signal, noise_mask, search_mask, sigma_factor, min_consecutive=3):
        time_s = np.asarray(time_s, dtype=float)
        signal = np.asarray(signal, dtype=float).reshape(-1)
        center, sigma = self._robust_noise_level(signal, noise_mask)
        threshold = float(sigma_factor) * sigma
        above = np.abs(signal - center) >= threshold
        above &= np.asarray(search_mask, dtype=bool)

        run = 0
        for idx, flag in enumerate(above):
            if flag:
                run += 1
                if run >= min_consecutive:
                    return int(idx - min_consecutive + 1), center, sigma, threshold
            else:
                run = 0

        raise RuntimeError("No onset found above threshold")

    def _get_last_capture_signal(self, channel):
        signals_v = getattr(self.ctx, "last_pico_signals", None)
        if signals_v is None:
            raise RuntimeError("Please run Capture Test first.")
        if channel not in signals_v:
            raise RuntimeError(
                f"Channel {channel} is not available in the last Capture Test. "
                f"Available channels: {list(signals_v.keys())}"
            )
        signal = np.asarray(signals_v[channel], dtype=float)
        if signal.ndim == 2:
            signal = signal[-1]
        return signal.reshape(-1)

    def estimate_hydrophone_distance(self):
        try:
            time_s = getattr(self.ctx, "last_pico_time", None)
            meta = getattr(self.ctx, "last_pico_meta", None) or {}
            if time_s is None or getattr(self.ctx, "last_pico_signals", None) is None:
                raise RuntimeError("Please run Capture Test first.")

            time_s = np.asarray(time_s, dtype=float).reshape(-1)
            if time_s.size < 10:
                raise RuntimeError("Captured waveform is too short.")

            trigger_ch = str(meta.get("trigger_source", "A")).strip().upper()
            hydro_ch = self.distance_hydrophone_channel_var.get().strip().upper()
            if trigger_ch not in ("A", "B", "C", "D"):
                raise RuntimeError(f"Invalid trigger channel: {trigger_ch}")
            if hydro_ch not in ("A", "B", "C", "D"):
                raise RuntimeError(f"Invalid hydrophone channel: {hydro_ch}")

            sound_speed = float(self.distance_sound_speed_var.get())
            sigma_factor = float(self.distance_threshold_sigma_var.get())
            if sound_speed <= 0:
                raise ValueError("Sound speed must be positive.")
            if sigma_factor <= 0:
                raise ValueError("Threshold sigma must be positive.")

            trigger_signal = self._get_last_capture_signal(trigger_ch)
            hydro_signal = self._get_last_capture_signal(hydro_ch)
            if trigger_signal.size != time_s.size or hydro_signal.size != time_s.size:
                raise RuntimeError("Signal length does not match time axis length.")

            pre_trigger_s = float(meta.get("pre_trigger_us", 0.0)) * 1e-6
            trigger_noise_mask = self._baseline_mask(
                time_s,
                end_s=0.8 * pre_trigger_s if pre_trigger_s > 0 else None,
            )
            trigger_idx, _, trigger_sigma, trigger_threshold = self._find_onset(
                time_s,
                trigger_signal,
                trigger_noise_mask,
                np.ones(time_s.shape, dtype=bool),
                sigma_factor=sigma_factor,
                min_consecutive=3,
            )
            trigger_time_s = float(time_s[trigger_idx])

            hydro_idx, _, hydro_sigma, hydro_threshold = self._find_onset(
                time_s,
                hydro_signal,
                self._baseline_mask(time_s, end_s=trigger_time_s),
                time_s >= trigger_time_s,
                sigma_factor=sigma_factor,
                min_consecutive=3,
            )
            hydro_time_s = float(time_s[hydro_idx])
            delay_s = hydro_time_s - trigger_time_s
            if delay_s < 0:
                raise RuntimeError("Detected hydrophone onset is before trigger onset.")

            distance_mm = delay_s * sound_speed * 1000.0
            self.distance_result_var.set(
                f"Distance: {distance_mm:.3f} mm | dt={delay_s * 1e6:.3f} us"
            )
            self.log(
                "[SCAN] Hydrophone distance estimate: "
                f"trigger={trigger_ch} at {trigger_time_s * 1e6:.3f} us, "
                f"hydro={hydro_ch} at {hydro_time_s * 1e6:.3f} us, "
                f"dt={delay_s * 1e6:.3f} us, "
                f"distance={distance_mm:.3f} mm, "
                f"trigger_noise_sigma={trigger_sigma:.3g}, trigger_threshold={trigger_threshold:.3g}, "
                f"hydro_noise_sigma={hydro_sigma:.3g}, hydro_threshold={hydro_threshold:.3g}"
            )
            self._mark_distance_on_plot(trigger_ch, hydro_ch, trigger_time_s, hydro_time_s)

        except Exception as e:
            self.log(f"[SCAN] Estimate distance failed: {e}")
            try:
                messagebox.showerror("Distance Estimate Error", str(e))
            except Exception:
                pass

    def _mark_distance_on_plot(self, trigger_ch, hydro_ch, trigger_time_s, hydro_time_s):
        pico_panel = getattr(self.ctx, "pico_panel", None)
        if pico_panel is None or not hasattr(pico_panel, "axes_map"):
            return

        trigger_us = trigger_time_s * 1e6
        hydro_us = hydro_time_s * 1e6
        delay_us = hydro_us - trigger_us
        for ch, t_us, color, label in (
            (trigger_ch, trigger_us, "tab:orange", "trigger onset"),
            (hydro_ch, hydro_us, "tab:red", "hydrophone onset"),
        ):
            ax = pico_panel.axes_map.get(ch)
            if ax is None:
                continue
            ax.axvline(t_us, color=color, linestyle="--", linewidth=1.2, label=label)
            y0, y1 = ax.get_ylim()
            y_text = y0 + 0.88 * (y1 - y0)
            ax.text(
                t_us,
                y_text,
                f"{label}\n{t_us:.3f} us",
                color=color,
                fontsize=9,
                rotation=90,
                va="top",
                ha="right",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.65, pad=1.5),
            )
            if ch == hydro_ch:
                ax.text(
                    t_us,
                    y0 + 0.08 * (y1 - y0),
                    f"dt={delay_us:.3f} us",
                    color=color,
                    fontsize=9,
                    va="bottom",
                    ha="left",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.65, pad=1.5),
                )
            try:
                ax.legend(fontsize=8, loc="upper right")
            except Exception:
                pass
        if hasattr(pico_panel, "canvas"):
            pico_panel.canvas.draw_idle()

    # ============================================================
    # Actions
    # ============================================================
    # ===========================================================
    # Test scan corner position
    # ===========================================================
    def test_scan_corner(self, corner: str):
        try:
            if self.ctx.stage is None or not self.ctx.stage.is_connected():
                raise RuntimeError("Stage is not connected.")

            stage = self.ctx.stage

            x_start = self._get_float(self.x_start_var, "X Start")
            x_stop = self._get_float(self.x_stop_var, "X Stop")
            y_start = self._get_float(self.y_start_var, "Y Start")
            y_stop = self._get_float(self.y_stop_var, "Y Stop")

            if x_stop < x_start:
                raise ValueError("X Stop must be >= X Start.")
            if y_stop < y_start:
                raise ValueError("Y Stop must be >= Y Start.")

            # Make sure software/display coordinates are valid
            pos = stage.get_position_mm()
            current_x = pos["axis1"]
            current_y = pos["axis2"]

            if current_x is None or current_y is None:
                raise RuntimeError(
                    "Stage software position is not initialized. "
                    "Please do Home+ & Set Zero for both axes first."
                )

            # Decide target corner
            mapping = {
                "LD": (x_start, y_start),
                "RD": (x_stop, y_start),
                "LT": (x_start, y_stop),
                "RT": (x_stop, y_stop),
            }
            if corner not in mapping:
                raise ValueError(f"Unknown corner: {corner}")

            target_x, target_y = mapping[corner]
            dx = target_x - current_x
            dy = target_y - current_y

            self.log(
                f"Test scan corner -> {corner}: "
                f"current=({current_x:.3f}, {current_y:.3f}) mm, "
                f"target=({target_x:.3f}, {target_y:.3f}) mm, "
                f"move=(dx={dx:.3f}, dy={dy:.3f}) mm"
            )

            # Move X first, then Y
            if abs(dx) > 1e-9:
                stage.move_rel_mm(1, dx)
                stage.wait_until_stop()

            if abs(dy) > 1e-9:
                stage.move_rel_mm(2, dy)
                stage.wait_until_stop()

            # Read updated software/display coordinates
            new_pos = stage.get_position_mm()
            self.log(
                f"Arrived at {corner}: "
                f"stage position = ({new_pos['axis1']:.3f}, {new_pos['axis2']:.3f}) mm"
            )

        except Exception as e:
            self.log(f"Test scan failed: {e}")
            try:
                messagebox.showerror("Test Error", str(e))
            except Exception:
                pass

    # Do the scan
    def start_scan(self):
        try:
            if self.ctx.stage is None:
                raise RuntimeError("Stage is not connected.")
            if self.ctx.afg is None:
                raise RuntimeError("AFG is not connected.")
            if self.ctx.pico is None or not self.ctx.pico.is_connected():
                raise RuntimeError("PicoScope is not connected.")
            if not self.ctx.pico.is_configured():
                raise RuntimeError("PicoScope is not configured. Please click Apply Config first.")

            save_dir = getattr(self.ctx.pico, "save_dir", None)
            if not save_dir:
                raise RuntimeError("Please choose a save folder in Pico panel before starting scan.")
            if not getattr(self.ctx.pico, "save_channels", None):
                raise RuntimeError("No save channels selected. Please apply Pico config first.")

            x_start = self._get_float(self.x_start_var, "X Start")
            x_stop = self._get_float(self.x_stop_var, "X Stop")
            x_step = self._get_float(self.x_step_var, "X Step")

            y_start = self._get_float(self.y_start_var, "Y Start")
            y_stop = self._get_float(self.y_stop_var, "Y Stop")
            y_step = self._get_float(self.y_step_var, "Y Step")

            dwell_s = self._get_float(self.dwell_var, "Dwell")
            frequencies_hz = self._build_frequency_list_hz()
            # Repeated sampling at one point is temporarily disabled.
            # trigger_count = self._get_int(self.trigger_count_var, "Trig/point")

            if x_step <= 0:
                raise ValueError("X Step must be positive.")
            if y_step <= 0:
                raise ValueError("Y Step must be positive.")
            if x_stop < x_start:
                raise ValueError("X Stop must be >= X Start.")
            if y_stop < y_start:
                raise ValueError("Y Stop must be >= Y Start.")
            # Repeated sampling at one point is temporarily disabled.
            # if trigger_count < 1 or trigger_count > 32:
            #     raise ValueError("Trig/point must be an integer from 1 to 32.")

            if self.scan_controller is not None and self.scan_controller.is_running:
                raise RuntimeError("A scan is already running.")

            self.scan_controller = ScanController(
                ctx=self.ctx,
                stage=self.ctx.stage,
                afg=self.ctx.afg,
                pico=self.ctx.pico,
                log_func=self.log,
            )
            # Reset the capture index and signal
            self.ctx.last_pico_time = None
            self.ctx.last_pico_signals = None
            self.ctx.last_pico_meta = None
            self.ctx.last_pico_update_id = 0
            self.ctx.scan_progress = {
                "status": "starting",
                "current_x_mm": x_start,
                "current_y_mm": y_start,
                "current_point_index": 1,
                "completed_points": 0,
                "total_points": 0,
                "completed_captures": 0,
                "total_captures": 0,
                "current_frequency_index": 0,
                "frequency_count": len(frequencies_hz),
                "elapsed_s": 0.0,
                "eta_s": None,
                "message": "Starting scan",
            }
            self.ctx.scan_progress_update_id = getattr(self.ctx, "scan_progress_update_id", 0) + 1
            self.set_distance_ready(False)

            self.log(
                f"[SCAN] Start requested: X {x_start}->{x_stop} step {x_step}; "
                f"Y {y_start}->{y_stop} step {y_step}; dwell={dwell_s}s; "
                f"freq/point={len(frequencies_hz)}; "
                f"freq={frequencies_hz[0] / 1e6:.6f}->{frequencies_hz[-1] / 1e6:.6f} MHz"
            )
            self.log("[SCAN] Make sure AFG trigger source is BUS and burst setup is already applied.")

            self.scan_controller.start_scan_thread(
                x_start=x_start,
                x_stop=x_stop,
                x_step=x_step,
                y_start=y_start,
                y_stop=y_stop,
                y_step=y_step,
                dwell_s=dwell_s,
                frequencies_hz=frequencies_hz,
                verbose=True,
            )
            self.log("Scan thread started.")

        except Exception as e:
            self.log(f"Start scan failed: {e}")
            try:
                messagebox.showerror("Scan Error", str(e))
            except Exception:
                pass

    def stop_scan(self):
        try:
            if self.scan_controller is None:
                self.log("No active scan controller.")
                return

            self.scan_controller.stop()
            self.log("Stop requested.")

        except Exception as e:
            self.log(f"Stop scan failed: {e}")
            try:
                messagebox.showerror("Scan Error", str(e))
            except Exception:
                pass
