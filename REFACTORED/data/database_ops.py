"""
Database operations for SPAM application.
Wraps SQLAlchemy session for measurement & calibration CRUD.
"""
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Engine / session setup
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_FILE = os.path.join(BASE_DIR, "spam.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------------------------
# Models (kept here so the refactored app is self-contained)
# ---------------------------------------------------------------------------
from sqlalchemy import Column, Integer, Float, DateTime, String, JSON
from sqlalchemy.sql import func


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    angle = Column(Float, nullable=False, index=True)
    permittivity = Column(Float, nullable=False)
    permeability = Column(Float, nullable=False)
    transmitted_power = Column(Float, nullable=True)
    reflected_power = Column(Float, nullable=True)
    transmitted_phase = Column(Float, nullable=True)
    reflected_phase = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return (f"<Measurement(id={self.id}, angle={self.angle}°, "
                f"ε={self.permittivity:.4f}, μ={self.permeability:.4f})>")


class Calibration(Base):
    __tablename__ = "calibrations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    parameters = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="completed")

    def __repr__(self):
        return f"<Calibration(id={self.id}, status={self.status})>"


# ---------------------------------------------------------------------------
# Manager class
# ---------------------------------------------------------------------------
class DatabaseManager:
    """High-level wrapper around SQLAlchemy session for SPAM data."""

    def __init__(self, log=None):
        self._log = log or (lambda msg, lvl="INFO": print(f"[{lvl}] {msg}"))
        Base.metadata.create_all(bind=engine)
        self.session = SessionLocal()
        self._log(f"Database connected: {engine.url}", "INFO")

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------
    def get_measurements(self, limit: int = 1000):
        try:
            return (self.session.query(Measurement)
                    .order_by(Measurement.timestamp.desc())
                    .limit(limit).all())
        except Exception as e:
            self._log(f"Error retrieving measurements: {e}", "ERROR")
            return []

    def create_measurement(self, angle, permittivity, permeability,
                           transmitted_power=None, reflected_power=None,
                           transmitted_phase=None, reflected_phase=None):
        try:
            m = Measurement(
                angle=angle,
                permittivity=permittivity,
                permeability=permeability,
                transmitted_power=transmitted_power,
                reflected_power=reflected_power,
                transmitted_phase=transmitted_phase,
                reflected_phase=reflected_phase,
                timestamp=datetime.now()
            )
            self.session.add(m)
            self.session.commit()
            self.session.refresh(m)
            self._log(f"Measurement recorded: {angle:.2f}°, ε={permittivity:.4f}, μ={permeability:.4f}", "DEBUG")
            return m
        except Exception as e:
            self.session.rollback()
            self._log(f"Error creating measurement: {e}", "ERROR")
            return None

    def clear_measurements(self):
        count = self.session.query(Measurement).count()
        self.session.query(Measurement).delete()
        self.session.commit()
        return count

    # ------------------------------------------------------------------
    # Calibrations
    # ------------------------------------------------------------------
    def create_calibration(self, parameters=None):
        try:
            c = Calibration(
                timestamp=datetime.now(),
                parameters=parameters or {},
                status="completed"
            )
            self.session.add(c)
            self.session.commit()
            self.session.refresh(c)
            return c
        except Exception as e:
            self.session.rollback()
            self._log(f"Error creating calibration: {e}", "ERROR")
            return None

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def close(self):
        self.session.close()
