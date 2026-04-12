from stage_controller import GSC02CStage
from afg_controller import TekAFG3022B
from pico_controller import PicoScope5442D
from scan_controller import ScanController


def main():
    # ========= 1. 基本配置 =========
    stage_port = "COM5"
    afg_resource = "GPIB0::11::INSTR"   # 改成你的实际GPIB地址

    # 扫描参数
    xs = [0, 100, 200]
    ys = [0, 100]

    # AFG参数
    afg_channel = 1
    afg_freq_hz = 2e6
    afg_vpp = 2.0
    afg_cycles = 10

    # Pico参数
    pico_channel = "A"
    pico_range = "PS5000A_5V"
    pico_coupling = "PS5000A_DC"
    pico_trigger_threshold_mv = 500
    pico_pre_trigger_samples = 500
    pico_post_trigger_samples = 1500
    pico_timebase = 4

    # 位移台速度
    stage_slow = 2000
    stage_fast = 20000
    stage_rate = 200

    # ========= 2. 创建设备对象 =========
    stage = GSC02CStage(port=stage_port)
    afg = TekAFG3022B(resource_name=afg_resource)
    pico = PicoScope5442D()

    try:
        # ========= 3. 连接位移台 =========
        print("Connecting stage...")
        stage.connect()
        print("Stage connected.")

        print("Setting stage speed...")
        stage.set_speed(axis=1, slow=stage_slow, fast=stage_fast, rate=stage_rate)
        stage.set_speed(axis=2, slow=stage_slow, fast=stage_fast, rate=stage_rate)
        print("Stage speed set.")

        # ========= 4. 连接AFG =========
        print("Connecting AFG...")
        idn = afg.connect()
        print("AFG ID:", idn)

        print("Configuring AFG burst...")
        afg.configure_burst(
            ch=afg_channel,
            freq_hz=afg_freq_hz,
            vpp=afg_vpp,
            cycles=afg_cycles
        )
        print("AFG configured.")

        # ========= 5. 连接Pico =========
        print("Connecting Pico...")
        print(pico.connect())

        print("Configuring Pico channel...")
        pico.configure_channel(
            channel=pico_channel,
            vrange=pico_range,
            coupling=pico_coupling,
            offset_v=0.0,
            enabled=True
        )

        print("Configuring Pico trigger...")
        pico.configure_trigger(
            threshold_mv=pico_trigger_threshold_mv,
            direction="RISING",
            auto_trigger_ms=1000,
            enabled=True
        )

        print("Configuring Pico block acquisition...")
        pico.configure_block(
            pre_trigger_samples=pico_pre_trigger_samples,
            post_trigger_samples=pico_post_trigger_samples,
            timebase=pico_timebase
        )
        print("Pico configured.")

        # ========= 6. 创建扫描器 =========
        scanner = ScanController(
            stage=stage,
            afg=afg,
            pico=pico,
            save_dir="results"
        )

        # ========= 7. 先做单点测试 =========
        print("\n===== Single-point test =====")
        scanner.acquire_point(x_step=0, y_step=0)

        # ========= 8. 再做二维扫描 =========
        print("\n===== Start raster scan =====")
        scanner.raster_scan(xs=xs, ys=ys, snake=True)

        print("\nScan finished successfully.")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        raise

    finally:
        print("\nClosing devices...")
        try:
            pico.close()
        except Exception as e:
            print("Error closing Pico:", e)

        try:
            afg.close()
        except Exception as e:
            print("Error closing AFG:", e)

        try:
            stage.close()
        except Exception as e:
            print("Error closing Stage:", e)

        print("All devices closed.")


if __name__ == "__main__":
    main()