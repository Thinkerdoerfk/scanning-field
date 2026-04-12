import serial
import time


class GSC02CStage:
    def __init__(self, port='COM5', baudrate=9600, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None

    def connect(self):
        self.ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
            rtscts=True
        )
        time.sleep(0.2)

    def close(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()

    def _write(self, cmd: str):
        if self.ser is None:
            raise RuntimeError("Stage not connected")
        self.ser.write(cmd.encode())

    def _readline(self) -> str:
        if self.ser is None:
            raise RuntimeError("Stage not connected")
        return self.ser.readline().decode(errors='ignore').strip()

    def query_status(self) -> str:
        self._write('Q:\r\n')
        return self._readline()

    def set_speed(self, axis: int, slow: int, fast: int, rate: int):
        cmd = f'D:{axis}S{slow}F{fast}R{rate}\r\n'
        self._write(cmd)

    def home(self, axis: int, positive=True):
        direction = '+' if positive else '-'
        cmd = f'H:{axis}{direction}\r\n'
        self._write(cmd)

    def move_rel(self, axis: int, steps: int):
        if steps == 0:
            return
        direction = '+' if steps > 0 else '-'
        steps_abs = abs(steps)
        cmd = f'M:{axis}{direction}P{steps_abs}\r\n'
        self._write(cmd)
        self._write('G:\r\n')

    def move_abs(self, axis: int, steps: int):
        direction = '+' if steps >= 0 else '-'
        steps_abs = abs(steps)
        cmd = f'A:{axis}{direction}P{steps_abs}\r\n'
        self._write(cmd)
        self._write('G:\r\n')

    def stop(self, axis: int):
        cmd = f'L:{axis}\r\n'
        self._write(cmd)

    def wait_until_stop(self, poll_interval=0.05, timeout=30):
        """
        这里先用一个保守占位逻辑。
        后面你把 Q: 的实际返回格式补齐后，再把这个判断改精确。
        """
        t0 = time.time()
        last = ""
        stable_count = 0

        while True:
            status = self.query_status()
            print(f"[Stage Status] {status}")

            if status == last and status != "":
                stable_count += 1
            else:
                stable_count = 0

            last = status

            if stable_count >= 3:
                return status

            if time.time() - t0 > timeout:
                raise TimeoutError(f"Stage motion timeout. Last status: {status}")

            time.sleep(poll_interval)