# gui_pico_panel.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from pico_controller import PicoController


class PicoPanel:
    def __init__(self, parent, ctx, log_func):
        self.ctx = ctx
        self.log = log_func

        self.frame = ttk.LabelFrame(parent, text="PicoScope", padding=10)
        self.frame.pack(fill="x", pady=(0, 10))

        self._build_controls()
        self._build_plot()

    def _build_controls(self):
        top = ttk.Frame(self.frame)
        top.pack(fill="x")

        ttk.Button(top, text="Connect Pico", command=self.connect_pico).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(top, text="Disconnect Pico", command=self.disconnect_pico).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(top, text="Capture Test", command=self.capture_test).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(top, text="Clear Plot", command=self.clear_plot).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(top, text="Channel").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.channel_var = tk.StringVar(value="A")
        ttk.Entry(top, textvariable=self.channel_var, width=8).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Range").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        self.range_var = tk.StringVar(value="100mV")
        ttk.Entry(top, textvariable=self.range_var, width=8).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Timebase").grid(row=1, column=4, sticky="e", padx=4, pady=4)
        self.timebase_var = tk.StringVar(value="3")
        ttk.Entry(top, textvariable=self.timebase_var, width=8).grid(row=1, column=5, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Samples").grid(row=1, column=6, sticky="e", padx=4, pady=4)
        self.samples_var = tk.StringVar(value="5000")
        ttk.Entry(top, textvariable=self.samples_var, width=10).grid(row=1, column=7, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Trigger mV").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.trigger_var = tk.StringVar(value="0")
        ttk.Entry(top, textvariable=self.trigger_var, width=8).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="PreTrig %").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        self.pretrig_var = tk.StringVar(value="20")
        ttk.Entry(top, textvariable=self.pretrig_var, width=8).grid(row=2, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="AutoTrig us").grid(row=2, column=4, sticky="e", padx=4, pady=4)
        self.autotrig_var = tk.StringVar(value="1000")
        ttk.Entry(top, textvariable=self.autotrig_var, width=10).grid(row=2, column=5, sticky="w", padx=4, pady=4)

        self.status_var = tk.StringVar(value="Pico: disconnected")
        ttk.Label(self.frame, textvariable=self.status_var).pack(anchor="w", pady=(6, 4))

    def _build_plot(self):
        plot_frame = ttk.Frame(self.frame)
        plot_frame.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(7, 3.8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("PicoScope Signal")
        self.ax.set_xlabel("Time (us)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.grid(True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def connect_pico(self):
        try:
            if self.ctx.pico is None:
                self.ctx.pico = PicoController()

            self.ctx.pico.connect()
            self.ctx.pico_connected = True

            ident = self.ctx.pico.identify()
            self.status_var.set(f"Pico: connected | {ident}")
            self.log(f"[PICO] Connected: {ident}")
        except Exception as e:
            self.ctx.pico_connected = False
            self.log(f"[PICO] Connect failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    def disconnect_pico(self):
        try:
            if self.ctx.pico is not None:
                self.ctx.pico.close()
            self.ctx.pico_connected = False
            self.status_var.set("Pico: disconnected")
            self.log("[PICO] Disconnected")
        except Exception as e:
            self.log(f"[PICO] Disconnect failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    def capture_test(self):
        try:
            if self.ctx.pico is None or not self.ctx.pico.is_connected():
                raise RuntimeError("PicoScope not connected")

            result = self.ctx.pico.capture_block(
                channel=self.channel_var.get().strip(),
                vrange=self.range_var.get().strip(),
                timebase=int(self.timebase_var.get().strip()),
                samples=int(self.samples_var.get().strip()),
                pre_trigger_percent=int(self.pretrig_var.get().strip()),
                trigger_threshold_mv=float(self.trigger_var.get().strip()),
                auto_trigger_us=int(self.autotrig_var.get().strip()),
            )

            self.ctx.last_pico_time = result.time_s
            self.ctx.last_pico_signal = result.signal_v
            self.ctx.last_pico_meta = result.meta

            self.plot_waveform(result.time_s, result.signal_v)
            self.log(
                f"[PICO] Captured: channel={result.meta['channel']}, "
                f"samples={result.meta['samples']}, timebase={result.meta['timebase']}"
            )
        except Exception as e:
            self.log(f"[PICO] Capture failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    def plot_waveform(self, time_s, signal_v):
        self.ax.clear()
        self.ax.plot(time_s * 1e6, signal_v)
        self.ax.set_title("PicoScope Signal")
        self.ax.set_xlabel("Time (us)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def clear_plot(self):
        self.ax.clear()
        self.ax.set_title("PicoScope Signal")
        self.ax.set_xlabel("Time (us)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.grid(True)
        self.canvas.draw()
        self.log("[PICO] Plot cleared")