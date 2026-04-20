from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from pico_controller import PicoController


class PicoPanel:
    def __init__(self, parent, ctx, log_func):
        self.ctx = ctx
        self.log = log_func
        self._last_seen_update_id = -1

        self.frame = ttk.LabelFrame(parent, text="PicoScope", padding=10)
        self.frame.pack(fill="x", pady=(0, 10))

        self._build_controls()
        self._build_plot()
        self._start_auto_refresh()

    def _build_controls(self):
        top = ttk.Frame(self.frame)
        top.pack(fill="x")

        ttk.Button(top, text="Connect Pico", command=self.connect_pico).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(top, text="Disconnect Pico", command=self.disconnect_pico).grid(row=0, column=1, padx=4, pady=4)
        ttk.Button(top, text="Apply Config", command=self.apply_config).grid(row=0, column=2, padx=4, pady=4)
        ttk.Button(top, text="Capture Test", command=self.capture_test).grid(row=0, column=3, padx=4, pady=4)
        ttk.Button(top, text="Choose Save Folder", command=self.choose_save_folder).grid(row=0, column=4, padx=4, pady=4)
        ttk.Button(top, text="Clear Plot", command=self.clear_plot).grid(row=0, column=5, padx=4, pady=4)

        # Row 1
        ttk.Label(top, text="Recv Ch").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.channel_var = tk.StringVar(value="A")
        ttk.Combobox(
            top, textvariable=self.channel_var, width=8,
            values=["A", "B", "C", "D"], state="readonly"
        ).grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Range").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        self.range_var = tk.StringVar(value="100mV")
        ttk.Combobox(
            top, textvariable=self.range_var, width=8,
            values=["10mV", "20mV", "50mV", "100mV", "200mV", "500mV", "1V", "2V", "5V", "10V", "20V"],
            state="readonly"
        ).grid(row=1, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Coupling").grid(row=1, column=4, sticky="e", padx=4, pady=4)
        self.coupling_var = tk.StringVar(value="DC")
        ttk.Combobox(
            top, textvariable=self.coupling_var, width=8,
            values=["DC", "AC"], state="readonly"
        ).grid(row=1, column=5, sticky="w", padx=4, pady=4)

        # Row 2
        ttk.Label(top, text="Sample Rate (MHz)").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.sample_rate_var = tk.StringVar(value="62.5")
        ttk.Combobox(
            top, textvariable=self.sample_rate_var, width=8,
            values=["15.625", "31.25", "62.5"], state="readonly"
        ).grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="PreTrig (us)").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        self.pretrigger_us_var = tk.StringVar(value="0")
        ttk.Entry(top, textvariable=self.pretrigger_us_var, width=10).grid(row=2, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="PostTrig (us)").grid(row=2, column=4, sticky="e", padx=4, pady=4)
        self.posttrigger_us_var = tk.StringVar(value="20")
        ttk.Entry(top, textvariable=self.posttrigger_us_var, width=10).grid(row=2, column=5, sticky="w", padx=4, pady=4)

        # Row 3
        ttk.Label(top, text="Trigger Src").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        self.trigger_source_var = tk.StringVar(value="EXT")
        ttk.Combobox(
            top, textvariable=self.trigger_source_var, width=8,
            values=["EXT", "A", "B", "C", "D"], state="readonly"
        ).grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Direction").grid(row=3, column=2, sticky="e", padx=4, pady=4)
        self.trigger_direction_var = tk.StringVar(value="RISING")
        ttk.Combobox(
            top, textvariable=self.trigger_direction_var, width=12,
            values=["RISING", "FALLING", "RISING_OR_FALLING"], state="readonly"
        ).grid(row=3, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(top, text="Threshold (mV)").grid(row=3, column=4, sticky="e", padx=4, pady=4)
        self.trigger_var = tk.StringVar(value="0")
        ttk.Entry(top, textvariable=self.trigger_var, width=10).grid(row=3, column=5, sticky="w", padx=4, pady=4)

        # Row 4
        ttk.Label(top, text="AutoTrig (us)").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        self.autotrig_var = tk.StringVar(value="0")
        ttk.Entry(top, textvariable=self.autotrig_var, width=10).grid(row=4, column=1, sticky="w", padx=4, pady=4)

        self.save_dir_var = tk.StringVar(value="")
        ttk.Label(top, text="Save Folder").grid(row=4, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(top, textvariable=self.save_dir_var, width=42).grid(row=4, column=3, columnspan=3, sticky="we", padx=4, pady=4)

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

    def _start_auto_refresh(self):
        self.frame.after(200, self._poll_latest_waveform)

    def _poll_latest_waveform(self):
        try:
            update_id = getattr(self.ctx, "last_pico_update_id", 0)

            if update_id != self._last_seen_update_id:
                time_s = getattr(self.ctx, "last_pico_time", None)
                signal_v = getattr(self.ctx, "last_pico_signal", None)

                if time_s is not None and signal_v is not None:
                    self.plot_waveform(time_s, signal_v)
                    self._last_seen_update_id = update_id

        except Exception as e:
            self.log(f"[PICO] Auto-refresh failed: {e}")

        self.frame.after(200, self._poll_latest_waveform)

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

    def choose_save_folder(self):
        try:
            folder = filedialog.askdirectory(title="Choose Pico save folder")
            if not folder:
                return

            if self.ctx.pico is None:
                self.ctx.pico = PicoController()

            self.ctx.pico.set_save_directory(folder)
            self.save_dir_var.set(folder)
            self.log(f"[PICO] Save folder set: {folder}")
        except Exception as e:
            self.log(f"[PICO] Set save folder failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    def apply_config(self):
        try:
            if self.ctx.pico is None or not self.ctx.pico.is_connected():
                raise RuntimeError("PicoScope not connected")

            pre_us = float(self.pretrigger_us_var.get().strip())
            post_us = float(self.posttrigger_us_var.get().strip())

            if pre_us < 0 or post_us <= 0:
                raise ValueError("Require PreTrig >= 0 and PostTrig > 0")

            summary = self.ctx.pico.apply_config(
                recv_channel=self.channel_var.get().strip(),
                vrange=self.range_var.get().strip(),
                coupling=self.coupling_var.get().strip(),
                sample_rate_mhz=float(self.sample_rate_var.get().strip()),
                duration_us=post_us,
                pre_trigger_us=pre_us,
                trigger_source=self.trigger_source_var.get().strip(),
                trigger_direction=self.trigger_direction_var.get().strip(),
                trigger_threshold_mv=float(self.trigger_var.get().strip()),
                auto_trigger_us=int(self.autotrig_var.get().strip()),
            )

            self.status_var.set(
                "Pico: configured | "
                f"fs={summary['requested_sample_rate_mhz']} MHz, "
                f"samples={summary['samples']}, "
                f"pre={summary['pre_trigger_percent']}%"
            )

            self.log(
                "[PICO] Config applied: "
                f"recv={summary['recv_channel']}, "
                f"trig={summary['trigger_source']} {summary['trigger_direction']}, "
                f"requested_fs={summary['requested_sample_rate_mhz']} MHz, "
                f"actual_fs={summary['actual_sample_rate_mhz']}, "
                f"samples={summary['samples']}, "
                f"pre={summary['pre_trigger_percent']}%"
            )
        except Exception as e:
            self.log(f"[PICO] Apply config failed: {e}")
            messagebox.showerror("PicoScope Error", str(e))

    def capture_test(self):
        try:
            if self.ctx.pico is None or not self.ctx.pico.is_connected():
                raise RuntimeError("PicoScope not connected")
            if not self.ctx.pico.is_configured():
                raise RuntimeError("PicoScope not configured. Please click Apply Config first.")

            self.ctx.pico.arm_current_capture()
            self.log("[PICO] Armed. Waiting for trigger...")

            result = self.ctx.pico.wait_and_fetch_current_capture()

            self.ctx.last_pico_time = result.time_s
            self.ctx.last_pico_signal = result.signal_v
            self.ctx.last_pico_meta = result.meta
            self.ctx.last_pico_update_id = getattr(self.ctx, "last_pico_update_id", 0) + 1

            self.log(
                f"[PICO] Captured: recv={result.meta['recv_channel']}, "
                f"samples={result.meta['samples']}, "
                f"dt={result.meta['dt_s']}"
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