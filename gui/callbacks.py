"""CallbacksMixin: status, calibrate, export, help, fullscreen, debug log."""

import os
import json
import csv
import time
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog

from backend import CalibrationSweep, ExtractionResult
from core.calibration import ARM_STEP_DEG, MATERIAL_STEP_DEG, MATERIAL_START_DEG, MAX_ARM_DEG


class CallbacksMixin:
    """Provides command callbacks: status update, calibrate, export, help, fullscreen, debug log."""

    def _update_status(self, message: str, status_type: str = "info"):
        self.status_text_var.set(message)
        ts = datetime.now().strftime("%H:%M:%S")
        self.time_label.config(text=ts)
        cmap = {"success": self._t('success'), "warning": self._t('warning'),
                "error": self._t('error'), "info": self._t('accent')}
        self._status_dot.config(fg=cmap.get(status_type, self._t('success')))
        self._last_status_type = status_type

    def _on_calibrate(self):
        if self.is_measuring:
            messagebox.showwarning("Busy", "Stop the current measurement before calibrating.")
            return
        if getattr(self, '_cal_running', False):
            messagebox.showwarning("Busy", "Calibration is already running.")
            return
        r = messagebox.askokcancel("Calibration - Step 1 (Through)",
            "Remove ALL material from the fixture.\n"
            "This will sweep 0\u00b0\u201380\u00b0 and record through-reference voltages.\n\n"
            "Click OK to begin.")
        if not r:
            return
        # Lifecycle setup mirroring _on_start_measurement so cal runs on the
        # same hardware path as the working measurement sweep.
        self._cal_running = True
        self._stop_requested = False
        try:
            self._reset_adc_demo_series()
        except Exception:
            pass
        self._start_adc_stream_thread()
        self.current_angle = 0.0
        self._cal_missing_warned = False
        self.status_var.set("Calibrating...")
        self._update_status("Through calibration sweep...", "warning")
        self._log_debug("Calibration: Through sweep started", "INFO")
        threading.Thread(target=self._cal_through_worker, daemon=True).start()

    def _cal_sweep_angles(self):
        """Return the list of calibration sweep angles (matches measurement sweep)."""
        angles = []
        a = 0.0
        while a <= MAX_ARM_DEG:
            angles.append(a)
            a += ARM_STEP_DEG
        return angles

    @staticmethod
    def _cal_material_angle(arm_angle):
        """Material motor position that matches arm_angle during a sweep."""
        return MATERIAL_START_DEG + (arm_angle / ARM_STEP_DEG) * MATERIAL_STEP_DEG

    def _run_cal_sweep(self, kind: str):
        """Run one calibration arm sweep (0-80 degrees) at horn 0 deg.

        Structured to mirror gui/measurement.py:_run_single_sweep exactly so
        the cal runs on the same motor + ADC path as the working measurement.

        Parameters
        ----------
        kind : str
            "through" — store V_tx per point.
            "reflect" — store V_rx per point.

        Returns
        -------
        (angles, voltages, completed)
            angles    : list[float] of arm angles actually sampled.
            voltages  : list[[real, imag]] parallel to angles.
            completed : True iff arm reached MAX_ARM_DEG without abort.
        """
        label = "Through" if kind == "through" else "Reflect"
        voltages = []
        angles = []
        arm_angle = 0.0
        material_angle = MATERIAL_START_DEG
        max_arm_angle = MAX_ARM_DEG

        def _store(v_tx, v_rx):
            v = v_tx if kind == "through" else v_rx
            voltages.append([v.real, v.imag])
            angles.append(arm_angle)
            self.after(0, lambda a=arm_angle, vv=v: self._log_debug(
                f"  {label} {a:.0f}\u00b0: |V|={abs(vv):.6f}", "INFO"))

        # --- Angle 0: read with no motor commands (matches measurement). ---
        if not getattr(self, '_cal_running', False):
            return angles, voltages, False
        self.current_angle = arm_angle
        v_tx, v_rx = self._take_raw_voltage()
        _store(v_tx, v_rx)

        # --- Subsequent angles: material first, then arm, then settle, read. ---
        while getattr(self, '_cal_running', False) and arm_angle < max_arm_angle:
            arm_angle += ARM_STEP_DEG
            material_angle += MATERIAL_STEP_DEG
            self.current_angle = arm_angle

            # Material first so it is in position before the arm swings to
            # the new angle. Material-move failure is tolerated (no abort),
            # matching measurement's handling.
            if not self._move_motor_and_wait(2, material_angle, f"Cal-{label}-Material"):
                if self.motor_collision_detected:
                    self._cal_running = False
                    return angles, voltages, False

            if not self._move_motor_and_wait(1, arm_angle, f"Cal-{label}-Arm"):
                if self.motor_collision_detected:
                    self._cal_running = False
                    return angles, voltages, False
                self.after(0, lambda a=arm_angle: self._log_debug(
                    f"Cal {label.lower()}: arm fail at {a:.0f}\u00b0 — aborting", "ERROR"))
                self._cal_running = False
                return angles, voltages, False

            # Let SPI bus / PID pipeline settle after I2C motor traffic
            # before reading the ADC. Measurement sweep uses the same 0.15 s.
            time.sleep(0.15)
            v_tx, v_rx = self._take_raw_voltage()
            _store(v_tx, v_rx)

            if int(arm_angle) % 10 == 0:
                self.after(0, lambda a=arm_angle, lbl=label: self._log_debug(
                    f"[{lbl}] Progress: {a:.1f}\u00b0 / {max_arm_angle:.0f}\u00b0", "INFO"))

        completed = arm_angle >= max_arm_angle
        return angles, voltages, completed

    def _cal_through_worker(self):
        """Background: sweep Through calibration (no material)."""
        angles, voltages, completed = self._run_cal_sweep("through")

        if not completed or not getattr(self, '_cal_running', False):
            # Aborted mid-sweep — clean up and bail.
            self._stop_adc_stream_thread()
            self._cal_running = False
            self.after(0, lambda a=self.current_angle: self._log_debug(
                f"Through cal stopped at {a:.1f}\u00b0", "WARNING"))
            self.after(0, lambda: self._update_status("Calibration aborted", "warning"))
            self.after(0, lambda: self.status_var.set("Ready"))
            return

        # Store through reference.
        self.cal_through = {a: complex(v[0], v[1]) for a, v in zip(angles, voltages)}
        self._save_cal_sweep("through", angles, voltages)
        self.after(0, lambda: self._log_debug(
            f"Through cal done: {len(angles)} angles", "SUCCESS"))

        # Home before reflect sweep.
        self._send_home_command()
        self._wait_for_motor_position(timeout=15.0)

        # Prompt for reflect step (must happen on main thread).
        self.after(0, self._cal_prompt_reflect)

    def _cal_prompt_reflect(self):
        """Main-thread: prompt user then launch reflect sweep."""
        r = messagebox.askokcancel("Calibration - Step 2 (Reflect)",
            "Place a METAL SHEET in the fixture.\n"
            "This will sweep 0\u00b0\u201380\u00b0 and record reflect-reference voltages.\n\n"
            "Click OK to begin.")
        if not r:
            self._cal_running = False
            self.status_var.set("Ready")
            self._log_debug("Calibration cancelled after through step", "WARNING")
            return
        self._update_status("Reflect calibration sweep...", "warning")
        self._log_debug("Calibration: Reflect sweep started", "INFO")
        threading.Thread(target=self._cal_reflect_worker, daemon=True).start()

    def _cal_reflect_worker(self):
        """Background: sweep Reflect calibration (metal sheet)."""
        angles, voltages, completed = self._run_cal_sweep("reflect")

        if not completed or not getattr(self, '_cal_running', False):
            # Aborted mid-sweep — clean up and bail.
            self._stop_adc_stream_thread()
            self._cal_running = False
            self.after(0, lambda a=self.current_angle: self._log_debug(
                f"Reflect cal stopped at {a:.1f}\u00b0", "WARNING"))
            self.after(0, lambda: self._update_status("Calibration aborted", "warning"))
            self.after(0, lambda: self.status_var.set("Ready"))
            return

        # Store reflect reference.
        self.cal_reflect = {a: complex(v[0], v[1]) for a, v in zip(angles, voltages)}
        self._save_cal_sweep("reflect", angles, voltages)

        # Home after cal complete.
        self._send_home_command()
        self._wait_for_motor_position(timeout=15.0)

        # Teardown — mirrors measurement worker's end of run.
        self._stop_adc_stream_thread()
        self._cal_running = False
        self.after(0, lambda: self._log_debug(
            f"Reflect cal done: {len(angles)} angles", "SUCCESS"))
        self.after(0, lambda: self._update_status("Calibration complete", "success"))
        self.after(0, lambda: self.status_var.set("Ready"))
        self.after(0, lambda: messagebox.showinfo("Calibration Complete",
            f"Through + Reflect calibration stored.\n{len(angles)} angles each.\n\n"
            "NOTE: Geometry d and d_sheet are currently set to "
            f"{self.cal_d:.4f} m and {self.cal_d_sheet:.4f} m.\n"
            "Update in Settings \u2192 Connection Setup if needed."))

    def _save_cal_sweep(self, sweep_type, angles, voltages):
        """Persist a calibration sweep to the database."""
        try:
            rec = CalibrationSweep(
                sweep_type=sweep_type,
                angles_json=angles,
                voltages_json=voltages,
                geometry_json={"d": self.cal_d, "d_sheet": self.cal_d_sheet},
                f0_ghz=self.extraction_f0_ghz,
            )
            db = self._safe_db
            db.add(rec)
            db.commit()
            self._log_debug(f"Cal sweep '{sweep_type}' saved to DB", "INFO")
        except Exception as e:
            self._safe_db.rollback()
            self._log_debug(f"Cal sweep save failed: {e}", "ERROR")

    def _load_latest_calibration(self):
        """Load the most recent through + reflect sweeps from DB into memory."""
        try:
            db = self._safe_db
            through = (db.query(CalibrationSweep)
                       .filter(CalibrationSweep.sweep_type == "through")
                       .order_by(CalibrationSweep.timestamp.desc()).first())
            reflect = (db.query(CalibrationSweep)
                       .filter(CalibrationSweep.sweep_type == "reflect")
                       .order_by(CalibrationSweep.timestamp.desc()).first())
            if through and through.angles_json and through.voltages_json:
                self.cal_through = {
                    a: complex(v[0], v[1])
                    for a, v in zip(through.angles_json, through.voltages_json)
                }
                self._log_debug(f"Loaded through cal ({len(self.cal_through)} angles)", "INFO")
            if reflect and reflect.angles_json and reflect.voltages_json:
                self.cal_reflect = {
                    a: complex(v[0], v[1])
                    for a, v in zip(reflect.angles_json, reflect.voltages_json)
                }
                self._log_debug(f"Loaded reflect cal ({len(self.cal_reflect)} angles)", "INFO")
        except Exception as e:
            self._log_debug(f"Cal load from DB failed: {e}", "WARNING")

    def _update_button_states(self):
        if hasattr(self, 'start_container') and hasattr(self, 'stop_container') and hasattr(self, 'clear_container'):
            sidebar_bg = self._t('bg_sidebar')
            homing = getattr(self, '_homing', False)
            if self.is_measuring:
                self.start_container.pack_forget()
                self.stop_container.pack(fill=tk.X, padx=6, pady=3, before=self.clear_container)
                btn = self.stop_button
                real_bg = self._t('error')
            else:
                self.stop_container.pack_forget()
                self.start_container.pack(fill=tk.X, padx=6, pady=3, before=self.clear_container)
                btn = self.start_button
                real_bg = self._t('success') if not homing else self._t('warning')
            if btn:
                btn.config(bg=sidebar_bg, state=tk.NORMAL if not homing or self.is_measuring else tk.DISABLED)
                self.after(120, lambda b=btn, c=real_bg: b.config(bg=c))

    def _on_export(self):
        ms = self._get_measurements()
        if not ms:
            messagebox.showwarning("No Data", "Nothing to export.")
            return
        # Chronological order (oldest first)
        ms = list(reversed(ms))
        fp = filedialog.asksaveasfilename(defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")])
        if not fp:
            return
        try:
            # Latest extraction result
            extraction = None
            try:
                extraction = (self.db.query(ExtractionResult)
                              .order_by(ExtractionResult.timestamp.desc()).first())
            except Exception:
                pass

            if fp.endswith('.csv'):
                with open(fp, 'w', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['id', 'angle', 'polarization',
                                'transmitted_power_dB', 'reflected_power_dB',
                                'transmitted_phase_deg', 'reflected_phase_deg',
                                'permittivity', 'permeability', 'timestamp'])
                    for m in ms:
                        w.writerow([
                            m.id, m.angle,
                            getattr(m, 'polarization', 0.0) or 0.0,
                            m.transmitted_power, m.reflected_power,
                            m.transmitted_phase, m.reflected_phase,
                            m.permittivity, m.permeability,
                            m.timestamp.isoformat()
                        ])
                    if extraction:
                        w.writerow([])
                        w.writerow(['# Extraction Result'])
                        w.writerow(['fit_error', 'tensor_type', 'f0_ghz', 'd_mil'])
                        cfg = extraction.config_json or {}
                        w.writerow([extraction.fit_error, extraction.tensor_type,
                                    cfg.get('f0_ghz', ''), cfg.get('d_mil', '')])
            else:
                data = [{
                    "id": m.id,
                    "angle": m.angle,
                    "polarization": getattr(m, 'polarization', 0.0) or 0.0,
                    "transmitted_power_dB": m.transmitted_power,
                    "reflected_power_dB": m.reflected_power,
                    "transmitted_phase_deg": m.transmitted_phase,
                    "reflected_phase_deg": m.reflected_phase,
                    "permittivity": m.permittivity,
                    "permeability": m.permeability,
                    "timestamp": m.timestamp.isoformat()
                } for m in ms]
                export = {"measurements": data}
                if extraction:
                    export["extraction"] = {
                        "fit_error": extraction.fit_error,
                        "tensor_type": extraction.tensor_type,
                        "erv": extraction.erv_json,
                        "mrv": extraction.mrv_json,
                        "config": extraction.config_json,
                        "timestamp": extraction.timestamp.isoformat()
                    }
                with open(fp, 'w') as f:
                    json.dump(export, f, indent=2)
            self._update_status(f"Exported to {os.path.basename(fp)}", "success")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes('-fullscreen', self.is_fullscreen)

    def _exit_fullscreen(self):
        if self.is_fullscreen:
            self._toggle_fullscreen()

    def _on_help(self):
        messagebox.showinfo("About SPAM",
            "SPAM \u2014 Scanner for Polarized Anisotropic Materials\n"
            "Version 2.0 \u2014 Expo Build\n\n"
            "Dual-polarization (0\u00b0 + 90\u00b0) T-matrix material extraction at 24 GHz.\n\n"
            "Shortcuts: F11 Fullscreen, Ctrl+D Debug, Esc Exit fullscreen")

    def _on_debug_console(self):
        from .debug_console import DebugConsole
        if self.debug_window is None or not self.debug_window.winfo_exists():
            self.debug_window = DebugConsole(self)
        else:
            self.debug_window.lift()
            self.debug_window.focus()

    def _on_home(self):
        if not getattr(self, 'motor_control_enabled', False) and not True:
            return
        self._log_debug("Manual home requested", "INFO")
        threading.Thread(target=self._home_worker, daemon=True).start()

    def _home_worker(self):
        self._homing = True
        self.after(0, self._update_button_states)
        try:
            if self._send_home_command():
                self._wait_for_motor_position(timeout=15.0)
                self.after(0, lambda: self.motor_status_var.set("Ready"))
                self.after(0, lambda: self._log_debug("Homing complete", "SUCCESS"))
        finally:
            self._homing = False
            self.after(0, self._update_button_states)

    def _log_debug(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{level}] {message}"
        self.debug_log.append(line)
        if len(self.debug_log) > 1000:
            self.debug_log = self.debug_log[-1000:]
        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.update_console_log()
        try:
            log_path = Path.home() / "SPAM" / "spam_run.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(line + "\n")
        except Exception:
            pass
