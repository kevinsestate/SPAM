"""
Hiwonder HPS-2518MG PWM Servo Driver

Standard hobby servo: 50 Hz, 1000-2000 µs pulse width -> 0-180 degrees.
Uses pigpio (DMA hardware PWM, jitter-free) when available, falls back to
RPi.GPIO software PWM. On non-Linux platforms, operates in simulation mode.

Wiring:
  Red    -> 5V-6V power supply (dedicated, NOT Pi 3.3V rail)
  Black  -> GND (shared with Pi)
  Orange -> GPIO signal pin (BCM 18 default)

pigpio setup (recommended, eliminates jitter):
  sudo apt install pigpio python3-pigpio -y
  sudo systemctl enable pigpiod
  sudo systemctl start pigpiod
"""

import platform
import time

_PULSE_MIN_US = 900     # pulse width at 0 degrees (calibrated)
_PULSE_MAX_US = 2200    # pulse width at 180 degrees (calibrated)
_PWM_FREQ_HZ  = 50
_PERIOD_US    = 20000   # 1 / 50 Hz = 20 ms

_SIM_MODE   = False
_USE_PIGPIO = False
_pigpio     = None
_GPIO       = None

try:
    import pigpio as _pigpio
    _USE_PIGPIO = True
except ImportError:
    try:
        import RPi.GPIO as _GPIO
    except ImportError:
        _SIM_MODE = True


class HPS2518Servo:
    """PWM-controlled Hiwonder HPS-2518MG hobby servo (0-180 degrees).

    Prefers pigpio for hardware-accurate, jitter-free DMA PWM.
    Falls back to RPi.GPIO software PWM if pigpio is unavailable or its
    daemon is not running.

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
        self._pi  = None   # pigpio connection
        self._pwm = None   # RPi.GPIO PWM object

        if self._sim:
            self._log(
                f"HPS2518Servo: simulation mode (GPIO not available), pin={gpio_pin}",
                "WARNING"
            )
            return

        if _USE_PIGPIO:
            self._pi = _pigpio.pi()
            if self._pi.connected:
                self._pi.set_servo_pulsewidth(self._pin, _PULSE_MIN_US)
                self._angle = 0.0
                self._log(
                    f"HPS2518Servo: initialized (pigpio) on GPIO{gpio_pin}, homed to 0°",
                    "SUCCESS"
                )
            else:
                self._log("pigpio daemon not running — falling back to RPi.GPIO", "WARNING")
                self._pi = None
                self._init_rpigpio(gpio_pin)
        else:
            self._init_rpigpio(gpio_pin)

    def _init_rpigpio(self, gpio_pin: int):
        _GPIO.setwarnings(False)
        _GPIO.setmode(_GPIO.BCM)
        _GPIO.setup(self._pin, _GPIO.OUT)
        self._pwm = _GPIO.PWM(self._pin, _PWM_FREQ_HZ)
        self._pwm.start(self._angle_to_duty(0.0))
        self._angle = 0.0
        self._log(
            f"HPS2518Servo: initialized (RPi.GPIO) on GPIO{gpio_pin}, homed to 0°",
            "SUCCESS"
        )

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

        pulse_us = int(_PULSE_MIN_US + (angle / 180.0) * (_PULSE_MAX_US - _PULSE_MIN_US))

        if self._pi is not None:
            self._pi.set_servo_pulsewidth(self._pin, pulse_us)
            time.sleep(settle_s)
            self._angle = angle
            self._log(f"HPS2518Servo: -> {angle:.1f}° (pulse={pulse_us}µs)", "INFO")
        elif self._pwm is not None:
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

    @property
    def backend(self) -> str:
        """Active PWM backend: 'pigpio', 'RPi.GPIO', or 'sim'."""
        if self._sim:
            return 'sim'
        return 'pigpio' if self._pi is not None else 'RPi.GPIO'

    def close(self):
        """Stop PWM output and release the GPIO pin."""
        if self._pi is not None:
            try:
                self._pi.set_servo_pulsewidth(self._pin, 0)
                self._pi.stop()
            except Exception:
                pass
            self._pi = None
        if self._pwm is not None:
            try:
                self._pwm.stop()
            except Exception:
                pass
            self._pwm = None
        if not self._sim and _GPIO is not None:
            try:
                _GPIO.cleanup(self._pin)
            except Exception:
                pass
        self._angle = None

    @staticmethod
    def _angle_to_duty(angle: float) -> float:
        """Convert 0-180 degrees to duty cycle percent for 50 Hz PWM."""
        pulse_us = _PULSE_MIN_US + (angle / 180.0) * (_PULSE_MAX_US - _PULSE_MIN_US)
        return (pulse_us / _PERIOD_US) * 100.0
