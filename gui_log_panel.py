import time
import tkinter as tk
from tkinter import ttk


class LogPanel:
    def __init__(self, parent):
        frame = ttk.LabelFrame(parent, text="Log", padding=10)
        frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(frame, width=55, height=22)
        self.log_text.pack(fill="both", expand=True)

    def log(self, msg: str):
        now = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{now}] {msg}\n")
        self.log_text.see("end")
        self.log_text.update_idletasks()