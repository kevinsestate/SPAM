"""
Calibration logic – two-step calibration process.
"""
from datetime import datetime


class CalibrationManager:
    """Manages the two-step calibration process."""

    def __init__(self, db, log=None):
        self.db = db
        self._log = log or (lambda msg, lvl="INFO": print(f"[{lvl}] {msg}"))

    def run_step1(self):
        """Step 1: empty fixture measurement (placeholder)."""
        self._log("Calibration Step 1: Empty measurement started", "INFO")
        # TODO: read S-parameters with no material
        self._log("Calibration Step 1: Empty measurement completed", "SUCCESS")

    def run_step2(self):
        """Step 2: material placement measurement (placeholder)."""
        self._log("Calibration Step 2: Material measurement started", "INFO")
        # TODO: read S-parameters with material
        self._log("Calibration Step 2: Material measurement completed", "SUCCESS")

    def save(self):
        """Save calibration record with both steps."""
        params = {
            "step1": "empty_measurement",
            "step2": "material_measurement",
            "timestamp_step1": datetime.now().isoformat(),
            "timestamp_step2": datetime.now().isoformat()
        }
        cal = self.db.create_calibration(parameters=params)
        if cal:
            self._log(f"Calibration completed (ID: {cal.id})", "SUCCESS")
        else:
            self._log("Calibration save failed", "ERROR")
        return cal
