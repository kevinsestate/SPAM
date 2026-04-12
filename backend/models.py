"""
SQLAlchemy models for SPAM application.
"""
from sqlalchemy import Column, Integer, Float, DateTime, String, JSON
from sqlalchemy.sql import func
from .database import Base


class Measurement(Base):
    """Measurement model for storing angle sweep data."""
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    angle = Column(Float, nullable=False, index=True)
    permittivity = Column(Float, nullable=False)
    permeability = Column(Float, nullable=False)
    transmitted_power = Column(Float, nullable=True)
    reflected_power = Column(Float, nullable=True)
    transmitted_phase = Column(Float, nullable=True)
    reflected_phase = Column(Float, nullable=True)
    s_matrix_json = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    def __repr__(self):
        return f"<Measurement(id={self.id}, angle={self.angle}, e={self.permittivity:.4f}, u={self.permeability:.4f})>"


class Calibration(Base):
    """Calibration model for storing calibration records."""
    __tablename__ = "calibrations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    parameters = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="completed")

    def __repr__(self):
        return f"<Calibration(id={self.id}, status={self.status}, timestamp={self.timestamp})>"


class CalibrationSweep(Base):
    """Stores per-angle reference voltages from a calibration sweep."""
    __tablename__ = "calibration_sweeps"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    sweep_type = Column(String, nullable=False)  # "through" or "reflect"
    angles_json = Column(JSON, nullable=True)     # list of angle floats
    voltages_json = Column(JSON, nullable=True)   # list of [i, q] pairs per angle
    geometry_json = Column(JSON, nullable=True)    # {"d": ..., "d_sheet": ...} in metres
    f0_ghz = Column(Float, nullable=True)

    def __repr__(self):
        n = len(self.angles_json) if self.angles_json else 0
        return f"<CalibrationSweep(id={self.id}, type={self.sweep_type}, angles={n})>"


class ExtractionResult(Base):
    """Stores results from T-matrix material extraction."""
    __tablename__ = "extraction_results"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    erv_json = Column(JSON, nullable=True)
    mrv_json = Column(JSON, nullable=True)
    fit_error = Column(Float, nullable=True)
    tensor_type = Column(String, nullable=True)
    config_json = Column(JSON, nullable=True)

    def __repr__(self):
        return f"<ExtractionResult(id={self.id}, fit_error={self.fit_error}, type={self.tensor_type})>"
