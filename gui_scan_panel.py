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
        self.scan_mode_var = tk.StringVar(value="Fixed voltage: sweep frequency")
        self.freq_start_mhz_var = tk.StringVar(value="1.0")
        self.freq_stop_mhz_var = tk.StringVar(value="2.0")
        self.freq_step_khz_var = tk.StringVar(value="100")
        self.voltage_start_vpp_var = tk.StringVar(value="0.1")
        self.voltage_stop_vpp_var = tk.StringVar(value="1.0")
        self.voltage_step_vpp_var = tk.StringVar(value="0.1")
        self.distance_hydrophone_channel_var = tk.StringVar(value="D")
        self.distance_sound_speed_var = tk.StringVar(value="1500")
        self.distance_threshold_sigma_var = tk.StringVar(value="6")
        self.distance_result_var = tk.StringVar(value="Distance: N/A")
        self.distance_button = None
        self.power_voltage_channel_var = tk.StringVar(value="A")
        self.power_current_channel_var = tk.StringVar(value="B")
        self.power_t1_us_var = tk.StringVar(value="0")
        self.power_cycles_var = tk.StringVar(value="20")
        self.power_result_var = tk.StringVar(value="Power: N/A")
        self.power_button = None
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
        for c in range(7):
            self.frame.columnconfigure(c, weight=0)
        self.frame.columnconfigure(6, weight=1, minsize=220)

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
        ttk.Label(self.frame, text="Mode").grid(row=row, column=2, padx=2, pady=2, sticky="w")
        self.scan_mode_combo = ttk.Combobox(
            self.frame,
            textvariable=self.scan_mode_var,
            values=["Fixed voltage: sweep frequency", "Fixed frequency: sweep voltage"],
            width=28,
            state="readonly",
        )
        self.scan_mode_combo.grid(row=row, column=3, columnspan=3, padx=2, pady=2, sticky="ew")
        self.scan_mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_scan_mode_ui())

        row += 1
        self.frequency_sweep_frame = ttk.Frame(self.frame)
        self.frequency_sweep_frame.grid(row=row, column=0, columnspan=6, padx=2, pady=2, sticky="w")
        ttk.Label(self.frequency_sweep_frame, text="Freq MHz").pack(side="left")
        ttk.Entry(self.frequency_sweep_frame, textvariable=self.freq_start_mhz_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(self.frequency_sweep_frame, text="to").pack(side="left", padx=(4, 0))
        ttk.Entry(self.frequency_sweep_frame, textvariable=self.freq_stop_mhz_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(self.frequency_sweep_frame, text="step kHz").pack(side="left", padx=(8, 0))
        ttk.Entry(self.frequency_sweep_frame, textvariable=self.freq_step_khz_var, width=7).pack(side="left", padx=(4, 0))

        self.voltage_sweep_frame = ttk.Frame(self.frame)
        self.voltage_sweep_frame.grid(row=row, column=0, columnspan=6, padx=2, pady=2, sticky="w")
        ttk.Label(self.voltage_sweep_frame, text="Fixed MHz").pack(side="left")
        ttk.Entry(self.voltage_sweep_frame, textvariable=self.freq_start_mhz_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(self.voltage_sweep_frame, text="Vpp").pack(side="left", padx=(10, 0))
        ttk.Entry(self.voltage_sweep_frame, textvariable=self.voltage_start_vpp_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(self.voltage_sweep_frame, text="to").pack(side="left", padx=(4, 0))
        ttk.Entry(self.voltage_sweep_frame, textvariable=self.voltage_stop_vpp_var, width=7).pack(side="left", padx=(4, 0))
        ttk.Label(self.voltage_sweep_frame, text="step").pack(side="left", padx=(8, 0))
        ttk.Entry(self.voltage_sweep_frame, textvariable=self.voltage_step_vpp_var, width=7).pack(side="left", padx=(4, 0))
        self._refresh_scan_mode_ui()
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

        power_frame = ttk.Frame(self.frame)
        power_frame.grid(row=row + 1, column=0, columnspan=6, padx=2, pady=2, sticky="ew")
        ttk.Label(power_frame, text="Power V ch").pack(side="left")
        ttk.Combobox(
            power_frame,
            textvariable=self.power_voltage_channel_var,
            values=["A", "B", "C", "D"],
            width=4,
            state="readonly",
        ).pack(side="left", padx=(4, 8))
        ttk.Label(power_frame, text="I ch").pack(side="left")
        ttk.Combobox(
            power_frame,
            textvariable=self.power_current_channel_var,
            values=["A", "B", "C", "D"],
            width=4,
            state="readonly",
        ).pack(side="left", padx=(4, 8))
        ttk.Label(power_frame, text="t0 us").pack(side="left")
        ttk.Entry(power_frame, textvariable=self.power_t1_us_var, width=6).pack(side="left", padx=(4, 2))
        ttk.Label(power_frame, text="cycles N").pack(side="left")
        ttk.Entry(power_frame, textvariable=self.power_cycles_var, width=5).pack(side="left", padx=(4, 8))
        self.power_button = ttk.Button(
            power_frame,
            text="∫ Calculate Power",
            command=self.calculate_power,
            state="disabled",
        )
        self.power_button.pack(side="left", padx=(0, 10))
        ttk.Label(power_frame, textvariable=self.power_result_var).pack(side="left")

        monitor_frame = ttk.LabelFrame(self.frame, text="📈 Scan Monitor", padding=5)
        monitor_frame.grid(row=8, column=0, columnspan=7, padx=2, pady=(4, 2), sticky="ew")
        monitor_frame.columnconfigure(0, weight=1)

        monitor_top = ttk.Frame(monitor_frame)
        monitor_top.grid(row=0, column=0, sticky="ew")
        ttk.Label(monitor_top, textvariable=self.monitor_status_var).pack(side="left", padx=(0, 12))
        ttk.Label(monitor_top, textvariable=self.monitor_position_var).pack(side="left", padx=(0, 12))
        ttk.Label(monitor_top, textvariable=self.monitor_point_var).pack(side="left", padx=(0, 12))
        ttk.Label(monitor_top, textvariable=self.monitor_frequency_var).pack(side="left", padx=(0, 12))

        ttk.Progressbar(
            monitor_frame,
            variable=self.monitor_progress_var,
            maximum=100.0,
            mode="determinate",
            length=220,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 2))

        monitor_bottom = ttk.Frame(monitor_frame)
        monitor_bottom.grid(row=2, column=0, sticky="ew")
        ttk.Label(monitor_bottom, textvariable=self.monitor_elapsed_var).pack(side="left", padx=(0, 16))
        ttk.Label(monitor_bottom, textvariable=self.monitor_eta_var).pack(side="left")

        assist_frame = ttk.LabelFrame(self.frame, text="✅ Readiness / XY Preview", padding=6)
        assist_frame.grid(row=3, column=6, rowspan=3, padx=(10, 4), pady=2, sticky="nsew")
        assist_frame.columnconfigure(0, weight=1)
        ttk.Label(assist_frame, textvariable=self.readiness_var).grid(row=0, column=0, sticky="w")
        ttk.Button(
            assist_frame,
            text="📂 Open Save Folder",
            command=self.open_save_folder,
        ).grid(row=1, column=0, sticky="ew", pady=(4, 5))
        self.preview_canvas = tk.Canvas(
            assist_frame,
            width=210,
            height=82,
            bg="#ffffff",
            highlightthickness=1,
            highlightbackground="#b7c6d8",
        )
        self.preview_canvas.grid(row=2, column=0, sticky="ew")

        row += 2
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

    def _is_voltage_sweep_mode(self):
        return self.scan_mode_var.get().strip() == "Fixed frequency: sweep voltage"

    def _refresh_scan_mode_ui(self):
        if not hasattr(self, "frequency_sweep_frame") or not hasattr(self, "voltage_sweep_frame"):
            return
        if self._is_voltage_sweep_mode():
            self.frequency_sweep_frame.grid_remove()
            self.voltage_sweep_frame.grid()
        else:
            self.voltage_sweep_frame.grid_remove()
            self.frequency_sweep_frame.grid()

    def _build_voltage_list_vpp(self):
        voltage_start = self._get_float(self.voltage_start_vpp_var, "Voltage Start Vpp")
        voltage_stop = self._get_float(self.voltage_stop_vpp_var, "Voltage Stop Vpp")
        voltage_step = self._get_float(self.voltage_step_vpp_var, "Voltage Step Vpp")

        if voltage_start <= 0:
            raise ValueError("Voltage Start must be positive.")
        if voltage_stop < voltage_start:
            raise ValueError("Voltage Stop must be >= Voltage Start.")
        if voltage_step <= 0:
            raise ValueError("Voltage Step must be positive.")

        voltages = np.arange(voltage_start, voltage_stop + voltage_step * 1e-9, voltage_step, dtype=float)
        if len(voltages) == 0:
            raise ValueError("Voltage list is empty.")
        return voltages

    def _build_excitation_lists(self):
        if self._is_voltage_sweep_mode():
            fixed_freq_mhz = self._get_float(self.freq_start_mhz_var, "Fixed Freq MHz")
            if fixed_freq_mhz <= 0:
                raise ValueError("Fixed Freq MHz must be positive.")
            amplitudes_vpp = self._build_voltage_list_vpp()
            frequencies_hz = np.full(len(amplitudes_vpp), fixed_freq_mhz * 1e6, dtype=float)
            return "voltage_sweep", frequencies_hz, amplitudes_vpp

        frequencies_hz = self._build_frequency_list_hz()
        return "frequency_sweep", frequencies_hz, None

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
            self._refresh_power_button_state()
            xs, ys = self._preview_grid_values()
            self._draw_preview_grid(xs, ys)
        except Exception as e:
            self.readiness_var.set(self._readiness_text())
            self._refresh_power_button_state()
            try:
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(125, 46, text=f"Preview: {e}", fill="#9a3412")
            except Exception:
                pass
        finally:
            self.frame.after(800, self._refresh_scan_helpers)

    def _power_channels_ready(self):
        signals_v = getattr(self.ctx, "last_pico_signals", None)
        if not isinstance(signals_v, dict):
            return False
        v_ch = self.power_voltage_channel_var.get().strip().upper()
        i_ch = self.power_current_channel_var.get().strip().upper()
        return v_ch in signals_v and i_ch in signals_v

    def _refresh_power_button_state(self):
        ready = self._power_channels_ready()
        if self.power_button is not None:
            self.power_button.configure(state="normal" if ready else "disabled")
        if not ready:
            self.power_result_var.set("Power: N/A")

    def _estimate_frequency_hz_from_signal(self, time_s, signal):
        t = np.asarray(time_s, dtype=float).reshape(-1)
        y = np.asarray(signal, dtype=float).reshape(-1)
        if len(t) != len(y) or len(t) < 4:
            raise RuntimeError("Not enough samples to estimate frequency.")

        dt = float(np.median(np.diff(t)))
        if dt <= 0:
            raise RuntimeError("Invalid time axis for frequency estimation.")

        y = y - float(np.mean(y))
        if not np.any(np.isfinite(y)) or float(np.max(np.abs(y))) <= 0:
            raise RuntimeError("Signal is too small to estimate frequency.")

        window = np.hanning(len(y))
        spectrum = np.abs(np.fft.rfft(y * window))
        freqs = np.fft.rfftfreq(len(y), d=dt)
        if len(spectrum) < 3:
            raise RuntimeError("FFT result is too short to estimate frequency.")

        spectrum[0] = 0.0
        idx = int(np.argmax(spectrum))
        if idx <= 0 or spectrum[idx] <= 0:
            raise RuntimeError("No dominant frequency peak found.")

        # Parabolic interpolation around the FFT peak gives a better estimate
        # than the raw frequency-bin spacing for short capture windows.
        if 0 < idx < len(spectrum) - 1:
            left = float(spectrum[idx - 1])
            center = float(spectrum[idx])
            right = float(spectrum[idx + 1])
            denom = left - 2.0 * center + right
            if abs(denom) > 1e-30:
                idx = idx + 0.5 * (left - right) / denom

        bin_hz = freqs[1] - freqs[0]
        frequency_hz = float(idx * bin_hz)
        if frequency_hz <= 0:
            raise RuntimeError("Estimated frequency is not positive.")
        return frequency_hz

    def _get_power_frequency_hz(self, time_s=None, signal=None):
        meta = getattr(self.ctx, "last_pico_meta", None) or {}

        freqs = meta.get("excitation_frequencies_hz")
        if freqs is not None:
            freqs = np.asarray(freqs, dtype=float).reshape(-1)
            if len(freqs) > 0 and freqs[-1] > 0:
                return float(freqs[-1])

        for key in ("excitation_frequency_hz", "frequency_hz", "afg_frequency_hz"):
            value = meta.get(key)
            if value is not None:
                value = float(np.asarray(value).reshape(-1)[0])
                if value > 0:
                    return value

        if time_s is not None and signal is not None:
            try:
                return self._estimate_frequency_hz_from_signal(time_s, signal)
            except Exception as e:
                self.log(f"[SCAN] FFT frequency estimate failed: {e}")

        try:
            if self.ctx.afg is not None:
                freq = float(self.ctx.afg.query(f"SOURce{self.ctx.afg.channel}:FREQuency:FIXed?"))
                if freq > 0:
                    return freq
        except Exception:
            pass

        return self._get_float(self.freq_start_mhz_var, "Freq MHz") * 1e6

    def calculate_power(self):
        try:
            time_s = getattr(self.ctx, "last_pico_time", None)
            signals_v = getattr(self.ctx, "last_pico_signals", None)
            if time_s is None or not isinstance(signals_v, dict):
                raise RuntimeError("Please run Capture Test first.")

            v_ch = self.power_voltage_channel_var.get().strip().upper()
            i_ch = self.power_current_channel_var.get().strip().upper()
            if v_ch not in signals_v:
                raise RuntimeError(f"Voltage channel {v_ch} is not available in the last capture.")
            if i_ch not in signals_v:
                raise RuntimeError(f"Current channel {i_ch} is not available in the last capture.")

            t = np.asarray(time_s, dtype=float).reshape(-1)
            voltage = np.asarray(signals_v[v_ch], dtype=float)
            current = np.asarray(signals_v[i_ch], dtype=float)
            if voltage.ndim == 2:
                voltage = voltage[-1]
            if current.ndim == 2:
                current = current[-1]
            voltage = voltage.reshape(-1)
            current = current.reshape(-1)

            if len(t) != len(voltage) or len(t) != len(current):
                raise RuntimeError("Voltage/current signal length does not match time axis.")

            t1_s = float(self.power_t1_us_var.get()) * 1e-6
            cycles = int(float(self.power_cycles_var.get()))
            if cycles < 1:
                raise ValueError("Power integration cycles N must be >= 1.")
            frequency_hz = self._get_power_frequency_hz(time_s=t, signal=voltage)
            if frequency_hz <= 0:
                raise ValueError("Cannot determine excitation frequency for cycle-based integration.")
            period_s = 1.0 / frequency_hz
            t2_s = t1_s + cycles * period_s
            if t1_s < t[0] or t2_s > t[-1]:
                raise RuntimeError(
                    f"Power integration window {t1_s * 1e6:.3f}-{t2_s * 1e6:.3f} us "
                    f"is outside captured range {t[0] * 1e6:.3f}-{t[-1] * 1e6:.3f} us."
                )

            mask = (t >= t1_s) & (t <= t2_s)
            if np.count_nonzero(mask) < 1:
                raise RuntimeError("Power integration window contains no samples.")

            voltage_offset = float(np.mean(voltage[mask]))
            current_offset = float(np.mean(current[mask]))
            voltage = voltage - voltage_offset
            current = current - current_offset

            inner_t = t[mask]
            t_gate = np.unique(np.concatenate(([t1_s], inner_t, [t2_s]))).astype(float)
            # Fixed probe conversions:
            # voltage channel: measured scope voltage * 10 = actual drive voltage.
            # current probe: 5 mV / mA = 0.005 V / mA, so I[A] = V_scope / 5.
            v_gate = np.interp(t_gate, t, voltage) * 10.0
            i_gate = np.interp(t_gate, t, current) / 5.0
            p_inst = v_gate * i_gate
            energy_j = float(np.trapz(p_inst, t_gate))
            avg_power_w = energy_j / float(t2_s - t1_s)
            vrms = float(np.sqrt(np.mean(v_gate ** 2)))
            irms = float(np.sqrt(np.mean(i_gate ** 2)))
            p_peak_w = float(np.max(np.abs(p_inst)))

            self.power_result_var.set(
                f"Pavg={avg_power_w:.4g} W | E={energy_j:.4g} J | {cycles}T"
            )
            self.log(
                "[SCAN] Electrical power estimate: "
                f"Vch={v_ch}, Ich={i_ch}, "
                f"f={frequency_hz / 1e6:.6f} MHz, cycles={cycles}, "
                f"window={t1_s * 1e6:.3f}-{t2_s * 1e6:.3f} us, "
                f"Voffset={voltage_offset:.6g} V, Ioffset={current_offset:.6g} V(scope), "
                f"Pavg={avg_power_w:.6g} W, E={energy_j:.6g} J, "
                f"Vrms={vrms:.6g} V, Irms={irms:.6g} A, Ppeak_abs={p_peak_w:.6g} W"
            )

        except Exception as e:
            self.log(f"[SCAN] Calculate power failed: {e}")
            try:
                messagebox.showerror("Power Calculation Error", str(e))
            except Exception:
                pass

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
                mode = str(progress.get("scan_mode", "frequency_sweep"))
                label = "V step" if mode == "voltage_sweep" else "Freq"
                self.monitor_frequency_var.set(f"{label}: {freq_index} / {freq_count}")
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
            scan_mode, frequencies_hz, amplitudes_vpp = self._build_excitation_lists()
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
                "scan_mode": scan_mode,
                "elapsed_s": 0.0,
                "eta_s": None,
                "message": "Starting scan",
            }
            self.ctx.scan_progress_update_id = getattr(self.ctx, "scan_progress_update_id", 0) + 1
            self.set_distance_ready(False)

            if amplitudes_vpp is None:
                sweep_text = (
                    f"mode=fixed voltage / sweep frequency; freq/point={len(frequencies_hz)}; "
                    f"freq={frequencies_hz[0] / 1e6:.6f}->{frequencies_hz[-1] / 1e6:.6f} MHz"
                )
            else:
                sweep_text = (
                    f"mode=fixed frequency / sweep voltage; voltage/point={len(amplitudes_vpp)}; "
                    f"freq={frequencies_hz[0] / 1e6:.6f} MHz; "
                    f"Vpp={amplitudes_vpp[0]:.6g}->{amplitudes_vpp[-1]:.6g}"
                )
            self.log(
                f"[SCAN] Start requested: X {x_start}->{x_stop} step {x_step}; "
                f"Y {y_start}->{y_stop} step {y_step}; dwell={dwell_s}s; {sweep_text}"
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
                amplitudes_vpp=amplitudes_vpp,
                scan_mode=scan_mode,
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
