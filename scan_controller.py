import time
import threading
import numpy as np


class ScanController:
    """
    Stage + AFG scan controller using relative motion only.

    Scan pattern:
        For each row:
            scan X from x_start to x_stop
            return X back to x_start
            move Y by one step
            scan forward again

    Notes:
        - relative move only
        - no Pico acquisition yet
        - trigger AFG once at each point
    """

    def __init__(self, stage, afg, log_func=None):
        self.stage = stage
        self.afg = afg
        self.log_func = log_func

        self._stop_requested = False
        self._scan_thread = None
        self._is_running = False

    # ============================================================
    # Logging
    # ============================================================
    def log(self, msg: str):
        if self.log_func is not None:
            self.log_func(msg)
        else:
            print(msg)

    # ============================================================
    # State
    # ============================================================
    @property
    def is_running(self) -> bool:
        return self._is_running

    def stop(self):
        self._stop_requested = True
        self.log("Scan stop requested.")

    # ============================================================
    # Basic actions
    # ============================================================
    def trigger_here(self, dwell_s: float = 0.0, verbose: bool = True):
        if dwell_s > 0:
            time.sleep(dwell_s)

        if verbose:
            self.log("Trigger AFG once.")

        self.afg.fire_software_trigger_once()

    def move_x_rel(self, dx_mm: float, verbose: bool = True):
        if abs(dx_mm) <= 1e-12:
            return
        if verbose:
            self.log(f"Move X relatively by {dx_mm:.3f} mm")
        self.stage.move_rel_mm(axis=1, mm=dx_mm)
        self.stage.wait_until_stop()

    def move_y_rel(self, dy_mm: float, verbose: bool = True):
        if abs(dy_mm) <= 1e-12:
            return
        if verbose:
            self.log(f"Move Y relatively by {dy_mm:.3f} mm")
        self.stage.move_rel_mm(axis=2, mm=dy_mm)
        self.stage.wait_until_stop()

    # ============================================================
    # Main scan
    # ============================================================
    def raster_scan_return(
        self,
        x_start: float,
        x_stop: float,
        x_step: float,
        y_start: float,
        y_stop: float,
        y_step: float,
        dwell_s: float = 0.0,
        first_without_move: bool = True,
        verbose: bool = True,
    ):
        """
        Raster scan with X returning to row start after each row.

        Assumption:
            Before starting, stage is already physically at (x_start, y_start).

        Scan path:
            Row 1: x_start -> x_stop
            Return X to x_start
            Move Y +
            Row 2: x_start -> x_stop
            Return X to x_start
            ...
        """
        self._stop_requested = False
        self._is_running = True

        try:
            if x_step <= 0 or y_step <= 0:
                raise ValueError("x_step and y_step must be positive")
            if x_stop < x_start or y_stop < y_start:
                raise ValueError("Require x_stop >= x_start and y_stop >= y_start")

            xs = np.arange(x_start, x_stop + 0.5 * x_step, x_step, dtype=float)
            ys = np.arange(y_start, y_stop + 0.5 * y_step, y_step, dtype=float)

            if len(xs) == 0 or len(ys) == 0:
                raise ValueError("Empty scan grid")

            self.log("Stage + AFG scan started.")
            self.log(
                f"X: {x_start} -> {x_stop} step {x_step}, "
                f"Y: {y_start} -> {y_stop} step {y_step}, "
                f"dwell={dwell_s} s, first_without_move={first_without_move}"
            )
            self.log(f"X points: {xs}")
            self.log(f"Y points: {ys}")

            current_x = float(x_start)
            current_y = float(y_start)

            for j, y in enumerate(ys):
                if self._stop_requested:
                    self.log("Scan stopped by user.")
                    return

                self.log(f"===== Row {j + 1}/{len(ys)} : y = {y:.3f} mm =====")

                if j > 0:
                    dy = float(y - current_y)
                    self.move_y_rel(dy, verbose=verbose)
                    current_y = float(y)

                if abs(current_x - x_start) > 1e-12:
                    dx_back = float(x_start - current_x)
                    self.log("Return X to row start.")
                    self.move_x_rel(dx_back, verbose=verbose)
                    current_x = float(x_start)

                for i, x in enumerate(xs):
                    if self._stop_requested:
                        self.log("Scan stopped by user.")
                        return

                    self.log(f"=== Point: x={x:.3f} mm, y={current_y:.3f} mm ===")

                    if j == 0 and i == 0 and first_without_move:
                        self.log("First point: acquire before moving.")
                        self.trigger_here(dwell_s=dwell_s, verbose=verbose)
                        continue

                    dx = float(x - current_x)
                    self.move_x_rel(dx, verbose=verbose)
                    current_x = float(x)

                    self.trigger_here(dwell_s=dwell_s, verbose=verbose)

                if j < len(ys) - 1:
                    dx_return = float(x_start - current_x)
                    self.log("Row finished. Return X to start.")
                    self.move_x_rel(dx_return, verbose=verbose)
                    current_x = float(x_start)

            self.log("Scan finished successfully.")

        finally:
            self._is_running = False

    # ============================================================
    # Thread wrapper for GUI
    # ============================================================
    def start_scan_thread(
        self,
        x_start: float,
        x_stop: float,
        x_step: float,
        y_start: float,
        y_stop: float,
        y_step: float,
        dwell_s: float = 0.0,
        first_without_move: bool = True,
        verbose: bool = True,
    ):
        if self._is_running:
            raise RuntimeError("Scan is already running")

        self._scan_thread = threading.Thread(
            target=self.raster_scan_return,
            kwargs=dict(
                x_start=x_start,
                x_stop=x_stop,
                x_step=x_step,
                y_start=y_start,
                y_stop=y_stop,
                y_step=y_step,
                dwell_s=dwell_s,
                first_without_move=first_without_move,
                verbose=verbose,
            ),
            daemon=True,
        )
        self._scan_thread.start()