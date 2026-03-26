import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import csv
from datetime import datetime
import threading
import time
import platform
import math

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

if platform.system() == 'Windows':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from database import SessionLocal, engine, Base
from models import Measurement, Calibration, ExtractionResult

from spam_calc import compute_k0d, mil_to_m
from spam_optimizer import extract_material_progressive
from hardware import AD7193, RFSwitch

# ---------------------------------------------------------------------------
# Theme palettes
# ---------------------------------------------------------------------------
THEMES = {
    "dark": {
        "bg":          "#1E1E1E",
        "bg_sidebar":  "#252526",
        "bg_panel":    "#2D2D2D",
        "bg_elevated": "#333333",
        "bg_input":    "#3C3C3C",
        "text":        "#CCCCCC",
        "text_sec":    "#858585",
        "text_em":     "#FFFFFF",
        "border":      "#3E3E3E",
        "border_vis":  "#505050",
        "accent":      "#0078D4",
        "accent_hover":"#1A8AD4",
        "success":     "#4EC9B0",
        "warning":     "#DCDCAA",
        "error":       "#F44747",
        "plot1":       "#569CD6",
        "plot2":       "#4EC9B0",
        "grid":        "#3E3E3E",
    },
    "light": {
        "bg":          "#F5F5F5",
        "bg_sidebar":  "#E8E8E8",
        "bg_panel":    "#FFFFFF",
        "bg_elevated": "#FAFAFA",
        "bg_input":    "#FFFFFF",
        "text":        "#1E1E1E",
        "text_sec":    "#616161",
        "text_em":     "#000000",
        "border":      "#D4D4D4",
        "border_vis":  "#B0B0B0",
        "accent":      "#0078D4",
        "accent_hover":"#106EBE",
        "success":     "#16825D",
        "warning":     "#BF8803",
        "error":       "#CD3131",
        "plot1":       "#0451A5",
        "plot2":       "#16825D",
        "grid":        "#E0E0E0",
    },
}

_FONT      = "Segoe UI"
_MONO       = "Consolas"
_ICON_FONT  = "Segoe UI Symbol"


