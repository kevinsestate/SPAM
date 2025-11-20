"""
Database models for SPAM application
"""
from sqlalchemy import Column, Integer, Float, DateTime, String, JSON
from sqlalchemy.sql import func
from database import Base


class Measurement(Base):
    """Measurement data model"""
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    angle = Column(Float, nullable=False)
    permittivity = Column(Float, nullable=False)
    permeability = Column(Float, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Calibration(Base):
    """Calibration data model"""
    __tablename__ = "calibrations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    parameters = Column(JSON, nullable=True)
    status = Column(String, default="pending")

