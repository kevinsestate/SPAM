"""
FastAPI backend for SPAM - Scanner for Polarized Anisotropic Materials
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
from datetime import datetime
import json

from database import SessionLocal, engine, Base
from models import Measurement, Calibration
from schemas import (
    MeasurementCreate, MeasurementResponse,
    CalibrationCreate, CalibrationResponse,
    StatusResponse, SystemStatus
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SPAM API", version="1.0.0")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "SPAM API", "version": "1.0.0"}


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get current system status"""
    return StatusResponse(
        status="ready",
        message="System Ready",
        timestamp=datetime.now().isoformat(),
        system_status=SystemStatus(
            angle=0.0,
            permittivity=2.00,
            permeability=1.50,
            status="Ready"
        )
    )


@app.post("/api/calibrate", response_model=CalibrationResponse)
async def calibrate(calibration: CalibrationCreate, db: Session = Depends(get_db)):
    """Start calibration process"""
    try:
        # Create calibration record
        db_calibration = Calibration(
            timestamp=datetime.now(),
            parameters=calibration.parameters,
            status="completed"
        )
        db.add(db_calibration)
        db.commit()
        db.refresh(db_calibration)
        
        # Broadcast calibration completion
        await manager.broadcast({
            "type": "calibration",
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        })
        
        return CalibrationResponse(
            id=db_calibration.id,
            timestamp=db_calibration.timestamp.isoformat(),
            parameters=db_calibration.parameters,
            status=db_calibration.status
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/measurements/start")
async def start_measurement():
    """Start a new measurement session"""
    try:
        # Broadcast measurement start
        await manager.broadcast({
            "type": "measurement",
            "action": "started",
            "timestamp": datetime.now().isoformat()
        })
        
        return {"message": "Measurement started", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/measurements", response_model=MeasurementResponse)
async def create_measurement(measurement: MeasurementCreate, db: Session = Depends(get_db)):
    """Create a new measurement record"""
    try:
        db_measurement = Measurement(
            angle=measurement.angle,
            permittivity=measurement.permittivity,
            permeability=measurement.permeability,
            timestamp=datetime.now()
        )
        db.add(db_measurement)
        db.commit()
        db.refresh(db_measurement)
        
        # Broadcast new measurement
        await manager.broadcast({
            "type": "measurement",
            "data": {
                "angle": db_measurement.angle,
                "permittivity": db_measurement.permittivity,
                "permeability": db_measurement.permeability,
                "timestamp": db_measurement.timestamp.isoformat()
            }
        })
        
        return MeasurementResponse(
            id=db_measurement.id,
            angle=db_measurement.angle,
            permittivity=db_measurement.permittivity,
            permeability=db_measurement.permeability,
            timestamp=db_measurement.timestamp.isoformat()
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/measurements", response_model=List[MeasurementResponse])
async def get_measurements(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all measurements with pagination"""
    measurements = db.query(Measurement).offset(skip).limit(limit).all()
    return [
        MeasurementResponse(
            id=m.id,
            angle=m.angle,
            permittivity=m.permittivity,
            permeability=m.permeability,
            timestamp=m.timestamp.isoformat()
        )
        for m in measurements
    ]


@app.get("/api/measurements/{measurement_id}", response_model=MeasurementResponse)
async def get_measurement(measurement_id: int, db: Session = Depends(get_db)):
    """Get a specific measurement by ID"""
    measurement = db.query(Measurement).filter(Measurement.id == measurement_id).first()
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")
    
    return MeasurementResponse(
        id=measurement.id,
        angle=measurement.angle,
        permittivity=measurement.permittivity,
        permeability=measurement.permeability,
        timestamp=measurement.timestamp.isoformat()
    )


@app.delete("/api/measurements/{measurement_id}")
async def delete_measurement(measurement_id: int, db: Session = Depends(get_db)):
    """Delete a measurement"""
    measurement = db.query(Measurement).filter(Measurement.id == measurement_id).first()
    if not measurement:
        raise HTTPException(status_code=404, detail="Measurement not found")
    
    db.delete(measurement)
    db.commit()
    return {"message": "Measurement deleted"}


@app.get("/api/export")
async def export_data(format: str = "json", db: Session = Depends(get_db)):
    """Export all measurements in specified format"""
    measurements = db.query(Measurement).all()
    
    if format == "json":
        data = [
            {
                "id": m.id,
                "angle": m.angle,
                "permittivity": m.permittivity,
                "permeability": m.permeability,
                "timestamp": m.timestamp.isoformat()
            }
            for m in measurements
        ]
        return JSONResponse(content=data)
    elif format == "csv":
        csv_lines = ["angle,permittivity,permeability,timestamp"]
        for m in measurements:
            csv_lines.append(f"{m.angle},{m.permittivity},{m.permeability},{m.timestamp.isoformat()}")
        return {"content": "\n".join(csv_lines), "format": "csv"}
    else:
        raise HTTPException(status_code=400, detail="Unsupported format")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            # Echo back or process message
            await websocket.send_json({"type": "ack", "message": "Received"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

