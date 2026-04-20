import tkinter as tk
from tkinter import ttk, messagebox

from afg_controller import AFGController


class AFGPanel:
    def __init__(self, parent, ctx, log_func):
        self.ctx = ctx
        self.log = log_func

        self.frame = ttk.LabelFrame(parent, text="AFG Control")
        self.frame.pack(fill="x", padx=5, pady=5)

        self.resource_var = tk.StringVar(value="GPIB0::11::INSTR")
        self.channel_var = tk.StringVar(value="1")

        self.freq_var = tk.StringVar(value="1000000")
        self.amp_var = tk.StringVar(value="1.0")
        self.offset_var = tk.StringVar(value="0.0")
        self.cycles_var = tk.StringVar(value="10")
        self.delay_var = tk.StringVar(value="0.0")

        self.trigger_out_mode_var = tk.StringVar(value="TRIG")
        self.burst_mode_var = tk.StringVar(value="TRIG")
        self.trigger_source_var = tk.StringVar(value="BUS")

        self._build()

    def _build(self):
        # r is the row number of these buttons
        r = 0

        ttk.Label(self.frame, text="Resource").grid(row=r, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(self.frame, textvariable=self.resource_var, width=18).grid(row=r, column=1, padx=4, pady=3)

        ttk.Label(self.frame, text="Channel").grid(row=r, column=2, sticky="w", padx=4, pady=3)
        ttk.Combobox(
            self.frame,
            textvariable=self.channel_var,
            values=["1", "2"],
            width=6,
            state="readonly",
        ).grid(row=r, column=3, padx=4, pady=3)

        ttk.Button(self.frame, text="Connect AFG", command=self.on_connect).grid(row=r, column=4, padx=4, pady=3)
        ttk.Button(self.frame, text="Disconnect AFG", command=self.on_disconnect).grid(row=r, column=5, padx=4, pady=3)

        r += 1
        ttk.Label(self.frame, text="Freq (Hz)").grid(row=r, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(self.frame, textvariable=self.freq_var, width=12).grid(row=r, column=1, padx=4, pady=3)

        ttk.Label(self.frame, text="Amp (Vpp)").grid(row=r, column=2, sticky="w", padx=4, pady=3)
        ttk.Entry(self.frame, textvariable=self.amp_var, width=10).grid(row=r, column=3, padx=4, pady=3)

        ttk.Label(self.frame, text="Offset (V)").grid(row=r, column=4, sticky="w", padx=4, pady=3)
        ttk.Entry(self.frame, textvariable=self.offset_var, width=10).grid(row=r, column=5, padx=4, pady=3)

        ttk.Button(self.frame, text="Apply Sine", command=self.on_apply_sine).grid(row=r, column=6, padx=4, pady=3)
        ttk.Button(self.frame, text="Output ON", command=self.on_output_on).grid(row=r, column=7, padx=4, pady=3)
        ttk.Button(self.frame, text="Output OFF", command=self.on_output_off).grid(row=r, column=8, padx=4, pady=3)

        r += 1
        ttk.Label(self.frame, text="Burst Cycles").grid(row=r, column=0, sticky="w", padx=4, pady=3)
        ttk.Entry(self.frame, textvariable=self.cycles_var, width=10).grid(row=r, column=1, padx=4, pady=3)

        ttk.Label(self.frame, text="Burst Delay (s)").grid(row=r, column=2, sticky="w", padx=4, pady=3)
        ttk.Entry(self.frame, textvariable=self.delay_var, width=10).grid(row=r, column=3, padx=4, pady=3)

        ttk.Label(self.frame, text="Burst Mode").grid(row=r, column=4, sticky="w", padx=4, pady=3)
        ttk.Combobox(
            self.frame,
            textvariable=self.burst_mode_var,
            values=["TRIG", "GAT"],
            width=8,
            state="readonly",
        ).grid(row=r, column=5, padx=4, pady=3)

        ttk.Label(self.frame, text="Trig Out Mode").grid(row=r, column=6, sticky="w", padx=4, pady=3)
        ttk.Combobox(
            self.frame,
            textvariable=self.trigger_out_mode_var,
            values=["TRIG", "SYNC"],
            width=8,
            state="readonly",
        ).grid(row=r, column=7, padx=4, pady=3)

        ttk.Button(self.frame, text="Apply Trigger Setup", command=self.on_apply_trigger_setup).grid(
            row=r, column=8, padx=4, pady=3
        )

        r += 1
        ttk.Label(self.frame, text="Trigger Source").grid(row=r, column=0, sticky="w", padx=4, pady=3)
        ttk.Combobox(
            self.frame,
            textvariable=self.trigger_source_var,
            values=["BUS", "EXT", "TIM"],
            width=8,
            state="readonly",
        ).grid(row=r, column=1, padx=4, pady=3)

        ttk.Button(self.frame, text="Apply Trigger Source", command=self.on_apply_trigger_source).grid(
            row=r, column=2, padx=4, pady=3
        )
        ttk.Button(self.frame, text="Test Burst", command=self.on_test_burst).grid(row=r, column=3, padx=4, pady=3)
        ttk.Button(self.frame, text="Disable Burst", command=self.on_disable_burst).grid(row=r, column=4, padx=4, pady=3)
        ttk.Button(self.frame, text="Refresh AFG Status", command=self.on_refresh_status).grid(row=r, column=5, padx=4, pady=3)

    def _get_afg(self) -> AFGController:
        afg = self.ctx.afg
        if afg is None or not afg.is_connected():
            raise RuntimeError("AFG not connected")
        return afg

    def _update_channel(self, afg: AFGController):
        afg.set_channel(int(self.channel_var.get()))

    def on_connect(self):
        try:
            afg = AFGController(
                resource_name=self.resource_var.get().strip(),
                channel=int(self.channel_var.get()),
            )
            afg.connect()
            self.ctx.afg = afg
            self.ctx.afg_connected = True

            idn = afg.identify()
            self.log(f"AFG connected: {idn}")
            self.on_refresh_status()
        except Exception as e:
            messagebox.showerror("AFG Connect Error", str(e))

    def on_disconnect(self):
        try:
            if self.ctx.afg is not None:
                self.ctx.afg.safe_stop()
                self.ctx.afg.close()

            self.ctx.afg = None
            self.ctx.afg_connected = False
            self.log("AFG disconnected")
        except Exception as e:
            messagebox.showerror("AFG Disconnect Error", str(e))

    def on_apply_sine(self):
        try:
            afg = self._get_afg()
            self._update_channel(afg)

            freq = float(self.freq_var.get())
            amp = float(self.amp_var.get())
            offset = float(self.offset_var.get())

            afg.set_sine(freq, amp, offset)
            self.log(f"AFG sine applied: f={freq} Hz, amp={amp} Vpp, offset={offset} V")
        except Exception as e:
            messagebox.showerror("AFG Apply Sine Error", str(e))

    def on_output_on(self):
        try:
            afg = self._get_afg()
            self._update_channel(afg)
            afg.output_on()
            self.log("AFG output ON")
        except Exception as e:
            messagebox.showerror("AFG Output ON Error", str(e))

    def on_output_off(self):
        try:
            afg = self._get_afg()
            self._update_channel(afg)
            afg.output_off()
            self.log("AFG output OFF")
        except Exception as e:
            messagebox.showerror("AFG Output OFF Error", str(e))

    def on_apply_trigger_setup(self):
        try:
            afg = self._get_afg()
            self._update_channel(afg)

            freq = float(self.freq_var.get())
            amp = float(self.amp_var.get())
            offset = float(self.offset_var.get())
            cycles = int(self.cycles_var.get())
            delay_s = float(self.delay_var.get())
            burst_mode = self.burst_mode_var.get().strip().upper()
            trig_out_mode = self.trigger_out_mode_var.get().strip().upper()

            afg.prepare_burst_waiting(
                frequency_hz=freq,
                amplitude_vpp=amp,
                offset_v=offset,
                cycles=cycles,
                trigger_out_mode=trig_out_mode,
                burst_mode=burst_mode,
                trigger_delay_s=delay_s,
                keep_output_on=True,
            )

            self.log(
                f"AFG trigger setup applied: "
                f"f={freq} Hz, amp={amp} Vpp, cycles={cycles}, "
                f"burst_mode={burst_mode}, trig_out_mode={trig_out_mode}, delay={delay_s} s"
            )
        except Exception as e:
            messagebox.showerror("AFG Trigger Setup Error", str(e))

    def on_apply_trigger_source(self):
        try:
            afg = self._get_afg()
            source = self.trigger_source_var.get().strip().upper()

            if source == "BUS":
                afg.set_trigger_source_bus()
            elif source == "EXT":
                afg.set_trigger_source_external()
            elif source == "TIM":
                afg.set_trigger_source_internal()
            else:
                raise ValueError(f"Unsupported trigger source: {source}")

            actual = afg.get_trigger_source()
            self.log(f"AFG trigger source set to {source}, instrument reports: {actual}")
        except Exception as e:
            messagebox.showerror("AFG Trigger Source Error", str(e))

    def on_test_burst(self):
        try:
            afg = self._get_afg()
            afg.fire_software_trigger_once()
            self.log("AFG software trigger sent once")
        except Exception as e:
            messagebox.showerror("AFG Test Burst Error", str(e))

    def on_disable_burst(self):
        try:
            afg = self._get_afg()
            self._update_channel(afg)
            afg.disable_burst()
            self.log("AFG burst disabled")
        except Exception as e:
            messagebox.showerror("AFG Disable Burst Error", str(e))

    def on_refresh_status(self):
        try:
            afg = self._get_afg()
            self._update_channel(afg)
            data = afg.get_basic_settings()

            self.log("------ AFG STATUS ------")
            for k, v in data.items():
                self.log(f"{k}: {v}")
            self.log("------------------------")
        except Exception as e:
            messagebox.showerror("AFG Refresh Error", str(e))