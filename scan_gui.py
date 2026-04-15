import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

from stage_controller import GSC02CStage


class ScanGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Scanning Field Control Panel")
        self.root.geometry("1100x760")

        self.stage = None
        self.stage_connected = False
        self.stage_busy = False
        self.scan_stop_requested = False

        self._build_variables()
        self._build_layout()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ============================================================
    # Variables
    # ============================================================
    def _build_variables(self):
        # Stage
        self.stage_port_var = tk.StringVar(value="COM5")
        self.axis_var = tk.IntVar(value=1)

        self.move_rel_mm_var = tk.StringVar(value="5.0")

        self.slow_var = tk.StringVar(value="200")
        self.fast_var = tk.StringVar(value="800")
        self.rate_var = tk.StringVar(value="80")

        self.status_var = tk.StringVar(value="Not connected")
        self.pos1_var = tk.StringVar(value="Axis1: --- mm (not initialized)")
        self.pos2_var = tk.StringVar(value="Axis2: --- mm (not initialized)")

        # AFG placeholders
        self.afg_resource_var = tk.StringVar(value="GPIB0::11::INSTR")
        self.afg_freq_var = tk.StringVar(value="2000000")
        self.afg_vpp_var = tk.StringVar(value="2.0")
        self.afg_cycles_var = tk.StringVar(value="10")

        # Pico placeholders
        self.pico_channel_var = tk.StringVar(value="A")
        self.pico_range_var = tk.StringVar(value="PS5000A_5V")
        self.pico_pre_var = tk.StringVar(value="500")
        self.pico_post_var = tk.StringVar(value="1500")

        # Scan panel
        self.x_start_var = tk.StringVar(value="0")
        self.x_stop_var = tk.StringVar(value="2")
        self.x_step_var = tk.StringVar(value="0.1")

        self.y_start_var = tk.StringVar(value="0")
        self.y_stop_var = tk.StringVar(value="2")
        self.y_step_var = tk.StringVar(value="0.1")

        self.scan_dwell_var = tk.StringVar(value="1.0")

    # ============================================================
    # Layout
    # ============================================================
    def _build_layout(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)

        self._build_stage_frame(left)
        self._build_log_frame(left)

        self._build_afg_placeholder(right)
        self._build_pico_placeholder(right)
        self._build_scan_panel(right)

    def _build_stage_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Stage Control", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="COM Port").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.stage_port_var, width=12).grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(frame, text="Connect", command=self.connect_stage).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(frame, text="Disconnect", command=self.disconnect_stage).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Axis").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Radiobutton(frame, text="Axis 1", variable=self.axis_var, value=1).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        ttk.Radiobutton(frame, text="Axis 2", variable=self.axis_var, value=2).grid(row=1, column=2, sticky="w", padx=5, pady=5)

        ttk.Label(frame, text="Relative Move (mm)").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.move_rel_mm_var, width=12).grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(frame, text="Move +", command=self.move_rel_positive).grid(row=2, column=2, padx=5, pady=5)
        ttk.Button(frame, text="Move -", command=self.move_rel_negative).grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(
            frame,
            text="Minimum command step: 0.001 mm",
            foreground="gray"
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

        ttk.Label(frame, text="Slow").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.slow_var, width=10).grid(row=4, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(frame, text="Fast").grid(row=4, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.fast_var, width=10).grid(row=4, column=3, sticky="w", padx=5, pady=5)

        ttk.Label(frame, text="Rate").grid(row=4, column=4, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.rate_var, width=10).grid(row=4, column=5, sticky="w", padx=5, pady=5)

        ttk.Button(frame, text="Set Speed Axis1", command=lambda: self.set_speed(1)).grid(row=5, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Set Speed Axis2", command=lambda: self.set_speed(2)).grid(row=5, column=2, padx=5, pady=5)

        ttk.Button(frame, text="Home+ & Set Zero", command=self.home_plus_set_zero).grid(row=6, column=0, padx=5, pady=5)
        ttk.Button(frame, text="Home-", command=self.home_minus).grid(row=6, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Stop", command=self.stop_stage).grid(row=6, column=2, padx=5, pady=5)
        ttk.Button(frame, text="Refresh Status", command=self.refresh_status).grid(row=6, column=3, padx=5, pady=5)

        ttk.Button(frame, text="Set Current as Zero", command=self.set_current_as_zero).grid(row=7, column=0, padx=5, pady=5)
        ttk.Button(frame, text="Clear Zero", command=self.clear_zero).grid(row=7, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Controller Status").grid(row=8, column=0, sticky="w", padx=5, pady=5)
        ttk.Label(frame, textvariable=self.status_var, width=58).grid(row=8, column=1, columnspan=5, sticky="w", padx=5, pady=5)

        ttk.Label(frame, textvariable=self.pos1_var).grid(row=9, column=0, columnspan=3, sticky="w", padx=5, pady=5)
        ttk.Label(frame, textvariable=self.pos2_var).grid(row=9, column=3, columnspan=3, sticky="w", padx=5, pady=5)

    def _build_afg_placeholder(self, parent):
        frame = ttk.LabelFrame(parent, text="Signal Generator (Reserved)", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Resource").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.afg_resource_var, width=22).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Frequency (Hz)").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.afg_freq_var, width=15).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Vpp").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.afg_vpp_var, width=10).grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Cycles").grid(row=1, column=4, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.afg_cycles_var, width=10).grid(row=1, column=5, padx=5, pady=5)

        ttk.Button(frame, text="Connect AFG", state="disabled").grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Configure Burst", state="disabled").grid(row=2, column=2, padx=5, pady=5)
        ttk.Button(frame, text="Trigger Test", state="disabled").grid(row=2, column=3, padx=5, pady=5)

    def _build_pico_placeholder(self, parent):
        frame = ttk.LabelFrame(parent, text="PicoScope (Reserved)", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Channel").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.pico_channel_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Range").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.pico_range_var, width=15).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Pre Samples").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.pico_pre_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Post Samples").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.pico_post_var, width=10).grid(row=1, column=3, padx=5, pady=5)

        ttk.Button(frame, text="Connect Pico", state="disabled").grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Acquire Test", state="disabled").grid(row=2, column=2, padx=5, pady=5)

    def _build_scan_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Scan Panel", padding=10)
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="X Start (mm)").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.x_start_var, width=10).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(frame, text="X Stop (mm)").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.x_stop_var, width=10).grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(frame, text="X Step (mm)").grid(row=0, column=4, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.x_step_var, width=10).grid(row=0, column=5, padx=5, pady=5)

        ttk.Label(frame, text="Y Start (mm)").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.y_start_var, width=10).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(frame, text="Y Stop (mm)").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.y_stop_var, width=10).grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(frame, text="Y Step (mm)").grid(row=1, column=4, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.y_step_var, width=10).grid(row=1, column=5, padx=5, pady=5)

        ttk.Label(frame, text="Dwell per point (s)").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(frame, textvariable=self.scan_dwell_var, width=10).grid(row=2, column=1, padx=5, pady=5)

        ttk.Button(frame, text="Start Empty Scan", command=self.start_empty_scan).grid(row=3, column=2, padx=5, pady=8)
        ttk.Button(frame, text="Stop Scan", command=self.stop_empty_scan).grid(row=3, column=3, padx=5, pady=8)

        ttk.Label(
            frame,
            text="No trigger, no acquisition. Stage-only scan with 1 s dwell is supported.",
            foreground="gray"
        ).grid(row=4, column=0, columnspan=6, sticky="w", padx=5, pady=(2, 0))

    def _build_log_frame(self, parent):
        frame = ttk.LabelFrame(parent, text="Log", padding=10)
        frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(frame, width=55, height=22)
        self.log_text.pack(fill="both", expand=True)

    # ============================================================
    # Logging
    # ============================================================
    def log(self, msg):
        now = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{now}] {msg}\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    # ============================================================
    # Helpers
    # ============================================================
    def _require_stage(self):
        if not self.stage_connected or self.stage is None:
            messagebox.showwarning("Warning", "Stage is not connected.")
            return False
        return True

    def _run_in_thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _axis_initialized(self, axis: int) -> bool:
        pos = self.stage.get_position_mm()
        return pos[f"axis{axis}"] is not None

    def _sleep_with_stop_check(self, seconds: float) -> bool:
        t0 = time.time()
        while time.time() - t0 < seconds:
            if self.scan_stop_requested:
                return False
            time.sleep(0.05)
        return True

    def _frange_inclusive(self, start: float, stop: float, step: float):
        values = []
        if step <= 0:
            raise ValueError("Step must be positive.")

        if stop >= start:
            x = start
            while x <= stop + 1e-12:
                values.append(round(x, 10))
                x += step
        else:
            x = start
            while x >= stop - 1e-12:
                values.append(round(x, 10))
                x -= step

        return values

    def _move_axis_to(self, axis: int, target_mm: float):
        pos = self.stage.get_position_mm()[f"axis{axis}"]
        if pos is None:
            raise RuntimeError(f"Axis {axis} is not initialized. Please run Home+ & Set Zero first.")
        delta = target_mm - pos
        if abs(delta) > 1e-12:
            self.stage.move_rel_mm(axis=axis, mm=delta)
            self.stage.wait_until_stop(verbose=False)

    def _move_to_xy(self, x_mm: float, y_mm: float):
        self._move_axis_to(2, y_mm)
        self._move_axis_to(1, x_mm)

    # ============================================================
    # Stage actions
    # ============================================================
    def connect_stage(self):
        if self.stage_connected:
            self.log("Stage already connected.")
            return

        port = self.stage_port_var.get().strip()

        try:
            if self.stage is not None:
                try:
                    self.stage.close()
                except Exception:
                    pass
                self.stage = None

            self.stage = GSC02CStage(port=port)
            self.stage.connect()
            self.stage_connected = True
            self.stage_busy = False
            self.status_var.set("Connected")
            self.log(f"Stage connected on {port}")
            self.refresh_status()

        except Exception as e:
            self.stage_connected = False
            self.stage_busy = False
            self.stage = None
            messagebox.showerror("Stage Connection Error", str(e))
            self.log(f"Stage connection failed: {e}")

    def disconnect_stage(self):
        try:
            self.scan_stop_requested = True

            if self.stage is not None:
                try:
                    axis = self.axis_var.get()
                    try:
                        self.stage.stop(axis)
                        time.sleep(0.1)
                    except Exception as e:
                        self.log(f"Stop before disconnect warning: {e}")

                    self.stage.close()
                except Exception as e:
                    self.log(f"Disconnect warning: {e}")

            self.stage = None
            self.stage_connected = False
            self.stage_busy = False
            self.status_var.set("Disconnected")
            self.pos1_var.set("Axis1: --- mm (not initialized)")
            self.pos2_var.set("Axis2: --- mm (not initialized)")
            self.log("Stage disconnected.")

        except Exception as e:
            messagebox.showerror("Disconnect Error", str(e))

    def set_speed(self, axis):
        if not self._require_stage():
            return

        try:
            slow = int(self.slow_var.get().strip())
            fast = int(self.fast_var.get().strip())
            rate = int(self.rate_var.get().strip())

            self.stage.set_speed(axis=axis, slow=slow, fast=fast, rate=rate)
            self.log(f"Speed set for Axis {axis}: S={slow}, F={fast}, R={rate}")
        except Exception as e:
            messagebox.showerror("Set Speed Error", str(e))

    def move_rel_positive(self):
        self._move_rel_with_sign(+1)

    def move_rel_negative(self):
        self._move_rel_with_sign(-1)

    def _move_rel_with_sign(self, sign):
        if not self._require_stage():
            return

        try:
            axis = self.axis_var.get()
            mm = float(self.move_rel_mm_var.get().strip())
            target_mm = sign * mm

            def _job():
                try:
                    self.stage_busy = True
                    self.status_var.set("Moving...")
                    self.log(f"Axis {axis} move {target_mm:.3f} mm")
                    self.stage.move_rel_mm(axis=axis, mm=target_mm)
                    self.stage.wait_until_stop(verbose=False)
                    self.status_var.set("Ready")
                    self.refresh_status()

                    pos = self.stage.get_position_mm()
                    if pos[f"axis{axis}"] is None:
                        self.log(f"Axis {axis} move finished, but axis is not initialized yet.")
                    else:
                        self.log(f"Axis {axis} move finished: {target_mm:.3f} mm")

                except Exception as e:
                    self.status_var.set("Error")
                    self.log(f"Move failed: {e}")
                    self.root.after(0, lambda: messagebox.showerror("Stage Move Error", str(e)))
                finally:
                    self.stage_busy = False

            self._run_in_thread(_job)

        except Exception as e:
            messagebox.showerror("Move Error", str(e))

    def home_plus_set_zero(self):
        if not self._require_stage():
            return

        axis = self.axis_var.get()

        def _job():
            try:
                self.stage_busy = True
                self.status_var.set("Homing + ...")
                self.log(f"Axis {axis} -> Home+ and set zero")
                self.stage.home_plus_and_set_zero(axis=axis, verbose=False)
                self.status_var.set("Ready")
                self.refresh_status()
                self.log(f"Axis {axis} home+ finished, zero set.")
            except Exception as e:
                self.status_var.set("Error")
                self.log(f"Home+ failed: {e}")
                self.root.after(0, lambda: messagebox.showerror("Home+ Error", str(e)))
            finally:
                self.stage_busy = False

        self._run_in_thread(_job)

    def home_minus(self):
        if not self._require_stage():
            return

        axis = self.axis_var.get()

        def _job():
            try:
                self.stage_busy = True
                self.status_var.set("Homing - ...")
                self.log(f"Axis {axis} -> Home-")
                self.stage.home_minus(axis=axis, verbose=False)
                self.status_var.set("Ready")
                self.refresh_status()

                pos = self.stage.get_position_mm()
                if pos[f"axis{axis}"] is None:
                    self.log(f"Axis {axis} home- finished, but axis is not initialized yet.")
                else:
                    self.log(f"Axis {axis} home- finished.")

            except Exception as e:
                self.status_var.set("Error")
                self.log(f"Home- failed: {e}")
                self.root.after(0, lambda: messagebox.showerror("Home- Error", str(e)))
            finally:
                self.stage_busy = False

        self._run_in_thread(_job)

    def set_current_as_zero(self):
        if not self._require_stage():
            return

        try:
            axis = self.axis_var.get()
            self.stage.set_current_as_zero(axis)
            self.refresh_status()
            self.log(f"Axis {axis} current position set as zero.")
        except Exception as e:
            messagebox.showerror("Set Zero Error", str(e))

    def clear_zero(self):
        if not self._require_stage():
            return

        try:
            axis = self.axis_var.get()
            self.stage.clear_zero(axis)
            self.refresh_status()
            self.log(f"Axis {axis} software zero cleared.")
        except Exception as e:
            messagebox.showerror("Clear Zero Error", str(e))

    def stop_stage(self):
        if not self._require_stage():
            return

        axis = self.axis_var.get()

        def _job():
            try:
                self.status_var.set("Stopping...")
                self.log(f"Stop command sent to Axis {axis}")
                self.stage.stop(axis=axis)
                time.sleep(0.15)

                try:
                    self.refresh_status()
                except Exception as e:
                    self.log(f"Status refresh after stop warning: {e}")

                self.status_var.set("Ready/Stopped")
            except Exception as e:
                self.log(f"Stop warning: {e}")
                self.status_var.set("Stop warning")
            finally:
                self.stage_busy = False

        self._run_in_thread(_job)

    def refresh_status(self):
        if not self._require_stage():
            return

        try:
            raw = self.stage.query_status()
            self.status_var.set(raw)

            try:
                pos = self.stage.get_position_mm()

                if pos["axis1"] is None:
                    self.pos1_var.set("Axis1: --- mm (not initialized)")
                else:
                    self.pos1_var.set(f"Axis1: {pos['axis1']:.3f} mm")

                if pos["axis2"] is None:
                    self.pos2_var.set("Axis2: --- mm (not initialized)")
                else:
                    self.pos2_var.set(f"Axis2: {pos['axis2']:.3f} mm")

            except Exception as parse_error:
                self.log(f"Position parse warning: {parse_error}")

            self.log(f"Status refreshed: {raw}")
        except Exception as e:
            messagebox.showerror("Status Error", str(e))

    # ============================================================
    # Empty scan
    # ============================================================
    def start_empty_scan(self):
        if not self._require_stage():
            return

        if self.stage_busy:
            self.log("Stage is busy.")
            return

        try:
            # Require both axes initialized
            if not self._axis_initialized(1):
                raise RuntimeError("Axis 1 is not initialized. Please run Home+ & Set Zero first.")
            if not self._axis_initialized(2):
                raise RuntimeError("Axis 2 is not initialized. Please run Home+ & Set Zero first.")

            x_start = float(self.x_start_var.get().strip())
            x_stop = float(self.x_stop_var.get().strip())
            x_step = float(self.x_step_var.get().strip())

            y_start = float(self.y_start_var.get().strip())
            y_stop = float(self.y_stop_var.get().strip())
            y_step = float(self.y_step_var.get().strip())

            dwell = float(self.scan_dwell_var.get().strip())

            xs = self._frange_inclusive(x_start, x_stop, x_step)
            ys = self._frange_inclusive(y_start, y_stop, y_step)

            self.scan_stop_requested = False

            def _job():
                try:
                    self.stage_busy = True
                    self.status_var.set("Scanning...")
                    self.log("Empty scan started.")

                    # Move to start point
                    self.log(f"Move to start point: ({x_start:.3f}, {y_start:.3f}) mm")
                    self._move_to_xy(x_start, y_start)
                    self.refresh_status()

                    # Dwell at starting point
                    self.log(f"Dwell at start point for {dwell:.2f} s")
                    if not self._sleep_with_stop_check(dwell):
                        self.log("Scan stopped during initial dwell.")
                        return

                    # Snake scan
                    for j, y in enumerate(ys):
                        row_xs = xs if (j % 2 == 0) else list(reversed(xs))

                        for i, x in enumerate(row_xs):
                            if self.scan_stop_requested:
                                self.log("Scan stop requested.")
                                return

                            # Skip first point because we're already there
                            if not (j == 0 and i == 0):
                                self.log(f"Move to point: ({x:.3f}, {y:.3f}) mm")
                                self._move_to_xy(x, y)
                                self.refresh_status()

                            self.log(f"Dwell at point ({x:.3f}, {y:.3f}) for {dwell:.2f} s")
                            if not self._sleep_with_stop_check(dwell):
                                self.log("Scan stopped during dwell.")
                                return

                    # Return to start point
                    self.log(f"Return to start point: ({x_start:.3f}, {y_start:.3f}) mm")
                    self._move_to_xy(x_start, y_start)
                    self.refresh_status()

                    self.log("Empty scan finished.")
                    self.status_var.set("Scan finished")

                except Exception as e:
                    self.status_var.set("Scan error")
                    self.log(f"Empty scan failed: {e}")
                    self.root.after(0, lambda: messagebox.showerror("Empty Scan Error", str(e)))
                finally:
                    self.stage_busy = False
                    self.scan_stop_requested = False

            self._run_in_thread(_job)

        except Exception as e:
            messagebox.showerror("Start Scan Error", str(e))

    def stop_empty_scan(self):
        self.scan_stop_requested = True
        self.log("Stop scan requested.")

    # ============================================================
    # Safe close
    # ============================================================
    def on_close(self):
        try:
            self.log("Closing GUI...")
            self.scan_stop_requested = True

            if self.stage is not None:
                try:
                    axis = self.axis_var.get()
                    try:
                        self.stage.stop(axis)
                        time.sleep(0.1)
                    except Exception as e:
                        self.log(f"Stop during close warning: {e}")

                    self.stage.close()
                    self.log("Stage serial port closed.")
                except Exception as e:
                    self.log(f"Stage close warning: {e}")

            self.stage = None
            self.stage_connected = False
            self.stage_busy = False

        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = ScanGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()