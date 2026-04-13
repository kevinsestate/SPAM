"""ConfigMixin: load/save settings, _safe_float, resonance advisory."""

import os
import json
import math

from core.spam_calc import compute_k0d, mil_to_m


class ConfigMixin:
    """Provides config persistence and parameter validation helpers."""

    def _load_connection_settings(self):
        defaults = {
            'spi_bus': '0', 'spi_cs': '0', 'spi_speed': '1000000',
            'adc_gain': '1', 'adc_data_rate': '96', 'adc_samples_per_point': '8',
            'enable_rf_switch': '0',
            'switch_gpio': '22',
            'microcontroller_address': '0x55', 'isr_pin': '17', 'servo_gpio': '18',
            'extraction_f0_ghz': '24.0', 'extraction_d_mil': '60.0',
            'extraction_tensor_type': 'diagonal',
            'cal_d_m': '0.0', 'cal_d_sheet_m': '0.0',
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
