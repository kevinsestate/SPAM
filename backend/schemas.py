"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class MeasurementBase(BaseModel):
    angle: float
    permittivity: float
    permeability: float


class MeasurementCreate(MeasurementBase):
    pass


class MeasurementResponse(MeasurementBase):
    id: int
    timestamp: str

    class Config:
        from_attributes = True


class CalibrationCreate(BaseModel):
    parameters: Optional[Dict[str, Any]] = None


class CalibrationResponse(BaseModel):
    id: int
    timestamp: str
    parameters: Optional[Dict[str, Any]] = None
    status: str

    class Config:
        from_attributes = True


class SystemStatus(BaseModel):
    angle: float
    permittivity: float
    permeability: float
    status: str


class StatusResponse(BaseModel):
    status: str
    message: str
    timestamp: str
    system_status: SystemStatus

