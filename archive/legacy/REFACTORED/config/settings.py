"""
Configuration management for SPAM application.
Handles loading, saving, and validating settings from spam_config.json.
"""
import os
import json


# Default configuration values
DEFAULT_SETTINGS = {
    'i2c_bus': '1',
    'adc_address': '0x48',
    'if_i_channel': '0',
    'if_q_channel': '1',
    'sampling_rate': '1000',
    'microcontroller_address': '0x55',
    'isr_pin': '17',
    'serial_port': 'COM1',
    'baud_rate': '9600',
    'timeout': '5.0',
    'connection_type': 'I2C'
}


class Settings:
    """Manages application settings persistence."""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            config_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_file = os.path.join(config_dir, 'spam_config.json')
        self.connection = self.load()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------
    def load(self) -> dict:
        """Load connection settings from file or return defaults."""
        settings = dict(DEFAULT_SETTINGS)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    saved = json.load(f)
                    settings.update(saved)
            except Exception as e:
                print(f"Error loading config file: {e}, using defaults")
        return settings

    def save(self, log_callback=None):
        """Save current connection settings to file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.connection, f, indent=2)
            if log_callback:
                log_callback(f"Saved connection settings to {self.config_file}", "INFO")
        except Exception as e:
            if log_callback:
                log_callback(f"Error saving config file: {e}", "WARNING")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def get(self, key: str, default=None):
        return self.connection.get(key, default)

    def set(self, key: str, value):
        self.connection[key] = value

    def update(self, new_settings: dict):
        self.connection.update(new_settings)
