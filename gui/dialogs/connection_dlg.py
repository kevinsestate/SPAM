"""ConnectionDialogMixin: connection setup dialog."""

import tkinter as tk
from tkinter import messagebox

from ..themes import _FONT


class ConnectionDialogMixin:
    """Provides _on_connection_setup dialog."""

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
