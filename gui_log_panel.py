import time
import tkinter as tk
from tkinter import ttk


class LogPanel:
    def __init__(self, parent, height=8):
        frame = ttk.LabelFrame(parent, text="📋 Log", padding=6)
        frame.pack(fill="both", expand=True)

        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(
            frame,
            width=55,
            height=height,
            wrap="word",
            bg="#f8fafc",
            fg="#17202a",
            insertbackground="#17202a",
            selectbackground="#cfe3f6",
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#b7c6d8",
            highlightcolor="#2563a9",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=yscroll.set)

    def log(self, msg: str):
        now = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{now}] {msg}\n")
        self.log_text.see("end")
        self.log_text.update_idletasks()
