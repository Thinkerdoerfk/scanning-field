import threading
import tkinter as tk
from tkinter import ttk, messagebox

from scan_controller import ScanController


class ScanPanel:
    def __init__(self, parent, ctx, log_func):
        self.parent = parent
        self.ctx = ctx
        self.log = log_func

        self.scan_controller = None
        #self.scan_thread = None
        #self.test_scan_thread = None

        self.frame = ttk.LabelFrame(parent, text="Scan", padding=6)
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

        self._build_ui()

    # ============================================================
    # UI
    # ============================================================
    def _build_ui(self):
        for c in range(7):
            self.frame.columnconfigure(c, weight=0)
        self.frame.columnconfigure(6, weight=1)

        row = 0
        ttk.Label(self.frame, text="X0").grid(row=row, column=0, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.x_start_var, width=7).grid(row=row, column=1, padx=2, pady=2)
        ttk.Label(self.frame, text="X1").grid(row=row, column=2, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.x_stop_var, width=7).grid(row=row, column=3, padx=2, pady=2)
        ttk.Label(self.frame, text="dX").grid(row=row, column=4, padx=2, pady=2, sticky="w")
        ttk.Entry(self.frame, textvariable=self.x_step_var, width=7).grid(row=row, column=5, padx=2, pady=2)

        corner_frame = ttk.Frame(self.frame)
        corner_frame.grid(row=0, column=6, rowspan=3, padx=(8, 2), pady=2, sticky="ne")
        ttk.Label(corner_frame, text="Corners").grid(row=0, column=0, columnspan=2, sticky="w")
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
        ttk.Label(self.frame, text="Path: X+ / return / Y+").grid(row=row, column=2, columnspan=4, padx=4, pady=2,
                                                                  sticky="w")

        row += 1
        ttk.Button(self.frame, text="Start Scan", command=self.start_scan).grid(row=row, column=2, padx=4, pady=5,
                                                                                sticky="ew")
        ttk.Button(self.frame, text="Stop Scan", command=self.stop_scan).grid(row=row, column=3, padx=4, pady=5,
                                                                              sticky="ew")

        row += 1
        ttk.Label(
            self.frame,
            text="Stage must already be at (X0, Y0) before Start.",
        ).grid(row=row, column=0, columnspan=6, padx=2, pady=(2, 0), sticky="w")

    # ============================================================
    # Helpers
    # ============================================================
    def _get_float(self, var, name):
        try:
            return float(var.get().strip())
        except Exception:
            raise ValueError(f"Invalid value for {name}")

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

            x_start = self._get_float(self.x_start_var, "X Start")
            x_stop = self._get_float(self.x_stop_var, "X Stop")
            x_step = self._get_float(self.x_step_var, "X Step")

            y_start = self._get_float(self.y_start_var, "Y Start")
            y_stop = self._get_float(self.y_stop_var, "Y Stop")
            y_step = self._get_float(self.y_step_var, "Y Step")

            dwell_s = self._get_float(self.dwell_var, "Dwell")

            if x_step <= 0:
                raise ValueError("X Step must be positive.")
            if y_step <= 0:
                raise ValueError("Y Step must be positive.")
            if x_stop < x_start:
                raise ValueError("X Stop must be >= X Start.")
            if y_stop < y_start:
                raise ValueError("Y Stop must be >= Y Start.")

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

            self.log(
                f"[SCAN] Start requested: X {x_start}->{x_stop} step {x_step}; "
                f"Y {y_start}->{y_stop} step {y_step}; dwell={dwell_s}s"
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