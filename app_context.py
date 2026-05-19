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

        self.scan_progress = {
            "status": "idle",
            "current_x_mm": None,
            "current_y_mm": None,
            "current_point_index": 0,
            "completed_points": 0,
            "total_points": 0,
            "completed_captures": 0,
            "total_captures": 0,
            "current_frequency_index": 0,
            "frequency_count": 0,
            "elapsed_s": 0.0,
            "eta_s": None,
            "message": "Idle",
        }
        self.scan_progress_update_id = 0

        # software-tracked stage position in mm
        self.stage_x_mm = None
        self.stage_y_mm = None
