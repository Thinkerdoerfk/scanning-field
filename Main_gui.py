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
        self._configure_theme()

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        w = min(1500, screen_w - 80)
        h = min(900, screen_h - 100)

        self.root.geometry(f"{w}x{h}")
        self.root.minsize(900, 620)

        self.ctx = AppContext()

        main = self._build_scrollable_main(root)

        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=0)  # 左边相对固定
        main.grid_columnconfigure(1, weight=1)  # 右边优先扩展

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_rowconfigure(0, weight=0)
        left.grid_rowconfigure(1, weight=0)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_rowconfigure(0, weight=0)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        left_afg = ttk.Frame(left)
        left_afg.grid(row=0, column=0, sticky="ew")
        left_stage = ttk.Frame(left)
        left_stage.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        left_log = ttk.Frame(left)
        left_log.grid(row=2, column=0, sticky="nsew", pady=(8, 0))

        self.log_panel = LogPanel(left_log, height=8)
        self.afg_panel = AFGPanel(left_afg, self.ctx, self.log_panel.log)
        self.stage_panel = StagePanel(left_stage, self.ctx, self.log_panel.log)

        self.scan_panel = ScanPanel(right, self.ctx, self.log_panel.log)
        self.pico_panel = PicoPanel(right, self.ctx, self.log_panel.log)
        self.ctx.scan_panel = self.scan_panel
        self.ctx.pico_panel = self.pico_panel
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_scrollable_main(self, root):
        viewport = ttk.Frame(root)
        viewport.pack(fill="both", expand=True)
        viewport.rowconfigure(0, weight=1)
        viewport.columnconfigure(0, weight=1)

        self.main_canvas = tk.Canvas(
            viewport,
            bg=self.colors["app_bg"],
            highlightthickness=0,
            borderwidth=0,
        )
        yscroll = ttk.Scrollbar(viewport, orient="vertical", command=self.main_canvas.yview)
        xscroll = ttk.Scrollbar(viewport, orient="horizontal", command=self.main_canvas.xview)
        self.main_canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        self.main_canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        main = ttk.Frame(self.main_canvas, padding=10)
        self.main_canvas_window = self.main_canvas.create_window((0, 0), window=main, anchor="nw")

        def _update_scrollregion(_event=None):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def _fit_width(event):
            requested = main.winfo_reqwidth()
            self.main_canvas.itemconfigure(self.main_canvas_window, width=max(requested, event.width))
            _update_scrollregion()

        def _wheel(event):
            if event.state & 0x0001:
                self.main_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        main.bind("<Configure>", _update_scrollregion)
        self.main_canvas.bind("<Configure>", _fit_width)
        self.main_canvas.bind_all("<MouseWheel>", _wheel)
        return main

    def _configure_theme(self):
        self.colors = {
            "app_bg": "#eaf0f6",
            "panel_bg": "#f8fafc",
            "panel_border": "#b7c6d8",
            "text": "#17202a",
            "muted": "#536579",
            "accent": "#2563a9",
            "accent_hover": "#1f528c",
            "entry_bg": "#ffffff",
            "disabled_bg": "#d8e1eb",
        }

        self.root.configure(bg=self.colors["app_bg"])

        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("Segoe UI", 9), background=self.colors["app_bg"], foreground=self.colors["text"])
        style.configure("TFrame", background=self.colors["app_bg"])
        style.configure("TLabel", background=self.colors["app_bg"], foreground=self.colors["text"])
        style.configure("TLabelFrame", background=self.colors["panel_bg"], bordercolor=self.colors["panel_border"])
        style.configure(
            "TLabelFrame.Label",
            background=self.colors["app_bg"],
            foreground=self.colors["accent"],
            font=("Segoe UI", 9, "bold"),
        )
        style.configure("TLabelframe", background=self.colors["panel_bg"])
        style.configure("TLabelframe.Label", background=self.colors["app_bg"], foreground=self.colors["accent"])

        style.configure(
            "TButton",
            background="#edf4fb",
            foreground=self.colors["text"],
            bordercolor="#9db2c8",
            focusthickness=1,
            focuscolor=self.colors["accent"],
            padding=(6, 3),
        )
        style.map(
            "TButton",
            background=[
                ("active", "#dcecfb"),
                ("pressed", "#cfe3f6"),
                ("disabled", self.colors["disabled_bg"]),
            ],
            foreground=[("disabled", "#7d8b99")],
        )

        style.configure(
            "TEntry",
            fieldbackground=self.colors["entry_bg"],
            background=self.colors["entry_bg"],
            foreground=self.colors["text"],
            insertcolor=self.colors["text"],
            bordercolor="#9db2c8",
        )
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["entry_bg"],
            background="#edf4fb",
            foreground=self.colors["text"],
            arrowcolor=self.colors["accent"],
            bordercolor="#9db2c8",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.colors["entry_bg"]), ("disabled", self.colors["disabled_bg"])],
            foreground=[("disabled", "#7d8b99")],
        )
        style.configure("TRadiobutton", background=self.colors["app_bg"], foreground=self.colors["text"])


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
