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

    def _measurement_worker(self):
        angle_step = self.angle_step
        max_angle = 90.0
        while self.is_measuring and self.current_angle <= max_angle:
            if self.motor_control_enabled or platform.system() == 'Linux':
                motor_success = self._send_motor_command(self.motor_num, self.current_angle, self.motor_command)
                if not motor_success:
                    self.after(0, lambda: self._log_debug(f"Motor cmd fail at {self.current_angle:.2f}\u00b0", "ERROR"))
                if not self._wait_for_motor_position(timeout=5.0):
                    if self.motor_collision_detected:
                        self.after(0, lambda: self._log_debug("Collision - stopping", "ERROR"))
                        self.is_measuring = False
                        break
                    else:
                        self.after(0, lambda: self._log_debug(f"Motor timeout at {self.current_angle:.2f}\u00b0", "WARNING"))

            if self.adc is not None:
                # --- Real ADC reads ---
                if self.adc.is_simulated:
                    self.adc.set_sim_angle(self.current_angle)

                if self.rf_switch is not None:
                    # S21 (transmission): switch to RXt, read I/Q
                    self.rf_switch.select_transmission()
                    time.sleep(0.01)
                    i_tx, q_tx = self.adc.read_iq()

                    # S11 (reflection): switch to RXp, read I/Q
                    self.rf_switch.select_reflection()
                    time.sleep(0.01)
                    i_rx, q_rx = self.adc.read_iq()
                else:
                    # ADC-only mode: expects path state to be handled externally.
                    if not self._adc_only_hint_logged:
                        self._adc_only_hint_logged = True
                        self.after(0, lambda: self._log_debug(
                            "ADC-only mode active: RF path switching is external/not app-controlled.",
                            "INFO"
                        ))
                    i_tx, q_tx = self.adc.read_iq()
                    time.sleep(0.01)
                    i_rx, q_rx = self.adc.read_iq()

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
                angle_rad = math.radians(self.current_angle)
                transmitted_power = -20.0 * (self.current_angle / 90.0)
                reflected_power = -15.0 - 10.0 * (self.current_angle / 90.0)
                transmitted_phase = -90.0 + 180.0 * (self.current_angle / 90.0)
                reflected_phase = -45.0 + 135.0 * (self.current_angle / 90.0)

            self.transmitted_power = transmitted_power
            self.reflected_power = reflected_power
            self.transmitted_phase = transmitted_phase
            self.reflected_phase = reflected_phase
            angle_rad = math.radians(self.current_angle)
            permittivity = 2.0 + 0.1 * math.sin(angle_rad)
            permeability = 1.5 + 0.05 * math.cos(angle_rad)
            self._create_measurement(self.current_angle, permittivity, permeability,
                                     transmitted_power=transmitted_power, reflected_power=reflected_power,
                                     transmitted_phase=transmitted_phase, reflected_phase=reflected_phase)
            self.after(0, lambda: self._log_debug(
                f"Pos: {self.current_angle:.2f}\u00b0 | TX: {transmitted_power:.1f}dBm | RX: {reflected_power:.1f}dBm", "INFO"))
            self.current_angle += angle_step
            if int(self.current_angle) % 10 == 0:
                self.after(0, lambda: self._log_debug(f"Progress: {self.current_angle:.1f}\u00b0 / 90\u00b0", "INFO"))
            time.sleep(self.measurement_interval)
        self.is_measuring = False
        if self.current_angle > max_angle:
            self.after(0, lambda: self._log_debug("Sweep complete (0-90\u00b0)", "SUCCESS"))
            self.after(0, lambda: self._update_status("Sweep complete", "success"))
            self.after(100, self._run_extraction)
        else:
            self.after(0, lambda: self._log_debug(f"Stopped at {self.current_angle:.1f}\u00b0", "INFO"))
            self.after(0, lambda: self._update_status(f"Stopped at {self.current_angle:.1f}\u00b0", "info"))
        self.after(0, lambda: self.status_var.set("Ready"))
        self.after(0, self._update_button_states)

    def _on_start_measurement(self):
        if self.is_measuring:
            return
        self.is_measuring = True
        self.current_angle = 0.0
        self.status_var.set("Measuring...")
        self._update_status("Sweeping 0\u00b0 to 90\u00b0", "info")
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
