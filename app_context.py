class AppContext:
    def __init__(self):
        self.stage = None
        self.afg = None
        self.pico = None

        self.stage_connected = False
        self.afg_connected = False
        self.pico_connected = False

        self.stage_busy = False
        self.scan_stop_requested = False

        self.last_pico_time = None
        self.last_pico_signals = None
        self.last_pico_meta = None
        self.last_pico_update_id = 1

        # software-tracked stage position in mm
        self.stage_x_mm = None
        self.stage_y_mm = None