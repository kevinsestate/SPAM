"""DebugConsole: standalone Toplevel window for debugging."""

import sys
import platform
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np

from .themes import _FONT, _MONO
from backend import Measurement, Calibration, SQLALCHEMY_DATABASE_URL


class DebugConsole(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        t = parent.theme
        self.title("SPAM - Debug Console")
        self.geometry("1000x650")
        self.configure(bg=t['bg'])
        self.transient(parent)
        self.grab_set()

        self._autoscroll_var = tk.BooleanVar(value=True)
        self._log_count_var = tk.StringVar(value="0 entries")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._create_console_tab()
        self._create_system_tab()
        self._create_database_tab()
        self._create_measurement_tab()
        self._create_config_tab()
        self._create_motor_tab()

        bf = tk.Frame(self, bg=t['bg'])
        bf.pack(fill=tk.X, padx=8, pady=(0, 8))
        parent._make_btn(bf, "Close", self.destroy, "ghost").pack(side=tk.RIGHT)
        parent._make_btn(bf, "Refresh", self._refresh_all, "accent").pack(side=tk.RIGHT, padx=(0, 4))

        self._refresh_all()
        self._schedule_refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _t(self, key):
        return self.parent.theme[key]

    def _text_widget(self, parent, dark_bg=False):
        bg = "#1A1A1A" if dark_bg else self._t('bg_panel')
        fg = "#4EC9B0" if dark_bg else self._t('text')
        f = tk.Frame(parent, bg=bg)
        f.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tw = tk.Text(f, bg=bg, fg=fg, font=(_MONO, 9), yscrollcommand=sb.set,
                     wrap=tk.WORD, padx=8, pady=8, insertbackground=fg,
                     relief=tk.FLAT, bd=0)
        tw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=tw.yview)
        return tw

    def _create_system_tab(self):
        f = tk.Frame(self.notebook, bg=self._t('bg'))
        self.notebook.add(f, text="System Info")
        self.system_info_text = self._text_widget(f)

    def _create_database_tab(self):
        f = tk.Frame(self.notebook, bg=self._t('bg'))
        self.notebook.add(f, text="Database")
        self.database_text = self._text_widget(f)

    def _create_measurement_tab(self):
        f = tk.Frame(self.notebook, bg=self._t('bg'))
        self.notebook.add(f, text="Measurements")
        tf = tk.Frame(f, bg=self._t('bg'))
        tf.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        sy = ttk.Scrollbar(tf, orient=tk.VERTICAL)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = ttk.Scrollbar(tf, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        tree = ttk.Treeview(tf, columns=("ID","Angle","Perm","Perm_b","Time"),
                            show="headings", yscrollcommand=sy.set, xscrollcommand=sx.set)
        for col, hdr, w in [("ID","ID",50),("Angle","Angle",80),("Perm","\u03b5",110),
                             ("Perm_b","\u03bc",110),("Time","Timestamp",180)]:
            tree.heading(col, text=hdr)
            tree.column(col, width=w)
        tree.pack(fill=tk.BOTH, expand=True)
        sy.config(command=tree.yview)
        sx.config(command=tree.xview)
        self.measurement_tree = tree

    def _create_console_tab(self):
        f = tk.Frame(self.notebook, bg=self._t('bg'))
        self.notebook.add(f, text="Console")

        # text area
        bg = "#1A1A1A"
        fg = "#CCCCCC"
        tf = tk.Frame(f, bg=bg)
        tf.pack(fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tw = tk.Text(tf, bg=bg, fg=fg, font=(_MONO, 10), yscrollcommand=sb.set,
                     wrap=tk.WORD, padx=10, pady=8, insertbackground=fg,
                     relief=tk.FLAT, bd=0, state=tk.DISABLED)
        tw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=tw.yview)
        self.console_text = tw

        # color tags
        tw.tag_configure("SUCCESS", foreground="#4EC9B0")
        tw.tag_configure("ERROR",   foreground="#F44747")
        tw.tag_configure("WARNING", foreground="#DCDCAA")
        tw.tag_configure("INFO",    foreground="#CCCCCC")
        tw.tag_configure("DEBUG",   foreground="#858585")

        # footer bar
        footer = tk.Frame(f, bg=self._t('bg_elevated'), height=32)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)
        self.parent._make_btn(footer, "Clear Log", self._clear_log, "ghost").pack(
            side=tk.LEFT, padx=(6, 0), pady=4)
        tk.Checkbutton(
            footer, text="Auto-scroll", variable=self._autoscroll_var,
            bg=self._t('bg_elevated'), fg=self._t('text_sec'),
            selectcolor=self._t('bg_input'), activebackground=self._t('bg_elevated'),
            font=(_FONT, 9), bd=0, highlightthickness=0
        ).pack(side=tk.LEFT, padx=8, pady=4)
        tk.Label(footer, textvariable=self._log_count_var,
                 bg=self._t('bg_elevated'), fg=self._t('text_sec'),
                 font=(_FONT, 8)).pack(side=tk.RIGHT, padx=10)

    def _create_config_tab(self):
        f = tk.Frame(self.notebook, bg=self._t('bg'))
        self.notebook.add(f, text="Config")
        self.config_text = self._text_widget(f)

    def _create_motor_tab(self):
        f = tk.Frame(self.notebook, bg=self._t('bg'))
        self.notebook.add(f, text="Motor")
        content = tk.Frame(f, bg=self._t('bg'), padx=16, pady=16)
        content.pack(fill=tk.BOTH, expand=True)
        tk.Label(content, text="Manual Motor Control", bg=self._t('bg'),
                 fg=self._t('text'), font=(_FONT, 12, "bold")).pack(pady=(0, 12))
        sf = tk.LabelFrame(content, text="Status", bg=self._t('bg_panel'),
                           fg=self._t('text'), font=(_FONT, 9, "bold"), padx=12, pady=8)
        sf.pack(fill=tk.X, pady=(0, 12))
        self.motor_status_label = tk.Label(sf, text="Status: --", bg=self._t('bg_panel'),
                                           fg=self._t('text'), font=(_MONO, 9), anchor="w")
        self.motor_status_label.pack(fill=tk.X, pady=2)
        self.motor_position_label = tk.Label(sf, text="Position: 0.0\u00b0", bg=self._t('bg_panel'),
                                              fg=self._t('text'), font=(_MONO, 9), anchor="w")
        self.motor_position_label.pack(fill=tk.X, pady=2)
        # arm movement
        af = tk.LabelFrame(content, text="Arm Movement", bg=self._t('bg_panel'),
                           fg=self._t('text'), font=(_FONT, 9, "bold"), padx=12, pady=8)
        af.pack(fill=tk.X, pady=(0, 12))
        af.columnconfigure(1, weight=1)
        arm_motor_v = tk.StringVar(value="1")
        arm_pos_v = tk.StringVar(value="0.0")
        tk.Label(af, text="Motor #:", bg=self._t('bg_panel'), fg=self._t('text_sec'),
                 font=(_FONT, 9)).grid(row=0, column=0, sticky="w", padx=(0, 6))
        tk.Entry(af, textvariable=arm_motor_v, bg=self._t('bg_input'), fg=self._t('text'),
                 font=(_MONO, 9), width=6, relief=tk.FLAT).grid(row=0, column=1, sticky="w")
        tk.Label(af, text="Position:", bg=self._t('bg_panel'), fg=self._t('text_sec'),
                 font=(_FONT, 9)).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(4, 0))
        tk.Entry(af, textvariable=arm_pos_v, bg=self._t('bg_input'), fg=self._t('text'),
                 font=(_MONO, 9), width=10, relief=tk.FLAT).grid(row=1, column=1, sticky="w", pady=(4, 0))
        def move_arm():
            try:
                mn = int(arm_motor_v.get()); pos = float(arm_pos_v.get())
                self.parent._send_motor_command(mn, pos, command=1)
            except ValueError as e:
                messagebox.showerror("Error", str(e))
        self.parent._make_btn(af, "Move", move_arm, "accent").grid(row=2, column=0, columnspan=2, pady=(8, 0))
        # quick positions
        qf = tk.LabelFrame(content, text="Quick Positions", bg=self._t('bg_panel'),
                           fg=self._t('text'), font=(_FONT, 9, "bold"), padx=12, pady=8)
        qf.pack(fill=tk.X, pady=(0, 12))
        qf.columnconfigure(0, weight=1); qf.columnconfigure(1, weight=1)
        for i, (lbl, pos) in enumerate([("0\u00b0", 0), ("45\u00b0", 45), ("90\u00b0", 90)]):
            self.parent._make_btn(qf, lbl,
                lambda p=pos: self.parent._send_motor_command(0, p, command=0),
                "ghost").grid(row=i//2, column=i%2, padx=2, pady=2, sticky="ew")
        self.parent._make_btn(qf, "Home \u2302",
            lambda: threading.Thread(target=self.parent._home_worker, daemon=True).start(),
            "accent").grid(row=1, column=1, padx=2, pady=2, sticky="ew")

    def _schedule_refresh(self):
        if self.winfo_exists():
            self._update_measurement_log()
            if hasattr(self, 'motor_status_label'):
                self._update_motor_status()
            self.after(2000, self._schedule_refresh)

    def _refresh_all(self):
        self._update_system_info()
        self._update_database_info()
        self._update_measurement_log()
        self.update_console_log()
        self._update_config()
        self._update_motor_status()

    def _update_system_info(self):
        import sqlalchemy, matplotlib
        info = [
            "SYSTEM INFO", "=" * 50, "",
            f"Python: {sys.version}", f"Platform: {platform.system()} {platform.release()}",
            f"Machine: {platform.machine()}", "",
            f"SQLAlchemy: {sqlalchemy.__version__}", f"Matplotlib: {matplotlib.__version__}",
            f"NumPy: {np.__version__}", "",
            f"Measuring: {self.parent.is_measuring}", f"Angle: {self.parent.current_angle:.2f}\u00b0",
        ]
        self.system_info_text.config(state=tk.NORMAL)
        self.system_info_text.delete(1.0, tk.END)
        self.system_info_text.insert(1.0, "\n".join(info))
        self.system_info_text.config(state=tk.DISABLED)

    def _update_database_info(self):
        info = ["DATABASE", "=" * 50, "", f"URL: {SQLALCHEMY_DATABASE_URL}", ""]
        try:
            mc = self.parent.db.query(Measurement).count()
            cc = self.parent.db.query(Calibration).count()
            info += [f"Measurements: {mc}", f"Calibrations: {cc}"]
        except Exception as e:
            info.append(f"Error: {e}")
        self.database_text.config(state=tk.NORMAL)
        self.database_text.delete(1.0, tk.END)
        self.database_text.insert(1.0, "\n".join(info))
        self.database_text.config(state=tk.DISABLED)

    def _update_measurement_log(self):
        for item in self.measurement_tree.get_children():
            self.measurement_tree.delete(item)
        try:
            for m in self.parent.db.query(Measurement).order_by(Measurement.timestamp.desc()).limit(100).all():
                self.measurement_tree.insert("", tk.END, values=(
                    m.id, f"{m.angle:.2f}", f"{m.permittivity:.4f}",
                    f"{m.permeability:.4f}", m.timestamp.strftime("%H:%M:%S")))
        except:
            pass

    def _clear_log(self):
        self.parent.debug_log.clear()
        self.update_console_log()

    def update_console_log(self):
        tw = self.console_text
        tw.config(state=tk.NORMAL)
        tw.delete(1.0, tk.END)
        lines = self.parent.debug_log[-200:] if self.parent.debug_log else ["No log entries."]
        for line in lines:
            tag = "INFO"
            for lvl in ("SUCCESS", "ERROR", "WARNING", "DEBUG"):
                if f"[{lvl}]" in line:
                    tag = lvl
                    break
            tw.insert(tk.END, line + "\n", tag)
        if self._autoscroll_var.get():
            tw.see(tk.END)
        tw.config(state=tk.DISABLED)
        count = len(self.parent.debug_log)
        self._log_count_var.set(f"{count} {'entry' if count == 1 else 'entries'}")

    def _update_config(self):
        info = ["CONFIG", "=" * 50, ""]
        info += [f"  {k}: {v}" for k, v in self.parent.connection_settings.items()]
        info += ["", f"Window: {self.parent.winfo_width()}x{self.parent.winfo_height()}",
                 f"Theme: {self.parent._theme_name}"]
        self.config_text.config(state=tk.NORMAL)
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(1.0, "\n".join(info))
        self.config_text.config(state=tk.DISABLED)

    def _update_motor_status(self):
        if hasattr(self, 'motor_status_label'):
            self.motor_status_label.config(text=f"Status: {self.parent.motor_status_var.get()}")
        if hasattr(self, 'motor_position_label'):
            self.motor_position_label.config(text=f"Position: {self.parent.motor_position_var.get()}")

    def _on_close(self):
        self.grab_release()
        self.destroy()
