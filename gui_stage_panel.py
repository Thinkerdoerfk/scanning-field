import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from stage_controller import GSC02CStage


class StagePanel:
    def __init__(self, parent, ctx, log_func):
        self.ctx = ctx
        self.log = log_func

        self.stage_port_var = tk.StringVar(value="COM5")
        self.axis_var = tk.IntVar(value=1)

        self.move_rel_mm_var = tk.StringVar(value="5.0")

        self.slow_var = tk.StringVar(value="200")
        self.fast_var = tk.StringVar(value="800")
        self.rate_var = tk.StringVar(value="80")

        self.status_var = tk.StringVar(value="Not connected")
        self.pos1_var = tk.StringVar(value="Axis1: --- mm (not initialized)")
        self.pos2_var = tk.StringVar(value="Axis2: --- mm (not initialized)")

        self.frame = ttk.LabelFrame(parent, text="Stage Control", padding=10)
        self.frame.pack(fill="x", pady=(0, 10))

        self._build()

    def _build(self):
        frame = self.frame

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

        ttk.Label(frame, text="Minimum command step: 0.001 mm", foreground="gray").grid(
            row=3, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5)
        )

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

    def _require_stage(self):
        if not self.ctx.stage_connected or self.ctx.stage is None:
            messagebox.showwarning("Warning", "Stage is not connected.")
            return False
        return True

    def _run_in_thread(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def connect_stage(self):
        if self.ctx.stage_connected:
            self.log("Stage already connected.")
            return

        port = self.stage_port_var.get().strip()

        try:
            if self.ctx.stage is not None:
                try:
                    self.ctx.stage.close()
                except Exception:
                    pass
                self.ctx.stage = None

            self.ctx.stage = GSC02CStage(port=port)
            self.ctx.stage.connect()
            self.ctx.stage_connected = True
            self.ctx.stage_busy = False
            self.status_var.set("Connected")
            self.log(f"Stage connected on {port}")
            self.refresh_status()

        except Exception as e:
            self.ctx.stage_connected = False
            self.ctx.stage_busy = False
            self.ctx.stage = None
            messagebox.showerror("Stage Connection Error", str(e))
            self.log(f"Stage connection failed: {e}")

    def disconnect_stage(self):
        try:
            self.ctx.scan_stop_requested = True

            if self.ctx.stage is not None:
                try:
                    axis = self.axis_var.get()
                    try:
                        self.ctx.stage.stop(axis)
                        time.sleep(0.1)
                    except Exception as e:
                        self.log(f"Stop before disconnect warning: {e}")

                    self.ctx.stage.close()
                except Exception as e:
                    self.log(f"Disconnect warning: {e}")

            self.ctx.stage = None
            self.ctx.stage_connected = False
            self.ctx.stage_busy = False
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

            self.ctx.stage.set_speed(axis=axis, slow=slow, fast=fast, rate=rate)
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
                    self.ctx.stage_busy = True
                    self.status_var.set("Moving...")
                    self.log(f"Axis {axis} move {target_mm:.3f} mm")
                    self.ctx.stage.move_rel_mm(axis=axis, mm=target_mm)
                    self.ctx.stage.wait_until_stop(verbose=False)
                    self.status_var.set("Ready")
                    self.refresh_status()

                    pos = self.ctx.stage.get_position_mm()
                    if pos[f"axis{axis}"] is None:
                        self.log(f"Axis {axis} move finished, but axis is not initialized yet.")
                    else:
                        self.log(f"Axis {axis} move finished: {target_mm:.3f} mm")

                except Exception as e:
                    self.status_var.set("Error")
                    self.log(f"Move failed: {e}")
                    messagebox.showerror("Stage Move Error", str(e))
                finally:
                    self.ctx.stage_busy = False

            self._run_in_thread(_job)

        except Exception as e:
            messagebox.showerror("Move Error", str(e))

    def home_plus_set_zero(self):
        if not self._require_stage():
            return

        axis = self.axis_var.get()

        def _job():
            try:
                self.ctx.stage_busy = True
                self.status_var.set("Homing + ...")
                self.log(f"Axis {axis} -> Home+ and set zero")
                self.ctx.stage.home_plus_and_set_zero(axis=axis, verbose=False)
                self.status_var.set("Ready")
                self.refresh_status()
                self.log(f"Axis {axis} home+ finished, zero set.")
            except Exception as e:
                self.status_var.set("Error")
                self.log(f"Home+ failed: {e}")
                messagebox.showerror("Home+ Error", str(e))
            finally:
                self.ctx.stage_busy = False

        self._run_in_thread(_job)

    def home_minus(self):
        if not self._require_stage():
            return

        axis = self.axis_var.get()

        def _job():
            try:
                self.ctx.stage_busy = True
                self.status_var.set("Homing - ...")
                self.log(f"Axis {axis} -> Home-")
                self.ctx.stage.home_minus(axis=axis, verbose=False)
                self.status_var.set("Ready")
                self.refresh_status()

                pos = self.ctx.stage.get_position_mm()
                if pos[f"axis{axis}"] is None:
                    self.log(f"Axis {axis} home- finished, but axis is not initialized yet.")
                else:
                    self.log(f"Axis {axis} home- finished.")

            except Exception as e:
                self.status_var.set("Error")
                self.log(f"Home- failed: {e}")
                messagebox.showerror("Home- Error", str(e))
            finally:
                self.ctx.stage_busy = False

        self._run_in_thread(_job)

    def set_current_as_zero(self):
        if not self._require_stage():
            return

        try:
            axis = self.axis_var.get()
            self.ctx.stage.set_current_as_zero(axis)
            self.refresh_status()
            self.log(f"Axis {axis} current position set as zero.")
        except Exception as e:
            messagebox.showerror("Set Zero Error", str(e))

    def clear_zero(self):
        if not self._require_stage():
            return

        try:
            axis = self.axis_var.get()
            self.ctx.stage.clear_zero(axis)
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
                self.ctx.stage.stop(axis=axis)
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
                self.ctx.stage_busy = False

        self._run_in_thread(_job)

    def refresh_status(self):
        if not self._require_stage():
            return

        try:
            raw = self.ctx.stage.query_status()
            self.status_var.set(raw)

            try:
                pos = self.ctx.stage.get_position_mm()

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