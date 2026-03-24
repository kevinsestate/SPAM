"""Bottom status bar."""
import tkinter as tk
from datetime import datetime
from gui.colors import COLORS


def create_status_bar(root):
    """Build and return (frame, status_text_var, indicator_label, time_label)."""
    frame = tk.Frame(root, bg=COLORS['primary'], height=35)
    frame.pack(side=tk.BOTTOM, fill=tk.X)
    frame.pack_propagate(False)

    left = tk.Frame(frame, bg=COLORS['primary'])
    left.pack(side=tk.LEFT, fill=tk.Y)

    indicator = tk.Label(left, text="*", bg=COLORS['primary'],
                         fg=COLORS['success'], font=("Segoe UI", 14))
    indicator.pack(side=tk.LEFT, padx=(15, 5))

    text_var = tk.StringVar(value="System Ready")
    tk.Label(left, textvariable=text_var, bg=COLORS['primary'],
             fg=COLORS['text_light'], font=("Segoe UI", 10)).pack(side=tk.LEFT, pady=5)

    right = tk.Frame(frame, bg=COLORS['primary'])
    right.pack(side=tk.RIGHT, fill=tk.Y)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_label = tk.Label(right, text=f"Last Update: {ts}",
                          bg=COLORS['primary'], fg=COLORS['text_muted'],
                          font=("Segoe UI", 9))
    time_label.pack(side=tk.RIGHT, padx=15, pady=5)

    return frame, text_var, indicator, time_label
