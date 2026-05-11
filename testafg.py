import pyvisa

RESOURCE = "GPIB0::11::INSTR"   # 改成你的 AFG 资源名


def main():
    rm = pyvisa.ResourceManager()
    inst = None
    try:
        inst = rm.open_resource(RESOURCE)
        inst.timeout = 1000  # ms
        inst.write_termination = "\n"
        inst.read_termination = "\n"

        print("Connected to:", RESOURCE)

        idn = inst.query("*IDN?").strip()
        print("IDN:", idn)

        # 清状态
        inst.write("*CLS")

        # 关输出
        try:
            inst.write("OUTPut1:STATe OFF")
        except Exception:
            pass
        try:
            inst.write("OUTPut2:STATe OFF")
        except Exception:
            pass

        # 关 burst
        try:
            inst.write("SOURce1:BURSt:STATe OFF")
        except Exception:
            pass
        try:
            inst.write("SOURce2:BURSt:STATe OFF")
        except Exception:
            pass

        # 触发源先切到 BUS，方便后面软件触发
        try:
            inst.write("TRIGger:SEQuence:SOURce BUS")
        except Exception:
            pass

        print("AFG recovered to safe state.")

    except Exception as e:
        print("AFG recovery failed:", e)

    finally:
        try:
            if inst is not None:
                inst.close()
        except Exception:
            pass
        try:
            rm.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()