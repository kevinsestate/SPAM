"""
SPAMGui assembly — combines all mixins into the final application class.
"""

import tkinter as tk
import os
import platform

from gui.themes import THEMES
from gui.widgets import WidgetsMixin
from gui.config import ConfigMixin
from gui.hardware_mixin import HardwareMixin
from gui.db_helpers import DBMixin
from gui.measurement import MeasurementMixin
from gui.extraction import ExtractionMixin
from gui.graphs import GraphsMixin
from gui.callbacks import CallbacksMixin
from gui.panels.menu import MenuMixin
from gui.panels.status_bar import StatusBarMixin
from gui.panels.sidebar import SidebarMixin
from gui.panels.detail_panel import DetailPanelMixin
from gui.dialogs.base import DialogBaseMixin
from gui.dialogs.extraction_dlg import ExtractionDialogMixin
from gui.dialogs.parameters_dlg import ParametersDialogMixin
from gui.dialogs.connection_dlg import ConnectionDialogMixin

if platform.system() == 'Windows':
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass


class SPAMGui(
    WidgetsMixin,
    ConfigMixin,
    HardwareMixin,
    DBMixin,
    MeasurementMixin,
    ExtractionMixin,
    GraphsMixin,
    CallbacksMixin,
    MenuMixin,
    StatusBarMixin,
    SidebarMixin,
    DetailPanelMixin,
    DialogBaseMixin,
    ExtractionDialogMixin,
    ParametersDialogMixin,
    ConnectionDialogMixin,
    tk.Tk,
):
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
        self.adc_samples_per_point = int(self.connection_settings.get('adc_samples_per_point', '8'))

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
        self.adc_demo_window_sec = 45.0
        self.adc_demo_graph_enabled = False
        self.adc_demo_t = []
        self.adc_demo_tx_v = []
        self.adc_demo_rx_v = []
        self.adc_demo_sample_count = 0
        self.adc_demo_sample_rate_hz = 0.0
        self.adc_demo_t0 = None

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

    def _on_close(self):
        self.is_measuring = False
        if self.motor_gpio:
            try: self.motor_gpio.cleanup()
            except: pass
        if self.adc:
            try: self.adc.stop_stream()
            except: pass
            try: self.adc.close()
            except: pass
        if self.rf_switch:
            try: self.rf_switch.close()
            except: pass
        if hasattr(self, 'db'):
            self.db.close()
        self.destroy()


def main() -> None:
    app = SPAMGui()
    app.mainloop()


if __name__ == "__main__":
    main()
