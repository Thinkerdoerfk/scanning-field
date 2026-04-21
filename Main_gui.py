import tkinter as tk
from tkinter import ttk

from app_context import AppContext
from gui_log_panel import LogPanel
from gui_stage_panel import StagePanel
from gui_afg_panel import AFGPanel
from gui_pico_panel import PicoPanel
from gui_scan_panel import ScanPanel


class MainGUIApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Scanning Field Control Panel")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        w = min(1120, screen_w - 80)
        h = min(800, screen_h - 100)

        self.root.geometry(f"{w}x{h}")

        self.ctx = AppContext()

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=0)  # 左边相对固定
        main.grid_columnconfigure(1, weight=1)  # 右边优先扩展

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="ns")

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self.log_panel = LogPanel(left)
        self.stage_panel = StagePanel(left, self.ctx, self.log_panel.log)

        self.afg_panel = AFGPanel(right, self.ctx, self.log_panel.log)
        self.scan_panel = ScanPanel(right, self.ctx, self.log_panel.log)
        self.pico_panel = PicoPanel(right, self.ctx, self.log_panel.log)
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
    app = MainGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()