#!/usr/bin/env python3
"""Interactive servo calibration — find exact pulse widths for 0 and 180 degrees.

Usage:
  cd ~/SPAM
  python3 scripts/pi/servo_test.py

Commands at the prompt:
  0 / 90 / 180      Jump to that angle
  <angle>           Any angle 0-180
  p<us>             Raw pulse width e.g. p1500
  min<us>           Set 0-degree pulse e.g. min900
  max<us>           Set 180-degree pulse e.g. max2000
  sweep             Slow 0->180->0 sweep (10 deg steps)
  scan              Scan 500-2400 us to find physical stops
  status            Print current MIN/MAX
  q                 Quit and print final values
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GPIO_PIN  = 18
PERIOD_US = 20000

pi  = None
pwm = None

try:
    import pigpio
    pi = pigpio.pi()
    if not pi.connected:
        pi = None
        print("[WARN] pigpiod not running.  Start it: sudo systemctl start pigpiod")
        print("       Falling back to RPi.GPIO (may jitter)")
    else:
        print(f"[OK] pigpio connected — GPIO{GPIO_PIN}")
except ImportError:
    print("[INFO] pigpio not installed — using RPi.GPIO")

if pi is None:
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_PIN, GPIO.OUT)
        pwm = GPIO.PWM(GPIO_PIN, 50)
        pwm.start(0)
        print(f"[OK] RPi.GPIO PWM on GPIO{GPIO_PIN}")
    except ImportError:
        print("[ERROR] Neither pigpio nor RPi.GPIO available. Are you on the Pi?")
        sys.exit(1)


def send(us: int) -> int:
    us = max(400, min(2500, int(us)))
    if pi is not None:
        pi.set_servo_pulsewidth(GPIO_PIN, us)
    else:
        pwm.ChangeDutyCycle((us / PERIOD_US) * 100.0)
    return us


def release():
    if pi is not None:
        pi.set_servo_pulsewidth(GPIO_PIN, 0)
        pi.stop()
    else:
        pwm.stop()
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup(GPIO_PIN)
        except Exception:
            pass


def angle_to_us(angle: float, mn: int, mx: int) -> int:
    return int(mn + (max(0.0, min(180.0, angle)) / 180.0) * (mx - mn))


# Starting calibration — matches hardware/servo.py defaults
pulse_min = 900
pulse_max = 2000

print(f"\nStarting calibration: MIN={pulse_min}us (0 deg)  MAX={pulse_max}us (180 deg)")
print("Commands: 0  90  180  p<us>  min<us>  max<us>  sweep  scan  status  q\n")

print("Homing to 0 deg...")
send(pulse_min)
time.sleep(1.2)

try:
    while True:
        try:
            cmd = input("servo> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not cmd:
            continue
        c = cmd.lower()

        if c in ("q", "quit", "exit"):
            break

        elif c == "0":
            print(f"  0 deg  -> {send(pulse_min)}us")
            time.sleep(1.0)

        elif c == "90":
            us = angle_to_us(90, pulse_min, pulse_max)
            print(f"  90 deg -> {send(us)}us")
            time.sleep(1.0)

        elif c == "180":
            print(f"  180 deg -> {send(pulse_max)}us")
            time.sleep(1.0)

        elif c == "sweep":
            print(f"  Sweeping 0->180->0  (MIN={pulse_min} MAX={pulse_max})")
            for a in range(0, 181, 10):
                us = angle_to_us(a, pulse_min, pulse_max)
                print(f"    {a:3d} deg -> {send(us)}us")
                time.sleep(0.5)
            for a in range(170, -1, -10):
                us = angle_to_us(a, pulse_min, pulse_max)
                print(f"    {a:3d} deg -> {send(us)}us")
                time.sleep(0.5)
            print("  Sweep done")

        elif c == "scan":
            print("  Scanning 500 -> 2400us in 100us steps")
            print("  Watch the servo -- note where it stops moving")
            for us in range(500, 2450, 100):
                print(f"    {us}us", end="  ", flush=True)
                send(us)
                time.sleep(0.5)
            print()
            send(pulse_min)
            print("  Back to MIN")

        elif c == "status":
            backend = "pigpio" if pi is not None else "RPi.GPIO"
            print(f"  MIN={pulse_min}us (0 deg)   MAX={pulse_max}us (180 deg)")
            print(f"  Backend: {backend}   GPIO: BCM{GPIO_PIN}")

        elif c.startswith("min"):
            try:
                pulse_min = int(c[3:])
                print(f"  MIN set to {pulse_min}us -- moving to 0 deg")
                send(pulse_min)
                time.sleep(1.0)
            except ValueError:
                print("  Usage: min900  (no space)")

        elif c.startswith("max"):
            try:
                pulse_max = int(c[3:])
                print(f"  MAX set to {pulse_max}us -- moving to 180 deg")
                send(pulse_max)
                time.sleep(1.0)
            except ValueError:
                print("  Usage: max2000  (no space)")

        elif c.startswith("p"):
            try:
                us = int(c[1:])
                print(f"  Raw pulse -> {send(us)}us")
                time.sleep(0.5)
            except ValueError:
                print("  Usage: p1500  (no space)")

        else:
            try:
                angle = float(c)
                us = angle_to_us(angle, pulse_min, pulse_max)
                print(f"  {angle:.1f} deg -> {send(us)}us")
                time.sleep(0.8)
            except ValueError:
                print(f"  Unknown: '{cmd}'  -- try: 0  90  180  p1500  min900  max2000  sweep  scan  q")

finally:
    print(f"\n=== Final calibration ===")
    print(f"  MIN = {pulse_min}us  (0 deg)")
    print(f"  MAX = {pulse_max}us  (180 deg)")
    print(f"\nUpdate hardware/servo.py lines 22-23 with:")
    print(f"  _PULSE_MIN_US = {pulse_min}")
    print(f"  _PULSE_MAX_US = {pulse_max}")
    release()
    print("Servo released.")
