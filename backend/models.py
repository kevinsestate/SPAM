"""
SQLAlchemy models for SPAM application.
"""
from sqlalchemy import Column, Integer, Float, DateTime, String, JSON
from sqlalchemy.sql import func
from database import Base


class Measurement(Base):
    """Measurement model for storing angle sweep data."""
    __tablename__ = "measurements"
    
    id = Column(Integer, primary_key=True, index=True)
    angle = Column(Float, nullable=False, index=True)  # Angle in degrees
    permittivity = Column(Float, nullable=False)  # Permittivity (ε)
    permeability = Column(Float, nullable=False)  # Permeability (μ)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Measurement(id={self.id}, angle={self.angle}°, ε={self.permittivity:.4f}, μ={self.permeability:.4f})>"


class Calibration(Base):
    """Calibration model for storing calibration records."""
    __tablename__ = "calibrations"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    parameters = Column(JSON, nullable=True)  # Calibration parameters as JSON
    status = Column(String, nullable=False, default="completed")  # Calibration status
    
    def __repr__(self):
        return f"<Calibration(id={self.id}, status={self.status}, timestamp={self.timestamp})>"
