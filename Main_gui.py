import json
import os
import tkinter as tk
from tkinter import ttk, messagebox

from app_context import AppContext
from gui_log_panel import LogPanel
from gui_stage_panel import StagePanel
from gui_afg_panel import AFGPanel
from gui_pico_panel import PicoPanel
from gui_scan_panel import ScanPanel
from gui_realtime_postprocess_panel import RealtimePostprocessPanel


class MainGUIApp:
    SETTINGS_VERSION = 1
    TRANSIENT_VAR_NAMES = {
        "var_status",
        "var_idn",
        "status_var",
        "pos1_var",
        "pos2_var",
        "distance_result_var",
        "power_result_var",
        "monitor_status_var",
        "monitor_point_var",
        "monitor_position_var",
        "monitor_frequency_var",
        "monitor_eta_var",
        "monitor_elapsed_var",
        "monitor_progress_var",
        "readiness_var",
        "var_processed",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Scanning Field Control Panel")
        self._configure_theme()
        self.settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_settings.json")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w = min(1500, screen_w - 80)
        h = min(900, screen_h - 100)
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(900, 620)

        self.ctx = AppContext()
        self._scrollregion_after = None
        self._paned_height = None

        main = self._build_scrollable_main(root)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        paned = tk.PanedWindow(
            main,
            orient=tk.HORIZONTAL,
            sashwidth=7,
            sashrelief=tk.RAISED,
            bg=self.colors["panel_border"],
            bd=0,
            opaqueresize=False,
        )
        self.main_paned = paned
        paned.grid(row=0, column=0, sticky="nsew")

        control_area = ttk.Frame(paned)
        postprocess_area = ttk.Frame(paned)
        self.control_area = control_area
        self.postprocess_area = postprocess_area
        paned.add(control_area, minsize=640, stretch="always")
        paned.add(postprocess_area, minsize=24, stretch="never", width=32)

        control_area.grid_rowconfigure(0, weight=1)
        control_area.grid_columnconfigure(0, weight=1)

        control_paned = tk.PanedWindow(
            control_area,
            orient=tk.HORIZONTAL,
            sashwidth=6,
            sashrelief=tk.RAISED,
            bg=self.colors["panel_border"],
            bd=0,
            opaqueresize=False,
        )
        self.control_paned = control_paned
        control_paned.grid(row=0, column=0, sticky="nsew")

        left = ttk.Frame(control_paned)
        middle = ttk.Frame(control_paned)
        self.left_area = left
        self.middle_area = middle
        control_paned.add(left, minsize=300, stretch="never")
        control_paned.add(middle, minsize=420, stretch="always")

        left.grid_rowconfigure(0, weight=0)
        left.grid_rowconfigure(1, weight=0)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        middle.grid_rowconfigure(0, weight=1)
        middle.grid_columnconfigure(0, weight=1)
        right = ttk.Frame(middle)
        self.right_area = right
        right.grid(row=0, column=0, sticky="nsew", padx=(10, 0))
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
        self.realtime_postprocess_panel = RealtimePostprocessPanel(
            postprocess_area,
            self.ctx,
            self.log_panel.log,
        )
        self.realtime_postprocess_panel.pack(fill="both", expand=True)

        self.ctx.scan_panel = self.scan_panel
        self.ctx.pico_panel = self.pico_panel
        self.ctx.realtime_postprocess_panel = self.realtime_postprocess_panel
        self.load_panel_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after_idle(self._sync_paned_height)

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

        def _update_scrollregion():
            self._scrollregion_after = None
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        def _schedule_scrollregion(_event=None):
            if self._scrollregion_after is None:
                self._scrollregion_after = self.root.after_idle(_update_scrollregion)

        def _fit_viewport(event):
            requested = main.winfo_reqwidth()
            requested_h = main.winfo_reqheight()
            self.main_canvas.itemconfigure(
                self.main_canvas_window,
                width=max(requested, event.width),
                height=max(requested_h, event.height),
            )
            _schedule_scrollregion()

        def _wheel(event):
            if event.state & 0x0001:
                self.main_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        main.bind("<Configure>", _schedule_scrollregion)
        self.main_canvas.bind("<Configure>", _fit_viewport)
        self.main_canvas.bind_all("<MouseWheel>", _wheel)
        return main

    def _sync_paned_height(self):
        try:
            heights = [
                self.control_area.winfo_reqheight(),
                getattr(self, "left_area", self.control_area).winfo_reqheight(),
                getattr(self, "right_area", self.control_area).winfo_reqheight(),
                self.postprocess_area.winfo_reqheight(),
                self.root.winfo_height() - 40,
                620,
            ]
            height = max(int(h) for h in heights if h is not None)
            if height != self._paned_height:
                self.main_paned.configure(height=height)
                if hasattr(self, "control_paned"):
                    self.control_paned.configure(height=height)
                self._paned_height = height
                if self._scrollregion_after is None:
                    def _refresh_scrollregion():
                        self._scrollregion_after = None
                        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

                    self._scrollregion_after = self.root.after_idle(_refresh_scrollregion)
        except Exception:
            pass
        finally:
            self.root.after(1000, self._sync_paned_height)

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

    def _settings_panels(self):
        return {
            "afg": getattr(self, "afg_panel", None),
            "stage": getattr(self, "stage_panel", None),
            "scan": getattr(self, "scan_panel", None),
            "pico": getattr(self, "pico_panel", None),
            "realtime_postprocess": getattr(self, "realtime_postprocess_panel", None),
        }

    def _iter_persistent_panel_vars(self, panel):
        if panel is None:
            return
        for name, value in vars(panel).items():
            if name in self.TRANSIENT_VAR_NAMES:
                continue
            if isinstance(value, tk.Variable):
                yield name, value

    def _refresh_loaded_settings_ui(self):
        scan_panel = getattr(self, "scan_panel", None)
        if scan_panel is not None and hasattr(scan_panel, "_refresh_scan_mode_ui"):
            try:
                scan_panel._refresh_scan_mode_ui()
            except Exception:
                pass

        pico_panel = getattr(self, "pico_panel", None)
        if pico_panel is not None and hasattr(pico_panel, "apply_waveform_y_limits"):
            try:
                pico_panel.apply_waveform_y_limits()
            except Exception:
                pass

    def load_panel_settings(self):
        if not os.path.exists(self.settings_path):
            return
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.log_panel.log(f"[GUI] Failed to load saved settings: {e}")
            return

        panels_data = data.get("panels", {})
        for panel_name, panel in self._settings_panels().items():
            saved_vars = panels_data.get(panel_name, {})
            if not isinstance(saved_vars, dict):
                continue
            for var_name, saved_value in saved_vars.items():
                var = getattr(panel, var_name, None)
                if not isinstance(var, tk.Variable):
                    continue
                if var_name in self.TRANSIENT_VAR_NAMES:
                    continue
                try:
                    var.set(saved_value)
                except Exception:
                    pass

        self._refresh_loaded_settings_ui()
        self.log_panel.log("[GUI] Loaded saved panel settings.")

    def save_panel_settings(self):
        panels_data = {}
        for panel_name, panel in self._settings_panels().items():
            saved_vars = {}
            for var_name, var in self._iter_persistent_panel_vars(panel):
                try:
                    saved_vars[var_name] = var.get()
                except Exception:
                    pass
            panels_data[panel_name] = saved_vars

        data = {
            "version": self.SETTINGS_VERSION,
            "panels": panels_data,
        }

        tmp_path = f"{self.settings_path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self.settings_path)
        except Exception as e:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            self.log_panel.log(f"[GUI] Failed to save panel settings: {e}")

    def on_close(self):
        scan_controller = getattr(getattr(self, "scan_panel", None), "scan_controller", None)
        scan_running = bool(scan_controller is not None and scan_controller.is_running)
        if scan_running:
            should_close = messagebox.askyesno(
                "Scan is running",
                "A scan is still running.\n\nStop the scan and close the GUI?",
            )
            if not should_close:
                return

        try:
            self.save_panel_settings()

            if scan_running:
                try:
                    scan_controller.stop()
                except Exception:
                    pass

            if hasattr(self, "realtime_postprocess_panel"):
                try:
                    self.realtime_postprocess_panel.stop_worker()
                except Exception:
                    pass

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
                for axis in (1, 2):
                    try:
                        self.ctx.stage.stop(axis)
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
    MainGUIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
