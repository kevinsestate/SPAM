"""DBMixin: background init, CRUD helpers."""

import threading
from datetime import datetime

from backend import SessionLocal, engine, Base, Measurement, Calibration

_thread_local = threading.local()


class DBMixin:
    """Provides database initialization and CRUD helper methods."""

    @property
    def _safe_db(self):
        """Return a per-thread SQLAlchemy session, creating one if needed."""
        sess = getattr(_thread_local, 'session', None)
        if sess is None:
            sess = SessionLocal()
            _thread_local.session = sess
        return sess

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
            return self._safe_db.query(Measurement).order_by(Measurement.timestamp.desc()).limit(limit).all()
        except Exception as e:
            print(f"Error retrieving measurements: {e}")
            return []

    def _get_measurements_for_graph(self):
        """Fetch only the most recent measurements needed for graphing (capped at 100).
        A full dual-polarization sweep produces 34 points; 100 gives two full runs of headroom.
        Use this instead of _get_measurements() inside graph update paths to avoid fetching
        large result sets on every 500 ms redraw tick."""
        try:
            rows = (self._safe_db.query(Measurement)
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
            db = self._safe_db
            db.add(m)
            db.commit()
            db.refresh(m)
            self._last_graph_count = -1
            return m
        except Exception as e:
            self._safe_db.rollback()
            print(f"Error creating measurement: {e}")
            return None

    def _create_calibration(self, parameters=None):
        try:
            c = Calibration(timestamp=datetime.now(), parameters=parameters or {}, status="completed")
            db = self._safe_db
            db.add(c)
            db.commit()
            db.refresh(c)
            return c
        except Exception as e:
            self._safe_db.rollback()
            return None
