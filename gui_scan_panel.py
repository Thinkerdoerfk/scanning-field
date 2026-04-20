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
        self.scan_thread = None
        self.test_scan_thread = None

        self.frame = ttk.LabelFrame(parent, text="Scan Panel", padding=10)
        self.frame.pack(fill="x", padx=5, pady=8)

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
        self.first_without_move_var = tk.BooleanVar(value=True)

        self._build_ui()

    # ============================================================
    # UI
    # ============================================================
    def _build_ui(self):
        # row number of buttons
        row = 0

        ttk.Label(self.frame, text="X Start (mm)").grid(
            row=row, column=0, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.x_start_var, width=10).grid(
            row=row, column=1, padx=4, pady=4
        )

        ttk.Label(self.frame, text="X Stop (mm)").grid(
            row=row, column=2, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.x_stop_var, width=10).grid(
            row=row, column=3, padx=4, pady=4
        )

        ttk.Label(self.frame, text="X Step (mm)").grid(
            row=row, column=4, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.x_step_var, width=10).grid(
            row=row, column=5, padx=4, pady=4
        )

        test_frame = ttk.LabelFrame(self.frame, text="Test Scan Corner")
        test_frame.grid(row=0, column=6, rowspan=4, padx=(12, 4), pady=4, sticky="n")

        ttk.Button(test_frame, text="LT", width=6,
                   command=lambda: self.test_scan_corner("LT")).grid(row=0, column=0, padx=3, pady=3)
        ttk.Button(test_frame, text="RT", width=6,
                   command=lambda: self.test_scan_corner("RT")).grid(row=0, column=1, padx=3, pady=3)
        ttk.Button(test_frame, text="LD", width=6,
                   command=lambda: self.test_scan_corner("LD")).grid(row=1, column=0, padx=3, pady=3)
        ttk.Button(test_frame, text="RD", width=6,
                   command=lambda: self.test_scan_corner("RD")).grid(row=1, column=1, padx=3, pady=3)

        row += 1

        ttk.Label(self.frame, text="Y Start (mm)").grid(
            row=row, column=0, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.y_start_var, width=10).grid(
            row=row, column=1, padx=4, pady=4
        )

        ttk.Label(self.frame, text="Y Stop (mm)").grid(
            row=row, column=2, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.y_stop_var, width=10).grid(
            row=row, column=3, padx=4, pady=4
        )

        ttk.Label(self.frame, text="Y Step (mm)").grid(
            row=row, column=4, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.y_step_var, width=10).grid(
            row=row, column=5, padx=4, pady=4
        )

        row += 1

        ttk.Label(self.frame, text="Dwell (s)").grid(
            row=row, column=0, padx=4, pady=4, sticky="w"
        )
        ttk.Entry(self.frame, textvariable=self.dwell_var, width=10).grid(
            row=row, column=1, padx=4, pady=4
        )

        ttk.Checkbutton(
            self.frame,
            text="First point without moving",
            variable=self.first_without_move_var,
        ).grid(row=row, column=2, columnspan=2, padx=4, pady=4, sticky="w")

        ttk.Label(
            self.frame,
            text="Mode: X forward → return to X start → Y+ → repeat"
        ).grid(row=row, column=4, columnspan=2, padx=4, pady=4, sticky="w")

        row += 1

        ttk.Button(self.frame, text="Start Scan", command=self.start_scan).grid(
            row=row, column=2, padx=6, pady=8
        )
        ttk.Button(self.frame, text="Stop Scan", command=self.stop_scan).grid(
            row=row, column=3, padx=6, pady=8
        )

        row += 1

        ttk.Label(
            self.frame,
            text="Note: before starting, stage should already be at (X Start, Y Start)."
        ).grid(row=row, column=0, columnspan=6, padx=4, pady=(6, 2), sticky="w")

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
            if corner == "LD":
                target_x = x_start
                target_y = y_start
            elif corner == "RD":
                target_x = x_stop
                target_y = y_start
            elif corner == "LT":
                target_x = x_start
                target_y = y_stop
            elif corner == "RT":
                target_x = x_stop
                target_y = y_stop
            else:
                raise ValueError(f"Unknown corner: {corner}")

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

            x_start = self._get_float(self.x_start_var, "X Start")
            x_stop = self._get_float(self.x_stop_var, "X Stop")
            x_step = self._get_float(self.x_step_var, "X Step")

            y_start = self._get_float(self.y_start_var, "Y Start")
            y_stop = self._get_float(self.y_stop_var, "Y Stop")
            y_step = self._get_float(self.y_step_var, "Y Step")

            dwell_s = self._get_float(self.dwell_var, "Dwell")
            first_without_move = self.first_without_move_var.get()

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
                stage=self.ctx.stage,
                afg=self.ctx.afg,
                log_func=self.log,
            )

            self.log("Preparing scan thread...")
            self.log(
                f"X: {x_start} -> {x_stop}, step={x_step}; "
                f"Y: {y_start} -> {y_stop}, step={y_step}; "
                f"dwell={dwell_s}; first_without_move={first_without_move}"
            )
            self.log("Make sure stage is already at (X Start, Y Start).")

            self.scan_thread = threading.Thread(
                target=self.scan_controller.raster_scan_return,
                kwargs=dict(
                    x_start=x_start,
                    x_stop=x_stop,
                    x_step=x_step,
                    y_start=y_start,
                    y_stop=y_stop,
                    y_step=y_step,
                    dwell_s=dwell_s,
                    first_without_move=first_without_move,
                    verbose=True,
                ),
                daemon=True,
            )
            self.scan_thread.start()

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