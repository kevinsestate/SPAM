"""
SPAM – Scanner for Polarized Anisotropic Materials
===================================================
Refactored main application.  Orchestrates the modules in:
    config/      – settings persistence
    hardware/    – motor control (I2C / GPIO)
    data/        – database CRUD and export
    measurement/ – sweep worker and calibration
    gui/         – UI components, graphs, dialogs
"""
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
import threading
import platform

# ---------------------------------------------------------------------------
# Make sure sub-packages are importable regardless of how the script is run
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# DPI awareness (Windows)
if platform.system() == 'Windows':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------
from config.settings import Settings
from hardware.motor_control import MotorController
from data.database_ops import DatabaseManager
from data.export import export_measurements
from measurement.worker import MeasurementWorker
from measurement.calibration import CalibrationManager

from gui.colors import COLORS
from gui.components.menu_bar import create_menu
from gui.components.sidebar import create_sidebar
from gui.components.info_panel import create_info_panel
from gui.components.control_panel import create_control_panel
from gui.components.status_bar import create_status_bar
from gui.graphs.graph_manager import GraphManager
from gui.dialogs.debug_console import DebugConsole


class SPAMGui(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("SPAM - Scanner for Polarized Anisotropic Materials")

        # Window sizing
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if platform.system() == 'Windows':
            self.state('zoomed')
        else:
            self.geometry(f"{min(sw, 1920)}x{min(sh, 1080)}")
            self.update_idletasks()
            self.geometry(f"+{(sw - self.winfo_width()) // 2}+{(sh - self.winfo_height()) // 2}")

        self.configure(bg=COLORS['bg_main'])
        self.is_fullscreen = False
        self.resize_timer = None
        self.resize_delay = 150

        # Debug log
        self.debug_log: list[str] = []
        self.debug_window = None

        # ----- shared mutable state dict (used by worker thread) -----
        self.state = {
            'is_measuring': False,
            'current_angle': 0.0,
            'angle_step': 5.0,
            'measurement_interval': 0.5,
            'motor_num': 1,
            'motor_command': 1,
            'transmitted_power': 0.0,
            'reflected_power': 0.0,
            'transmitted_phase': 0.0,
            'reflected_phase': 0.0,
        }

        # Scalar parameters (not shared with thread)
        self.frequency = 10.0
        self.power_level = -10.0
        self.calibration_error = 0.0
        self.noise_level = 0.0
        self.temperature = 25.0
        self.humidity = 45.0

        # S-parameters
        self.s11_mag = self.s11_phase = 0.0
        self.s12_mag = self.s12_phase = 0.0
        self.s21_mag = self.s21_phase = 0.0
        self.s22_mag = self.s22_phase = 0.0

        # ----- services -----
        self.settings = Settings(config_dir=_HERE)
        self.motor = MotorController(
            settings=self.settings.connection,
            log=self._log_debug,
            gui_after=self.after
        )
        # Wire motor callbacks
        self.motor.on_collision = lambda: self.after(0, self._on_motor_collision)
        self.motor.on_position_reached = lambda: self.after(0, self._on_motor_ready)

        # Tk display variables
        self.motor_status_var = tk.StringVar(value="Not Initialized")
        self.motor_position_var = tk.StringVar(value="0.0°")

        # Start motor init on Pi
        if platform.system() == 'Linux':
            self.after(200, self._init_motor)

        # ----- build GUI -----
        self._build_ui()

        # Deferred heavy init (database, periodic refresh)
        self.after(100, self._init_background)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # UI assembly
    # ==================================================================
    def _build_ui(self):
        # Tk StringVars for the info panel
        self._tk = {
            'angle': tk.StringVar(value="0.0°"),
            'permittivity': tk.StringVar(value="0.00"),
            'permeability': tk.StringVar(value="0.00"),
            'status': tk.StringVar(value="Ready"),
            's11': tk.StringVar(value="0.00∠0°"),
            's12': tk.StringVar(value="0.00∠0°"),
            's21': tk.StringVar(value="0.00∠0°"),
            's22': tk.StringVar(value="0.00∠0°"),
            'motor_status': self.motor_status_var,
            'motor_position': self.motor_position_var,
            'system_status': tk.StringVar(value="Ready"),
        }
        self._ctrl_vars = {
            'freq': tk.StringVar(value="10.0 GHz"),
            'power': tk.StringVar(value="-10.0 dBm"),
            'angle_step': tk.StringVar(value="5.0°"),
            'interval': tk.StringVar(value="0.5 s"),
        }
        self._ni_vars = {
            'cal_error': tk.StringVar(value="0.0%"),
            'noise': tk.StringVar(value="0.0 dB"),
            'temp': tk.StringVar(value="25.0°C"),
            'humidity': tk.StringVar(value="45.0%"),
        }

        # Menu
        create_menu(self, {
            'export': self._on_export,
            'adjust_params': self._on_adjust_parameters,
            'connection_setup': self._on_connection_setup,
            'debug_console': self._on_debug_console,
            'toggle_fullscreen': self._toggle_fullscreen,
            'exit_fullscreen': self._exit_fullscreen,
            'help': self._on_help,
        })

        # Status bar (pack BOTTOM first so it stays at the bottom)
        self._status_frame, self._status_text, self._status_ind, self._time_lbl = \
            create_status_bar(self)

        # Sidebar
        self._sidebar = create_sidebar(self, {
            'calibrate': self._on_calibrate,
            'start': self._on_start,
            'stop': self._on_stop,
            'clear': self._on_clear,
            'view_results': self._on_view_results,
            'export': self._on_export,
            'debug_console': self._on_debug_console,
        })

        # Info panel (RIGHT)
        create_info_panel(self, self._tk)

        # Centre – scrollable graph area
        self._build_center()

    def _build_center(self):
        center = tk.Frame(self, bg=COLORS['bg_main'])
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(15, 0), pady=15)

        tk.Label(center, text="Real-Time Measurements", bg=COLORS['bg_main'],
                 fg=COLORS['text_dark'], font=("Segoe UI", 16, "bold")).pack(
            fill=tk.X, pady=(5, 10), side=tk.TOP, anchor="w")

        # Scrollable canvas
        cc = tk.Frame(center, bg=COLORS['bg_main'])
        cc.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(cc, orient=tk.VERTICAL)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(cc, bg=COLORS['bg_main'], yscrollcommand=sb.set, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=COLORS['bg_main'])
        cw = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Graphs
        self.graphs = GraphManager(scrollable)

        # Control + Non-idealities panels (below graphs)
        create_control_panel(scrollable, self._ctrl_vars, self._ni_vars)

        self._graphs_canvas = canvas

        # Resize debounce
        def _on_resize(event):
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            self.resize_timer = self.after(self.resize_delay, self.graphs.relayout)
        self.bind('<Configure>', _on_resize)

    # ==================================================================
    # Deferred init
    # ==================================================================
    def _init_background(self):
        try:
            self.db = DatabaseManager(log=self._log_debug)
        except Exception as e:
            self._log_debug(f"Database init error: {e}", "ERROR")
        self._update_display()

    def _init_motor(self):
        self.motor.initialize()
        if self.motor.enabled:
            self.motor_status_var.set("Ready")
        else:
            self.motor_status_var.set(
                "Not Available (Windows)" if platform.system() != 'Linux'
                else "Init Failed"
            )

    # ==================================================================
    # Motor callbacks
    # ==================================================================
    def _on_motor_collision(self):
        self._log_debug("COLLISION DETECTED", "ERROR")
        self.motor_status_var.set("COLLISION!")
        self._update_status("Motor collision detected!", "error")
        if self.state['is_measuring']:
            self._on_stop()

    def _on_motor_ready(self):
        self._log_debug("POSITION REACHED", "INFO")
        self.motor_status_var.set("Ready")

    # ==================================================================
    # Periodic display refresh
    # ==================================================================
    def _update_display(self):
        if hasattr(self, 'db'):
            measurements = self.db.get_measurements()
            self.graphs.update(measurements)

            latest = measurements[0] if measurements else None
            if latest:
                self._tk['angle'].set(f"{latest.angle:.1f}°")
                self._tk['permittivity'].set(f"{latest.permittivity:.2f}")
                self._tk['permeability'].set(f"{latest.permeability:.2f}")
            else:
                self._tk['angle'].set("0.0°")
                self._tk['permittivity'].set("0.00")
                self._tk['permeability'].set("0.00")

        # S-params
        self._tk['s11'].set(f"{self.s11_mag:.3f}∠{self.s11_phase:.1f}°")
        self._tk['s12'].set(f"{self.s12_mag:.3f}∠{self.s12_phase:.1f}°")
        self._tk['s21'].set(f"{self.s21_mag:.3f}∠{self.s21_phase:.1f}°")
        self._tk['s22'].set(f"{self.s22_mag:.3f}∠{self.s22_phase:.1f}°")

        self.motor_position_var.set(f"{self.state['current_angle']:.1f}°")

        self._ctrl_vars['freq'].set(f"{self.frequency:.1f} GHz")
        self._ctrl_vars['power'].set(f"{self.power_level:.1f} dBm")
        self._ctrl_vars['angle_step'].set(f"{self.state['angle_step']:.1f}°")
        self._ctrl_vars['interval'].set(f"{self.state['measurement_interval']:.2f} s")

        if not self.state['is_measuring']:
            self.calibration_error = 0.0
            self.noise_level = 0.0
        self._ni_vars['cal_error'].set(f"{self.calibration_error:.2f}%")
        self._ni_vars['noise'].set(f"{self.noise_level:.1f} dB")
        self._ni_vars['temp'].set(f"{self.temperature:.1f}°C")
        self._ni_vars['humidity'].set(f"{self.humidity:.1f}%")

        if hasattr(self, 'db'):
            try:
                self._graphs_canvas.configure(scrollregion=self._graphs_canvas.bbox("all"))
            except Exception:
                pass

        self.after(1000, self._update_display)

    # ==================================================================
    # Status helpers
    # ==================================================================
    def _update_status(self, msg, kind="info"):
        self._status_text.set(msg)
        self._time_lbl.config(text=f"Last Update: {datetime.now():%Y-%m-%d %H:%M:%S}")
        cm = {"success": COLORS['success'], "warning": COLORS['warning'],
              "error": COLORS['danger'], "info": COLORS['secondary']}
        self._status_ind.config(fg=cm.get(kind, COLORS['success']))

    def _log_debug(self, msg, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] [{level}] {msg}"
        self.debug_log.append(entry)
        if len(self.debug_log) > 1000:
            self.debug_log = self.debug_log[-1000:]
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.update_console_log()

    # ==================================================================
    # Button state management
    # ==================================================================
    def _update_button_states(self):
        s = self._sidebar
        if self.state['is_measuring']:
            s['start_container'].pack_forget()
            s['stop_container'].pack(padx=20, pady=8, fill=tk.X, before=s['clear_container'])
        else:
            s['stop_container'].pack_forget()
            s['start_container'].pack(padx=20, pady=8, fill=tk.X, before=s['clear_container'])

    # ==================================================================
    # Command handlers
    # ==================================================================
    def _on_start(self):
        if self.state['is_measuring']:
            return
        self.state['is_measuring'] = True
        self.state['current_angle'] = 0.0
        self._tk['status'].set("Measuring...")
        self._update_status("Measurement started – sweeping 0°→90°", "info")
        self._update_button_states()
        self._log_debug("Measurement started", "INFO")
        worker = MeasurementWorker(self.motor, self.db, self.state,
                                   log=self._log_debug, gui_after=self.after)
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

    def _on_stop(self):
        if not self.state['is_measuring']:
            return
        self.state['is_measuring'] = False
        self._tk['status'].set("Stopping...")
        self._update_status("Stopping…", "warning")
        self._update_button_states()
        self._log_debug(f"Stopped at {self.state['current_angle']:.2f}°", "INFO")
        self.after(500, lambda: self._tk['status'].set("Ready"))

    def _on_clear(self):
        measurements = self.db.get_measurements()
        if not measurements:
            messagebox.showinfo("No Data", "No measurements to clear.")
            return
        if messagebox.askyesno("Confirm", f"Delete all {len(measurements)} measurements?", icon='warning'):
            n = self.db.clear_measurements()
            self.state['current_angle'] = 0.0
            self.graphs.update([])
            self._tk['angle'].set("0.0°")
            self._tk['permittivity'].set("0.00")
            self._tk['permeability'].set("0.00")
            self._update_status(f"Cleared {n} measurements", "success")

    def _on_calibrate(self):
        if not messagebox.askokcancel("Calibration – Step 1",
                                       "Remove material from fixture.\nClick OK to begin."):
            return
        self._tk['status'].set("Calibrating (Empty)…")
        self._log_debug("Calibration step 1: empty", "INFO")

        def _step2():
            self._log_debug("Step 1 complete", "SUCCESS")
            if not messagebox.askokcancel("Calibration – Step 2",
                                           "Place material in fixture.\nClick OK."):
                self._tk['status'].set("Ready")
                return
            self._tk['status'].set("Calibrating (Material)…")
            self._log_debug("Calibration step 2: material", "INFO")

            def _done():
                cm = CalibrationManager(self.db, log=self._log_debug)
                c = cm.save()
                if c:
                    self._update_status("Calibration completed", "success")
                    self._tk['status'].set("Ready")
                    messagebox.showinfo("Done", "Calibration completed!")
                else:
                    self._update_status("Calibration failed", "error")
            self.after(2000, _done)
        self.after(2000, _step2)

    def _on_view_results(self):
        ms = self.db.get_measurements()
        if not ms:
            messagebox.showinfo("No Results", "No measurements available.")
            return
        angles = [m.angle for m in ms]
        eps = [m.permittivity for m in ms]
        mu = [m.permeability for m in ms]
        txt = (f"Total: {len(ms)}\nAngle: {min(angles):.1f}°–{max(angles):.1f}°\n\n"
               f"ε  min={min(eps):.4f}  max={max(eps):.4f}  avg={sum(eps)/len(eps):.4f}\n"
               f"μ  min={min(mu):.4f}  max={max(mu):.4f}  avg={sum(mu)/len(mu):.4f}")
        messagebox.showinfo("Results", txt)

    def _on_export(self):
        ms = self.db.get_measurements()
        if not ms:
            messagebox.showwarning("No Data", "Nothing to export.")
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("All", "*.*")])
        if fp:
            ok = export_measurements(ms, fp, log=self._log_debug)
            if ok:
                self._update_status(f"Exported to {os.path.basename(fp)}", "success")
            else:
                messagebox.showerror("Error", "Export failed.")

    # ---- Dialogs ----
    def _on_adjust_parameters(self):
        dlg = tk.Toplevel(self)
        dlg.title("Adjust Parameters")
        dlg.geometry("450x400")
        dlg.configure(bg=COLORS['bg_main'])
        dlg.transient(self)
        dlg.grab_set()
        dlg.update_idletasks()
        dlg.geometry(f"450x400+{dlg.winfo_screenwidth()//2-225}+{dlg.winfo_screenheight()//2-200}")

        tk.Label(dlg, text="Measurement Parameters", bg=COLORS['bg_main'],
                 fg=COLORS['text_dark'], font=("Segoe UI", 14, "bold")).pack(pady=20)
        content = tk.Frame(dlg, bg=COLORS['bg_panel'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        fv = tk.StringVar(value=str(self.frequency))
        pv = tk.StringVar(value=str(self.power_level))
        av = tk.StringVar(value=str(self.state['angle_step']))
        iv = tk.StringVar(value=str(self.state['measurement_interval']))

        for lbl, var in [("Frequency (GHz):", fv), ("Power (dBm):", pv),
                         ("Angle Step (°):", av), ("Interval (s):", iv)]:
            r = tk.Frame(content, bg=COLORS['bg_panel'])
            r.pack(fill=tk.X, pady=8)
            tk.Label(r, text=lbl, bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                     font=("Segoe UI", 10), width=22, anchor="w").pack(side=tk.LEFT)
            tk.Entry(r, textvariable=var, font=("Segoe UI", 10), width=15,
                     relief=tk.SOLID, bd=1).pack(side=tk.LEFT)

        bf = tk.Frame(dlg, bg=COLORS['bg_main'])
        bf.pack(fill=tk.X, padx=20, pady=(0, 20))

        def _save():
            try:
                self.frequency = float(fv.get())
                self.power_level = float(pv.get())
                self.state['angle_step'] = float(av.get())
                self.state['measurement_interval'] = float(iv.get())
                self._log_debug(f"Params updated: f={self.frequency}, P={self.power_level}", "INFO")
                self._update_status("Parameters updated", "success")
                dlg.destroy()
            except ValueError as e:
                messagebox.showerror("Error", str(e))

        tk.Button(bf, text="Cancel", command=dlg.destroy, bg=COLORS['text_muted'],
                  fg=COLORS['text_light'], font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(bf, text="Save", command=_save, bg=COLORS['success'],
                  fg=COLORS['text_light'], font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.RIGHT)

    def _on_connection_setup(self):
        dlg = tk.Toplevel(self)
        dlg.title("Connection Setup")
        dlg.geometry("500x450")
        dlg.configure(bg=COLORS['bg_main'])
        dlg.transient(self)
        dlg.grab_set()
        dlg.update_idletasks()
        dlg.geometry(f"500x450+{dlg.winfo_screenwidth()//2-250}+{dlg.winfo_screenheight()//2-225}")

        tk.Label(dlg, text="Connection Configuration", bg=COLORS['bg_main'],
                 fg=COLORS['text_dark'], font=("Segoe UI", 14, "bold")).pack(pady=20)
        content = tk.Frame(dlg, bg=COLORS['bg_panel'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        sf = tk.LabelFrame(content, text="I2C / ADC", bg=COLORS['bg_panel'],
                           fg=COLORS['text_dark'], font=("Segoe UI", 11, "bold"), padx=15, pady=15)
        sf.pack(fill=tk.X, pady=(0, 15))

        vars_ = {}
        fields = [
            ("I2C Bus:", 'i2c_bus'), ("ADC Address:", 'adc_address'),
            ("IF-I Channel:", 'if_i_channel'), ("IF-Q Channel:", 'if_q_channel'),
            ("Sampling Rate:", 'sampling_rate'), ("MCU Address:", 'microcontroller_address'),
            ("ISR Pin:", 'isr_pin'),
        ]
        for i, (lbl, key) in enumerate(fields):
            tk.Label(sf, text=lbl, bg=COLORS['bg_panel'], fg=COLORS['text_dark'],
                     font=("Segoe UI", 10)).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=self.settings.get(key, ''))
            tk.Entry(sf, textvariable=v, font=("Segoe UI", 10), width=20).grid(
                row=i, column=1, sticky="w", pady=3)
            vars_[key] = v

        bf = tk.Frame(dlg, bg=COLORS['bg_main'])
        bf.pack(fill=tk.X, padx=20, pady=(0, 20))

        def _save():
            new = {k: v.get().strip() for k, v in vars_.items()}
            self.settings.update(new)
            self.settings.save(log_callback=self._log_debug)
            # Reinitialize motor
            if platform.system() == 'Linux':
                self.motor.cleanup()
                self.motor = MotorController(self.settings.connection,
                                             log=self._log_debug, gui_after=self.after)
                self.after(200, self._init_motor)
            self._update_status("Connection settings saved", "success")
            messagebox.showinfo("Saved", "Settings saved. Motor will reinitialize.")
            dlg.destroy()

        tk.Button(bf, text="Cancel", command=dlg.destroy, bg=COLORS['text_muted'],
                  fg=COLORS['text_light'], font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(bf, text="Save", command=_save, bg=COLORS['success'],
                  fg=COLORS['text_light'], font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.RIGHT)

    def _on_debug_console(self):
        if self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugConsole(self)
        else:
            self.debug_window.lift()
            self.debug_window.focus()

    def _on_help(self):
        messagebox.showinfo("About SPAM",
                            "SPAM – Scanner for Polarized Anisotropic Materials\n"
                            "Version 1.01\n\nKeyboard: F11=Fullscreen, Ctrl+D=Debug, Esc=Exit FS")

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)

    def _exit_fullscreen(self):
        if self.is_fullscreen:
            self._toggle_fullscreen()

    # ==================================================================
    # Cleanup
    # ==================================================================
    def _on_close(self):
        self.state['is_measuring'] = False
        self.motor.cleanup()
        if hasattr(self, 'db'):
            self.db.close()
        self.destroy()


# ======================================================================
def main():
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
    main()
