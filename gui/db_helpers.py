"""DBMixin: background init, CRUD helpers."""

from datetime import datetime

from backend import SessionLocal, engine, Base, Measurement, Calibration


class DBMixin:
    """Provides database initialization and CRUD helper methods."""

    def _initialize_background(self):
        try:
            Base.metadata.create_all(bind=engine)
            self.db = SessionLocal()
            self._log_debug("Database connection established", "INFO")
        except Exception as e:
            self._log_debug(f"Database init error: {e}", "ERROR")
        # Load latest calibration data from DB into memory
        try:
            self._load_latest_calibration()
        except Exception as e:
            self._log_debug(f"Cal load skipped: {e}", "WARNING")
        self._update_display()

    def _get_measurements(self, limit=1000):
        try:
            return self.db.query(Measurement).order_by(Measurement.timestamp.desc()).limit(limit).all()
        except Exception as e:
            print(f"Error retrieving measurements: {e}")
            return []

    def _get_measurements_for_graph(self):
        """Fetch only the most recent measurements needed for graphing (capped at 100).
        A full dual-polarization sweep produces 34 points; 100 gives two full runs of headroom.
        Use this instead of _get_measurements() inside graph update paths to avoid fetching
        large result sets on every 500 ms redraw tick."""
        try:
            rows = (self.db.query(Measurement)
                    .order_by(Measurement.timestamp.desc())
                    .limit(100)
                    .all())
            return list(reversed(rows))
        except Exception as e:
            print(f"Error retrieving measurements for graph: {e}")
            return []

    def _create_measurement(self, angle, permittivity, permeability,
                            transmitted_power=None, reflected_power=None,
                            transmitted_phase=None, reflected_phase=None,
                            polarization=0.0):
        try:
            m = Measurement(angle=angle, permittivity=permittivity, permeability=permeability,
                            transmitted_power=transmitted_power, reflected_power=reflected_power,
                            transmitted_phase=transmitted_phase, reflected_phase=reflected_phase,
                            polarization=polarization,
                            timestamp=datetime.now())
            self.db.add(m)
            self.db.commit()
            self.db.refresh(m)
            self._last_graph_count = -1
            return m
        except Exception as e:
            self.db.rollback()
            print(f"Error creating measurement: {e}")
            return None

    def _create_calibration(self, parameters=None):
        try:
            c = Calibration(timestamp=datetime.now(), parameters=parameters or {}, status="completed")
            self.db.add(c)
            self.db.commit()
            self.db.refresh(c)
            return c
        except Exception as e:
            self.db.rollback()
            return None
