import time
import threading
import traceback
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
        - trigger AFG once for each requested frequency at each point
    """

    def __init__(self, ctx, stage, afg, pico, log_func=None):
        self.ctx = ctx
        self.stage = stage
        self.afg = afg
        self.pico = pico
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
    def trigger_here(
            self,
            point_index: int,
            x_mm: float,
            y_mm: float,
            dwell_s: float = 0.0,
            frequencies_hz=None,
            verbose: bool = True,
    ) -> None:
        """
        At current scan point:
            1. optionally wait dwell_s once at this scan point
            2. set AFG frequency
            3. arm Pico (already configured in PicoPanel)
            4. fire AFG software trigger
            5. wait Pico capture complete
            6. repeat 2-5 for each frequency
            7. save all frequency waveforms for this point to one NPZ
            8. publish latest waveform to ctx for PicoPanel auto-refresh
        """
        pico = self.ctx.pico
        afg = self.ctx.afg

        if pico is None:
            raise RuntimeError("Pico controller is not available")
        if afg is None:
            raise RuntimeError("AFG controller is not available")

        if not pico.is_connected():
            raise RuntimeError("Pico is not connected")
        if not pico.is_configured():
            raise RuntimeError("Pico is not configured in Pico panel")
        if frequencies_hz is None:
            frequencies_hz = [float(afg.query(f"SOURce{afg.channel}:FREQuency:FIXed?"))]
        frequencies_hz = np.asarray(frequencies_hz, dtype=float)
        if frequencies_hz.ndim != 1 or len(frequencies_hz) == 0:
            raise ValueError("frequencies_hz must be a non-empty 1D sequence")
        if np.any(frequencies_hz <= 0):
            raise ValueError("All frequencies must be positive")

        if verbose:
            self.log(
                f"[SCAN] Point #{point_index}: x={x_mm:.3f} mm, y={y_mm:.3f} mm, "
                f"freq/point={len(frequencies_hz)}"
            )

        # Dwell is a point-settling delay, so apply it once before the frequency sweep.
        if dwell_s > 0:
            time.sleep(dwell_s)

        results = []
        # Previous repeated-sampling mode, kept for future reuse:
        # for trig_index in range(1, trigger_count + 1):
        #     pico.arm_current_capture()
        #     afg.fire_software_trigger_once()
        #     results.append(pico.wait_and_fetch_current_capture())
        for freq_index, frequency_hz in enumerate(frequencies_hz, start=1):
            if self._stop_requested:
                self.log("[SCAN] Scan stopped by user.")
                return

            if verbose:
                self.log(
                    f"[SCAN] Point #{point_index}, frequency {freq_index}/{len(frequencies_hz)}: "
                    f"{frequency_hz / 1e6:.6f} MHz."
                )

            # 1. Set excitation frequency while keeping existing amplitude/burst settings.
            afg.set_frequency(float(frequency_hz))

            # 2. Pico enters waiting-for-trigger state
            pico.arm_current_capture()

            # 3. fire AFG
            afg.fire_software_trigger_once()

            # 4. wait and fetch waveform
            results.append(pico.wait_and_fetch_current_capture())

        result = self._combine_point_results(results, point_index, x_mm, y_mm, frequencies_hz)

        # 5. save waveform
        save_paths = pico.save_capture_npz(
            result=result,
            point_index=point_index,
            x_mm=x_mm,
            y_mm=y_mm,
        )

        # 6. publish latest waveform to shared context
        self.ctx.last_pico_time = result.time_s
        self.ctx.last_pico_signals = {
            ch: np.asarray(signal, dtype=float)[-1] if np.asarray(signal).ndim == 2 else signal
            for ch, signal in result.signals_v.items()
        }
        self.ctx.last_pico_meta = result.meta
        self.ctx.last_pico_update_id = getattr(self.ctx, "last_pico_update_id", 0) + 1

        if verbose:
            for ch, path in save_paths.items():
                self.log(f"[SCAN] Saved channel {ch}: {path}")

    def _combine_point_results(self, results, point_index, x_mm, y_mm, frequencies_hz):
        if not results:
            raise RuntimeError("No Pico captures were collected for this point")

        first = results[0]
        combined_signals = {}
        for ch in first.signals_v.keys():
            combined_signals[ch] = np.stack(
                [np.asarray(result.signals_v[ch], dtype=float) for result in results],
                axis=0,
            )

        meta = dict(first.meta)
        meta.update(
            {
                "point_index": int(point_index),
                "x_mm": float(x_mm),
                "y_mm": float(y_mm),
                "frequency_count": int(len(frequencies_hz)),
                "excitation_frequencies_hz": np.asarray(frequencies_hz, dtype=float),
                "excitation_frequencies_mhz": np.asarray(frequencies_hz, dtype=float) / 1e6,
                "signal_shape": "frequency_count x samples",
                "per_frequency_meta": [dict(result.meta) for result in results],
                # Backward-compatible name for older analysis scripts.
                "per_trigger_meta": [dict(result.meta) for result in results],
            }
        )

        return type(first)(
            time_s=np.asarray(first.time_s, dtype=float),
            signals_v=combined_signals,
            meta=meta,
        )

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
        frequencies_hz=None,
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
            if frequencies_hz is None:
                frequencies_hz = [float(self.afg.query(f"SOURce{self.afg.channel}:FREQuency:FIXed?"))]
            frequencies_hz = np.asarray(frequencies_hz, dtype=float)
            if frequencies_hz.ndim != 1 or len(frequencies_hz) == 0:
                raise ValueError("frequencies_hz must be a non-empty 1D sequence")
            if np.any(frequencies_hz <= 0):
                raise ValueError("All frequencies must be positive")

            xs = np.arange(x_start, x_stop + 0.5 * x_step, x_step, dtype=float)
            ys = np.arange(y_start, y_stop + 0.5 * y_step, y_step, dtype=float)

            if len(xs) == 0 or len(ys) == 0:
                raise ValueError("Empty scan grid")

            self.log("Stage + AFG scan started.")
            self.log(
                f"X: {x_start} -> {x_stop} step {x_step}, "
                f"Y: {y_start} -> {y_stop} step {y_step}, "
                f"dwell={dwell_s} s, freq/point={len(frequencies_hz)}"
            )
            self.log(f"X points: {xs}")
            self.log(f"Y points: {ys}")
            self.log(f"Frequencies (MHz): {frequencies_hz / 1e6}")

            current_x = float(x_start)
            current_y = float(y_start)
            point_index = 1# number of points

            for j, y in enumerate(ys):
                if self._stop_requested:
                    self.log("Scan stopped by user.")
                    return

                # If current row is not the first row, move one step in y direction
                if j > 0:
                    dy = float(y - current_y)
                    self.move_y_rel(dy, verbose=verbose)# Also controls the software pos display
                    current_y = float(y)
                self.log(f"===== Row {j + 1}/{len(ys)} : y = {current_y:.3f} mm =====")

                if abs(current_x - x_start) > 1e-12:
                    dx_back = float(x_start - current_x)
                    self.move_x_rel(dx_back, verbose=verbose)# Also controls the software pos display
                    current_x = float(x_start)

                for i in range(len(xs)):
                    if self._stop_requested:
                        self.log("[SCAN] Scan stopped by user.")
                        return

                    self.log(f"[SCAN] === Point: x={current_x:.3f} mm, y={current_y:.3f} mm ===")
                    self.trigger_here(
                        point_index=point_index,
                        x_mm=current_x,
                        y_mm=current_y,
                        dwell_s=dwell_s,
                        frequencies_hz=frequencies_hz,
                        verbose=verbose,
                    )
                    point_index += 1

                    if i < len(xs) - 1:
                        next_x = float(xs[i + 1])
                        dx = next_x - current_x
                        self.move_x_rel(dx, verbose=verbose)
                        current_x = next_x

                if j < len(ys) - 1 and abs(current_x - x_start) > 1e-12:
                    self.log("[SCAN] Row finished. Return X to row start.")
                    dx_return = float(x_start - current_x)
                    self.move_x_rel(dx_return, verbose=verbose)
                    current_x = float(x_start)

        # Return to the starting point after scan finished
            self.log("[SCAN] Scan finished. Returning to global scan start point.")
            if abs(current_x - x_start) > 1e-12:
                dx_back_home = float(x_start - current_x)
                self.move_x_rel(dx_back_home, verbose=verbose)
                current_x = float(x_start)

            if abs(current_y - y_start) > 1e-12:
                dy_back_home = float(y_start - current_y)
                self.move_y_rel(dy_back_home, verbose=verbose)
                current_y = float(y_start)

            self.log("[SCAN] Scan finished successfully. Returned to start point.")

        finally:
            self._is_running = False

    # ============================================================
    # Thread wrapper for GUI
    # ============================================================
    def _thread_entry(self, **kwargs):
        try:
            self.raster_scan_return(**kwargs)
        except Exception as e:
            self.log(f"[SCAN] Scan crashed: {e}")
            self.log(traceback.format_exc())
            self._is_running = False

    def start_scan_thread(
        self,
        x_start: float,
        x_stop: float,
        x_step: float,
        y_start: float,
        y_stop: float,
        y_step: float,
        dwell_s: float = 0.0,
        frequencies_hz=None,
        verbose: bool = True,
    ):
        if self._is_running:
            raise RuntimeError("Scan is already running")

        self._scan_thread = threading.Thread(
            target=self._thread_entry,
            kwargs=dict(
                x_start=x_start,
                x_stop=x_stop,
                x_step=x_step,
                y_start=y_start,
                y_stop=y_stop,
                y_step=y_step,
                dwell_s=dwell_s,
                frequencies_hz=frequencies_hz,
                verbose=verbose,
            ),
            daemon=True,
        )
        self._scan_thread.start()
