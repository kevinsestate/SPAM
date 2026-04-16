"""ExtractionMixin: _run_extraction, worker, save."""

import threading
import numpy as np

from core.spam_calc import compute_k0d, mil_to_m
from core.spam_optimizer import extract_material_progressive
from backend import ExtractionResult


class ExtractionMixin:
    """Provides material extraction trigger, background worker, and DB save."""

    def _run_extraction(self):
        if self.extraction_running:
            return
        measurements = self._get_measurements()
        if len(measurements) < 3:
            self._log_debug("Not enough data for extraction", "WARNING")
            return
        self.extraction_running = True
        self.extraction_status_var.set("Running...")
        self._log_debug("Starting extraction...", "INFO")
        self.extraction_thread = threading.Thread(target=self._extraction_worker,
                                                  args=(measurements,), daemon=True)
        self.extraction_thread.start()

    def _extraction_worker(self, measurements):
        import warnings as _w
        try:
            # --- Group by angle, pair pol-0 and pol-90 to build full 4x4 S-matrix ---
            pol0 = {}   # angle -> measurement
            pol90 = {}  # angle -> measurement
            for m in measurements:
                pol = getattr(m, 'polarization', None) or 0.0
                # Round angle to nearest 0.5 deg for grouping
                key = round(m.angle * 2) / 2.0
                if pol >= 45.0:
                    if key not in pol90:
                        pol90[key] = m
                else:
                    if key not in pol0:
                        pol0[key] = m

            # Use angles that have at least pol-0 data
            angle_keys = sorted(pol0.keys())
            if not angle_keys:
                angle_keys = sorted({round(m.angle * 2) / 2.0 for m in measurements})

            angles = np.array(angle_keys)
            n = len(angles)
            s_matrices = np.zeros((n, 4, 4), dtype=complex)

            for i, key in enumerate(angle_keys):
                m0 = pol0.get(key)
                m90 = pol90.get(key)

                def _s_complex(m, use_s21=True):
                    if m is None:
                        return complex(0.0)
                    if use_s21:
                        tp = m.transmitted_power if m.transmitted_power else -60.0
                        tph = m.transmitted_phase if m.transmitted_phase else 0.0
                        return 10 ** (tp / 20.0) * np.exp(1j * np.deg2rad(tph))
                    else:
                        rp = m.reflected_power if m.reflected_power else -60.0
                        rph = m.reflected_phase if m.reflected_phase else 0.0
                        return 10 ** (rp / 20.0) * np.exp(1j * np.deg2rad(rph))

                s21_hh = _s_complex(m0,  use_s21=True)
                s11_hh = _s_complex(m0,  use_s21=False)
                s21_vv = _s_complex(m90, use_s21=True)  if m90 else s21_hh
                s11_vv = _s_complex(m90, use_s21=False) if m90 else s11_hh

                # 4x4 SPAM S-matrix: [hh, vv] x [hh, vv] blocks
                # S = [[S11_hh, 0,      0,      0     ],
                #      [0,      S11_vv, 0,      0     ],
                #      [0,      0,      S21_hh, 0     ],
                #      [0,      0,      0,      S21_vv]]
                s_matrices[i] = np.array([
                    [s11_hh, 0,      0,      0     ],
                    [0,      s11_vv, 0,      0     ],
                    [0,      0,      s21_hh, 0     ],
                    [0,      0,      0,      s21_vv],
                ], dtype=complex)

            pol_pairs = sum(1 for k in angle_keys if k in pol0 and k in pol90)
            self.after(0, lambda: self._log_debug(
                f"Extraction: {n} angles, {len(pol0)} pol-0° pts, "
                f"{len(pol90)} pol-90° pts, {pol_pairs} paired", "INFO"))
            f_hz = self.extraction_f0_ghz * 1e9
            d_m = mil_to_m(self.extraction_d_mil)
            k0d = compute_k0d(f_hz, d_m)
            self.after(0, lambda: self._log_debug(
                f"Extraction: f0={self.extraction_f0_ghz}GHz d={self.extraction_d_mil}mil "
                f"k0d={k0d:.4f} type={self.extraction_tensor_type} {n} angles", "INFO"))
            def stage_update(stage, res):
                self.after(0, lambda s=stage, e=res['fit_error']:
                    self._log_debug(f"  [{s}] error={e:.6f}", "INFO"))
            with _w.catch_warnings():
                _w.simplefilter("ignore")
                result = extract_material_progressive(s_matrices, angles, k0d,
                    target_type=self.extraction_tensor_type, max_iter_per_stage=2000,
                    callback=stage_update)
            erv, mrv, fit_err = result["erv"], result["mrv"], result["fit_error"]

            if not np.isfinite(fit_err) or fit_err > 1.0:
                self.after(0, lambda: self.extraction_status_var.set("No Converge"))
                self.after(0, lambda: self.extraction_error_var.set("--"))
                self.after(0, lambda: self.extraction_eps_var.set("--"))
                self.after(0, lambda: self.extraction_mu_var.set("--"))
                self.after(0, lambda: self._log_debug(
                    "Extraction did not converge -- simulated/placeholder data is not "
                    "valid S-parameter data. Will work with real hardware measurements.", "WARNING"))
            else:
                eps_d = f"[{erv[0].real:.2f}, {erv[3].real:.2f}, {erv[5].real:.2f}]"
                mu_d = f"[{mrv[0].real:.2f}, {mrv[3].real:.2f}, {mrv[5].real:.2f}]"
                self.after(0, lambda: self.extraction_status_var.set("Done"))
                self.after(0, lambda: self.extraction_error_var.set(f"{fit_err:.6f}"))
                self.after(0, lambda e=eps_d: self.extraction_eps_var.set(e))
                self.after(0, lambda m=mu_d: self.extraction_mu_var.set(m))
                self.after(0, lambda: self._log_debug(f"Extraction done: error={fit_err:.6f}", "SUCCESS"))
                self._save_extraction_result(result)
        except Exception as exc:
            import traceback
            err_msg = str(exc)
            tb_msg = traceback.format_exc()
            self.after(0, lambda: self.extraction_status_var.set("Error"))
            self.after(0, lambda m=err_msg: self._log_debug(f"Extraction failed: {m}", "ERROR"))
            self.after(0, lambda m=tb_msg: self._log_debug(f"Traceback:\n{m}", "ERROR"))
        finally:
            self.extraction_running = False

    def _save_extraction_result(self, result):
        try:
            erv_json = [[complex(v).real, complex(v).imag] for v in result["erv"]]
            mrv_json = [[complex(v).real, complex(v).imag] for v in result["mrv"]]
            rec = ExtractionResult(erv_json=erv_json, mrv_json=mrv_json,
                                   fit_error=float(result["fit_error"]),
                                   tensor_type=self.extraction_tensor_type,
                                   config_json={"f0_ghz": self.extraction_f0_ghz,
                                                "d_mil": self.extraction_d_mil,
                                                "k0d": compute_k0d(
                                                    self.extraction_f0_ghz * 1e9,
                                                    mil_to_m(self.extraction_d_mil)
                                                )})
            db = self._safe_db
            db.add(rec)
            db.commit()
        except Exception as exc:
            self._safe_db.rollback()
            self._log_debug(f"Save extraction failed: {exc}", "ERROR")