class SPAMGui(tk.Tk):
    """Main application window for the SPAM GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.title("SPAM - Scanner for Polarized Anisotropic Materials")

        self.config_file = os.path.join(os.path.dirname(__file__), 'spam_config.json')
        self.connection_settings = self._load_connection_settings()

        saved_theme = self.connection_settings.get('theme', 'dark')
        self.theme = THEMES.get(saved_theme, THEMES["dark"])
        self._theme_name = saved_theme

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        if platform.system() == 'Windows':
            self.state('zoomed')
        else:
            self.geometry(f"{min(screen_w, 1920)}x{min(screen_h, 1080)}")
            self.update_idletasks()
            x = (screen_w - self.winfo_width()) // 2
            y = (screen_h - self.winfo_height()) // 2
            self.geometry(f"+{x}+{y}")

        self.configure(bg=self.theme['bg'])
        self.is_fullscreen = False
        self.resize_timer = None
        self.resize_delay = 150

        self.debug_log = []
        self.debug_window = None

        self.is_measuring = False
        self.measurement_thread = None
        self.current_angle = 0.0
        self.current_permittivity = 0.00
        self.current_permeability = 0.00

        self.transmitted_power = 0.0
        self.reflected_power = 0.0
        self.transmitted_phase = 0.0
        self.reflected_phase = 0.0

        self.s11_mag = 0.0; self.s11_phase = 0.0
        self.s12_mag = 0.0; self.s12_phase = 0.0
        self.s21_mag = 0.0; self.s21_phase = 0.0
        self.s22_mag = 0.0; self.s22_phase = 0.0

        self.frequency = 10.0
        self.power_level = -10.0
        self.angle_step = 5.0
        self.measurement_interval = 0.5

        self.calibration_error = 0.0
        self.noise_level = 0.0

        self.motor_control_enabled = False
        self.motor_bus = None
        self.motor_gpio = None
        self.motor_movement_status = True
        self.motor_collision_detected = False
        self.motor_num = 1
        self.motor_command = 1
        self.motor_status_var = tk.StringVar(value="Not Initialized")
        self.motor_position_var = tk.StringVar(value="0.0\u00b0")

        self.adc = None
        self.rf_switch = None
        self.rf_switch_enabled = str(self.connection_settings.get('enable_rf_switch', '0')).strip().lower() in ('1', 'true', 'yes', 'on')
        self._adc_only_hint_logged = False

        self._last_graph_count = -1

        self.extraction_f0_ghz = self._safe_float(
            self.connection_settings.get('extraction_f0_ghz', '24.0'), 24.0
        )
        self.extraction_d_mil = self._safe_float(
            self.connection_settings.get('extraction_d_mil', '60.0'), 60.0
        )
        self.extraction_tensor_type = self.connection_settings.get('extraction_tensor_type', "diagonal")
        if self.extraction_tensor_type not in ("isotropic", "diagonal", "symmetric"):
            self.extraction_tensor_type = "diagonal"
        self.extraction_thread = None
        self.extraction_running = False
        self.extraction_status_var = tk.StringVar(value="Not Run")
        self.extraction_error_var = tk.StringVar(value="--")
        self.extraction_eps_var = tk.StringVar(value="--")
        self.extraction_mu_var = tk.StringVar(value="--")

        self.after(200, self._initialize_hardware)

        self._configure_ttk_style()
        self._create_menu()
        self._create_status_bar()
        self._create_sidebar()
        self._create_detail_panel()
        self._create_center_panel()

        if hasattr(self, 'start_container') and hasattr(self, 'stop_container'):
            self._update_button_states()

        self.after(100, self._initialize_background)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Theme helpers
    # ------------------------------------------------------------------
    def _t(self, key):
        return self.theme[key]

    def _configure_ttk_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        t = self.theme
        style.configure(".", background=t['bg_panel'], foreground=t['text'],
                        fieldbackground=t['bg_input'], bordercolor=t['border'],
                        troughcolor=t['bg'], arrowcolor=t['text_sec'])
        style.configure("TNotebook", background=t['bg'], borderwidth=0)
        style.configure("TNotebook.Tab", background=t['bg_elevated'],
                        foreground=t['text_sec'], padding=[10, 4],
                        font=(_FONT, 9))
        style.map("TNotebook.Tab",
                  background=[("selected", t['bg_panel'])],
                  foreground=[("selected", t['text'])])
        style.configure("TCombobox", fieldbackground=t['bg_input'],
                        background=t['bg_elevated'], foreground=t['text'],
                        arrowcolor=t['text_sec'], borderwidth=1)
        style.configure("Treeview", background=t['bg_panel'],
                        foreground=t['text'], fieldbackground=t['bg_panel'],
                        borderwidth=0, font=(_MONO, 9))
        style.configure("Treeview.Heading", background=t['bg_elevated'],
                        foreground=t['text_sec'], font=(_FONT, 9, "bold"),
                        borderwidth=0)
        style.map("Treeview", background=[("selected", t['accent'])],
                  foreground=[("selected", t['text_em'])])
        style.configure("Vertical.TScrollbar", background=t['bg_elevated'],
                        troughcolor=t['bg'], borderwidth=0, arrowsize=12)
        style.configure("Horizontal.TScrollbar", background=t['bg_elevated'],
                        troughcolor=t['bg'], borderwidth=0, arrowsize=12)

    def _toggle_theme(self):
        new = "light" if self._theme_name == "dark" else "dark"
        self._theme_name = new
        self.theme = THEMES[new]
        self.connection_settings['theme'] = new
        self._save_connection_settings()
        messagebox.showinfo("Theme Changed",
                            f"Switched to {new} theme.\n\nRestart the application for the theme to take full effect.")

    # ------------------------------------------------------------------
    # Styled widget helpers
    # ------------------------------------------------------------------
    def _make_btn(self, parent, text, command, style="accent", width=None):
        colors = {
            "accent":  (self._t('accent'), self._t('accent_hover'), self._t('text_em')),
            "danger":  (self._t('error'),  '#D32F2F',               self._t('text_em')),
            "ghost":   (self._t('bg_elevated'), self._t('border_vis'), self._t('text')),
            "success": (self._t('success'), '#3DAA9A',              self._t('text_em')),
            "warn":    (self._t('warning'), '#D4A017',              self._t('bg')),
        }
        bg, hover, fg = colors.get(style, colors['accent'])
        kw = dict(text=text, command=command, bg=bg, fg=fg,
                  activebackground=hover, activeforeground=fg,
                  font=(_FONT, 9), relief=tk.FLAT, bd=0,
                  highlightthickness=0, cursor="hand2", padx=12, pady=4)
        if width:
            kw['width'] = width
        btn = tk.Button(parent, **kw)
        btn.bind('<Enter>', lambda e, b=btn, h=hover: b.config(bg=h))
        btn.bind('<Leave>', lambda e, b=btn, c=bg: b.config(bg=c))
        return btn

    def _attach_tooltip(self, widget, text, bg_normal, bg_hover):
        """Bind hover tooltip and color change to a widget, with proper closure capture."""
        def on_enter(e, w=widget, t=text, h=bg_hover):
            w.config(bg=h)
            tw = tk.Toplevel(w)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{e.x_root+20}+{e.y_root}")
            tk.Label(tw, text=t, bg=self._t('bg_elevated'), fg=self._t('text'),
                     font=(_FONT, 8), padx=6, pady=2, relief=tk.SOLID,
                     borderwidth=1).pack()
            w._tip = tw

        def on_leave(e, w=widget, c=bg_normal):
            w.config(bg=c)
            if hasattr(w, '_tip') and w._tip:
                w._tip.destroy()
                w._tip = None

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def _sep(self, parent, orient="h"):
        f = tk.Frame(parent, bg=self._t('border'),
                     height=1 if orient == "h" else None,
                     width=1 if orient == "v" else None)
        f.pack(fill=tk.X if orient == "h" else tk.Y, padx=0, pady=0)
        return f

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------
    def _load_connection_settings(self):
        defaults = {
            'spi_bus': '0', 'spi_cs': '0', 'spi_speed': '1000000',
            'adc_gain': '1', 'adc_data_rate': '96',
            'enable_rf_switch': '0',
            'switch_gpio': '22',
            'microcontroller_address': '0x55', 'isr_pin': '17',
            'extraction_f0_ghz': '24.0', 'extraction_d_mil': '60.0',
            'extraction_tensor_type': 'diagonal',
            'theme': 'dark',
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    defaults.update(json.load(f))
            except Exception as e:
                print(f"Error loading config: {e}")
        return defaults

    def _save_connection_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.connection_settings, f, indent=2)
            self._log_debug(f"Settings saved to {self.config_file}", "INFO")
        except Exception as e:
            self._log_debug(f"Error saving config: {e}", "WARNING")

    def _safe_float(self, value, fallback):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def _thickness_resonance_advisory(self, f0_ghz, d_mil):
        """Advisory-only resonance sensitivity check from k0*d."""
        f_hz = f0_ghz * 1e9
        d_m = mil_to_m(d_mil)
        k0d = compute_k0d(f_hz, d_m)
        targets = [n * math.pi / 2.0 for n in range(1, 9)]
        nearest = min(targets, key=lambda t: abs(k0d - t))
        nearest_order = targets.index(nearest) + 1
        dist = abs(k0d - nearest)

        if dist < 0.08:
            level = "warning"
            msg = (
                f"Thickness may be resonance-sensitive: k0d={k0d:.3f} is very close "
                f"to {nearest_order}*pi/2 ({nearest:.3f}). Consider adjusting thickness."
            )
        elif dist < 0.18:
            level = "warning"
            msg = (
                f"Thickness is near a resonance zone: k0d={k0d:.3f}, nearest "
                f"{nearest_order}*pi/2={nearest:.3f}. Use caution and verify fit quality."
            )
        else:
            level = "info"
            msg = f"Thickness looks away from quarter-wave resonance zones (k0d={k0d:.3f})."

        return {"level": level, "message": msg, "k0d": k0d}

    # ------------------------------------------------------------------
    # Background init
    # ------------------------------------------------------------------
    def _initialize_background(self):
        try:
            Base.metadata.create_all(bind=engine)
            self.db = SessionLocal()
            self._log_debug("Database connection established", "INFO")
        except Exception as e:
            self._log_debug(f"Database init error: {e}", "ERROR")
        self._update_display()

    # ------------------------------------------------------------------
    # Motor control (unchanged logic, compact formatting)
    # ------------------------------------------------------------------
    def _initialize_hardware(self):
        # --- Motor control (Linux / Pi only) ---
        if platform.system() != 'Linux':
            self.motor_status_var.set("Not Available (Windows)")
        else:
            try:
                from smbus import SMBus
                import RPi.GPIO as GPIO
                mcu_address = int(self.connection_settings.get('microcontroller_address', '0x55'), 16)
                isr_pin = int(self.connection_settings.get('isr_pin', '17'))
                self.motor_bus = SMBus(1)
                try:
                    status = self.motor_bus.read_byte_data(mcu_address, 0x00)
                    self._log_debug(f"MCU at 0x{mcu_address:02X}, status=0x{status:02X}", "SUCCESS")
                except Exception as e:
                    self._log_debug(f"MCU read warning: {e}", "WARNING")
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(isr_pin, GPIO.IN)
                self.motor_gpio = GPIO
                def handle_alert(channel):
                    try:
                        st = self.motor_bus.read_byte_data(mcu_address, 0x00)
                        if st & 0x01:
                            self.motor_collision_detected = True
                            self.after(0, lambda: self._log_debug("COLLISION DETECTED", "ERROR"))
                            self.after(0, lambda: self.motor_status_var.set("COLLISION!"))
                            if self.is_measuring:
                                self.after(0, self._on_stop_measurement)
                        if st & 0x02:
                            self.motor_movement_status = True
                            self.after(0, lambda: self.motor_status_var.set("Ready"))
                    except Exception as e:
                        self.after(0, lambda: self._log_debug(f"Motor status error: {e}", "ERROR"))
                GPIO.add_event_detect(isr_pin, GPIO.RISING, callback=handle_alert)
                self.motor_control_enabled = True
                self.motor_status_var.set("Ready")
                self._log_debug("Motor control initialized", "SUCCESS")
            except ImportError as e:
                self.motor_status_var.set("Libraries N/A")
                self._log_debug(f"Motor libs missing: {e}", "ERROR")
                self.motor_control_enabled = False

        # --- AD7193 ADC (Pmod AD5) ---
        try:
            spi_bus = int(self.connection_settings.get('spi_bus', '0'))
            spi_cs = int(self.connection_settings.get('spi_cs', '0'))
            spi_speed = int(self.connection_settings.get('spi_speed', '1000000'))
            gain = int(self.connection_settings.get('adc_gain', '1'))
            data_rate = int(self.connection_settings.get('adc_data_rate', '96'))
            self.adc = AD7193(spi_bus, spi_cs, spi_speed, log_fn=self._log_debug)
            self.adc.configure(gain=gain, data_rate=data_rate)
            mode_str = "SIM" if self.adc.is_simulated else "SPI"
            self._log_debug(f"ADC ready ({mode_str})", "SUCCESS")
        except Exception as e:
            self._log_debug(f"ADC init failed: {e}", "ERROR")
            self.adc = None

        # --- RF Switch (optional) ---
        self.rf_switch_enabled = str(self.connection_settings.get('enable_rf_switch', '0')).strip().lower() in ('1', 'true', 'yes', 'on')
        if not self.rf_switch_enabled:
            self.rf_switch = None
            self._log_debug("RF switch control disabled (ADC-only mode)", "INFO")
        else:
            try:
                sw_pin = int(self.connection_settings.get('switch_gpio', '22'))
                self.rf_switch = RFSwitch(gpio_pin=sw_pin, log_fn=self._log_debug)
                mode_str = "SIM" if self.rf_switch.is_simulated else "GPIO"
                self._log_debug(f"RF switch ready ({mode_str})", "SUCCESS")
            except Exception as e:
                self._log_debug(f"RF switch init failed: {e}", "ERROR")
                self.rf_switch = None

    def _send_motor_command(self, motor_num: int, position: float, command: int = 1) -> bool:
        if not self.motor_control_enabled or self.motor_bus is None:
            self.motor_movement_status = False
            self.motor_status_var.set("Moving (Sim)")
            self.after(0, lambda: self._log_debug(f"Motor {motor_num}: Sim move to {position:.2f}\u00b0", "INFO"))
            self.after(int(self.measurement_interval * 1000), self._simulate_motor_complete)
            return True
        try:
            import struct
            mcu_address = int(self.connection_settings.get('microcontroller_address', '0x55'), 16)
            packed_val = struct.pack('<f', position)
            message = list(packed_val)
            message.insert(0, command)
            message.insert(1, motor_num)
            msg_dec = ', '.join(str(b) for b in message)
            self._log_debug(f"I2C cmd: [{msg_dec}]", "INFO")
            self.motor_bus.write_i2c_block_data(mcu_address, 0x00, message)
            self.motor_movement_status = False
            self.motor_status_var.set("Moving...")
            self.motor_num = motor_num
            self.motor_command = command
            self.motor_position_var.set(f"{position:.1f}\u00b0")
            return True
        except Exception as e:
            self._log_debug(f"Motor cmd error: {e}", "ERROR")
            self.motor_status_var.set("Error")
            return False

    def _simulate_motor_complete(self):
        self.motor_movement_status = True
        self.motor_status_var.set("Ready (Sim)")

    def _wait_for_motor_position(self, timeout: float = 5.0) -> bool:
        if not self.motor_control_enabled:
            time.sleep(0.1)
            return True
        start = time.time()
        while not self.motor_movement_status and (time.time() - start) < timeout:
            if self.motor_collision_detected:
                return False
            time.sleep(0.05)
        return self.motor_movement_status

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _create_menu(self) -> None:
        menubar = tk.Menu(self, bg=self._t('bg_elevated'), fg=self._t('text'),
                          activebackground=self._t('accent'), activeforeground=self._t('text_em'),
                          borderwidth=0)
        file_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                            activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        file_menu.add_command(label="Export Data", command=self._on_export)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        settings_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                                activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        settings_menu.add_command(label="Adjust Parameters", command=self._on_adjust_parameters)
        settings_menu.add_command(label="Connection Setup", command=self._on_connection_setup)
        settings_menu.add_command(label="Extraction Settings", command=self._on_extraction_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label="Toggle Dark/Light Theme", command=self._toggle_theme)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        view_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                            activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        view_menu.add_command(label="Debug Console", command=self._on_debug_console, accelerator="Ctrl+D")
        view_menu.add_separator()
        view_menu.add_command(label="Fullscreen", command=self._toggle_fullscreen, accelerator="F11")
        menubar.add_cascade(label="View", menu=view_menu)
        help_menu = tk.Menu(menubar, tearoff=0, bg=self._t('bg_panel'), fg=self._t('text'),
                            activebackground=self._t('accent'), activeforeground=self._t('text_em'))
        help_menu.add_command(label="About SPAM", command=self._on_help)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.bind('<Control-d>', lambda e: self._on_debug_console())
        self.bind('<F11>', lambda e: self._toggle_fullscreen())
        self.bind('<Escape>', lambda e: self._exit_fullscreen() if self.is_fullscreen else None)
        self.config(menu=menubar)

    # ------------------------------------------------------------------
    # Status bar  (bottom, 28px)
    # ------------------------------------------------------------------
    def _create_status_bar(self) -> None:
        sf = tk.Frame(self, bg=self._t('bg_sidebar'), height=28)
        sf.pack(side=tk.BOTTOM, fill=tk.X)
        sf.pack_propagate(False)
        left = tk.Frame(sf, bg=self._t('bg_sidebar'))
        left.pack(side=tk.LEFT, fill=tk.Y)
        self._status_dot = tk.Label(left, text="\u25cf", bg=self._t('bg_sidebar'),
                                    fg=self._t('success'), font=(_FONT, 8))
        self._status_dot.pack(side=tk.LEFT, padx=(10, 4))
        self.status_text_var = tk.StringVar(value="System Ready")
        tk.Label(left, textvariable=self.status_text_var, bg=self._t('bg_sidebar'),
                 fg=self._t('text_sec'), font=(_FONT, 9)).pack(side=tk.LEFT)
        right = tk.Frame(sf, bg=self._t('bg_sidebar'))
        right.pack(side=tk.RIGHT, fill=tk.Y)
        self.time_label = tk.Label(right, text="", bg=self._t('bg_sidebar'),
                                   fg=self._t('text_sec'), font=(_FONT, 8))
        self.time_label.pack(side=tk.RIGHT, padx=10)
        self.status_frame = sf

    # ------------------------------------------------------------------
    # Sidebar  (56px icon rail)
    # ------------------------------------------------------------------
    def _create_sidebar(self) -> None:
        rail = tk.Frame(self, bg=self._t('bg_sidebar'), width=56)
        rail.pack(side=tk.LEFT, fill=tk.Y)
        rail.pack_propagate(False)

        # branding
        tk.Label(rail, text="S", bg=self._t('bg_sidebar'), fg=self._t('accent'),
                 font=(_FONT, 18, "bold")).pack(pady=(12, 16))
        self._sep(rail)

        icons = [
            ("\u2699", "Calibrate",       self._on_calibrate,         "accent"),
            ("\u25b6", "Start",           self._on_start_measurement, "success"),
            ("\u25a0", "Stop",            self._on_stop_measurement,  "danger"),
            ("\u2715", "Clear",           self._on_clear_measurements,"warn"),
            ("\u2261", "Results",         self._on_view_results,      "ghost"),
            ("\u21e9", "Export",          self._on_export,            "ghost"),
            ("\u2630", "Debug",           self._on_debug_console,     "ghost"),
        ]

        self.buttons = []
        self.start_button = None; self.stop_button = None
        self.start_container = None; self.stop_container = None
        self.clear_container = None

        for icon, tip, cmd, sty in icons:
            ctr = tk.Frame(rail, bg=self._t('bg_sidebar'))
            ctr.pack(fill=tk.X, padx=6, pady=3)
            colors_map = {
                "accent":  (self._t('accent'), self._t('accent_hover'), self._t('text_em')),
                "success": (self._t('success'), '#3DAA9A',              self._t('text_em')),
                "danger":  (self._t('error'),  '#D32F2F',               self._t('text_em')),
                "warn":    (self._t('warning'),'#D4A017',               self._t('bg')),
                "ghost":   (self._t('bg_sidebar'), self._t('border_vis'), self._t('text_sec')),
            }
            bg_c, hover_c, fg_c = colors_map.get(sty, colors_map['ghost'])
            btn = tk.Button(ctr, text=icon, command=cmd, bg=bg_c, fg=fg_c,
                            activebackground=hover_c, activeforeground=fg_c,
                            font=(_ICON_FONT, 14), relief=tk.FLAT, bd=0,
                            highlightthickness=0, cursor="hand2")
            btn.pack(fill=tk.X, ipady=4)

            self._attach_tooltip(btn, tip, bg_c, hover_c)

            if tip == "Start":
                self.start_button = btn; self.start_container = ctr
            elif tip == "Stop":
                self.stop_button = btn; self.stop_container = ctr
                ctr.pack_forget()
            elif tip == "Clear":
                self.clear_container = ctr
            self.buttons.append(btn)

        tk.Frame(rail, bg=self._t('bg_sidebar')).pack(expand=True)

        # theme toggle at bottom
        theme_icon = "\u263e" if self._theme_name == "dark" else "\u2600"
        tbtn = tk.Button(rail, text=theme_icon, command=self._toggle_theme,
                         bg=self._t('bg_sidebar'), fg=self._t('text_sec'),
                         font=(_ICON_FONT, 12), relief=tk.FLAT, bd=0,
                         highlightthickness=0, cursor="hand2")
        tbtn.pack(pady=(0, 4))

        tk.Label(rail, text="v1.01", bg=self._t('bg_sidebar'),
                 fg=self._t('text_sec'), font=(_FONT, 7)).pack(pady=(0, 8))

        self.sidebar_frame = rail

    # ------------------------------------------------------------------
    # Detail panel  (right, 280px, collapsible sections)
    # ------------------------------------------------------------------
    def _create_detail_panel(self) -> None:
        pf = tk.Frame(self, bg=self._t('bg_panel'), width=280)
        pf.pack(side=tk.RIGHT, fill=tk.Y)
        pf.pack_propagate(False)

        # scrollable interior
        canvas = tk.Canvas(pf, bg=self._t('bg_panel'), highlightthickness=0, width=280)
        sb = ttk.Scrollbar(pf, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg=self._t('bg_panel'))
        canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        def _resize_inner(e):
            canvas.itemconfig("inner", width=e.width)
        canvas.bind("<Configure>", _resize_inner)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # scoped mousewheel
        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        def _bind_wheel(e):
            canvas.bind_all("<MouseWheel>", _on_wheel)
        def _unbind_wheel(e):
            canvas.unbind_all("<MouseWheel>")
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        self._collapsed = {}

        def section(parent, title, items, mono_val=True):
            hdr = tk.Frame(parent, bg=self._t('bg_panel'))
            hdr.pack(fill=tk.X, padx=10, pady=(10, 0))
            tk.Label(hdr, text=title.upper(), bg=self._t('bg_panel'),
                     fg=self._t('text_sec'), font=(_FONT, 8, "bold"),
                     anchor="w").pack(side=tk.LEFT)
            body = tk.Frame(parent, bg=self._t('bg_panel'))
            body.pack(fill=tk.X, padx=10, pady=(2, 0))
            self._sep(parent)
            val_font = (_MONO, 10) if mono_val else (_FONT, 10, "bold")
            for lbl_text, var in items:
                row = tk.Frame(body, bg=self._t('bg_panel'))
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=lbl_text, bg=self._t('bg_panel'),
                         fg=self._t('text_sec'), font=(_FONT, 9),
                         anchor="w").pack(side=tk.LEFT)
                tk.Label(row, textvariable=var, bg=self._t('bg_panel'),
                         fg=self._t('text'), font=val_font,
                         anchor="e").pack(side=tk.RIGHT)

        # -- StringVars --
        self.angle_var = tk.StringVar(value="0.0\u00b0")
        self.permittivity_var = tk.StringVar(value="0.00")
        self.permeability_var = tk.StringVar(value="0.00")
        self.status_var = tk.StringVar(value="Ready")
        self.s11_var = tk.StringVar(value="0.00\u22200\u00b0")
        self.s12_var = tk.StringVar(value="0.00\u22200\u00b0")
        self.s21_var = tk.StringVar(value="0.00\u22200\u00b0")
        self.s22_var = tk.StringVar(value="0.00\u22200\u00b0")
        self.system_status_var = tk.StringVar(value="Ready")

        self.freq_var = tk.StringVar(value="10.0 GHz")
        self.power_var = tk.StringVar(value="-10.0 dBm")
        self.angle_step_var = tk.StringVar(value="5.0\u00b0")
        self.interval_var = tk.StringVar(value="0.50 s")
        self.thickness_var = tk.StringVar(value=f"{self.extraction_d_mil:.1f} mil")
        self.extract_type_var = tk.StringVar(value=self.extraction_tensor_type)
        self.cal_error_var = tk.StringVar(value="0.00%")
        self.noise_var = tk.StringVar(value="0.0 dB")

        section(inner, "Measurement", [
            ("Angle", self.angle_var),
            ("Permittivity (\u03b5)", self.permittivity_var),
            ("Permeability (\u03bc)", self.permeability_var),
            ("Status", self.status_var),
        ])
        section(inner, "Motor", [
            ("Status", self.motor_status_var),
            ("Position", self.motor_position_var),
        ])
        section(inner, "S-Parameters", [
            ("S\u2081\u2081", self.s11_var), ("S\u2081\u2082", self.s12_var),
            ("S\u2082\u2081", self.s21_var), ("S\u2082\u2082", self.s22_var),
        ])
        section(inner, "Extraction", [
            ("Status", self.extraction_status_var),
            ("Fit Error", self.extraction_error_var),
            ("\u03b5r diag", self.extraction_eps_var),
            ("\u03bcr diag", self.extraction_mu_var),
            ("Thickness (mil)", self.thickness_var),
            ("Tensor Type", self.extract_type_var),
        ])
        section(inner, "Parameters", [
            ("Frequency", self.freq_var), ("Power", self.power_var),
            ("Angle Step", self.angle_step_var), ("Interval", self.interval_var),
        ])
        section(inner, "Environment", [
            ("Cal Error", self.cal_error_var), ("Noise", self.noise_var),
        ])

        # system status at bottom
        tk.Frame(inner, bg=self._t('bg_panel')).pack(expand=True)
        row = tk.Frame(inner, bg=self._t('bg_panel'))
        row.pack(fill=tk.X, padx=10, pady=8)
        tk.Label(row, text="System", bg=self._t('bg_panel'),
                 fg=self._t('text_sec'), font=(_FONT, 8)).pack(side=tk.LEFT)
        tk.Label(row, textvariable=self.system_status_var, bg=self._t('bg_panel'),
                 fg=self._t('success'), font=(_MONO, 10)).pack(side=tk.RIGHT)

        self.info_frame = pf

    # ------------------------------------------------------------------
    # Center panel  (2x2 graph grid, no scroll)
    # ------------------------------------------------------------------
    def _create_center_panel(self) -> None:
        center = tk.Frame(self, bg=self._t('bg'))
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)

        center.rowconfigure(0, weight=1)
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)
        center.columnconfigure(1, weight=1)

        t = self.theme
        fc = t['bg_panel']
        tc = t['text']
        sc = t['text_sec']
        gc = t['grid']
        dpi = 100

        def make_graph(parent, row, col, title_text, ylabel_text):
            frame = tk.Frame(parent, bg=fc, highlightbackground=t['border'],
                             highlightthickness=1)
            frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
            fig = Figure(figsize=(5, 3), dpi=dpi, facecolor=fc)
            ax = fig.add_subplot(111, facecolor=fc)
            ax.set_xlim(0, 90)
            ax.set_title(title_text, color=tc, fontsize=10, fontweight='bold', pad=8)
            ax.set_xlabel("Angle (\u00b0)", color=sc, fontsize=9)
            ax.set_ylabel(ylabel_text, color=sc, fontsize=9)
            ax.grid(True, alpha=0.4, color=gc, linestyle='--', linewidth=0.5)
            ax.tick_params(colors=sc, labelsize=8)
            for sp in ['top', 'right']:
                ax.spines[sp].set_visible(False)
            for sp in ['left', 'bottom']:
                ax.spines[sp].set_color(t['border'])
            fig.tight_layout(pad=1.5)
            canvas = FigureCanvasTkAgg(fig, master=frame)
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw_idle()
            return fig, ax, canvas

        self.fig1, self.ax1, self.canvas1 = make_graph(center, 0, 0,
            "Permittivity (\u03b5) vs Angle", "Permittivity (\u03b5)")
        self.ax1.set_ylim(1.5, 2.5)

        self.fig2, self.ax2, self.canvas2 = make_graph(center, 0, 1,
            "Permeability (\u03bc) vs Angle", "Permeability (\u03bc)")
        self.ax2.set_ylim(1.0, 2.0)

        self.fig3, self.ax3, self.canvas3 = make_graph(center, 1, 0,
            "TX / RX Power vs Angle", "Power (dBm)")
        self.ax3.set_ylim(-30, 10)

        self.fig4, self.ax4, self.canvas4 = make_graph(center, 1, 1,
            "TX / RX Phase vs Angle", "Phase (\u00b0)")
        self.ax4.set_ylim(-180, 180)

        self.center_frame = center
        self.measurement_angles = []
        self.measurement_permittivity = []
        self.measurement_permeability = []
        self.measurement_transmitted_power = []
        self.measurement_reflected_power = []
        self.measurement_transmitted_phase = []
        self.measurement_reflected_phase = []

        def on_resize(event):
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
            def do_resize():
                try:
                    for f in [self.fig1, self.fig2, self.fig3, self.fig4]:
                        f.tight_layout(pad=1.5)
                    for c in [self.canvas1, self.canvas2, self.canvas3, self.canvas4]:
                        c.draw_idle()
                except:
                    pass
                self.resize_timer = None
            self.resize_timer = self.after(self.resize_delay, do_resize)
        self.bind('<Configure>', on_resize)

    # ------------------------------------------------------------------
    # Graph styling helper
    # ------------------------------------------------------------------
    def _style_ax(self, ax, title, ylabel):
        t = self.theme
        ax.set_title(title, color=t['text'], fontsize=10, fontweight='bold', pad=8)
        ax.set_xlabel("Angle (\u00b0)", color=t['text_sec'], fontsize=9)
        ax.set_ylabel(ylabel, color=t['text_sec'], fontsize=9)
        ax.grid(True, alpha=0.4, color=t['grid'], linestyle='--', linewidth=0.5)
        ax.tick_params(colors=t['text_sec'], labelsize=8)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)
        for sp in ['left', 'bottom']:
            ax.spines[sp].set_color(t['border'])

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------
    def _get_measurements(self, limit=1000):
        try:
            return self.db.query(Measurement).order_by(Measurement.timestamp.desc()).limit(limit).all()
        except Exception as e:
            print(f"Error retrieving measurements: {e}")
            return []

    def _create_measurement(self, angle, permittivity, permeability,
                            transmitted_power=None, reflected_power=None,
                            transmitted_phase=None, reflected_phase=None):
        try:
            m = Measurement(angle=angle, permittivity=permittivity, permeability=permeability,
                            transmitted_power=transmitted_power, reflected_power=reflected_power,
                            transmitted_phase=transmitted_phase, reflected_phase=reflected_phase,
                            timestamp=datetime.now())
            self.db.add(m)
            self.db.commit()
            self.db.refresh(m)
            self._last_graph_count = -1
            return m
        except Exception as e:
            self.db.rollback()
            print(f"Error creating measurement: {e}")
            return None

    def _create_calibration(self, parameters=None):
        try:
            c = Calibration(timestamp=datetime.now(), parameters=parameters or {}, status="completed")
            self.db.add(c)
            self.db.commit()
            self.db.refresh(c)
            return c
        except Exception as e:
            self.db.rollback()
            return None

    # ------------------------------------------------------------------
    # Graph updates
    # ------------------------------------------------------------------
    def _update_graphs(self):
        measurements = self._get_measurements()
        n = len(measurements) if measurements else 0
        if n == self._last_graph_count and n > 0:
            return
        self._last_graph_count = n
        t = self.theme
        p1, p2 = t['plot1'], t['plot2']

        if not measurements:
            for ax, title, yl, ylim in [
                (self.ax1, "Permittivity (\u03b5) vs Angle", "Permittivity (\u03b5)", (1.5, 2.5)),
                (self.ax2, "Permeability (\u03bc) vs Angle", "Permeability (\u03bc)", (1.0, 2.0)),
                (self.ax3, "TX / RX Power vs Angle", "Power (dBm)", (-30, 10)),
                (self.ax4, "TX / RX Phase vs Angle", "Phase (\u00b0)", (-180, 180)),
            ]:
                ax.clear()
                ax.set_xlim(0, 90)
                ax.set_ylim(*ylim)
                self._style_ax(ax, title, yl)
        else:
            angles = [m.angle for m in measurements]
            perm = [m.permittivity for m in measurements]
            perm_b = [m.permeability for m in measurements]
            tx_pow = [m.transmitted_power if m.transmitted_power is not None else 0.0 for m in measurements]
            rx_pow = [m.reflected_power if m.reflected_power is not None else 0.0 for m in measurements]
            tx_ph = [m.transmitted_phase if m.transmitted_phase is not None else 0.0 for m in measurements]
            rx_ph = [m.reflected_phase if m.reflected_phase is not None else 0.0 for m in measurements]

            self.ax1.clear()
            self.ax1.plot(angles, perm, color=p1, linewidth=1.8, label='\u03b5')
            if angles:
                self.ax1.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
                self.ax1.set_ylim(max(1.0, min(perm)-0.2), max(perm)+0.2)
            self._style_ax(self.ax1, "Permittivity (\u03b5) vs Angle", "Permittivity (\u03b5)")

            self.ax2.clear()
            self.ax2.plot(angles, perm_b, color=p2, linewidth=1.8, label='\u03bc')
            if angles:
                self.ax2.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
                self.ax2.set_ylim(max(0.5, min(perm_b)-0.2), max(perm_b)+0.2)
            self._style_ax(self.ax2, "Permeability (\u03bc) vs Angle", "Permeability (\u03bc)")

            self.ax3.clear()
            self.ax3.plot(angles, tx_pow, color=p1, linewidth=1.8, label='TX', marker='o', markersize=3)
            self.ax3.plot(angles, rx_pow, color=p2, linewidth=1.8, label='RX', marker='s', markersize=3)
            self.ax3.legend(loc='best', fontsize=8, framealpha=0.5)
            if angles:
                self.ax3.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
                all_p = [v for v in tx_pow + rx_pow if v != 0.0]
                if all_p:
                    self.ax3.set_ylim(min(all_p)-5, max(all_p)+5)
            self._style_ax(self.ax3, "TX / RX Power vs Angle", "Power (dBm)")

            self.ax4.clear()
            self.ax4.plot(angles, tx_ph, color=p1, linewidth=1.8, label='TX', marker='o', markersize=3)
            self.ax4.plot(angles, rx_ph, color=p2, linewidth=1.8, label='RX', marker='s', markersize=3)
            self.ax4.legend(loc='best', fontsize=8, framealpha=0.5)
            if angles:
                self.ax4.set_xlim(max(0, min(angles)-5), min(90, max(angles)+5))
            self.ax4.set_ylim(-180, 180)
            self._style_ax(self.ax4, "TX / RX Phase vs Angle", "Phase (\u00b0)")

        for f in [self.fig1, self.fig2, self.fig3, self.fig4]:
            f.tight_layout(pad=1.5)
        for c in [self.canvas1, self.canvas2, self.canvas3, self.canvas4]:
            c.draw_idle()

    # ------------------------------------------------------------------
    # Periodic display update
    # ------------------------------------------------------------------
    def _update_display(self):
        self._update_graphs()
        measurements = self._get_measurements(limit=1)
        if measurements:
            latest = measurements[0]
            self.angle_var.set(f"{latest.angle:.1f}\u00b0")
            self.permittivity_var.set(f"{latest.permittivity:.4f}")
            self.permeability_var.set(f"{latest.permeability:.4f}")
            self.current_angle = latest.angle
            self.current_permittivity = latest.permittivity
            self.current_permeability = latest.permeability
        else:
            self.angle_var.set("0.0\u00b0")
            self.permittivity_var.set("0.00")
            self.permeability_var.set("0.00")
        self.s11_var.set(f"{self.s11_mag:.3f}\u2220{self.s11_phase:.1f}\u00b0")
        self.s12_var.set(f"{self.s12_mag:.3f}\u2220{self.s12_phase:.1f}\u00b0")
        self.s21_var.set(f"{self.s21_mag:.3f}\u2220{self.s21_phase:.1f}\u00b0")
        self.s22_var.set(f"{self.s22_mag:.3f}\u2220{self.s22_phase:.1f}\u00b0")
        self.motor_position_var.set(f"{self.current_angle:.1f}\u00b0")
        self.freq_var.set(f"{self.frequency:.1f} GHz")
        self.power_var.set(f"{self.power_level:.1f} dBm")
        self.angle_step_var.set(f"{self.angle_step:.1f}\u00b0")
        self.interval_var.set(f"{self.measurement_interval:.2f} s")
        self.thickness_var.set(f"{self.extraction_d_mil:.1f} mil")
        self.extract_type_var.set(self.extraction_tensor_type)
        if not self.is_measuring:
            self.calibration_error = 0.0
            self.noise_level = 0.0
        self.cal_error_var.set(f"{self.calibration_error:.2f}%")
        self.noise_var.set(f"{self.noise_level:.1f} dB")
        self.after(2000, self._update_display)

    # ------------------------------------------------------------------
    # Measurement worker (unchanged logic)
    # ------------------------------------------------------------------
    def _measurement_worker(self):
        angle_step = self.angle_step
        max_angle = 90.0
        while self.is_measuring and self.current_angle <= max_angle:
            if self.motor_control_enabled or platform.system() == 'Linux':
                motor_success = self._send_motor_command(self.motor_num, self.current_angle, self.motor_command)
                if not motor_success:
                    self.after(0, lambda: self._log_debug(f"Motor cmd fail at {self.current_angle:.2f}\u00b0", "ERROR"))
                if not self._wait_for_motor_position(timeout=5.0):
                    if self.motor_collision_detected:
                        self.after(0, lambda: self._log_debug("Collision - stopping", "ERROR"))
                        self.is_measuring = False
                        break
                    else:
                        self.after(0, lambda: self._log_debug(f"Motor timeout at {self.current_angle:.2f}\u00b0", "WARNING"))
            import math

            if self.adc is not None:
                # --- Real ADC reads ---
                if self.adc.is_simulated:
                    self.adc.set_sim_angle(self.current_angle)

                if self.rf_switch is not None:
                    # S21 (transmission): switch to RXt, read I/Q
                    self.rf_switch.select_transmission()
                    time.sleep(0.01)
                    i_tx, q_tx = self.adc.read_iq()

                    # S11 (reflection): switch to RXp, read I/Q
                    self.rf_switch.select_reflection()
                    time.sleep(0.01)
                    i_rx, q_rx = self.adc.read_iq()
                else:
                    # ADC-only mode: expects path state to be handled externally.
                    if not self._adc_only_hint_logged:
                        self._adc_only_hint_logged = True
                        self.after(0, lambda: self._log_debug(
                            "ADC-only mode active: RF path switching is external/not app-controlled.",
                            "INFO"
                        ))
                    i_tx, q_tx = self.adc.read_iq()
                    time.sleep(0.01)
                    i_rx, q_rx = self.adc.read_iq()

                s21_mag = math.sqrt(i_tx**2 + q_tx**2)
                s21_phase = math.degrees(math.atan2(q_tx, i_tx))
                transmitted_power = 20.0 * math.log10(s21_mag) if s21_mag > 0 else -100.0
                transmitted_phase = s21_phase

                s11_mag = math.sqrt(i_rx**2 + q_rx**2)
                s11_phase = math.degrees(math.atan2(q_rx, i_rx))
                reflected_power = 20.0 * math.log10(s11_mag) if s11_mag > 0 else -100.0
                reflected_phase = s11_phase
            else:
                # --- Simulation fallback (no hardware) ---
                angle_rad = math.radians(self.current_angle)
                transmitted_power = -20.0 * (self.current_angle / 90.0)
                reflected_power = -15.0 - 10.0 * (self.current_angle / 90.0)
                transmitted_phase = -90.0 + 180.0 * (self.current_angle / 90.0)
                reflected_phase = -45.0 + 135.0 * (self.current_angle / 90.0)

            self.transmitted_power = transmitted_power
            self.reflected_power = reflected_power
            self.transmitted_phase = transmitted_phase
            self.reflected_phase = reflected_phase
            angle_rad = math.radians(self.current_angle)
            permittivity = 2.0 + 0.1 * math.sin(angle_rad)
            permeability = 1.5 + 0.05 * math.cos(angle_rad)
            self._create_measurement(self.current_angle, permittivity, permeability,
                                     transmitted_power=transmitted_power, reflected_power=reflected_power,
                                     transmitted_phase=transmitted_phase, reflected_phase=reflected_phase)
            self.after(0, lambda: self._log_debug(
                f"Pos: {self.current_angle:.2f}\u00b0 | TX: {transmitted_power:.1f}dBm | RX: {reflected_power:.1f}dBm", "INFO"))
            self.current_angle += angle_step
            if int(self.current_angle) % 10 == 0:
                self.after(0, lambda: self._log_debug(f"Progress: {self.current_angle:.1f}\u00b0 / 90\u00b0", "INFO"))
            time.sleep(self.measurement_interval)
        self.is_measuring = False
        if self.current_angle > max_angle:
            self.after(0, lambda: self._log_debug("Sweep complete (0-90\u00b0)", "SUCCESS"))
            self.after(0, lambda: self._update_status("Sweep complete", "success"))
            self.after(100, self._run_extraction)
        else:
            self.after(0, lambda: self._log_debug(f"Stopped at {self.current_angle:.1f}\u00b0", "INFO"))
            self.after(0, lambda: self._update_status(f"Stopped at {self.current_angle:.1f}\u00b0", "info"))
        self.after(0, lambda: self.status_var.set("Ready"))
        self.after(0, self._update_button_states)

    # ------------------------------------------------------------------
    # Material extraction (unchanged logic)
    # ------------------------------------------------------------------
    def _run_extraction(self):
        if self.extraction_running:
            return
        measurements = self._get_measurements()
        if len(measurements) < 3:
            self._log_debug("Not enough data for extraction", "WARNING")
            return
        self.extraction_running = True
        self.extraction_status_var.set("Running...")
        self._log_debug("Starting extraction...", "INFO")
        self.extraction_thread = threading.Thread(target=self._extraction_worker,
                                                  args=(measurements,), daemon=True)
        self.extraction_thread.start()

    def _extraction_worker(self, measurements):
        import warnings as _w
        try:
            angles = np.array([m.angle for m in measurements])
            n = len(angles)
            s_matrices = np.zeros((n, 4, 4), dtype=complex)
            for i, m in enumerate(measurements):
                if m.s_matrix_json:
                    s_matrices[i] = np.array(m.s_matrix_json, dtype=complex)
                else:
                    tp = m.transmitted_power if m.transmitted_power else 0.0
                    rp = m.reflected_power if m.reflected_power else 0.0
                    tph = m.transmitted_phase if m.transmitted_phase else 0.0
                    rph = m.reflected_phase if m.reflected_phase else 0.0
                    s21 = 10 ** (tp / 20.0) * np.exp(1j * np.deg2rad(tph))
                    s11 = 10 ** (rp / 20.0) * np.exp(1j * np.deg2rad(rph))
                    s_matrices[i] = np.array([[s11,0,0,0],[0,s11,0,0],[0,0,s21,0],[0,0,0,s21]])
            f_hz = self.extraction_f0_ghz * 1e9
            d_m = mil_to_m(self.extraction_d_mil)
            k0d = compute_k0d(f_hz, d_m)
            self.after(0, lambda: self._log_debug(
                f"Extraction: f0={self.extraction_f0_ghz}GHz d={self.extraction_d_mil}mil "
                f"k0d={k0d:.4f} type={self.extraction_tensor_type} {n} angles", "INFO"))
            def stage_update(stage, res):
                self.after(0, lambda s=stage, e=res['fit_error']:
                    self._log_debug(f"  [{s}] error={e:.6f}", "INFO"))
            with _w.catch_warnings():
                _w.simplefilter("ignore")
                result = extract_material_progressive(s_matrices, angles, k0d,
                    target_type=self.extraction_tensor_type, max_iter_per_stage=2000,
                    callback=stage_update)
            erv, mrv, fit_err = result["erv"], result["mrv"], result["fit_error"]

            if not np.isfinite(fit_err) or fit_err > 1.0:
                self.after(0, lambda: self.extraction_status_var.set("No Converge"))
                self.after(0, lambda: self.extraction_error_var.set("--"))
                self.after(0, lambda: self.extraction_eps_var.set("--"))
                self.after(0, lambda: self.extraction_mu_var.set("--"))
                self.after(0, lambda: self._log_debug(
                    "Extraction did not converge -- simulated/placeholder data is not "
                    "valid S-parameter data. Will work with real hardware measurements.", "WARNING"))
            else:
                eps_d = f"[{erv[0].real:.2f}, {erv[3].real:.2f}, {erv[5].real:.2f}]"
                mu_d = f"[{mrv[0].real:.2f}, {mrv[3].real:.2f}, {mrv[5].real:.2f}]"
                self.after(0, lambda: self.extraction_status_var.set("Done"))
                self.after(0, lambda: self.extraction_error_var.set(f"{fit_err:.6f}"))
                self.after(0, lambda e=eps_d: self.extraction_eps_var.set(e))
                self.after(0, lambda m=mu_d: self.extraction_mu_var.set(m))
                self.after(0, lambda: self._log_debug(f"Extraction done: error={fit_err:.6f}", "SUCCESS"))
                self._save_extraction_result(result)
        except Exception as exc:
            import traceback
            err_msg = str(exc)
            tb_msg = traceback.format_exc()
            self.after(0, lambda: self.extraction_status_var.set("Error"))
            self.after(0, lambda m=err_msg: self._log_debug(f"Extraction failed: {m}", "ERROR"))
            self.after(0, lambda m=tb_msg: self._log_debug(f"Traceback:\n{m}", "ERROR"))
        finally:
            self.extraction_running = False

    def _save_extraction_result(self, result):
        try:
            erv_json = [[complex(v).real, complex(v).imag] for v in result["erv"]]
            mrv_json = [[complex(v).real, complex(v).imag] for v in result["mrv"]]
            rec = ExtractionResult(erv_json=erv_json, mrv_json=mrv_json,
                                   fit_error=float(result["fit_error"]),
                                   tensor_type=self.extraction_tensor_type,
                                   config_json={"f0_ghz": self.extraction_f0_ghz,
                                                "d_mil": self.extraction_d_mil,
                                                "k0d": compute_k0d(
                                                    self.extraction_f0_ghz * 1e9,
                                                    mil_to_m(self.extraction_d_mil)
                                                )})
            self.db.add(rec)
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self._log_debug(f"Save extraction failed: {exc}", "ERROR")

    # ------------------------------------------------------------------
    # Dialog helper
    # ------------------------------------------------------------------
    def _themed_dialog(self, title, width=420, height=340):
        d = tk.Toplevel(self)
        d.title(title)
        d.geometry(f"{width}x{height}")
        d.configure(bg=self._t('bg'))
        d.transient(self)
        d.grab_set()
        d.update_idletasks()
        x = (d.winfo_screenwidth() // 2) - (width // 2)
        y = (d.winfo_screenheight() // 2) - (height // 2)
        d.geometry(f"{width}x{height}+{x}+{y}")
        return d

    def _dialog_entry_row(self, parent, label_text, var, row):
        tk.Label(parent, text=label_text, bg=self._t('bg_panel'), fg=self._t('text'),
                 font=(_FONT, 9), anchor="w").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 8))
        e = tk.Entry(parent, textvariable=var, bg=self._t('bg_input'), fg=self._t('text'),
                     font=(_MONO, 9), width=20, relief=tk.FLAT,
                     insertbackground=self._t('text'), highlightbackground=self._t('border'),
                     highlightthickness=1)
        e.grid(row=row, column=1, sticky="ew", pady=6)
        return e

    # ------------------------------------------------------------------
    # Extraction settings dialog
    # ------------------------------------------------------------------
    def _on_extraction_settings(self):
        d = self._themed_dialog("Extraction Settings", 430, 360)
        tk.Label(d, text="Material Extraction Settings", bg=self._t('bg'),
                 fg=self._t('text'), font=(_FONT, 12, "bold")).pack(pady=(16, 12))
        content = tk.Frame(d, bg=self._t('bg_panel'), padx=16, pady=16)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        f0_var = tk.StringVar(value=str(self.extraction_f0_ghz))
        d_var = tk.StringVar(value=str(self.extraction_d_mil))
        type_var = tk.StringVar(value=self.extraction_tensor_type)
        self._dialog_entry_row(content, "Frequency (GHz):", f0_var, 0)
        self._dialog_entry_row(content, "Thickness (mil, 1-500):", d_var, 1)
        tk.Label(content,
                 text="Advisory: choose thickness to avoid resonance-sensitive regimes.",
                 bg=self._t('bg_panel'), fg=self._t('text_sec'), font=(_FONT, 8),
                 anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(content, text="Tensor Type:", bg=self._t('bg_panel'), fg=self._t('text'),
                 font=(_FONT, 9)).grid(row=3, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Combobox(content, textvariable=type_var, state="readonly",
                     values=["isotropic", "diagonal", "symmetric"],
                     width=17).grid(row=3, column=1, sticky="ew", pady=6)
        def save():
            try:
                f0_ghz = float(f0_var.get())
                d_mil = float(d_var.get())
                tensor_type = type_var.get()
                if f0_ghz <= 0:
                    raise ValueError("Frequency must be greater than 0 GHz.")
                if d_mil < 1 or d_mil > 500:
                    raise ValueError("Thickness must be between 1 and 500 mil.")
                if tensor_type not in ("isotropic", "diagonal", "symmetric"):
                    raise ValueError("Tensor type must be isotropic, diagonal, or symmetric.")

                self.extraction_f0_ghz = f0_ghz
                self.extraction_d_mil = d_mil
                self.extraction_tensor_type = tensor_type

                self.connection_settings['extraction_f0_ghz'] = str(self.extraction_f0_ghz)
                self.connection_settings['extraction_d_mil'] = str(self.extraction_d_mil)
                self.connection_settings['extraction_tensor_type'] = self.extraction_tensor_type
                self._save_connection_settings()

                advisory = self._thickness_resonance_advisory(self.extraction_f0_ghz, self.extraction_d_mil)
                self._log_debug(
                    f"Extraction settings saved: f0={self.extraction_f0_ghz:.3f}GHz "
                    f"d={self.extraction_d_mil:.2f}mil k0d={advisory['k0d']:.4f} "
                    f"type={self.extraction_tensor_type}",
                    "INFO"
                )
                self._log_debug(advisory["message"], "WARNING" if advisory["level"] == "warning" else "INFO")
                if advisory["level"] == "warning":
                    messagebox.showwarning("Thickness Advisory", advisory["message"], parent=d)
                    self._update_status("Extraction settings saved (advisory issued)", "warning")
                else:
                    self._update_status("Extraction settings saved", "success")
                d.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid Extraction Settings", str(e), parent=d)
        bf = tk.Frame(content, bg=self._t('bg_panel'))
        bf.grid(row=4, column=0, columnspan=2, pady=(12, 0), sticky="e")
        self._make_btn(bf, "Cancel", d.destroy, "ghost").pack(side=tk.RIGHT, padx=(4, 0))
        self._make_btn(bf, "Save", save, "accent").pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Adjust parameters dialog
    # ------------------------------------------------------------------
    def _on_adjust_parameters(self):
        d = self._themed_dialog("Adjust Parameters", 440, 380)
        tk.Label(d, text="Measurement Parameters", bg=self._t('bg'),
                 fg=self._t('text'), font=(_FONT, 12, "bold")).pack(pady=(16, 12))
        content = tk.Frame(d, bg=self._t('bg_panel'), padx=16, pady=16)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        freq_v = tk.StringVar(value=str(self.frequency))
        pow_v = tk.StringVar(value=str(self.power_level))
        step_v = tk.StringVar(value=str(self.angle_step))
        int_v = tk.StringVar(value=str(self.measurement_interval))
        for i, (lbl, v) in enumerate([("Frequency (GHz):", freq_v), ("Power (dBm):", pow_v),
                                       ("Angle Step (\u00b0):", step_v), ("Interval (s):", int_v)]):
            self._dialog_entry_row(content, lbl, v, i)
        def save():
            try:
                self.frequency = float(freq_v.get())
                self.power_level = float(pow_v.get())
                self.angle_step = float(step_v.get())
                self.measurement_interval = float(int_v.get())
                self._log_debug(f"Params: f={self.frequency} P={self.power_level} step={self.angle_step} int={self.measurement_interval}", "INFO")
                self._update_status("Parameters updated", "success")
                d.destroy()
            except ValueError as e:
                messagebox.showerror("Invalid", str(e), parent=d)
        bf = tk.Frame(d, bg=self._t('bg'))
        bf.pack(fill=tk.X, padx=16, pady=(0, 16))
        self._make_btn(bf, "Cancel", d.destroy, "ghost").pack(side=tk.RIGHT, padx=(4, 0))
        self._make_btn(bf, "Save", save, "accent").pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Connection setup dialog
    # ------------------------------------------------------------------
    def _on_connection_setup(self):
        d = self._themed_dialog("Connection Setup", 500, 560)
        tk.Label(d, text="Connection Configuration", bg=self._t('bg'),
                 fg=self._t('text'), font=(_FONT, 12, "bold")).pack(pady=(16, 12))
        content = tk.Frame(d, bg=self._t('bg_panel'), padx=16, pady=12)
        content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        vars_ = {}

        row = 0
        def section_label(text, r):
            tk.Label(content, text=text, bg=self._t('bg_panel'),
                     fg=self._t('accent'), font=(_FONT, 9, "bold")).grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(8 if r > 0 else 0, 4))
            return r + 1

        row = section_label("ADC (AD7193 / Pmod AD5)", row)
        for lbl, key in [("SPI Bus:", 'spi_bus'), ("SPI CS:", 'spi_cs'),
                         ("SPI Speed (Hz):", 'spi_speed'), ("ADC Gain:", 'adc_gain'),
                         ("Data Rate (Hz):", 'adc_data_rate')]:
            v = tk.StringVar(value=self.connection_settings.get(key, ''))
            vars_[key] = v
            self._dialog_entry_row(content, lbl, v, row)
            row += 1

        row = section_label("RF Switch", row)
        for lbl, key in [("Enable RF Switch Control (0/1):", 'enable_rf_switch'),
                         ("Switch GPIO Pin:", 'switch_gpio')]:
            v = tk.StringVar(value=self.connection_settings.get(key, ''))
            vars_[key] = v
            self._dialog_entry_row(content, lbl, v, row)
            row += 1

        row = section_label("Motor Controller", row)
        for lbl, key in [("MCU Address:", 'microcontroller_address'),
                         ("ISR Pin:", 'isr_pin')]:
            v = tk.StringVar(value=self.connection_settings.get(key, ''))
            vars_[key] = v
            self._dialog_entry_row(content, lbl, v, row)
            row += 1

        def save():
            for key, v in vars_.items():
                self.connection_settings[key] = v.get().strip()
            self._save_connection_settings()
            self._log_debug("Connection settings saved", "SUCCESS")
            self._update_status("Connection saved", "success")
            # Tear down existing hardware and re-initialize
            if self.motor_gpio:
                try: self.motor_gpio.cleanup()
                except: pass
            if self.motor_bus:
                try: self.motor_bus.close()
                except: pass
            self.motor_control_enabled = False
            self.motor_bus = None
            if self.adc:
                try: self.adc.close()
                except: pass
                self.adc = None
            if self.rf_switch:
                try: self.rf_switch.close()
                except: pass
                self.rf_switch = None
            self.after(200, self._initialize_hardware)
            d.destroy()
        bf = tk.Frame(d, bg=self._t('bg'))
        bf.pack(fill=tk.X, padx=16, pady=(0, 16))
        self._make_btn(bf, "Cancel", d.destroy, "ghost").pack(side=tk.RIGHT, padx=(4, 0))
        self._make_btn(bf, "Save", save, "accent").pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Command callbacks
    # ------------------------------------------------------------------
    def _update_status(self, message: str, status_type: str = "info"):
        self.status_text_var.set(message)
        ts = datetime.now().strftime("%H:%M:%S")
        self.time_label.config(text=ts)
        cmap = {"success": self._t('success'), "warning": self._t('warning'),
                "error": self._t('error'), "info": self._t('accent')}
        self._status_dot.config(fg=cmap.get(status_type, self._t('success')))

    def _on_calibrate(self):
        r = messagebox.askokcancel("Calibration - Step 1",
            "Ensure NO material is in the fixture.\nClick OK to begin empty calibration.")
        if not r:
            return
        self.status_var.set("Calibrating...")
        self._update_status("Empty calibration...", "warning")
        self._log_debug("Calibration Step 1 started", "INFO")
        def step1_complete():
            self._log_debug("Step 1 complete", "SUCCESS")
            r2 = messagebox.askokcancel("Calibration - Step 2",
                "Place material sample and click OK.")
            if not r2:
                self.status_var.set("Ready")
                return
            self._update_status("Material calibration...", "warning")
            def step2_complete():
                cal = self._create_calibration({"step1": "empty", "step2": "material",
                    "ts1": datetime.now().isoformat(), "ts2": datetime.now().isoformat()})
                if cal:
                    self._log_debug("Calibration complete", "SUCCESS")
                    self._update_status("Calibration complete", "success")
                    self.status_var.set("Ready")
                    messagebox.showinfo("Done", "Calibration complete.")
                else:
                    self._update_status("Calibration failed", "error")
            self.after(2000, step2_complete)
        self.after(2000, step1_complete)

    def _update_button_states(self):
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container') and hasattr(self, 'clear_container'):
            if self.is_measuring:
                self.start_container.pack_forget()
                self.stop_container.pack(fill=tk.X, padx=6, pady=3, before=self.clear_container)
            else:
                self.stop_container.pack_forget()
                self.start_container.pack(fill=tk.X, padx=6, pady=3, before=self.clear_container)

    def _on_start_measurement(self):
        if self.is_measuring:
            return
        self.is_measuring = True
        self.current_angle = 0.0
        self.status_var.set("Measuring...")
        self._update_status("Sweeping 0\u00b0 to 90\u00b0", "info")
        self._update_button_states()
        self._log_debug("Sweep started", "INFO")
        self.measurement_thread = threading.Thread(target=self._measurement_worker, daemon=True)
        self.measurement_thread.start()

    def _on_stop_measurement(self):
        if not self.is_measuring:
            return
        self.is_measuring = False
        self.status_var.set("Stopping...")
        self._update_status("Stopping...", "warning")
        self._update_button_states()
        self._log_debug(f"Stopped at {self.current_angle:.2f}\u00b0", "INFO")
        self.after(500, lambda: self.status_var.set("Ready"))

    def _on_clear_measurements(self):
        ms = self._get_measurements()
        if not ms:
            messagebox.showinfo("No Data", "Nothing to clear.")
            return
        if messagebox.askyesno("Confirm", f"Delete all {len(ms)} measurements?", icon='warning'):
            try:
                self.db.query(Measurement).delete()
                self.db.commit()
                self._last_graph_count = -1
                self.current_angle = 0.0
                self._update_graphs()
                self.angle_var.set("0.0\u00b0")
                self.permittivity_var.set("0.00")
                self.permeability_var.set("0.00")
                self._update_status(f"Cleared {len(ms)} measurements", "success")
            except Exception as e:
                self.db.rollback()
                messagebox.showerror("Error", str(e))

    def _on_view_results(self):
        ms = self._get_measurements()
        if not ms:
            messagebox.showinfo("No Results", "No measurements available.")
            return
        angles = [m.angle for m in ms]
        perm = [m.permittivity for m in ms]
        perm_b = [m.permeability for m in ms]
        summary = (f"Measurements: {len(ms)}\n"
                   f"Angle: {min(angles):.1f}\u00b0 - {max(angles):.1f}\u00b0\n\n"
                   f"\u03b5: {min(perm):.4f} - {max(perm):.4f}  (avg {sum(perm)/len(perm):.4f})\n"
                   f"\u03bc: {min(perm_b):.4f} - {max(perm_b):.4f}  (avg {sum(perm_b)/len(perm_b):.4f})")
        messagebox.showinfo("Results", summary)

    def _on_export(self):
        ms = self._get_measurements()
        if not ms:
            messagebox.showwarning("No Data", "Nothing to export.")
            return
        fp = filedialog.asksaveasfilename(defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")])
        if not fp:
            return
        try:
            if fp.endswith('.csv'):
                with open(fp, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['id','angle','permittivity','permeability','timestamp'])
                    for m in ms:
                        w.writerow([m.id, m.angle, m.permittivity, m.permeability, m.timestamp.isoformat()])
            else:
                data = [{"id": m.id, "angle": m.angle, "permittivity": m.permittivity,
                         "permeability": m.permeability, "timestamp": m.timestamp.isoformat()} for m in ms]
                with open(fp, 'w') as f:
                    json.dump(data, f, indent=2)
            self._update_status(f"Exported to {os.path.basename(fp)}", "success")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)

    def _exit_fullscreen(self):
        if self.is_fullscreen:
            self._toggle_fullscreen()

    def _on_help(self):
        messagebox.showinfo("About SPAM",
            "SPAM - Scanner for Polarized Anisotropic Materials\nVersion 1.01\n\n"
            "Shortcuts: F11 Fullscreen, Ctrl+D Debug, Esc Exit fullscreen")

    def _on_debug_console(self):
        if self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugConsole(self)
        else:
            self.debug_window.lift()
            self.debug_window.focus()

    def _log_debug(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.debug_log.append(f"[{ts}] [{level}] {message}")
        if len(self.debug_log) > 1000:
            self.debug_log = self.debug_log[-1000:]
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.update_console_log()

    def _on_close(self):
        self.is_measuring = False
        if self.motor_gpio:
            try: self.motor_gpio.cleanup()
            except: pass
        if self.adc:
            try: self.adc.close()
            except: pass
        if self.rf_switch:
            try: self.rf_switch.close()
            except: pass
        if hasattr(self, 'db'):
            self.db.close()
        self.destroy()


# ======================================================================
# Debug Console
# ======================================================================
class DebugConsole(tk.Toplevel):
    def __init__(self, parent: SPAMGui):
        super().__init__(parent)
        self.parent = parent
        t = parent.theme
        self.title("SPAM - Debug Console")
        self.geometry("900x600")
        self.configure(bg=t['bg'])
        self.transient(parent)
        self.grab_set()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._create_system_tab()
        self._create_database_tab()
        self._create_measurement_tab()
        self._create_console_tab()
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
        self.console_text = self._text_widget(f, dark_bg=True)

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
        for i, (lbl, pos) in enumerate([("0\u00b0",0),("45\u00b0",45),("90\u00b0",90),("Home",0)]):
            self.parent._make_btn(qf, lbl,
                lambda p=pos: self.parent._send_motor_command(0, p, command=0),
                "ghost").grid(row=i//2, column=i%2, padx=2, pady=2, sticky="ew")

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
        from database import SQLALCHEMY_DATABASE_URL
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

    def update_console_log(self):
        self.console_text.config(state=tk.NORMAL)
        self.console_text.delete(1.0, tk.END)
        self.console_text.insert(1.0, "\n".join(self.parent.debug_log[-100:]) if self.parent.debug_log else "No log entries.")
        self.console_text.see(tk.END)
        self.console_text.config(state=tk.DISABLED)

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


def main() -> None:
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
    main()
