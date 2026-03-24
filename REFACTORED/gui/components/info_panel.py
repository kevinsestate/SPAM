"""Right-hand information panel."""
import tkinter as tk
from gui.colors import COLORS


def _card(parent, label_text, var, accent_color=None):
    accent = accent_color or COLORS['secondary']
    card = tk.Frame(parent, bg=COLORS['bg_panel'], relief=tk.FLAT, bd=0)
    card.pack(fill=tk.X, pady=4)
    tk.Frame(card, bg=accent, height=2).pack(fill=tk.X)
    content = tk.Frame(card, bg=COLORS['bg_panel'])
    content.pack(fill=tk.BOTH, padx=12, pady=8)
    row = tk.Frame(content, bg=COLORS['bg_panel'])
    row.pack(fill=tk.X)
    tk.Label(row, text=label_text, bg=COLORS['bg_panel'],
             fg=COLORS['text_muted'], font=("Segoe UI", 9)).pack(side=tk.LEFT)
    tk.Label(row, textvariable=var, bg=COLORS['bg_panel'],
             fg=COLORS['text_dark'], font=("Segoe UI", 12, "bold")).pack(side=tk.RIGHT)


def create_info_panel(root, tk_vars):
    """Build the right info panel.

    *tk_vars* is a dict of tk.StringVar instances:
        angle, permittivity, permeability, status,
        s11, s12, s21, s22,
        motor_status, motor_position, system_status
    """
    frame = tk.Frame(root, bg=COLORS['bg_main'], width=320)
    frame.pack(side=tk.RIGHT, fill=tk.Y, padx=15, pady=15)
    frame.pack_propagate(False)

    # Measurement Data
    tk.Label(frame, text="Measurement Data", bg=COLORS['bg_main'],
             fg=COLORS['text_dark'], font=("Segoe UI", 14, "bold")).pack(
        padx=0, pady=(10, 12), anchor="w")

    for lbl, key in [("Current Angle", 'angle'),
                     ("Permittivity (ε)", 'permittivity'),
                     ("Permeability (μ)", 'permeability'),
                     ("Status", 'status')]:
        _card(frame, lbl, tk_vars[key])

    # Motor Control
    tk.Label(frame, text="Motor Control", bg=COLORS['bg_main'],
             fg=COLORS['text_dark'], font=("Segoe UI", 14, "bold")).pack(
        padx=0, pady=(12, 12), anchor="w")
    for lbl, key in [("Status", 'motor_status'),
                     ("Position", 'motor_position')]:
        _card(frame, lbl, tk_vars[key], COLORS['warning'])

    # S-Parameters
    tk.Label(frame, text="S-Parameters", bg=COLORS['bg_main'],
             fg=COLORS['text_dark'], font=("Segoe UI", 14, "bold")).pack(
        padx=0, pady=(12, 12), anchor="w")
    for lbl, key in [("S₁₁", 's11'), ("S₁₂", 's12'),
                     ("S₂₁", 's21'), ("S₂₂", 's22')]:
        _card(frame, lbl, tk_vars[key], COLORS['accent'])

    # Spacer + system status
    tk.Frame(frame, bg=COLORS['bg_main']).pack(expand=True)
    sys_card = tk.Frame(frame, bg=COLORS['bg_panel'], relief=tk.FLAT, bd=0)
    sys_card.pack(fill=tk.X, pady=(8, 0))
    tk.Frame(sys_card, bg=COLORS['accent'], height=2).pack(fill=tk.X)
    sc = tk.Frame(sys_card, bg=COLORS['bg_panel'])
    sc.pack(fill=tk.BOTH, padx=12, pady=8)
    sr = tk.Frame(sc, bg=COLORS['bg_panel'])
    sr.pack(fill=tk.X)
    tk.Label(sr, text="System Status", bg=COLORS['bg_panel'],
             fg=COLORS['text_muted'], font=("Segoe UI", 9)).pack(side=tk.LEFT)
    tk.Label(sr, textvariable=tk_vars['system_status'], bg=COLORS['bg_panel'],
             fg=COLORS['success'], font=("Segoe UI", 12, "bold")).pack(side=tk.RIGHT)

    return frame
