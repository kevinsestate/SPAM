"""
RF Switch GPIO Control (Cobham 96341 MASC-347000-CCSSW1-OD)

Controls an SP2T coaxial RF switch via a single Raspberry Pi GPIO pin.
HIGH = transmission path (RXt / S21), LOW = reflection path (RXp / S11).

On non-Linux platforms, operates in simulation mode.
"""

import platform
import time

_SIM_MODE = False
try:
    import RPi.GPIO as GPIO
except ImportError:
    _SIM_MODE = True


class RFSwitch:
    """GPIO-controlled SP2T RF switch.

    Parameters
    ----------
    gpio_pin : int
        BCM GPIO pin number connected to the switch control line.
    log_fn : callable, optional
        Logging callback ``log_fn(message, level)``.
    """

    def __init__(self, gpio_pin=22, log_fn=None):
        self._log = log_fn or (lambda m, l: None)
        self._pin = gpio_pin
        self._sim = _SIM_MODE or platform.system() != 'Linux'
        self._state = None  # 'transmission' | 'reflection' | None

        if self._sim:
            self._log(f"RFSwitch: simulation mode (GPIO not available), pin={gpio_pin}", "WARNING")
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.LOW)
        self._state = 'reflection'
        self._log(f"RFSwitch: initialized on GPIO{gpio_pin}", "SUCCESS")

    def select_transmission(self):
        """Switch to transmission path (RXt / S21). Sets pin HIGH."""
        if self._sim:
            self._state = 'transmission'
            return

        GPIO.output(self._pin, GPIO.HIGH)
        self._state = 'transmission'

    def select_reflection(self):
        """Switch to reflection path (RXp / S11). Sets pin LOW."""
        if self._sim:
            self._state = 'reflection'
            return

        GPIO.output(self._pin, GPIO.LOW)
        self._state = 'reflection'

    @property
    def current_path(self):
        """Return the currently selected path name."""
        return self._state or 'unknown'

    @property
    def is_simulated(self):
        return self._sim

    def close(self):
        """Release the GPIO pin."""
        if not self._sim:
            try:
                GPIO.output(self._pin, GPIO.LOW)
                GPIO.cleanup(self._pin)
            except Exception:
                pass
        self._state = None
