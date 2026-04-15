import serial
import time
import threading
from typing import Dict, Optional


class GSC02CStage:
    """
    SIGMA KOKI GSC-02C controller for HPS80-50X-M5 stage.

    Final design:
    - Relative motion only
    - Software/display coordinate system
    - A valid coordinate system exists only after:
          Home+ & Set Zero
    - After initialization:
          home+ => 0 mm
          home- => +travel_mm
    - Repeated stop() should be harmless
    - HPS80-50X-M5: 1 pulse = 1 um = 0.001 mm
    """

    def __init__(
        self,
        port: str = "COM5",
        baudrate: int = 9600,
        timeout: float = 2.0,
        step_to_mm: float = 0.001,
        travel_mm: float = 50.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.step_to_mm = step_to_mm
        self.travel_mm = travel_mm

        self.ser: Optional[serial.Serial] = None
        self._io_lock = threading.RLock()

        # Software/display position in mm
        self.software_pos_mm = {
            1: 0.0,
            2: 0.0,
        }

        # Whether the software coordinate of an axis is initialized
        self.software_pos_valid = {
            1: False,
            2: False,
        }

        # Display positive direction = toward home-
        # Adjust per axis if needed.
        self.display_to_controller_sign = {
            1: -1,
            2: -1,
        }

    # ============================================================
    # Connection
    # ============================================================
    def connect(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            rtscts=True,
        )
        time.sleep(0.2)

    def close(self):
        with self._io_lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.ser = None

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open

    # ============================================================
    # Low-level I/O
    # ============================================================
    def _write(self, cmd: str):
        if not self.is_connected():
            raise RuntimeError("Stage not connected")
        with self._io_lock:
            self.ser.write(cmd.encode())

    def _readline(self) -> str:
        if not self.is_connected():
            raise RuntimeError("Stage not connected")
        with self._io_lock:
            return self.ser.readline().decode(errors="ignore").strip()

    def _query(self, cmd: str) -> str:
        if not self.is_connected():
            raise RuntimeError("Stage not connected")
        with self._io_lock:
            self.ser.write(cmd.encode())
            return self.ser.readline().decode(errors="ignore").strip()

    # ============================================================
    # Raw status parsing
    # ============================================================
    @staticmethod
    def _parse_int_field(text: str) -> int:
        """
        Handle fields like:
            '100'
            '   100'
            '-     17'
            '     -17'
        """
        cleaned = text.strip().replace(" ", "")
        return int(cleaned)

    def parse_status(self, status: Optional[str] = None) -> Dict[str, object]:
        if status is None:
            status = self.query_status()

        parts = [p.strip() for p in status.split(",")]
        if len(parts) < 5:
            raise ValueError(f"Unexpected status format: {status}")

        axis1 = self._parse_int_field(parts[0])
        axis2 = self._parse_int_field(parts[1])

        return {
            "axis1_pos_raw": axis1,
            "axis2_pos_raw": axis2,
            "axis1_state": parts[2],
            "axis2_state": parts[3],
            "motion_state": parts[4],  # B / R
            "raw": status,
        }

    # ============================================================
    # Status
    # ============================================================
    def query_status(self) -> str:
        return self._query("Q:\r\n")

    def get_position_steps_raw(self) -> Dict[str, int]:
        info = self.parse_status()
        return {
            "axis1": info["axis1_pos_raw"],
            "axis2": info["axis2_pos_raw"],
        }

    def get_position_mm(self) -> Dict[str, Optional[float]]:
        """
        Return display/software coordinates.
        None means: this axis is not initialized yet.
        """
        return {
            "axis1": self.software_pos_mm[1] if self.software_pos_valid[1] else None,
            "axis2": self.software_pos_mm[2] if self.software_pos_valid[2] else None,
        }

    # ============================================================
    # Raw controller relative motion
    # ============================================================
    def move_rel(self, axis: int, steps: int):
        self._validate_axis(axis)

        if steps == 0:
            return

        direction = "+" if steps > 0 else "-"
        steps_abs = abs(steps)
        cmd = f"M:{axis}{direction}P{steps_abs}\r\n"

        with self._io_lock:
            if not self.is_connected():
                raise RuntimeError("Stage not connected")
            self.ser.write(cmd.encode())
            self.ser.write("G:\r\n".encode())

    def mm_to_steps(self, mm: float) -> int:
        return int(round(mm / self.step_to_mm))

    def steps_to_mm(self, steps: int) -> float:
        return steps * self.step_to_mm

    def move_rel_mm_raw(self, axis: int, mm: float):
        steps = self.mm_to_steps(mm)
        self.move_rel(axis, steps)

    # ============================================================
    # Display-coordinate relative motion
    # ============================================================
    def move_rel_mm(self, axis: int, mm: float):
        """
        +mm => toward home- => display position increases
        -mm => toward home+ => display position decreases

        Software coordinate is updated ONLY if that axis has already
        been initialized by Home+ & Set Zero.
        """
        self._validate_axis(axis)

        controller_mm = mm * self.display_to_controller_sign[axis]
        self.move_rel_mm_raw(axis, controller_mm)

        if self.software_pos_valid[axis]:
            self.software_pos_mm[axis] += mm

    # ============================================================
    # Utilities
    # ============================================================
    def set_speed(self, axis: int, slow: int, fast: int, rate: int):
        self._validate_axis(axis)
        cmd = f"D:{axis}S{slow}F{fast}R{rate}\r\n"
        with self._io_lock:
            if not self.is_connected():
                raise RuntimeError("Stage not connected")
            self.ser.write(cmd.encode())

    def home(self, axis: int, positive: bool = True):
        self._validate_axis(axis)
        direction = "+" if positive else "-"
        cmd = f"H:{axis}{direction}\r\n"
        with self._io_lock:
            if not self.is_connected():
                raise RuntimeError("Stage not connected")
            self.ser.write(cmd.encode())

    def stop(self, axis: int):
        """
        Idempotent stop:
        repeated calls should be harmless.
        """
        self._validate_axis(axis)
        cmd = f"L:{axis}\r\n"
        with self._io_lock:
            if not self.is_connected():
                raise RuntimeError("Stage not connected")
            self.ser.write(cmd.encode())

    # ============================================================
    # Wait
    # ============================================================
    def wait_until_stop(
        self,
        poll_interval: float = 0.05,
        timeout: float = 30.0,
        verbose: bool = False,
    ):
        t0 = time.time()

        while True:
            status = self.query_status()

            if verbose:
                print(f"[Stage Status] {status}")

            if status.strip().endswith("R"):
                return status

            if time.time() - t0 > timeout:
                raise TimeoutError(f"Timeout. Last status: {status}")

            time.sleep(poll_interval)

    # ============================================================
    # Software coordinate system
    # ============================================================
    def set_current_as_zero(self, axis: int):
        """
        Manual zero set.
        This also marks the axis as initialized.
        """
        self._validate_axis(axis)
        self.software_pos_mm[axis] = 0.0
        self.software_pos_valid[axis] = True

    def clear_zero(self, axis: int):
        """
        Clear initialization state for this axis.
        After this, displayed position becomes invalid again.
        """
        self._validate_axis(axis)
        self.software_pos_mm[axis] = 0.0
        self.software_pos_valid[axis] = False

    def clear_all_zero(self):
        self.software_pos_mm[1] = 0.0
        self.software_pos_mm[2] = 0.0
        self.software_pos_valid[1] = False
        self.software_pos_valid[2] = False

    def home_plus_and_set_zero(self, axis: int, verbose: bool = False):
        """
        Required initialization:
            home+ => 0 mm
        """
        self._validate_axis(axis)
        self.home(axis=axis, positive=True)
        self.wait_until_stop(verbose=verbose)
        self.software_pos_mm[axis] = 0.0
        self.software_pos_valid[axis] = True

    def home_minus(self, axis: int, verbose: bool = False):
        """
        Only after initialization is done, home- becomes a meaningful
        display coordinate = travel_mm.
        """
        self._validate_axis(axis)
        self.home(axis=axis, positive=False)
        self.wait_until_stop(verbose=verbose)

        if self.software_pos_valid[axis]:
            self.software_pos_mm[axis] = self.travel_mm

    def step_scan_mm(self, axis: int, mm: float):
        self.move_rel_mm(axis, mm)

    # ============================================================
    # Validation
    # ============================================================
    @staticmethod
    def _validate_axis(axis: int):
        if axis not in (1, 2):
            raise ValueError("Axis must be 1 or 2")