import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class PicoPanel(ttk.LabelFrame):
    """
    Auto-packed Pico panel:
    no need to modify Main_gui.py

    2x2 plot layout:
        A | B
        C | D

    Plot logic:
    - always include trigger_source in display set
    - also include all capture_channels
    - channels not selected will show "No Data"
    """

    def __init__(self, parent, ctx, log_func=None):
        super().__init__(parent, text="PicoScope", padding=8)
        self.ctx = ctx
        self.log = log_func if log_func is not None else print

        self._build_vars()
        self._build_layout()
        self._build_plot()

        self._refresh_status()

        # auto place itself into parent, old-style
        self.pack(fill="both", expand=True, pady=4)

    # ------------------------------------------------------------------
    # vars
    # ------------------------------------------------------------------
    def _build_vars(self):
        self.var_status = tk.StringVar(value="Disconnected")
        self.var_idn = tk.StringVar(value="Not connected")

        self.var_capture_channels = tk.StringVar(value="B")
        self.var_vrange = tk.StringVar(value="V2")
        self.var_coupling = tk.StringVar(value="DC")
        self.var_sample_rate_mhz = tk.StringVar(value="62.5")
        self.var_duration_us = tk.StringVar(value="50.0")
        self.var_pre_trigger_us = tk.StringVar(value="0.0")

        self.var_trigger_source = tk.StringVar(value="A")
        self.var_trigger_direction = tk.StringVar(value="RISING")
        self.var_trigger_threshold_mv = tk.StringVar(value="100.0")
        self.var_auto_trigger_us = tk.StringVar(value="0")

        self.var_save_dir = tk.StringVar(value="")

    # ------------------------------------------------------------------
    # layout
    # ------------------------------------------------------------------
    def _build_layout(self):
        row = 0
        ttk.Label(self, text="Status:").grid(row=row, column=0, sticky="w")
        ttk.Label(self, textvariable=self.var_status).grid(row=row, column=1, sticky="w", padx=4)

        row += 1
        ttk.Label(self, text="Identify:").grid(row=row, column=0, sticky="w")
        ttk.Label(self, textvariable=self.var_idn, width=40).grid(row=row, column=1, columnspan=3, sticky="w", padx=4)

        row += 1
        ttk.Button(self, text="Connect", command=self.on_connect).grid(row=row, column=0, sticky="ew", pady=4)
        ttk.Button(self, text="Disconnect", command=self.on_disconnect).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(self, text="Apply Config", command=self.on_apply_config).grid(row=row, column=2, sticky="ew", pady=4)
        ttk.Button(self, text="Capture Test", command=self.capture_test).grid(row=row, column=3, sticky="ew", pady=4)

        row += 1
        cfg = ttk.LabelFrame(self, text="Configuration", padding=6)
        cfg.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=6)

        r = 0
        ttk.Label(cfg, text="Capture channels").grid(row=r, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_capture_channels, width=18).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Label(cfg, text="e.g. B or B,C or B,C,D").grid(row=r, column=2, columnspan=2, sticky="w")

        r += 1
        ttk.Label(cfg, text="Voltage range").grid(row=r, column=0, sticky="w")
        ttk.Combobox(
            cfg,
            textvariable=self.var_vrange,
            values=["10mV", "20mV", "50mV", "100mV", "200mV", "500mV", "V1", "V2", "V5", "V10", "V20"],
            width=15,
            state="readonly",
        ).grid(row=r, column=1, sticky="ew", padx=4)

        ttk.Label(cfg, text="Coupling").grid(row=r, column=2, sticky="w")
        ttk.Combobox(
            cfg,
            textvariable=self.var_coupling,
            values=["DC", "AC", "DC_50OHM"],
            width=15,
            state="readonly",
        ).grid(row=r, column=3, sticky="ew", padx=4)

        r += 1
        ttk.Label(cfg, text="Sample rate (MHz)").grid(row=r, column=0, sticky="w")
        ttk.Combobox(
            cfg,
            textvariable=self.var_sample_rate_mhz,
            values=["62.5"],
            width=15,
            state="readonly",
        ).grid(row=r, column=1, sticky="ew", padx=4)

        ttk.Label(cfg, text="Duration (us)").grid(row=r, column=2, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_duration_us, width=18).grid(row=r, column=3, sticky="ew", padx=4)

        r += 1
        ttk.Label(cfg, text="Pre-trigger (us)").grid(row=r, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_pre_trigger_us, width=18).grid(row=r, column=1, sticky="ew", padx=4)

        ttk.Label(cfg, text="Trigger source").grid(row=r, column=2, sticky="w")
        ttk.Combobox(
            cfg,
            textvariable=self.var_trigger_source,
            values=["A", "B", "C", "D"],
            width=15,
            state="readonly",
        ).grid(row=r, column=3, sticky="ew", padx=4)

        r += 1
        ttk.Label(cfg, text="Trigger direction").grid(row=r, column=0, sticky="w")
        ttk.Combobox(
            cfg,
            textvariable=self.var_trigger_direction,
            values=["RISING", "FALLING", "RISING_OR_FALLING", "ABOVE", "BELOW"],
            width=15,
            state="readonly",
        ).grid(row=r, column=1, sticky="ew", padx=4)

        ttk.Label(cfg, text="Trigger threshold (mV)").grid(row=r, column=2, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_trigger_threshold_mv, width=18).grid(row=r, column=3, sticky="ew", padx=4)

        r += 1
        ttk.Label(cfg, text="Auto trigger (us)").grid(row=r, column=0, sticky="w")
        ttk.Entry(cfg, textvariable=self.var_auto_trigger_us, width=18).grid(row=r, column=1, sticky="ew", padx=4)

        for c in range(4):
            cfg.columnconfigure(c, weight=1)

        row += 1
        savef = ttk.LabelFrame(self, text="Save", padding=6)
        savef.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=6)

        ttk.Label(savef, text="Folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(savef, textvariable=self.var_save_dir, width=50).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(savef, text="Choose Save Folder", command=self.on_choose_save_dir).grid(row=0, column=2, sticky="ew")

        savef.columnconfigure(1, weight=1)

        row += 1
        plotf = ttk.LabelFrame(self, text="Waveform", padding=6)
        plotf.grid(row=row, column=0, columnspan=4, sticky="nsew", pady=6)
        self.plot_frame = plotf

        for c in range(4):
            self.columnconfigure(c, weight=1)
        self.rowconfigure(row, weight=1)

    # ------------------------------------------------------------------
    # plot
    # ------------------------------------------------------------------
    def _build_plot(self):
        self.fig = Figure(figsize=(10, 7), dpi=100)

        self.axA = self.fig.add_subplot(2, 2, 1)
        self.axB = self.fig.add_subplot(2, 2, 2)
        self.axC = self.fig.add_subplot(2, 2, 3)
        self.axD = self.fig.add_subplot(2, 2, 4)

        self.axes_map = {
            "A": self.axA,
            "B": self.axB,
            "C": self.axC,
            "D": self.axD,
        }

        self.fig.subplots_adjust(
            left=0.08,
            right=0.98,
            bottom=0.08,
            top=0.93,
            wspace=0.28,
            hspace=0.40
        )

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        widget = self.canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)

        self._reset_plot()

    def _reset_plot(self):
        for ch, ax in self.axes_map.items():
            ax.clear()
            ax.set_title(f"Channel {ch}", fontsize=5)
            ax.set_xlabel("Time (us)", fontsize=4)
            ax.set_ylabel("Voltage (V)", fontsize=4)
            ax.tick_params(axis="both", labelsize=4)
            ax.grid(True)
            ax.text(
                0.5, 0.5, "No Data",
                ha="center", va="center",
                transform=ax.transAxes,
                fontsize=5
            )

        self.canvas.draw_idle()

    def _get_display_channels(self, result_meta, signals_v):
        """
        Plot channels = trigger_source + capture_channels
        unique, ordered as A/B/C/D display positions are fixed anyway
        """
        display = []

        trigger_source = str(result_meta.get("trigger_source", "")).strip().upper()
        if trigger_source in ("A", "B", "C", "D"):
            display.append(trigger_source)

        for ch in result_meta.get("capture_channels", []):
            ch = str(ch).strip().upper()
            if ch in ("A", "B", "C", "D") and ch not in display:
                display.append(ch)

        # fallback: if meta is incomplete, use returned signals directly
        if not display and isinstance(signals_v, dict):
            for ch in signals_v.keys():
                ch = str(ch).strip().upper()
                if ch in ("A", "B", "C", "D") and ch not in display:
                    display.append(ch)

        return display

    def _plot_result(self, time_s, signals_v, meta=None):
        if meta is None:
            meta = {}

        display_channels = self._get_display_channels(meta, signals_v)

        if time_s is None or signals_v is None:
            self._reset_plot()
            return

        t_us = np.asarray(time_s, dtype=float) * 1e6

        for ch, ax in self.axes_map.items():
            ax.clear()

            # 标题字体缩小
            ax.set_title(f"Channel {ch}", fontsize=5)

            # 只给左边一列加 y 标签
            if ch in ("A", "C"):
                ax.set_ylabel("Voltage (V)", fontsize=5)
            else:
                ax.set_ylabel("")

            # 只给底下一行加 x 标签
            if ch in ("C", "D"):
                ax.set_xlabel("Time (us)", fontsize=5)
            else:
                ax.set_xlabel("")

            # 刻度字体缩小
            ax.tick_params(axis="both", labelsize=4)

            ax.grid(True)

            if ch in display_channels and ch in signals_v:
                y = np.asarray(signals_v[ch], dtype=float)
                ax.plot(t_us, y, linewidth=1.0)
            else:
                ax.text(
                    0.5, 0.5, "No Data",
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontsize=5
                )

        # 不要只靠 tight_layout，手动调间距更稳
        self.fig.subplots_adjust(
            left=0.08,
            right=0.98,
            bottom=0.15,
            top=0.80,
            wspace=0.25,
            hspace=0.30,
        )

        self.canvas.draw_idle()

    # ------------------------------------------------------------------
    # parsing
    # ------------------------------------------------------------------
    def _parse_capture_channels(self):
        text = self.var_capture_channels.get().strip()
        if not text:
            raise ValueError("Capture channels cannot be empty")

        items = [x.strip().upper() for x in text.split(",") if x.strip()]
        if not items:
            raise ValueError("Capture channels cannot be empty")

        for ch in items:
            if ch not in ("A", "B", "C", "D"):
                raise ValueError(f"Invalid capture channel: {ch}")

        out = []
        seen = set()
        for ch in items:
            if ch not in seen:
                seen.add(ch)
                out.append(ch)
        return out

    # ------------------------------------------------------------------
    # connect/disconnect
    # ------------------------------------------------------------------
    def on_connect(self):
        try:
            if self.ctx.pico is None:
                from pico_controller import PicoController
                self.ctx.pico = PicoController()

            self.ctx.pico.connect()
            idn = self.ctx.pico.identify()
            self.var_idn.set(idn)
            self.var_status.set("Connected")
            self.log(f"[PICO] Connected: {idn}")

        except Exception as e:
            self.var_status.set("Disconnected")
            self.var_idn.set("Connect failed")
            self.log(f"[PICO] Connect failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

        self._refresh_status()

    def on_disconnect(self):
        try:
            if self.ctx.pico is not None:
                self.ctx.pico.disconnect()
            self.var_status.set("Disconnected")
            self.var_idn.set("Not connected")
            self.log("[PICO] Disconnected")
            self._reset_plot()

        except Exception as e:
            self.log(f"[PICO] Disconnect failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

        self._refresh_status()

    # ------------------------------------------------------------------
    # config / save
    # ------------------------------------------------------------------
    def on_apply_config(self):
        try:
            if self.ctx.pico is None or not self.ctx.pico.is_connected():
                raise RuntimeError("PicoScope not connected")

            capture_channels = self._parse_capture_channels()

            summary = self.ctx.pico.apply_config(
                capture_channels=capture_channels,
                vrange=self.var_vrange.get(),
                coupling=self.var_coupling.get(),
                sample_rate_mhz=float(self.var_sample_rate_mhz.get()),
                duration_us=float(self.var_duration_us.get()),
                pre_trigger_us=float(self.var_pre_trigger_us.get()),
                trigger_source=self.var_trigger_source.get(),
                trigger_direction=self.var_trigger_direction.get(),
                trigger_threshold_mv=float(self.var_trigger_threshold_mv.get()),
                auto_trigger_us=int(float(self.var_auto_trigger_us.get())),
            )

            self.log(f"[PICO] Config applied: {summary}")

            save_dir = self.var_save_dir.get().strip()
            if save_dir:
                self.ctx.pico.set_save_dir(save_dir)

        except Exception as e:
            self.log(f"[PICO] Apply config failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

        self._refresh_status()

    def on_choose_save_dir(self):
        folder = filedialog.askdirectory(title="Choose Pico Save Folder")
        if not folder:
            return

        self.var_save_dir.set(folder)

        try:
            if self.ctx.pico is not None:
                self.ctx.pico.set_save_dir(folder)
            self.log(f"[PICO] Save folder set: {folder}")
        except Exception as e:
            self.log(f"[PICO] Failed to set save folder: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    # ------------------------------------------------------------------
    # capture
    # ------------------------------------------------------------------
    def capture_test(self):
        try:
            if self.ctx.pico is None or not self.ctx.pico.is_connected():
                raise RuntimeError("PicoScope not connected")
            if not self.ctx.pico.is_configured():
                raise RuntimeError("PicoScope not configured. Please click Apply Config first.")

            self.ctx.pico.arm_current_capture()
            self.log("[PICO] Armed. Waiting using sleep-based fetch workaround...")

            result = self.ctx.pico.wait_and_fetch_current_capture()

            self.ctx.last_pico_time = result.time_s
            self.ctx.last_pico_signals = result.signals_v
            self.ctx.last_pico_meta = result.meta

            # 防止 last_pico_update_id = None 时出错
            current_id = getattr(self.ctx, "last_pico_update_id", None)
            if current_id is None:
                current_id = 0
            self.ctx.last_pico_update_id = current_id + 1

            self._plot_result(result.time_s, result.signals_v, result.meta)

            ch_info = ",".join(result.meta.get("capture_channels", []))
            display_info = ",".join(self._get_display_channels(result.meta, result.signals_v))

            self.log(
                f"[PICO] Captured: trigger={result.meta.get('trigger_source')}, "
                f"capture_channels={ch_info}, "
                f"display_channels={display_info}, "
                f"samples={result.meta.get('samples')}, "
                f"dt={result.meta.get('dt_s')}"
            )

            save_dir = self.var_save_dir.get().strip()
            if save_dir:
                path = self.ctx.pico.save_capture_npz(result, folder=save_dir)
                self.log(f"[PICO] Saved: {path}")

        except Exception as e:
            self.log(f"[PICO] Capture failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def _refresh_status(self):
        try:
            connected = self.ctx.pico is not None and self.ctx.pico.is_connected()
        except Exception:
            connected = False

        self.var_status.set("Connected" if connected else "Disconnected")

        if connected:
            try:
                self.var_idn.set(self.ctx.pico.identify())
            except Exception:
                self.var_idn.set("Connected")
        else:
            self.var_idn.set("Not connected")