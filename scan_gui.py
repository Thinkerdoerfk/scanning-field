import tkinter as tk
from tkinter import ttk

from app_context import AppContext
from gui_log_panel import LogPanel
from gui_stage_panel import StagePanel
from gui_afg_panel import AFGPanel
from gui_pico_panel import PicoPanel
from gui_scan_panel import ScanPanel


class ScanGUIApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scanning Field Control Panel")
        self.root.geometry("1120x800")

        self.ctx = AppContext()

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        left = ttk.Frame(main)
        left.pack(side="left", fill="both", expand=False, padx=(0, 10))

        right = ttk.Frame(main)
        right.pack(side="left", fill="both", expand=True)

        self.log_panel = LogPanel(left)
        self.stage_panel = StagePanel(left, self.ctx, self.log_panel.log)

        self.afg_panel = AFGPanel(right, self.ctx, self.log_panel.log)
        self.pico_panel = PicoPanel(right, self.ctx, self.log_panel.log)
        self.scan_panel = ScanPanel(right, self.ctx, self.log_panel.log)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        try:
            if self.ctx.afg is not None:
                try:
                    self.ctx.afg.output_off()
                except Exception:
                    pass
                try:
                    self.ctx.afg.close()
                except Exception:
                    pass

            if self.ctx.pico is not None:
                try:
                    self.ctx.pico.close()
                except Exception:
                    pass

            if self.ctx.stage is not None:
                try:
                    self.ctx.stage.stop()
                except Exception:
                    pass
                try:
                    self.ctx.stage.close()
                except Exception:
                    pass
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = ScanGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()