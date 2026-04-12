from stage_controller import GSC02CStage
import time


def test_axis_mm(stage, axis):
    print(f"\n===== Testing Axis {axis} (±5 mm) =====")

    print(f"Axis {axis} +5 mm")
    stage.move_rel_mm(axis=axis, mm=5.0)
    stage.wait_until_stop()

    time.sleep(0.5)

    print(f"Axis {axis} -5 mm")
    stage.move_rel_mm(axis=axis, mm=-5.0)
    stage.wait_until_stop()

    print(f"Axis {axis} ±5 mm test done.")


def main():
    stage = GSC02CStage(port="COM5")

    try:
        print("Connecting stage...")
        stage.connect()
        print("Connected.")

        print("Setting speed...")
        stage.set_speed(axis=1, slow=500, fast=1000, rate=100)
        stage.set_speed(axis=2, slow=500, fast=1000, rate=100)

        # 测试 Axis 1
        test_axis_mm(stage, axis=1)

        # 测试 Axis 2
        test_axis_mm(stage, axis=2)

        print("\nAll mm motion tests finished.")

    finally:
        stage.close()
        print("Stage closed.")


if __name__ == "__main__":
    main()