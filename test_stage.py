from stage_controller import GSC02CStage
import time


def test_axis(stage, axis):
    print(f"\n===== Testing Axis {axis} =====")

    print(f"Axis {axis} +500")
    stage.move_rel(axis=axis, steps=500)
    stage.wait_until_stop()

    time.sleep(0.5)

    print(f"Axis {axis} -500")
    stage.move_rel(axis=axis, steps=-500)
    stage.wait_until_stop()

    print(f"Axis {axis} test done.")


def main():
    stage = GSC02CStage(port="COM5")

    try:
        print("Connecting stage...")
        stage.connect()
        print("Connected.")

        print("Setting speed...")
        stage.set_speed(axis=1, slow=2000, fast=20000, rate=200)
        stage.set_speed(axis=2, slow=2000, fast=20000, rate=200)

        # 测试 Axis1
        test_axis(stage, axis=1)

        # 测试 Axis2
        test_axis(stage, axis=2)

        print("\nAll axis relative motion tests finished.")

    finally:
        stage.close()
        print("Stage closed.")


if __name__ == "__main__":
    main()