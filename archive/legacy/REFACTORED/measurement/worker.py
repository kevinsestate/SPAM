"""
Background measurement worker – runs the angular sweep in a thread.
"""
import math
import time
import platform


class MeasurementWorker:
    """Runs an angular sweep from 0° to 90° in the background."""

    def __init__(self, motor, db, state, log=None, gui_after=None):
        """
        Args:
            motor:     MotorController instance
            db:        DatabaseManager instance
            state:     dict-like object with shared mutable state keys:
                         is_measuring, current_angle, angle_step,
                         measurement_interval, motor_num, motor_command,
                         transmitted_power, reflected_power,
                         transmitted_phase, reflected_phase
            log:       callable(msg, level)
            gui_after: callable(ms, fn) for GUI-safe callbacks
        """
        self.motor = motor
        self.db = db
        self.state = state
        self._log = log or (lambda msg, lvl="INFO": print(f"[{lvl}] {msg}"))
        self._after = gui_after

    # ------------------------------------------------------------------
    def run(self):
        """Entry point – call from a background thread."""
        angle_step = self.state['angle_step']
        max_angle = 90.0

        while self.state['is_measuring'] and self.state['current_angle'] <= max_angle:
            current = self.state['current_angle']

            # --- Motor positioning ---
            if self.motor.enabled or platform.system() == 'Linux':
                ok = self.motor.send_command(
                    motor_num=self.state['motor_num'],
                    position=current,
                    command=self.state['motor_command']
                )
                if not ok:
                    self._safe_log(f"Failed to send motor command for {current:.2f}°", "ERROR")

                if not self.motor.wait_for_position(timeout=5.0):
                    if self.motor.collision_detected:
                        self._safe_log("Measurement stopped – motor collision", "ERROR")
                        self.state['is_measuring'] = False
                        break
                    else:
                        self._safe_log(f"Motor timeout at {current:.2f}° – continuing", "WARNING")

            # --- Data acquisition (placeholder) ---
            angle_rad = math.radians(current)
            transmitted_power = -20.0 * (current / 90.0)
            reflected_power = -15.0 - 10.0 * (current / 90.0)
            transmitted_phase = -90.0 + 180.0 * (current / 90.0)
            reflected_phase = -45.0 + 135.0 * (current / 90.0)
            permittivity = 2.0 + 0.1 * math.sin(angle_rad)
            permeability = 1.5 + 0.05 * math.cos(angle_rad)

            # Update shared state
            self.state['transmitted_power'] = transmitted_power
            self.state['reflected_power'] = reflected_power
            self.state['transmitted_phase'] = transmitted_phase
            self.state['reflected_phase'] = reflected_phase

            # Store in database
            self.db.create_measurement(
                current, permittivity, permeability,
                transmitted_power=transmitted_power,
                reflected_power=reflected_power,
                transmitted_phase=transmitted_phase,
                reflected_phase=reflected_phase
            )

            self._safe_log(
                f"Position {current:.2f}° | "
                f"TX Pwr: {transmitted_power:.2f} dBm, Phase: {transmitted_phase:.2f}° | "
                f"RX Pwr: {reflected_power:.2f} dBm, Phase: {reflected_phase:.2f}°",
                "INFO"
            )

            # Advance
            self.state['current_angle'] += angle_step
            if int(self.state['current_angle']) % 10 == 0:
                self._safe_log(f"Progress: {self.state['current_angle']:.1f}° / 90°", "INFO")

            time.sleep(self.state['measurement_interval'])

        # Done
        self.state['is_measuring'] = False
        if self.state['current_angle'] > max_angle:
            self._safe_log("Sweep completed 0°–90°", "SUCCESS")
        else:
            self._safe_log(f"Stopped at {self.state['current_angle']:.1f}°", "INFO")

    # ------------------------------------------------------------------
    def _safe_log(self, msg, lvl):
        """Log via GUI-safe callback if available."""
        if self._after:
            self._after(0, lambda: self._log(msg, lvl))
        else:
            self._log(msg, lvl)
