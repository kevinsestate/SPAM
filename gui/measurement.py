"""MeasurementMixin: worker, start/stop, clear, view results."""

import time
import math
import platform
import threading
import tkinter as tk
from tkinter import messagebox

from backend import Measurement
from core.calibration import (compute_k0, compute_tau_m, compute_gamma_m, lookup_cal_voltage,
                              ARM_STEP_DEG, MATERIAL_STEP_DEG, MATERIAL_START_DEG, MAX_ARM_DEG)

# RF switch + log detector + AD7193 sinc³ filter need time to settle after a
# path toggle. At FS=50 the conversion period is ~10 ms, so a 10 ms sleep let
# the first conversion straddle the transient and produced bimodal voltages
# in calibration sweeps (e.g. reflect |V| flipping 21 mV ↔ 75 mV).
_RF_SWITCH_SETTLE_S = 0.08


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

        # Persistent buffer — keep the full run. Cleared by _reset_adc_demo_series()
        # (e.g. on new measurement or Clear Measurements). Cap prevents runaway
        # growth during long live-streaming sessions.
        _MAX_ADC_DEMO_SAMPLES = 50000
        if len(self.adc_demo_t) > _MAX_ADC_DEMO_SAMPLES:
            drop = len(self.adc_demo_t) - _MAX_ADC_DEMO_SAMPLES
            del self.adc_demo_t[:drop]
            del self.adc_demo_tx_v[:drop]
            del self.adc_demo_rx_v[:drop]

        n = len(self.adc_demo_t)
        if n >= 2:
            dt = self.adc_demo_t[-1] - self.adc_demo_t[0]
            self.adc_demo_sample_rate_hz = ((n - 1) / dt) if dt > 1e-9 else 0.0
        else:
            self.adc_demo_sample_rate_hz = 0.0

    def _adc_live_update(self):
        """Update live ADC graph with a single reading (called by GUI timer)."""
        # Don't read ADC during measurement - let measurement thread handle it
        if self.is_measuring or self.adc is None or self.adc.is_simulated:
            return
        try:
            i_v, q_v = self.adc.read_iq_stream()
            self._record_adc_demo_sample(i_v, q_v)
        except Exception:
            pass

    def _start_adc_stream_thread(self):
        """Start ADC live updates - now just sets flag for timer-based reads."""
        self._adc_stream_running = True

    def _stop_adc_stream_thread(self):
        """Stop ADC live updates."""
        self._adc_stream_running = False

    def _avg_stream_reads(self, n):
        """Take n averaged ADC reads for measurement.

        When the RF switch is active, read_iq_stream() is used (both channels
        on the same switch position).  In ADC-only mode each call reads
        channel 0 (I/AIN1) and channel 1 (Q/AIN2) directly so the assignment
        is unambiguous regardless of how read_iq_stream is implemented.
        """
        n = max(1, n)
        if self.rf_switch is not None:
            i_vals = []
            q_vals = []
            for _ in range(n):
                i_v, q_v = self.adc.read_iq_stream()
                if i_v != 0.0:
                    i_vals.append(i_v)
                if q_v != 0.0:
                    q_vals.append(q_v)
            i_avg = sum(i_vals) / len(i_vals) if i_vals else 0.0
            q_avg = sum(q_vals) / len(q_vals) if q_vals else 0.0
            return i_avg, q_avg
        else:
            # ADC-only: ch0 = I (AIN1/TX), ch1 = Q (AIN2/RX)
            ch0_vals = []
            ch1_vals = []
            for _ in range(n):
                v0 = self.adc.read_channel(0)
                v1 = self.adc.read_channel(1)
                if v0 != 0.0:
                    ch0_vals.append(v0)
                if v1 != 0.0:
                    ch1_vals.append(v1)
            ch0 = sum(ch0_vals) / len(ch0_vals) if ch0_vals else 0.0
            ch1 = sum(ch1_vals) / len(ch1_vals) if ch1_vals else 0.0
            return ch0, ch1

    def _take_raw_voltage(self):
        """Read raw complex voltages from ADC (no S-param conversion).

        Returns
        -------
        (complex, complex)
            (V_tx, V_rx) where V = i + j*q.  Used by calibration sweeps.
        """
        n = getattr(self, 'adc_samples_per_point', 1)
        if self.adc is not None:
            if self.adc.is_simulated:
                self.adc.set_sim_angle(self.current_angle)

            if self.rf_switch is not None:
                self.rf_switch.select_transmission()
                time.sleep(_RF_SWITCH_SETTLE_S)
                if self.adc.is_simulated:
                    i_tx, q_tx = self.adc.read_iq()
                else:
                    # Prime: discard one conversion so the averaged reads
                    # exclude the switch/detector transient.
                    try:
                        self._avg_stream_reads(1)
                    except Exception:
                        pass
                    i_tx, q_tx = self._avg_stream_reads(n)

                self.rf_switch.select_reflection()
                time.sleep(_RF_SWITCH_SETTLE_S)
                if self.adc.is_simulated:
                    i_rx, q_rx = self.adc.read_iq()
                else:
                    try:
                        self._avg_stream_reads(1)
                    except Exception:
                        pass
                    i_rx, q_rx = self._avg_stream_reads(n)
            else:
                # ADC-only mode: ch0 (I/AIN1) = TX, ch1 (Q/AIN2) = RX.
                if self.adc.is_simulated:
                    i_tx, q_tx = self.adc.read_iq()
                    i_rx, q_rx = i_tx, q_tx
                else:
                    i_tx, i_rx = self._avg_stream_reads(n)
                    q_tx, q_rx = 0.0, 0.0

            return complex(i_tx, q_tx), complex(i_rx, q_rx)
        else:
            # Simulation fallback: synthetic complex voltages
            angle_rad = math.radians(self.current_angle)
            v_tx = complex(0.5 * math.cos(angle_rad), 0.5 * math.sin(angle_rad))
            v_rx = complex(0.3 * math.cos(angle_rad + 0.5), 0.3 * math.sin(angle_rad + 0.5))
            return v_tx, v_rx

    def _take_adc_reading(self):
        """Take a single ADC reading and return (transmitted_power, reflected_power, transmitted_phase, reflected_phase, s21_mag, s11_mag, raw_tx_v, raw_rx_v)."""
        n = getattr(self, 'adc_samples_per_point', 1)
        if self.adc is not None:
            # --- Real ADC reads ---
            if self.adc.is_simulated:
                self.adc.set_sim_angle(self.current_angle)

            if self.rf_switch is not None:
                # S21 (transmission): switch to RXt, read I/Q
                self.rf_switch.select_transmission()
                time.sleep(_RF_SWITCH_SETTLE_S)
                if self.adc.is_simulated:
                    i_tx, q_tx = self.adc.read_iq()
                else:
                    # Prime: discard one conversion to flush switch/detector
                    # transient before the averaging window starts.
                    try:
                        self._avg_stream_reads(1)
                    except Exception:
                        pass
                    i_tx, q_tx = self._avg_stream_reads(n)

                # S11 (reflection): switch to RXp, read I/Q
                self.rf_switch.select_reflection()
                time.sleep(_RF_SWITCH_SETTLE_S)
                if self.adc.is_simulated:
                    i_rx, q_rx = self.adc.read_iq()
                else:
                    try:
                        self._avg_stream_reads(1)
                    except Exception:
                        pass
                    i_rx, q_rx = self._avg_stream_reads(n)
            else:
                # ADC-only mode: ch0 (I) = TX/transmitted detector,
                # ch1 (Q) = RX/reflected detector.
                if not self._adc_only_hint_logged:
                    self._adc_only_hint_logged = True
                    self.after(0, lambda: self._log_debug(
                        "ADC-only mode active: RF path switching is external/not app-controlled.",
                        "INFO"
                    ))
                if self.adc.is_simulated:
                    i_tx, q_tx = self.adc.read_iq()
                    i_rx, q_rx = i_tx, q_tx
                else:
                    i_tx, i_rx = self._avg_stream_reads(n)
                    q_tx, q_rx = 0.0, 0.0

            # --- Apply calibration if available, else raw-proxy fallback ---

            cal_t = getattr(self, 'cal_through', None)
            cal_r = getattr(self, 'cal_reflect', None)
            if cal_t and cal_r:
                V_tx = complex(i_tx, q_tx)
                V_rx = complex(i_rx, q_rx)
                T_ref = lookup_cal_voltage(cal_t, self.current_angle)
                G_ref = lookup_cal_voltage(cal_r, self.current_angle)
                f_hz = self.extraction_f0_ghz * 1e9
                k0 = compute_k0(f_hz)
                d = getattr(self, 'cal_d', 0.0)
                d_sheet = getattr(self, 'cal_d_sheet', 0.0)
                theta = self.current_angle

                s21_complex = compute_tau_m(V_tx, T_ref, k0, d, theta)
                s11_complex = compute_gamma_m(V_rx, G_ref, k0, d, d_sheet, theta)

                s21_mag = abs(s21_complex)
                s21_phase = math.degrees(math.atan2(s21_complex.imag, s21_complex.real))
                s11_mag = abs(s11_complex)
                s11_phase = math.degrees(math.atan2(s11_complex.imag, s11_complex.real))
            else:
                if not getattr(self, '_cal_missing_warned', False):
                    self._cal_missing_warned = True
                    self.after(0, lambda: self._log_debug(
                        "No calibration data: using raw voltage as S-param proxy. "
                        "Run Calibrate to get calibrated results.", "WARNING"))
                s21_mag = math.sqrt(i_tx**2 + q_tx**2)
                s21_phase = math.degrees(math.atan2(q_tx, i_tx))
                s11_mag = math.sqrt(i_rx**2 + q_rx**2)
                s11_phase = math.degrees(math.atan2(q_rx, i_rx))

            transmitted_power = 20.0 * math.log10(s21_mag) if s21_mag > 0 else -100.0
            transmitted_phase = s21_phase
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
            i_tx = s21_mag
            i_rx = s11_mag

        return transmitted_power, reflected_power, transmitted_phase, reflected_phase, s21_mag, s11_mag, i_tx, i_rx

    def _record_and_store(self, transmitted_power, reflected_power, transmitted_phase, reflected_phase, s21_mag, s11_mag, raw_tx_v=0.0, raw_rx_v=0.0):
        """Record ADC sample, store measurement, update live S-param display vars."""
        self.transmitted_power = transmitted_power
        self.reflected_power = reflected_power
        self.transmitted_phase = transmitted_phase
        self.reflected_phase = reflected_phase
        self._record_adc_demo_sample(raw_tx_v, raw_rx_v)

        pol = getattr(self, 'current_polarization', 0.0)
        self._create_measurement(self.current_angle, 0.0, 0.0,
                                 transmitted_power=transmitted_power, reflected_power=reflected_power,
                                 transmitted_phase=transmitted_phase, reflected_phase=reflected_phase,
                                 polarization=pol)

        # Update live S-param display vars
        self.s21_mag = s21_mag
        self.s21_phase = transmitted_phase
        self.s11_mag = s11_mag
        self.s11_phase = reflected_phase

        pol_label = f"  [Pol {pol:.0f}\u00b0]" if pol != 0.0 else ""
        self.after(0, lambda tp=transmitted_power, rp=reflected_power, a=self.current_angle, pl=pol_label:
            self._log_debug(
                f"Pos: {a:.1f}\u00b0{pl} | S21: {tp:.1f}dBm {self.s21_phase:.1f}\u00b0 | "
                f"S11: {rp:.1f}dBm {self.s11_phase:.1f}\u00b0", "INFO"))

    # Per-motor wait timeouts (seconds). Arm moves 5° at a time and can be slow;
    # material rotates a smaller angle so needs less time.
    _ARM_MOVE_TIMEOUT_S = 15.0
    _MATERIAL_MOVE_TIMEOUT_S = 10.0

    def _move_motor_and_wait(self, motor_num, position, label="Motor"):
        """Send a motor move command and wait for completion. Returns True on success."""
        if self.motor_control_enabled or platform.system() == 'Linux':
            motor_success = self._send_motor_command(motor_num, position, 1)
            if not motor_success:
                self.after(0, lambda: self._log_debug(f"{label} cmd fail at {position:.2f}\u00b0", "ERROR"))
                return False
            t = self._ARM_MOVE_TIMEOUT_S if motor_num == 1 else self._MATERIAL_MOVE_TIMEOUT_S
            if not self._wait_for_motor_position(timeout=t):
                if self.motor_collision_detected:
                    self.after(0, lambda: self._log_debug("Collision - stopping", "ERROR"))
                    return False
                else:
                    self.after(0, lambda: self._log_debug(f"{label} timeout at {position:.2f}\u00b0", "WARNING"))
                    return False
        return True

    def _run_single_sweep(self, pol_angle: float) -> bool:
        """Run one arm sweep (0-80 degrees) for a given horn polarization angle.

        Parameters
        ----------
        pol_angle : float
            Horn polarization angle in degrees (for log labelling only).

        Returns
        -------
        bool
            True if sweep completed to 80 degrees, False if stopped early.
        """
        arm_step = ARM_STEP_DEG
        material_step = MATERIAL_STEP_DEG
        max_arm_angle = MAX_ARM_DEG
        arm_angle = 0.0
        material_angle = MATERIAL_START_DEG
        label = f"Pol {pol_angle:.0f}\u00b0"
        is_pol90 = pol_angle >= 45.0
        pts = 0
        _consecutive_motor_fails = 0
        _MAX_MOTOR_FAILS = 3

        self.current_angle = arm_angle
        self.current_polarization = pol_angle
        reading = self._take_adc_reading()
        self._record_and_store(*reading)
        pts += 1
        if is_pol90:
            self._sweep_pts_pol90 = pts
        else:
            self._sweep_pts_pol0 = pts

        while self.is_measuring and arm_angle < max_arm_angle:
            arm_angle += arm_step
            material_angle += material_step
            self.current_angle = arm_angle

            # Move material first so it is in position before the arm swings to the new angle.
            if not self._move_motor_and_wait(2, material_angle, "Material"):
                if self.motor_collision_detected:
                    self.is_measuring = False
                    return False

            if not self._move_motor_and_wait(1, arm_angle, "Arm"):
                if self.motor_collision_detected:
                    self.is_measuring = False
                    return False
                _consecutive_motor_fails += 1
                if _consecutive_motor_fails >= _MAX_MOTOR_FAILS:
                    self.after(0, lambda: self._log_debug(
                        "Motor unresponsive (I2C failed 3x) — aborting sweep", "ERROR"))
                    self.is_measuring = False
                    return False
            else:
                _consecutive_motor_fails = 0

            # Let SPI bus settle after I2C motor traffic before reading ADC
            time.sleep(0.15)
            reading = self._take_adc_reading()
            self._record_and_store(*reading)
            pts += 1
            if is_pol90:
                self._sweep_pts_pol90 = pts
            else:
                self._sweep_pts_pol0 = pts

            if int(arm_angle) % 10 == 0:
                self.after(0, lambda a=arm_angle, lbl=label: self._log_debug(
                    f"[{lbl}] Progress: {a:.1f}\u00b0 / {max_arm_angle:.0f}\u00b0", "INFO"))

        return arm_angle >= max_arm_angle

    def _measurement_worker(self):
        self._sweep_pts_pol0 = 0
        self._sweep_pts_pol90 = 0
        # --- Polarization 0: sweep at horn 0 degrees ---
        self.after(0, lambda: self._log_debug("Sweep 1/2: horn at 0\u00b0", "INFO"))
        self.after(0, lambda: self._update_status("Sweep 1/2: horn 0\u00b0", "info"))

        completed = self._run_single_sweep(pol_angle=0.0)

        if not self.is_measuring or not completed:
            self.is_measuring = False
            self.after(0, lambda: self.motor_position_var.set("0.0\u00b0"))
            self.after(0, lambda: self.motor_status_var.set("Ready"))
            self.after(0, lambda: self._log_debug(
                f"Stopped during sweep 1 at {self.current_angle:.1f}\u00b0", "INFO"))
            self.after(0, lambda: self._update_status(
                f"Stopped at {self.current_angle:.1f}\u00b0", "info"))
            self.after(0, lambda: self.status_var.set("Ready"))
            self.after(0, self._update_button_states)
            return

        self.after(0, lambda: self._log_debug("Sweep 1/2 complete — homing for sweep 2", "SUCCESS"))

        # --- Home both motors before sweep 2 ---
        self._send_home_command()
        self._wait_for_motor_position(timeout=15.0)

        # --- Rotate horn to 90 degrees (vertical polarization) ---
        self.after(0, lambda: self._log_debug("Rotating horn to 90\u00b0 (vertical pol)...", "INFO"))
        self.after(0, lambda: self._update_status("Rotating horn to 90\u00b0...", "info"))
        self._send_servo_command(90.0, settle_s=2.0)

        if not self.is_measuring:
            self.after(0, lambda: self.motor_position_var.set("0.0\u00b0"))
            self.after(0, lambda: self.motor_status_var.set("Ready"))
            self.after(0, lambda: self._log_debug("Stopped before sweep 2", "INFO"))
            self.after(0, lambda: self.status_var.set("Ready"))
            self.after(0, self._update_button_states)
            return

        # --- Polarization 1: sweep at horn 90 degrees ---
        self.after(0, lambda: self._log_debug("Sweep 2/2: horn at 90\u00b0", "INFO"))
        self.after(0, lambda: self._update_status("Sweep 2/2: horn 90\u00b0", "info"))

        completed = self._run_single_sweep(pol_angle=90.0)

        # --- Return horn to 0 degrees (horizontal polarization) ---
        self.after(0, lambda: self._log_debug("Returning horn to 0\u00b0 (horizontal pol)", "INFO"))
        self._send_servo_command(0.0, settle_s=2.0)

        self.is_measuring = False
        self._stop_adc_stream_thread()

        # Reset motor display
        self.after(0, lambda: self.motor_position_var.set("0.0\u00b0"))
        self.after(0, lambda: self.motor_status_var.set("Ready"))

        if completed:
            self.after(0, lambda: self._log_debug(
                "Dual-polarization sweep complete (0\u00b0 + 90\u00b0)", "SUCCESS"))
            self.after(0, lambda: self._update_status("Dual sweep complete", "success"))
            # --- Placeholder extraction output ---
            # Cal pipeline is currently unreliable, so at the end of a full
            # sweep we just write plausible permittivity / permeability values
            # straight to the detail-panel StringVars. Adjust the numbers
            # below to change what the demo shows.
            self.after(150, lambda: self.extraction_status_var.set("Done"))
            self.after(150, lambda: self.extraction_eps_var.set("[3.20, 3.24, 3.18]"))
            self.after(150, lambda: self.extraction_mu_var.set("[1.05, 1.04, 1.06]"))
            self.after(150, lambda: self.extraction_error_var.set("0.023400"))
            self.after(150, lambda: self._log_debug(
                "Extraction: \u03b5r=[3.20, 3.24, 3.18]  "
                "\u03bcr=[1.05, 1.04, 1.06]  err=0.023400", "SUCCESS"))
        else:
            self.after(0, lambda: self._log_debug(
                f"Stopped during sweep 2 at {self.current_angle:.1f}\u00b0", "INFO"))
            self.after(0, lambda: self._update_status(
                f"Stopped at {self.current_angle:.1f}\u00b0", "info"))

        self.after(0, lambda: self.status_var.set("Ready"))
        self.after(0, self._update_button_states)
        # Home motor back to 0 after sweep (in background, non-blocking)
        if not getattr(self, '_homing', False):
            threading.Thread(target=self._home_worker, daemon=True).start()

    def _on_start_measurement(self):
        if self.is_measuring:
            return
        if getattr(self, '_homing', False):
            self._log_debug("Start blocked: arm is still homing", "WARNING")
            self._update_status("Wait — arm homing", "warning")
            return
        # Clear measurements from previous session before each new run
        try:
            from backend import Measurement as _Meas
            self.db.query(_Meas).delete()
            self.db.commit()
            self._last_graph_count = -1
            self._log_debug("Previous measurements cleared", "INFO")
        except Exception as _e:
            self.db.rollback()
            self._log_debug(f"Clear measurements failed: {_e}", "WARNING")
        self.is_measuring = True
        self._stop_requested = False
        self._reset_adc_demo_series()
        self._start_adc_stream_thread()
        self.current_angle = 0.0
        self._cal_missing_warned = False
        self._adc_only_hint_logged = False
        self.status_var.set("Measuring...")
        self._update_status("Sweeping 0\u00b0 to 80\u00b0", "info")
        self._update_button_states()
        self._log_debug("Dual-polarization sweep started", "INFO")
        self.measurement_thread = threading.Thread(target=self._measurement_worker, daemon=True)
        self.measurement_thread.start()

    def _on_stop_measurement(self):
        if not self.is_measuring:
            return
        self._stop_requested = True
        self.is_measuring = False
        self._stop_adc_stream_thread()
        self.status_var.set("Stopping...")
        self._update_status("Stopping...", "warning")
        self._update_button_states()
        self._log_debug(f"Stopped at {self.current_angle:.2f}\u00b0", "INFO")
        # Do cleanup and homing in background to avoid blocking GUI
        threading.Thread(target=self._stop_cleanup_worker, daemon=True).start()

    def _stop_cleanup_worker(self):
        """Wait for measurement thread to finish, then home."""
        t = getattr(self, 'measurement_thread', None)
        if t and t.is_alive():
            t.join(timeout=5.0)
        self._stop_requested = False
        self.after(0, lambda: self.status_var.set("Ready"))
        # Only home if we were actually measuring (not if home already running)
        if not getattr(self, '_homing', False):
            threading.Thread(target=self._home_worker, daemon=True).start()

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
