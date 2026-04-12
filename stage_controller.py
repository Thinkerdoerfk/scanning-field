import serial
import time
from typing import Dict, Optional


class GSC02CStage:
    """
    SIGMA KOKI GSC-02C controller for HPS80-50X-M5 stage.

    For HPS80-50X-M5:
        1 pulse = 1 um = 0.001 mm
    """

    def __init__(
        self,
        port: str = "COM5",
        baudrate: int = 9600,
        timeout: float = 2.0,
        step_to_mm: float = 0.001,
    ):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.step_to_mm = step_to_mm
        self.ser: Optional[serial.Serial] = None

    # ------------------------------------------------------------------
    # Basic connection
    # ------------------------------------------------------------------
    def connect(self) -> None:
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

    def close(self) -> None:
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
            self.ser = None

    def is_connected(self) -> bool:
        return self.ser is not None and self.ser.is_open

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------
    def _write(self, cmd: str) -> None:
        if not self.is_connected():
            raise RuntimeError("Stage not connected")
        self.ser.write(cmd.encode())

    def _readline(self) -> str:
        if not self.is_connected():
            raise RuntimeError("Stage not connected")
        return self.ser.readline().decode(errors="ignore").strip()

    def _query(self, cmd: str) -> str:
        self._write(cmd)
        return self._readline()

    # ------------------------------------------------------------------
    # Controller commands
    # ------------------------------------------------------------------
    def query_status(self) -> str:
        """
        Example returned string:
            '100,         0,K,K,R'
            '11,         0,K,K,B'
        """
        return self._query("Q:\r\n")

    def parse_status(self, status: Optional[str] = None) -> Dict[str, object]:
        """
        Parse GSC-02C status string.

        Expected format:
            axis1_pos, axis2_pos, axis1_state, axis2_state, motion_state

        Example:
            100,         0,K,K,R
        """
        if status is None:
            status = self.query_status()

        parts = [p.strip() for p in status.split(",")]

        if len(parts) < 5:
            raise ValueError(f"Unexpected status format: {status}")

        return {
            "axis1_pos": int(parts[0]),
            "axis2_pos": int(parts[1]),
            "axis1_state": parts[2],
            "axis2_state": parts[3],
            "motion_state": parts[4],   # B = Busy, R = Ready
            "raw": status,
        }

    def set_speed(self, axis: int, slow: int, fast: int, rate: int) -> None:
        """
        axis: 1 or 2
        """
        self._validate_axis(axis)
        cmd = f"D:{axis}S{slow}F{fast}R{rate}\r\n"
        self._write(cmd)

    def home(self, axis: int, positive: bool = True) -> None:
        """
        Return to origin.
        """
        self._validate_axis(axis)
        direction = "+" if positive else "-"
        cmd = f"H:{axis}{direction}\r\n"
        self._write(cmd)

    def stop(self, axis: int) -> None:
        self._validate_axis(axis)
        cmd = f"L:{axis}\r\n"
        self._write(cmd)

    # ------------------------------------------------------------------
    # Pulse-based motion
    # ------------------------------------------------------------------
    def move_rel(self, axis: int, steps: int) -> None:
        """
        Relative move in pulses.
        """
        self._validate_axis(axis)

        if steps == 0:
            return

        direction = "+" if steps > 0 else "-"
        steps_abs = abs(steps)

        cmd = f"M:{axis}{direction}P{steps_abs}\r\n"
        self._write(cmd)
        self._write("G:\r\n")

    def move_abs(self, axis: int, steps: int) -> None:
        """
        Absolute move in pulses.
        """
        self._validate_axis(axis)

        direction = "+" if steps >= 0 else "-"
        steps_abs = abs(steps)

        cmd = f"A:{axis}{direction}P{steps_abs}\r\n"
        self._write(cmd)
        self._write("G:\r\n")

    # ------------------------------------------------------------------
    # mm-based motion
    # ------------------------------------------------------------------
    def mm_to_steps(self, mm: float) -> int:
        return int(round(mm / self.step_to_mm))

    def steps_to_mm(self, steps: int) -> float:
        return steps * self.step_to_mm

    def move_rel_mm(self, axis: int, mm: float) -> None:
        steps = self.mm_to_steps(mm)
        self.move_rel(axis, steps)

    def move_abs_mm(self, axis: int, mm: float) -> None:
        steps = self.mm_to_steps(mm)
        self.move_abs(axis, steps)

    def get_position_steps(self) -> Dict[str, int]:
        info = self.parse_status()
        return {
            "axis1": info["axis1_pos"],
            "axis2": info["axis2_pos"],
        }

    def get_position_mm(self) -> Dict[str, float]:
        pos = self.get_position_steps()
        return {
            "axis1": self.steps_to_mm(pos["axis1"]),
            "axis2": self.steps_to_mm(pos["axis2"]),
        }

    # ------------------------------------------------------------------
    # Motion wait
    # ------------------------------------------------------------------
    def wait_until_stop(self, poll_interval=0.05, timeout=30.0, verbose=True):
        t0 = time.time()

        while True:
            status = self.query_status()

            if verbose:
                print(f"[Stage Status] {status}")

            # 关键：用 endswith 判断（最稳）
            if status.strip().endswith("R"):
                return status

            if time.time() - t0 > timeout:
                raise TimeoutError(f"Stage motion timeout. Last status: {status}")

            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_axis(axis: int) -> None:
        if axis not in (1, 2):
            raise ValueError("Axis must be 1 or 2")