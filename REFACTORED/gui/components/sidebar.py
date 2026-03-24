"""Sidebar panel with action buttons."""
import tkinter as tk
from gui.colors import COLORS


def create_sidebar(root, callbacks):
    """Build the left sidebar with action buttons.

    *callbacks* dict keys:
        calibrate, start, stop, clear, view_results, export, debug_console

    Returns a dict with references:
        frame, start_btn, stop_btn, start_container, stop_container,
        clear_container, buttons
    """
    sidebar = tk.Frame(root, bg=COLORS['bg_sidebar'], width=280)
    sidebar.pack(side=tk.LEFT, fill=tk.Y)
    sidebar.pack_propagate(False)

    # Header
    header = tk.Frame(sidebar, bg=COLORS['primary'], height=80)
    header.pack(fill=tk.X, pady=(0, 20))
    header.pack_propagate(False)
    tk.Label(header, text="SPAM", bg=COLORS['primary'],
             fg=COLORS['text_light'], font=("Segoe UI", 24, "bold")).pack(pady=20)

    btn_style = {
        "font": ("Segoe UI", 11, "bold"),
        "fg": COLORS['text_light'],
        "relief": tk.FLAT,
        "activeforeground": COLORS['text_light'],
        "cursor": "hand2", "bd": 0, "highlightthickness": 0,
    }

    actions = [
        ("Calibrate",          callbacks['calibrate'],      COLORS['secondary']),
        ("Start Measurement",  callbacks['start'],          COLORS['success']),
        ("Stop Measurement",   callbacks['stop'],           COLORS['danger']),
        ("Clear Measurements", callbacks['clear'],          COLORS['warning']),
        ("View Results",       callbacks['view_results'],   COLORS['secondary']),
        ("Export Data",        callbacks['export'],         COLORS['secondary']),
        ("Debug Console",      callbacks['debug_console'],  COLORS['text_muted']),
    ]

    refs = {'buttons': [], 'frame': sidebar}

    for label, cmd, bg in actions:
        container = tk.Frame(sidebar, bg=COLORS['bg_sidebar'])
        container.pack(padx=20, pady=8, fill=tk.X)
        btn = tk.Button(container, text=label, command=cmd,
                        bg=bg, activebackground=COLORS['hover'], **btn_style)
        btn.pack(fill=tk.BOTH, ipady=12)
        btn.bind('<Enter>', lambda e, b=btn: b.config(bg=COLORS['hover']))
        btn.bind('<Leave>', lambda e, b=btn, c=bg: b.config(bg=c))

        if "Start" in label:
            refs['start_btn'] = btn
            refs['start_container'] = container
        elif "Stop" in label:
            refs['stop_btn'] = btn
            refs['stop_container'] = container
            container.pack_forget()
        elif "Clear" in label:
            refs['clear_container'] = container

        refs['buttons'].append(btn)

    # Spacer + version
    tk.Frame(sidebar, bg=COLORS['bg_sidebar']).pack(expand=True)
    tk.Label(sidebar, text="Version 1.01", bg=COLORS['bg_sidebar'],
             fg=COLORS['text_muted'], font=("Segoe UI", 8)).pack(pady=(0, 10))

    return refs
