import os
import time
import numpy as np


class ScanController:
    """
    High-level scan workflow controller.

    Main sequence:
        move stage
        -> wait until stop
        -> arm PicoScope
        -> trigger AFG burst
        -> read PicoScope data
        -> save result
    """

    def __init__(self, stage, afg, pico, save_dir="results"):
        self.stage = stage
        self.afg = afg
        self.pico = pico
        self.save_dir = save_dir
        os.makedirs(self.save_dir, exist_ok=True)

    def acquire_point(self, x_mm: float, y_mm: float, verbose: bool = True):
        """
        Move to a point and acquire one waveform.
        """
        if verbose:
            print(f"\n=== Acquire point: x={x_mm:.3f} mm, y={y_mm:.3f} mm ===")

        # 先移动 Y，再移动 X
        self.stage.move_abs_mm(axis=2, mm=y_mm)
        self.stage.wait_until_stop()

        self.stage.move_abs_mm(axis=1, mm=x_mm)
        self.stage.wait_until_stop()

        if verbose:
            print("Stage in position.")

        # Arm Pico
        self.pico.arm()
        time.sleep(0.01)

        # Trigger AFG burst
        self.afg.trigger()

        # Wait Pico ready
        self.pico.wait_until_ready()

        # Read waveform
        t, data = self.pico.read_data()

        # Save result
        filename = os.path.join(
            self.save_dir,
            f"x_{x_mm:.3f}_y_{y_mm:.3f}.npz".replace(".", "p")
        )
        np.savez(
            filename,
            t=t,
            data=data,
            x_mm=x_mm,
            y_mm=y_mm
        )

        if verbose:
            print(f"Saved: {filename}")

        return t, data

    def raster_scan(self, xs_mm, ys_mm, snake: bool = True, verbose: bool = True):
        """
        2D raster scan.
        """
        for j, y in enumerate(ys_mm):
            row_xs = xs_mm if (not snake or j % 2 == 0) else xs_mm[::-1]

            if verbose:
                print(f"\n===== Row y = {y:.3f} mm =====")

            for x in row_xs:
                self.acquire_point(x_mm=x, y_mm=y, verbose=verbose)