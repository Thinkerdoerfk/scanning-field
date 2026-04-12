import pyvisa


class TekAFG3022B:
    def __init__(self, resource_name: str):
        self.resource_name = resource_name
        self.rm = None
        self.inst = None

    def connect(self):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.resource_name)
        self.inst.timeout = 5000
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'
        return self.query("*IDN?").strip()

    def close(self):
        if self.inst is not None:
            self.inst.close()
            self.inst = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None

    def write(self, cmd: str):
        if self.inst is None:
            raise RuntimeError("AFG not connected")
        self.inst.write(cmd)

    def query(self, cmd: str) -> str:
        if self.inst is None:
            raise RuntimeError("AFG not connected")
        return self.inst.query(cmd)

    def configure_burst(self, ch: int = 1, freq_hz: float = 2e6, vpp: float = 2.0, cycles: int = 10):
        self.write("*CLS")
        self.write(f"SOUR{ch}:FUNC SIN")
        self.write(f"SOUR{ch}:FREQ {freq_hz}")
        self.write(f"SOUR{ch}:VOLT {vpp}")
        self.write(f"SOUR{ch}:BURS:STAT ON")
        self.write(f"SOUR{ch}:BURS:NCYC {cycles}")
        self.write("TRIG:SOUR BUS")
        self.write(f"OUTP{ch} ON")

    def trigger(self):
        self.write("*TRG")

    def output_on(self, ch: int = 1):
        self.write(f"OUTP{ch} ON")

    def output_off(self, ch: int = 1):
        self.write(f"OUTP{ch} OFF")