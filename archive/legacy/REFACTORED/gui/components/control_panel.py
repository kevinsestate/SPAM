"""Control parameters & non-idealities panel (inside the scrollable graph area)."""
import tkinter as tk
from gui.colors import COLORS


def create_control_panel(scrollable_frame, ctrl_vars, nonideal_vars):
    """Build the control parameters and non-idealities cards.

    *ctrl_vars*: dict of tk.StringVar  – freq, power, angle_step, interval
    *nonideal_vars*: dict of tk.StringVar – cal_error, noise, temp, humidity
    """
    # --- Control Parameters ---
    card = tk.Frame(scrollable_frame, bg=COLORS['bg_panel'], relief=tk.FLAT, bd=0)
    card.pack(fill=tk.X, pady=(0, 12), padx=5)
    tk.Frame(card, bg=COLORS['secondary'], height=2).pack(fill=tk.X)
    content = tk.Frame(card, bg=COLORS['bg_panel'])
    content.pack(fill=tk.BOTH, padx=18, pady=16)
    tk.Label(content, text="Control Parameters", bg=COLORS['bg_panel'],
             fg=COLORS['text_dark'], font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 14))

    for lbl, var in [("Frequency", ctrl_vars['freq']),
                     ("Power Level", ctrl_vars['power']),
                     ("Angle Step", ctrl_vars['angle_step']),
                     ("Measurement Interval", ctrl_vars['interval'])]:
        row = tk.Frame(content, bg=COLORS['bg_panel'])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=lbl, bg=COLORS['bg_panel'], fg=COLORS['text_muted'],
                 font=("Segoe UI", 10), width=20, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, textvariable=var, bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                 font=("Segoe UI", 11, "bold"), anchor="w").pack(side=tk.LEFT, padx=(10, 0))

    # --- Non-Idealities ---
    ni_card = tk.Frame(scrollable_frame, bg=COLORS['bg_panel'], relief=tk.FLAT, bd=0)
    ni_card.pack(fill=tk.X, pady=(0, 12), padx=5)
    tk.Frame(ni_card, bg=COLORS['accent'], height=2).pack(fill=tk.X)
    ni_content = tk.Frame(ni_card, bg=COLORS['bg_panel'])
    ni_content.pack(fill=tk.BOTH, padx=18, pady=16)
    tk.Label(ni_content, text="Non-Idealities & Compensation", bg=COLORS['bg_panel'],
             fg=COLORS['text_dark'], font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 14))

    for lbl, var in [("Calibration Error", nonideal_vars['cal_error']),
                     ("Noise Level", nonideal_vars['noise']),
                     ("Temperature", nonideal_vars['temp']),
                     ("Humidity", nonideal_vars['humidity'])]:
        row = tk.Frame(ni_content, bg=COLORS['bg_panel'])
        row.pack(fill=tk.X, pady=6)
        tk.Label(row, text=lbl, bg=COLORS['bg_panel'], fg=COLORS['text_muted'],
                 font=("Segoe UI", 10), width=20, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, textvariable=var, bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                 font=("Segoe UI", 11, "bold"), anchor="w").pack(side=tk.LEFT, padx=(10, 0))

    # Compensation info
    comp = tk.Text(ni_content, bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                   font=("Segoe UI", 9), wrap=tk.WORD, height=7,
                   padx=12, pady=12, relief=tk.FLAT, bd=0)
    comp.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
    comp.insert("1.0",
                "Compensation Methods:\n\n"
                "• Calibration Error: SOLT calibration applied\n"
                "• Noise Reduction: Averaging + digital filtering\n"
                "• Temperature Effects: Material-specific coefficients\n"
                "• Humidity Effects: Environmental compensation\n"
                "• Connector Repeatability: Multi-cycle assessment\n"
                "• Cable Flexure: Fixed cable routing")
    comp.config(state=tk.DISABLED)
