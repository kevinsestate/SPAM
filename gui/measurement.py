"""MeasurementMixin: worker, start/stop, clear, view results."""

import time
import math
import platform
import threading
import tkinter as tk
from tkinter import messagebox

from backend import Measurement


class MeasurementMixin:
    """Provides measurement sweep worker and start/stop/clear/view commands."""

    def _reset_adc_demo_series(self):
        """Reset rolling ADC demo buffers/counters for a new run."""
        self.adc_demo_t = []
        self.adc_demo_tx_v = []
        self.adc_demo_rx_v = []
        self.adc_demo_sample_count = 0
        self.adc_demo_sample_rate_hz = 0.0
        self.adc_demo_t0 = None

    def _record_adc_demo_sample(self, tx_v: float, rx_v: float):
        """Append one ADC demo sample and update effective sample-rate."""
        now = time.monotonic()
        if self.adc_demo_t0 is None:
            self.adc_demo_t0 = now
        t_rel = now - self.adc_demo_t0

        self.adc_demo_t.append(t_rel)
        self.adc_demo_tx_v.append(tx_v)
        self.adc_demo_rx_v.append(rx_v)
        self.adc_demo_sample_count += 1

        # Keep a bounded rolling window for responsive plotting on Pi.
        while self.adc_demo_t and (t_rel - self.adc_demo_t[0]) > self.adc_demo_window_sec:
            self.adc_demo_t.pop(0)
            self.adc_demo_tx_v.pop(0)
            self.adc_demo_rx_v.pop(0)

        n = len(self.adc_demo_t)
        if n >= 2:
            dt = self.adc_demo_t[-1] - self.adc_demo_t[0]
            self.adc_demo_sample_rate_hz = ((n - 1) / dt) if dt > 1e-9 else 0.0
        else:
            self.adc_demo_sample_rate_hz = 0.0

    def _take_adc_reading(self):
        """Take a single ADC reading and return (transmitted_power, reflected_power, transmitted_phase, reflected_phase, s21_mag, s11_mag)."""
        if self.adc is not None:
            # --- Real ADC reads ---
            if self.adc.is_simulated:
                self.adc.set_sim_angle(self.current_angle)

            if self.rf_switch is not None:
                # S21 (transmission): switch to RXt, read I/Q
                self.rf_switch.select_transmission()
                time.sleep(0.01)
                if self.adc.is_simulated:
                    i_tx, q_tx = self.adc.read_iq()
                else:
                    i_tx, q_tx = self.adc.read_iq_stream()

                # S11 (reflection): switch to RXp, read I/Q
                self.rf_switch.select_reflection()
                time.sleep(0.01)
                if self.adc.is_simulated:
                    i_rx, q_rx = self.adc.read_iq()
                else:
                    i_rx, q_rx = self.adc.read_iq_stream()
            else:
                # ADC-only mode: single I/Q read per point (no RF switch means
                # both paths see the same physical channels; duplicating the
                # pair for TX/RX keeps downstream math consistent).
                if not self._adc_only_hint_logged:
                    self._adc_only_hint_logged = True
                    self.after(0, lambda: self._log_debug(
                        "ADC-only mode active: RF path switching is external/not app-controlled.",
                        "INFO"
                    ))
                if self.adc.is_simulated:
                    i_tx, q_tx = self.adc.read_iq()
                else:
                    i_tx, q_tx = self.adc.read_iq_stream()
                i_rx, q_rx = i_tx, q_tx

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
            transmitted_power = -20.0 * (self.current_angle / 80.0)
            reflected_power = -15.0 - 10.0 * (self.current_angle / 80.0)
            transmitted_phase = -90.0 + 180.0 * (self.current_angle / 80.0)
            reflected_phase = -45.0 + 135.0 * (self.current_angle / 80.0)
            s21_mag = 10 ** (transmitted_power / 20.0)
            s11_mag = 10 ** (reflected_power / 20.0)

        return transmitted_power, reflected_power, transmitted_phase, reflected_phase, s21_mag, s11_mag

    def _record_and_store(self, transmitted_power, reflected_power, transmitted_phase, reflected_phase, s21_mag, s11_mag):
        """Record ADC sample, compute material properties, store measurement."""
        self.transmitted_power = transmitted_power
        self.reflected_power = reflected_power
        self.transmitted_phase = transmitted_phase
        self.reflected_phase = reflected_phase
        self._record_adc_demo_sample(s21_mag, s11_mag)
        angle_rad = math.radians(self.current_angle)
        permittivity = 2.0 + 0.1 * math.sin(angle_rad)
        permeability = 1.5 + 0.05 * math.cos(angle_rad)
        self._create_measurement(self.current_angle, permittivity, permeability,
                                 transmitted_power=transmitted_power, reflected_power=reflected_power,
                                 transmitted_phase=transmitted_phase, reflected_phase=reflected_phase)
        self.after(0, lambda tp=transmitted_power, rp=reflected_power: self._log_debug(
            f"Pos: {self.current_angle:.2f}\u00b0 | TX: {tp:.1f}dBm | RX: {rp:.1f}dBm", "INFO"))

    def _move_motor_and_wait(self, motor_num, position, label="Motor"):
        """Send a motor move command and wait for completion. Returns True on success."""
        if self.motor_control_enabled or platform.system() == 'Linux':
            motor_success = self._send_motor_command(motor_num, position, 1)
            if not motor_success:
                self.after(0, lambda: self._log_debug(f"{label} cmd fail at {position:.2f}\u00b0", "ERROR"))
                return False
            if not self._wait_for_motor_position(timeout=5.0):
                if self.motor_collision_detected:
                    self.after(0, lambda: self._log_debug("Collision - stopping", "ERROR"))
                    return False
                else:
                    self.after(0, lambda: self._log_debug(f"{label} timeout at {position:.2f}\u00b0", "WARNING"))
        return True

    def _measurement_worker(self):
        arm_step = 5.0
        material_step = 2.5
        max_arm_angle = 80.0
        arm_angle = 0.0
        material_angle = 0.0

        # --- Initial ADC measurement at home (0°) ---
        self.current_angle = arm_angle
        reading = self._take_adc_reading()
        self._record_and_store(*reading)
        time.sleep(self.measurement_interval)

        # --- Sweep: move then measure until arm reaches 80° ---
        while self.is_measuring and arm_angle < max_arm_angle:
            arm_angle += arm_step
            material_angle += material_step
            self.current_angle = arm_angle

            # Move arm motor (motor 1)
            if not self._move_motor_and_wait(1, arm_angle, "Arm"):
                if self.motor_collision_detected:
                    self.is_measuring = False
                    break

            # Move material motor (motor 2)
            if not self._move_motor_and_wait(2, material_angle, "Material"):
                if self.motor_collision_detected:
                    self.is_measuring = False
                    break

            # ADC measurement after both motors reach position
            reading = self._take_adc_reading()
            self._record_and_store(*reading)

            if int(arm_angle) % 10 == 0:
                self.after(0, lambda a=arm_angle: self._log_debug(f"Progress: {a:.1f}\u00b0 / {max_arm_angle:.0f}\u00b0", "INFO"))
            time.sleep(self.measurement_interval)

        self.is_measuring = False
        if arm_angle >= max_arm_angle:
            self.after(0, lambda: self._log_debug("Sweep complete (0-80\u00b0)", "SUCCESS"))
            self.after(0, lambda: self._update_status("Sweep complete", "success"))
            self.after(100, self._run_extraction)
        else:
            self.after(0, lambda a=arm_angle: self._log_debug(f"Stopped at {a:.1f}\u00b0", "INFO"))
            self.after(0, lambda a=arm_angle: self._update_status(f"Stopped at {a:.1f}\u00b0", "info"))
        self.after(0, lambda: self.status_var.set("Ready"))
        self.after(0, self._update_button_states)

    def _on_start_measurement(self):
        if self.is_measuring:
            return
        self.is_measuring = True
        self._reset_adc_demo_series()
        self.current_angle = 0.0
        self.status_var.set("Measuring...")
        self._update_status("Sweeping 0\u00b0 to 80\u00b0", "info")
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
                self._reset_adc_demo_series()
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
