"""
Hiwonder HPS-2518MG PWM Servo Driver

Standard hobby servo: 50 Hz, 1000-2000 µs pulse width -> 0-180 degrees.
Driven directly from a Raspberry Pi GPIO pin using RPi.GPIO software PWM.
On non-Linux platforms, operates in simulation mode.

Wiring:
  Red    -> 5V–6V power supply (dedicated, NOT Pi 3.3V rail)
  Black  -> GND (shared with Pi)
  Orange -> GPIO signal pin (BCM 18 default, Pi hardware PWM0)
"""

import platform
import time

_SIM_MODE = False
try:
    import RPi.GPIO as GPIO
except ImportError:
    _SIM_MODE = True

_PWM_FREQ_HZ = 50
_PULSE_MIN_US = 1000    # pulse width at 0 degrees
_PULSE_MAX_US = 2000    # pulse width at 180 degrees
_PERIOD_US    = 20000   # 1 / 50 Hz = 20 ms


class HPS2518Servo:
    """PWM-controlled Hiwonder HPS-2518MG hobby servo (0-180 degrees).

    Parameters
    ----------
    gpio_pin : int
        BCM GPIO pin number connected to the servo signal wire.
    log_fn : callable, optional
        Logging callback ``log_fn(message, level)``.
    """

    def __init__(self, gpio_pin: int = 18, log_fn=None):
        self._log = log_fn or (lambda m, l: None)
        self._pin = gpio_pin
        self._sim = _SIM_MODE or platform.system() != 'Linux'
        self._angle = None
        self._pwm = None

        if self._sim:
            self._log(
                f"HPS2518Servo: simulation mode (GPIO not available), pin={gpio_pin}",
                "WARNING"
            )
            return

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.OUT)
        self._pwm = GPIO.PWM(self._pin, _PWM_FREQ_HZ)
        duty = self._angle_to_duty(0.0)
        self._pwm.start(duty)
        self._angle = 0.0
        self._log(f"HPS2518Servo: initialized on GPIO{gpio_pin}, homed to 0°", "SUCCESS")

    def move_to(self, angle: float, settle_s: float = 0.5):
        """Command servo to *angle* degrees (0-180). Blocks for *settle_s* seconds.

        Parameters
        ----------
        angle : float
            Target angle in degrees, clamped to [0, 180].
        settle_s : float
            Seconds to wait after commanding the servo to let it reach position.
        """
        angle = max(0.0, min(180.0, angle))
        if self._sim:
            self._log(f"HPS2518Servo: (sim) -> {angle:.1f}°", "INFO")
            self._angle = angle
            return

        duty = self._angle_to_duty(angle)
        self._pwm.ChangeDutyCycle(duty)
        time.sleep(settle_s)
        self._angle = angle
        self._log(f"HPS2518Servo: -> {angle:.1f}° (duty={duty:.2f}%)", "INFO")

    @property
    def current_angle(self) -> float | None:
        """Current commanded angle in degrees, or None if not yet set."""
        return self._angle

    @property
    def is_simulated(self) -> bool:
        """True when running in simulation mode (no real GPIO)."""
        return self._sim

    def close(self):
        """Stop PWM output and release the GPIO pin."""
        if self._pwm is not None:
            try:
                self._pwm.stop()
            except Exception:
                pass
        if not self._sim:
            try:
                GPIO.cleanup(self._pin)
            except Exception:
                pass
        self._pwm = None
        self._angle = None

    @staticmethod
    def _angle_to_duty(angle: float) -> float:
        """Convert 0-180 degrees to duty cycle percent for 50 Hz PWM.

        Parameters
        ----------
        angle : float
            Angle in degrees [0, 180].

        Returns
        -------
        float
            Duty cycle in percent [5.0, 10.0].
        """
        pulse_us = _PULSE_MIN_US + (angle / 180.0) * (_PULSE_MAX_US - _PULSE_MIN_US)
        return (pulse_us / _PERIOD_US) * 100.0
