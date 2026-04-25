r"""
labjack_stage_controller.py

Python controller for a Thorlabs Kinesis LabJack / Integrated Stepper Motor device.
This file is translated from the provided MATLAB files:
  - connect_labjack.m
  - test_labjack_relative_move.m
  - disconnect_labjack.m

Requirements on the control PC:
  1) Windows
  2) Thorlabs Kinesis installed, default path:
       C:\Program Files\Thorlabs\Kinesis
  3) Python package:
       pip install pythonnet

Typical use:
    # Human-friendly millimetre mode, recommended after confirming direction:
    python labjack_stage_controller.py --mm 1
    python labjack_stage_controller.py --mm -1

    # Low-level device-count mode, same as the MATLAB relStep:
    python labjack_stage_controller.py --step-counts 100
    python labjack_stage_controller.py --home --step-counts 100
    python labjack_stage_controller.py --serial 49176874 --step-counts -5000

Important:
  - --mm uses the Kinesis real-unit API: MoveRelative(MotorDirection, Decimal mm, Int32 timeout).
  - --step-counts uses DEVICE COUNTS, exactly like the MATLAB relStep.
  - Positive/negative direction depends on your LabJack/stage mechanical setup.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Optional


DEFAULT_KINESIS_DIR = r"C:\Program Files\Thorlabs\Kinesis"


@dataclass
class MoveResult:
    pos_before: int
    pos_after_home: Optional[int]
    pos_after_move: int
    delta_move: int
    method_used: str


class LabJackStageController:
    """Small Python wrapper around Thorlabs Kinesis LabJack .NET API."""

    def __init__(
        self,
        serial_no: Optional[str] = None,
        kinesis_dir: str = DEFAULT_KINESIS_DIR,
        polling_ms: int = 250,
        verbose: bool = True,
    ) -> None:
        self.serial_no = serial_no or ""
        self.kinesis_dir = kinesis_dir
        self.polling_ms = int(polling_ms)
        self.verbose = bool(verbose)

        self.device: Any = None
        self.DM: Any = None

        self._load_kinesis_assemblies()

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    @staticmethod
    def _dotnet_list_get(dotnet_list: Any, index: int) -> Any:
        """Get an item from a .NET list in a way that works across pythonnet versions."""
        try:
            return dotnet_list[index]
        except Exception:
            return dotnet_list.Item[index]

    @staticmethod
    def _int32(value: int) -> Any:
        """Convert a Python int to System.Int32 for Kinesis overloaded .NET methods."""
        from System import Int32  # type: ignore
        return Int32(int(value))

    @staticmethod
    def _uint32(value: int) -> Any:
        """Convert a non-negative Python int to System.UInt32 for Kinesis device-unit step sizes."""
        from System import UInt32  # type: ignore
        value = int(value)
        if value < 0:
            raise ValueError("System.UInt32 cannot be negative.")
        return UInt32(value)

    @staticmethod
    def _decimal(value: float) -> Any:
        """Convert a Python float to System.Decimal for Kinesis real-unit methods."""
        from System import Decimal  # type: ignore
        from System.Globalization import CultureInfo  # type: ignore
        return Decimal.Parse(str(float(value)), CultureInfo.InvariantCulture)

    @staticmethod
    def _to_float(value: Any) -> float:
        """Convert Python/.NET numeric values, including System.Decimal, to Python float."""
        try:
            return float(value)
        except TypeError:
            from System import Convert  # type: ignore
            return float(Convert.ToDouble(value))

    @staticmethod
    def _get_motor_direction(step_counts: int) -> Optional[Any]:
        """Return a Kinesis MotorDirection enum if it is available in this Kinesis version."""
        try:
            from Thorlabs.MotionControl.GenericMotorCLI import MotorDirection  # type: ignore
        except Exception:
            return None

        names = (
            ("Forward", "Backward"),
            ("Forward", "Reverse"),
            ("Forwards", "Backwards"),
            ("Positive", "Negative"),
            ("Clockwise", "AntiClockwise"),
            ("Clockwise", "CounterClockwise"),
        )
        for positive_name, negative_name in names:
            try:
                return getattr(MotorDirection, positive_name) if step_counts >= 0 else getattr(MotorDirection, negative_name)
            except Exception:
                continue
        return None

    def _load_kinesis_assemblies(self) -> None:
        """Load the same Kinesis DLLs used in the MATLAB code."""
        try:
            import clr  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "pythonnet is not installed. Install it with: pip install pythonnet"
            ) from exc

        if not os.path.isdir(self.kinesis_dir):
            raise FileNotFoundError(
                f"Kinesis folder not found: {self.kinesis_dir}\n"
                "Install Thorlabs Kinesis or pass --kinesis-dir with the correct path."
            )

        dlls = [
            "Thorlabs.MotionControl.DeviceManagerCLI.dll",
            "Thorlabs.MotionControl.GenericMotorCLI.dll",
            "Thorlabs.MotionControl.IntegratedStepperMotorsCLI.dll",
        ]

        for dll in dlls:
            path = os.path.join(self.kinesis_dir, dll)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Required Kinesis DLL not found: {path}")
            clr.AddReference(path)

    def _import_kinesis_types(self) -> None:
        """Import .NET namespaces after DLLs are loaded."""
        # Imports must happen after clr.AddReference().
        from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI  # type: ignore
        from Thorlabs.MotionControl.IntegratedStepperMotorsCLI import LabJack  # type: ignore

        self._DeviceManagerCLI = DeviceManagerCLI
        self._LabJack = LabJack

    def connect(self) -> str:
        """
        Connect and enable the LabJack device.

        This follows the MATLAB sequence:
          BuildDeviceList -> CreateLabJack -> ClearDeviceExceptions
          -> ConnectDevice -> Connect -> WaitForSettingsInitialized
          -> StartPolling -> EnableDevice -> LoadMotorConfiguration
        """
        self._import_kinesis_types()

        self.DM = self._DeviceManagerCLI
        self.DM.BuildDeviceList()
        device_list = self.DM.GetDeviceList()

        if int(device_list.Count) < 1:
            raise RuntimeError("No Kinesis device found in the device list.")

        if not self.serial_no:
            self.serial_no = str(self._dotnet_list_get(device_list, 0))
        else:
            found = False
            for k in range(int(device_list.Count)):
                if str(self._dotnet_list_get(device_list, k)) == self.serial_no:
                    found = True
                    break
            if not found:
                available = [str(self._dotnet_list_get(device_list, k)) for k in range(int(device_list.Count))]
                raise RuntimeError(
                    f"Requested serial number {self.serial_no} not found. "
                    f"Available devices: {available}"
                )

        self.log(f"Connecting to device: {self.serial_no}")

        self.device = self._LabJack.CreateLabJack(self.serial_no)

        # Same working sequence as MATLAB.
        self.device.ClearDeviceExceptions()
        self.device.ConnectDevice(self.serial_no)
        self.device.Connect(self.serial_no)
        time.sleep(1.0)

        if not bool(self.device.IsSettingsInitialized()):
            self.log("Waiting for settings initialization...")
            self.device.WaitForSettingsInitialized(5000)

        self.device.StartPolling(self.polling_ms)
        time.sleep(0.5)

        self.device.EnableDevice()
        time.sleep(0.5)

        self.device.LoadMotorConfiguration(self.serial_no)
        time.sleep(0.5)

        self.log("Connected and enabled successfully.")
        return self.serial_no

    def disconnect(self) -> bool:
        """Safely stop polling, disconnect, dispose, and check if the device is visible again."""
        self.log("Disconnecting safely...")

        if self.device is not None:
            for name in ("StopPolling", "Disconnect", "Dispose"):
                try:
                    getattr(self.device, name)()
                    self.log(f"{name}() done.")
                except Exception as exc:
                    self.log(f"{name}() skipped/failed: {exc}")

        self.device = None
        time.sleep(1.0)

        released = False
        try:
            self.DM.BuildDeviceList()
            device_list = self.DM.GetDeviceList()
            for k in range(int(device_list.Count)):
                sn = str(self._dotnet_list_get(device_list, k))
                self.log(f"Available device {k}: {sn}")
                if self.serial_no and sn == self.serial_no:
                    released = True

            if released:
                self.log("Device released successfully and available again.")
            else:
                self.log("Device not visible in available device list after disconnect.")
        except Exception as exc:
            self.log(f"Post-disconnect check failed: {exc}")

        return released

    def _require_device(self) -> None:
        if self.device is None:
            raise RuntimeError("Device is not connected. Call connect() first.")

    def get_position_counts(self, request_delay_s: float = 0.2) -> int:
        """Read current position counter in device counts."""
        self._require_device()
        self.device.RequestPosition()
        time.sleep(float(request_delay_s))
        return int(self.device.GetPositionCounter())

    def get_position_mm(self, request_delay_s: float = 0.2) -> float:
        """Read current position in Kinesis real units. For a linear LabJack stage, this is normally mm."""
        self._require_device()
        self.device.RequestPosition()
        time.sleep(float(request_delay_s))
        try:
            return self._to_float(self.device.Position)
        except Exception:
            return self._to_float(self.device.get_Position())

    def home(self, timeout_ms: int = 60000, settle_s: float = 2.0) -> int:
        """Send HOME command and return the position counter after homing."""
        self._require_device()
        self.log("Sending HOME command...")
        self.device.Home(int(timeout_ms))
        time.sleep(float(settle_s))
        pos = self.get_position_counts()
        self.log(f"Position after home = {pos}")
        return pos

    def move_relative_mm(
        self,
        distance_mm: float,
        settle_s: float = 2.0,
        timeout_ms: int = 60000,
        counts_per_mm: Optional[float] = None,
    ) -> tuple[float, str]:
        """
        Move relatively in millimetres.

        Preferred Kinesis signature found by reflection:
        - MoveRelative(MotorDirection, Decimal stepSize, Int32 waitTimeout)

        If that real-unit method fails, and counts_per_mm is provided, this falls back
        to move_relative_counts(round(distance_mm * counts_per_mm)).
        """
        self._require_device()
        distance_mm = float(distance_mm)
        timeout_i32 = self._int32(int(timeout_ms))

        self.log(f"Sending relative move distance = {distance_mm:g} mm")

        if abs(distance_mm) < 1e-15:
            self.log("Distance is 0 mm, no movement requested.")
            return self.get_position_mm(), "No movement"

        errors: list[str] = []

        def finish(method: str) -> tuple[float, str]:
            self.log(f"Used {method}")
            time.sleep(float(settle_s))
            return self.get_position_mm(), method

        direction = self._get_motor_direction(1 if distance_mm >= 0 else -1)
        if direction is not None:
            try:
                step_decimal = self._decimal(abs(distance_mm))
                self.device.MoveRelative(direction, step_decimal, timeout_i32)
                return finish("MoveRelative(MotorDirection, Decimal mm, Int32 timeout)")
            except Exception as exc:
                errors.append(f"MoveRelative(direction, Decimal mm, timeout) failed: {exc}")
                self.log(errors[-1])
        else:
            errors.append("MotorDirection enum was not found; skipped real-unit relative move.")
            self.log(errors[-1])

        if counts_per_mm is not None:
            try:
                step_counts = int(round(distance_mm * float(counts_per_mm)))
                self.log(
                    f"Falling back to device counts: {distance_mm:g} mm * "
                    f"{float(counts_per_mm):g} counts/mm = {step_counts} counts"
                )
                self.move_relative_counts(step_counts, settle_s=settle_s, timeout_ms=timeout_ms)
                return self.get_position_mm(), "move_relative_counts(round(mm * counts_per_mm)) fallback"
            except Exception as exc:
                errors.append(f"counts_per_mm fallback failed: {exc}")
                self.log(errors[-1])

        raise RuntimeError(
            "Could not move in mm. Try providing --counts-per-mm, or test low-level --step-counts.\n"
            + "\n".join(errors)
        )

    def move_relative_counts(
        self,
        step_counts: int,
        settle_s: float = 2.0,
        timeout_ms: int = 60000,
    ) -> tuple[int, str]:
        """
        Move relatively in device counts.

        The reflected Kinesis signatures for this LabJack are:
        - MoveRelative_DeviceUnit(MotorDirection, UInt32 stepSize, Int32 waitTimeout)
        - SetMoveRelativeDistance_DeviceUnit(Int32 distance) + MoveRelative(Int32 waitTimeout)
        """
        self._require_device()
        step_counts = int(step_counts)
        timeout_ms = int(timeout_ms)

        step_i32 = self._int32(step_counts)
        abs_step_u32 = self._uint32(abs(step_counts))
        timeout_i32 = self._int32(timeout_ms)

        self.log(f"Sending relative move step = {step_counts} counts")

        if step_counts == 0:
            self.log("Step is 0, no movement requested.")
            return self.get_position_counts(), "No movement"

        errors: list[str] = []

        def finish(method: str) -> tuple[int, str]:
            self.log(f"Used {method}")
            time.sleep(float(settle_s))
            return self.get_position_counts(), method

        # Preferred exact signature found by reflection:
        # MoveRelative_DeviceUnit(direction: MotorDirection, stepSize: UInt32, waitTimeout: Int32)
        direction = self._get_motor_direction(step_counts)
        if direction is not None:
            try:
                self.device.MoveRelative_DeviceUnit(direction, abs_step_u32, timeout_i32)
                return finish("MoveRelative_DeviceUnit(MotorDirection, UInt32 abs_step, Int32 timeout)")
            except Exception as exc:
                errors.append(f"MoveRelative_DeviceUnit(direction, UInt32 abs_step, timeout) failed: {exc}")
                self.log(errors[-1])
        else:
            errors.append("MotorDirection enum was not found; skipped direction-based move signature.")
            self.log(errors[-1])

        # MATLAB-style two-step signature:
        # SetMoveRelativeDistance_DeviceUnit(distance: Int32), then MoveRelative(waitTimeout: Int32)
        try:
            self.device.SetMoveRelativeDistance_DeviceUnit(step_i32)
            self.device.MoveRelative(timeout_i32)
            return finish("SetMoveRelativeDistance_DeviceUnit(Int32 step) + MoveRelative(Int32 timeout)")
        except Exception as exc:
            errors.append(f"SetMoveRelativeDistance_DeviceUnit + MoveRelative(timeout) failed: {exc}")
            self.log(errors[-1])

        # Safe fallback: convert relative move to absolute target = current + step.
        try:
            current = self.get_position_counts(request_delay_s=0.05)
            target = self._int32(current + step_counts)
            self.device.MoveTo_DeviceUnit(target, timeout_i32)
            return finish("MoveTo_DeviceUnit(current + step, Int32 timeout)")
        except Exception as exc:
            errors.append(f"MoveTo_DeviceUnit(current + step, timeout) failed: {exc}")
            self.log(errors[-1])

        raise RuntimeError("Could not find a working relative move signature.\n" + "\n".join(errors))

    def test_relative_move(self, do_home: bool = False, rel_step: int = 10, timeout_ms: int = 60000) -> MoveResult:
        """Python equivalent of test_labjack_relative_move.m."""
        pos0 = self.get_position_counts()
        self.log(f"Current position counter = {pos0}")

        pos_home: Optional[int] = None
        if do_home:
            pos_home = self.home()

        pos_move, method = self.move_relative_counts(rel_step, timeout_ms=timeout_ms)
        delta = int(pos_move - pos0)

        self.log(f"Position after relative move = {pos_move}")
        self.log(f"Measured delta = {delta} counts")

        return MoveResult(
            pos_before=pos0,
            pos_after_home=pos_home,
            pos_after_move=pos_move,
            delta_move=delta,
            method_used=method,
        )

    def test_relative_move_mm(
        self,
        do_home: bool = False,
        rel_mm: float = 1.0,
        timeout_ms: int = 60000,
        counts_per_mm: Optional[float] = None,
    ) -> dict[str, Any]:
        """Human-friendly relative move test in millimetres."""
        pos0_mm = self.get_position_mm()
        pos0_counts = self.get_position_counts(request_delay_s=0.05)
        self.log(f"Current position = {pos0_mm:g} mm")
        self.log(f"Current position counter = {pos0_counts}")

        pos_home_counts: Optional[int] = None
        if do_home:
            pos_home_counts = self.home(timeout_ms=timeout_ms)

        pos1_mm, method = self.move_relative_mm(
            rel_mm,
            timeout_ms=timeout_ms,
            counts_per_mm=counts_per_mm,
        )
        pos1_counts = self.get_position_counts(request_delay_s=0.05)

        self.log(f"Position after relative move = {pos1_mm:g} mm")
        self.log(f"Position counter after relative move = {pos1_counts}")
        self.log(f"Measured delta = {pos1_mm - pos0_mm:g} mm")
        self.log(f"Measured counter delta = {pos1_counts - pos0_counts} counts")

        return {
            "pos_before_mm": pos0_mm,
            "pos_after_home_counts": pos_home_counts,
            "pos_after_move_mm": pos1_mm,
            "delta_move_mm": pos1_mm - pos0_mm,
            "pos_before_counts": pos0_counts,
            "pos_after_move_counts": pos1_counts,
            "delta_move_counts": pos1_counts - pos0_counts,
            "method_used": method,
        }

    def __enter__(self) -> "LabJackStageController":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Control a Thorlabs Kinesis LabJack stage from Python.")
    parser.add_argument("--serial", default="", help="Device serial number. If omitted, use first Kinesis device.")
    parser.add_argument("--kinesis-dir", default=DEFAULT_KINESIS_DIR, help="Thorlabs Kinesis install folder.")
    parser.add_argument("--mm", type=float, default=None, help="Relative move distance in millimetres, e.g. --mm 1 or --mm -0.5.")
    parser.add_argument("--step-counts", "--step", dest="step_counts", type=int, default=None, help="Low-level relative move step in device counts. --step is kept as an alias.")
    parser.add_argument("--counts-per-mm", type=float, default=None, help="Optional fallback conversion if Kinesis real-unit mm movement fails.")
    parser.add_argument("--home", action="store_true", help="Home before relative move.")
    parser.add_argument("--polling-ms", type=int, default=250, help="Kinesis polling interval in ms.")
    parser.add_argument("--timeout-ms", type=int, default=60000, help="Move timeout in ms.")
    args = parser.parse_args()

    ctrl = LabJackStageController(
        serial_no=args.serial,
        kinesis_dir=args.kinesis_dir,
        polling_ms=args.polling_ms,
        verbose=True,
    )

    try:
        ctrl.connect()
        if args.mm is not None:
            result = ctrl.test_relative_move_mm(
                do_home=args.home,
                rel_mm=args.mm,
                timeout_ms=args.timeout_ms,
                counts_per_mm=args.counts_per_mm,
            )
        else:
            # Backward-compatible default: if no --mm is given, use device-count mode.
            step_counts = 10 if args.step_counts is None else int(args.step_counts)
            result = ctrl.test_relative_move(do_home=args.home, rel_step=step_counts, timeout_ms=args.timeout_ms)
        print("\nResult:")
        print(result)
    finally:
        ctrl.disconnect()


if __name__ == "__main__":
    if os.name != "nt":
        print("Warning: Thorlabs Kinesis .NET control normally works on Windows only.", file=sys.stderr)
    main()
