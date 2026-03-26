"""Debug console window – diagnostics, logs, motor control."""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import platform

from gui.colors import COLORS


class DebugConsole(tk.Toplevel):
    """Multi-tab debug / diagnostics window."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("SPAM - Debug Console")
        self.geometry("900x700")
        self.configure(bg=COLORS['bg_main'])
        self.transient(app)
        self.grab_set()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_system_tab()
        self._create_database_tab()
        self._create_log_tab()
        self._create_console_tab()
        self._create_config_tab()
        self._create_motor_tab()

        # Buttons
        bf = tk.Frame(self, bg=COLORS['bg_main'])
        bf.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(bf, text="Close", command=self.destroy,
                  bg=COLORS['secondary'], fg=COLORS['text_light'],
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                  padx=20, pady=5, cursor="hand2").pack(side=tk.RIGHT)
        tk.Button(bf, text="Refresh All", command=self._refresh_all,
                  bg=COLORS['accent'], fg=COLORS['text_light'],
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                  padx=20, pady=5, cursor="hand2").pack(side=tk.RIGHT, padx=(0, 10))

        self._refresh_all()
        self._schedule()
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ---- periodic ----
    def _schedule(self):
        if self.winfo_exists():
            self._update_log_tab()
            self._update_motor_status()
            self.after(2000, self._schedule)

    # ---- tabs ----
    def _scrolled_text(self, parent, dark=False):
        f = tk.Frame(parent, bg=COLORS['bg_main'])
        f.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        bg = "#1E1E1E" if dark else COLORS['bg_panel']
        fg = "#00FF00" if dark else COLORS['text_dark']
        tw = tk.Text(f, bg=bg, fg=fg, font=("Consolas", 9),
                     yscrollcommand=sb.set, wrap=tk.WORD, padx=10, pady=10)
        tw.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=tw.yview)
        return tw

    def _create_system_tab(self):
        frame = tk.Frame(self.notebook, bg=COLORS['bg_main'])
        self.notebook.add(frame, text="System Info")
        self._sys_text = self._scrolled_text(frame)

    def _create_database_tab(self):
        frame = tk.Frame(self.notebook, bg=COLORS['bg_main'])
        self.notebook.add(frame, text="Database")
        self._db_text = self._scrolled_text(frame)

    def _create_log_tab(self):
        frame = tk.Frame(self.notebook, bg=COLORS['bg_main'])
        self.notebook.add(frame, text="Measurement Log")
        tf = tk.Frame(frame, bg=COLORS['bg_main'])
        tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        sy = tk.Scrollbar(tf)
        sy.pack(side=tk.RIGHT, fill=tk.Y)
        sx = tk.Scrollbar(tf, orient=tk.HORIZONTAL)
        sx.pack(side=tk.BOTTOM, fill=tk.X)
        tree = ttk.Treeview(tf,
                            columns=("ID", "Angle", "Permittivity", "Permeability", "Timestamp"),
                            show="headings", yscrollcommand=sy.set, xscrollcommand=sx.set)
        for c, w in [("ID", 50), ("Angle", 80), ("Permittivity", 120),
                     ("Permeability", 120), ("Timestamp", 200)]:
            tree.heading(c, text=c if c != "Angle" else "Angle (°)")
            tree.column(c, width=w)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.config(command=tree.yview)
        sx.config(command=tree.xview)
        self._log_tree = tree

    def _create_console_tab(self):
        frame = tk.Frame(self.notebook, bg=COLORS['bg_main'])
        self.notebook.add(frame, text="Console")
        self._console_text = self._scrolled_text(frame, dark=True)

    def _create_config_tab(self):
        frame = tk.Frame(self.notebook, bg=COLORS['bg_main'])
        self.notebook.add(frame, text="Configuration")
        self._cfg_text = self._scrolled_text(frame)

    def _create_motor_tab(self):
        frame = tk.Frame(self.notebook, bg=COLORS['bg_main'])
        self.notebook.add(frame, text="Motor Control")
        content = tk.Frame(frame, bg=COLORS['bg_main'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        tk.Label(content, text="Manual Motor Control", bg=COLORS['bg_main'],
                 fg=COLORS['text_dark'], font=("Segoe UI", 14, "bold")).pack(pady=(0, 20))

        # Status
        sf = tk.LabelFrame(content, text="Motor Status", bg=COLORS['bg_panel'],
                           fg=COLORS['text_dark'], font=("Segoe UI", 11, "bold"),
                           padx=15, pady=15)
        sf.pack(fill=tk.X, pady=(0, 20))
        self._motor_st = tk.Label(sf, text="Status: --", bg=COLORS['bg_panel'],
                                  fg=COLORS['text_dark'], font=("Segoe UI", 10), anchor="w")
        self._motor_st.pack(fill=tk.X, pady=5)
        self._motor_pos = tk.Label(sf, text="Position: 0.0°", bg=COLORS['bg_panel'],
                                   fg=COLORS['text_dark'], font=("Segoe UI", 10), anchor="w")
        self._motor_pos.pack(fill=tk.X, pady=5)

        # Arm
        af = tk.LabelFrame(content, text="Arm Movement", bg=COLORS['bg_panel'],
                           fg=COLORS['text_dark'], font=("Segoe UI", 11, "bold"),
                           padx=15, pady=15)
        af.pack(fill=tk.X, pady=(0, 15))
        ar = tk.Frame(af, bg=COLORS['bg_panel'])
        ar.pack(fill=tk.X, pady=5)
        tk.Label(ar, text="Motor #:", bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 5))
        arm_m = tk.StringVar(value="1")
        tk.Entry(ar, textvariable=arm_m, width=5, font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 15))
        tk.Label(ar, text="Position (°):", bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                 font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 5))
        arm_p = tk.StringVar(value="0.0")
        tk.Entry(ar, textvariable=arm_p, width=10, font=("Segoe UI", 10)).pack(side=tk.LEFT)

        def _move_arm():
            try:
                mn = int(arm_m.get())
                pos = float(arm_p.get())
                ok = self.app.motor.send_command(mn, pos, command=1)
                if ok:
                    messagebox.showinfo("OK", f"Motor {mn} → {pos:.2f}°")
                else:
                    messagebox.showerror("Error", "Command failed")
            except ValueError as e:
                messagebox.showerror("Input Error", str(e))

        tk.Button(af, text="Move Arm", command=_move_arm,
                  bg=COLORS['secondary'], fg=COLORS['text_light'],
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT,
                  padx=20, pady=8, cursor="hand2").pack(pady=(10, 0))

        # Quick positions
        qf = tk.LabelFrame(content, text="Quick Positions", bg=COLORS['bg_panel'],
                           fg=COLORS['text_dark'], font=("Segoe UI", 11, "bold"),
                           padx=15, pady=15)
        qf.pack(fill=tk.X, pady=(0, 15))
        qb = tk.Frame(qf, bg=COLORS['bg_panel'])
        qb.pack(fill=tk.X)
        for i, (lbl, pos) in enumerate([("0°", 0), ("45°", 45), ("90°", 90), ("Home", 0)]):
            tk.Button(qb, text=lbl,
                      command=lambda p=pos, l=lbl: self._quick(p, l),
                      bg=COLORS['text_muted'], fg=COLORS['text_light'],
                      font=("Segoe UI", 9), relief=tk.FLAT,
                      padx=15, pady=5, cursor="hand2").grid(
                row=i // 2, column=i % 2, padx=5, pady=5, sticky="ew")
        qb.grid_columnconfigure(0, weight=1)
        qb.grid_columnconfigure(1, weight=1)

    def _quick(self, pos, label):
        self.app.motor.send_command(1, pos, command=1)
        self.app._log_debug(f"Quick move: {label}", "INFO")

    # ---- refreshers ----
    def _refresh_all(self):
        self._update_sys()
        self._update_db()
        self._update_log_tab()
        self.update_console_log()
        self._update_cfg()
        self._update_motor_status()

    def _set_text(self, widget, text):
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.config(state=tk.DISABLED)

    def _update_sys(self):
        import sqlalchemy, matplotlib, numpy
        lines = [
            "=" * 60, "SYSTEM INFORMATION", "=" * 60, "",
            f"Python: {sys.version}",
            f"Platform: {platform.system()} {platform.release()}",
            f"Machine: {platform.machine()}", "",
            f"SQLAlchemy: {sqlalchemy.__version__}",
            f"Matplotlib: {matplotlib.__version__}",
            f"NumPy: {numpy.__version__}", "",
            f"Measuring: {self.app.state['is_measuring']}",
            f"Angle: {self.app.state['current_angle']:.2f}°",
        ]
        self._set_text(self._sys_text, "\n".join(lines))

    def _update_db(self):
        from data.database_ops import SQLALCHEMY_DATABASE_URL, Measurement, Calibration
        db = self.app.db
        mc = db.session.query(Measurement).count()
        cc = db.session.query(Calibration).count()
        lines = [
            "=" * 60, "DATABASE", "=" * 60, "",
            f"URL: {SQLALCHEMY_DATABASE_URL}",
            f"Measurements: {mc}",
            f"Calibrations: {cc}",
        ]
        self._set_text(self._db_text, "\n".join(lines))

    def _update_log_tab(self):
        from data.database_ops import Measurement
        for item in self._log_tree.get_children():
            self._log_tree.delete(item)
        try:
            ms = self.app.db.session.query(Measurement).order_by(
                Measurement.timestamp.desc()).limit(100).all()
            for m in ms:
                self._log_tree.insert("", tk.END, values=(
                    m.id, f"{m.angle:.2f}", f"{m.permittivity:.4f}",
                    f"{m.permeability:.4f}", m.timestamp.strftime("%Y-%m-%d %H:%M:%S")))
        except Exception:
            pass

    def update_console_log(self):
        logs = self.app.debug_log[-100:] if self.app.debug_log else ["No log entries."]
        self._set_text(self._console_text, "\n".join(logs))
        self._console_text.see(tk.END)

    def _update_cfg(self):
        lines = ["=" * 60, "CONFIGURATION", "=" * 60, ""]
        for k, v in self.app.settings.connection.items():
            lines.append(f"  {k}: {v}")
        lines += ["", "Color Scheme:"]
        for k, v in COLORS.items():
            lines.append(f"  {k}: {v}")
        self._set_text(self._cfg_text, "\n".join(lines))

    def _update_motor_status(self):
        if hasattr(self, '_motor_st'):
            self._motor_st.config(text=f"Status: {self.app.motor_status_var.get()}")
            self._motor_pos.config(text=f"Position: {self.app.motor_position_var.get()}")

    def _close(self):
        self.grab_release()
        self.destroy()
