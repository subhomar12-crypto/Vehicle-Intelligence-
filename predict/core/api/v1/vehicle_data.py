"""
Vehicle data endpoints for OBD and telemetry.

Handles:
- OBD data upload from mobile app
- Telemetry data (GPS, accelerometer)
- Historical data retrieval
- Live data streaming (WebSocket)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user, require_permission
from predict.core.db.models.vehicle import VehicleProfile, VehicleData, OBDRecord, TelemetryRecord
from predict.core.middleware.error_handler import APIError, ErrorCode
from predict.core.middleware.validation import validate_obd_payload

logger = logging.getLogger(__name__)

router = APIRouter()
legacy_router = APIRouter()


# ========================
# Request/Response Models
# ========================

class OBDUploadRequest(BaseModel):
    profile_id: Optional[int] = None
    vin: Optional[str] = None
    session_id: str
    timestamp: Optional[str] = None
    data: Dict[str, Any] = Field(..., description="OBD readings keyed by PID")


class TelemetryUploadRequest(BaseModel):
    profile_id: Optional[int] = None
    vin: Optional[str] = None
    session_id: str
    timestamp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    gps_speed: Optional[float] = None
    heading: Optional[int] = None
    acceleration_x: Optional[float] = None
    acceleration_y: Optional[float] = None
    acceleration_z: Optional[float] = None


class VehicleDataResponse(BaseModel):
    id: int
    timestamp: str
    rpm: Optional[int]
    speed: Optional[int]
    coolant_temp: Optional[int]
    battery_voltage: Optional[float]
    fuel_level: Optional[float]
    engine_load: Optional[float]
    maf: Optional[float]
    intake_temp: Optional[int]
    throttle_pos: Optional[float]


# ========================
# OBD Data Upload
# ========================

@router.post("/upload")
async def upload_obd_data(
    request: OBDUploadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload OBD data from mobile app.
    
    Either profile_id or vin must be provided to identify the vehicle.
    """
    # Validate payload
    is_valid, errors = validate_obd_payload(request.model_dump())
    if not is_valid:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid OBD data",
            details={"errors": errors},
        )
    
    # Get or create vehicle profile
    profile = await _get_or_create_profile(
        db, current_user['user_id'], request.profile_id, request.vin
    )
    
    # Parse timestamp
    ts = request.timestamp or datetime.now(timezone.utc).isoformat()
    
    # Extract standard OBD values
    data = request.data
    vehicle_data = VehicleData(
        profile_id=profile.id,
        timestamp=datetime.fromisoformat(ts.replace('Z', '+00:00')),
        rpm=_safe_int(data.get('RPM')),
        speed=_safe_int(data.get('SPEED')),
        coolant_temp=_safe_int(data.get('ENGINE_COOLANT_TEMP')),
        battery_voltage=_safe_float(data.get('BATTERY_VOLTAGE')),
        fuel_level=_safe_float(data.get('FUEL_LEVEL')),
        engine_load=_safe_float(data.get('ENGINE_LOAD')),
        maf=_safe_float(data.get('MAF')),
        intake_temp=_safe_int(data.get('INTAKE_AIR_TEMP')),
        throttle_pos=_safe_float(data.get('THROTTLE_POS')),
        raw_data=data,
    )
    
    db.add(vehicle_data)
    
    # Also store individual OBD records for detailed analysis
    for pid, value in data.items():
        if isinstance(value, (int, float)):
            record = OBDRecord(
                profile_id=profile.id,
                session_id=request.session_id,
                timestamp=vehicle_data.timestamp,
                pid=pid.upper(),
                value=_safe_float(value),
                is_calculated=False,
            )
            db.add(record)
    
    await db.commit()
    
    logger.debug(f"OBD data uploaded for profile {profile.id}")
    
    return {
        "success": True,
        "profile_id": profile.id,
        "records_stored": len(data),
    }


@legacy_router.post("/obd/upload")
async def upload_obd_data_legacy(
    request: OBDUploadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy OBD upload endpoint for Android compatibility."""
    return await upload_obd_data(request, current_user, db)


# ========================
# Telemetry Upload
# ========================

@router.post("/telemetry")
async def upload_telemetry(
    request: TelemetryUploadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload GPS and accelerometer telemetry data."""
    profile = await _get_or_create_profile(
        db, current_user['user_id'], request.profile_id, request.vin
    )
    
    ts = request.timestamp or datetime.now(timezone.utc).isoformat()
    
    telemetry = TelemetryRecord(
        profile_id=profile.id,
        session_id=request.session_id,
        timestamp=datetime.fromisoformat(ts.replace('Z', '+00:00')),
        latitude=request.latitude,
        longitude=request.longitude,
        altitude=request.altitude,
        gps_speed=request.gps_speed,
        heading=request.heading,
        acceleration_x=request.acceleration_x,
        acceleration_y=request.acceleration_y,
        acceleration_z=request.acceleration_z,
    )
    
    db.add(telemetry)
    await db.commit()
    
    return {"success": True, "profile_id": profile.id}


# ========================
# Data Retrieval
# ========================

@router.get("/data/{profile_id}", response_model=List[VehicleDataResponse])
async def get_vehicle_data(
    profile_id: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get historical OBD data for a vehicle profile."""
    # Verify ownership
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == profile_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    if not result.scalar_one_or_none():
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    # Build query
    query = select(VehicleData).where(
        VehicleData.profile_id == profile_id
    ).order_by(desc(VehicleData.timestamp))
    
    # Add time filters
    if start_time:
        query = query.where(VehicleData.timestamp >= start_time)
    if end_time:
        query = query.where(VehicleData.timestamp <= end_time)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    records = result.scalars().all()
    
    return [
        VehicleDataResponse(
            id=r.id,
            timestamp=r.timestamp.isoformat() if r.timestamp else None,
            rpm=r.rpm,
            speed=r.speed,
            coolant_temp=r.coolant_temp,
            battery_voltage=float(r.battery_voltage) if r.battery_voltage else None,
            fuel_level=float(r.fuel_level) if r.fuel_level else None,
            engine_load=float(r.engine_load) if r.engine_load else None,
            maf=float(r.maf) if r.maf else None,
            intake_temp=r.intake_temp,
            throttle_pos=float(r.throttle_pos) if r.throttle_pos else None,
        )
        for r in records
    ]


@router.get("/latest/{profile_id}")
async def get_latest_data(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent OBD data for a vehicle."""
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == profile_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    if not result.scalar_one_or_none():
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    result = await db.execute(
        select(VehicleData).where(
            VehicleData.profile_id == profile_id
        ).order_by(desc(VehicleData.timestamp)).limit(1)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        return {"data": None}
    
    return {
        "data": VehicleDataResponse(
            id=record.id,
            timestamp=record.timestamp.isoformat() if record.timestamp else None,
            rpm=record.rpm,
            speed=record.speed,
            coolant_temp=record.coolant_temp,
            battery_voltage=float(record.battery_voltage) if record.battery_voltage else None,
            fuel_level=float(record.fuel_level) if record.fuel_level else None,
            engine_load=float(record.engine_load) if record.engine_load else None,
            maf=float(record.maf) if record.maf else None,
            intake_temp=record.intake_temp,
            throttle_pos=float(record.throttle_pos) if record.throttle_pos else None,
        )
    }


# ========================
# Helpers
# ========================

async def _get_or_create_profile(
    db: AsyncSession,
    user_id: int,
    profile_id: Optional[int],
    vin: Optional[str],
) -> VehicleProfile:
    """Get existing profile or create new one."""
    if profile_id:
        result = await db.execute(
            select(VehicleProfile).where(
                VehicleProfile.id == profile_id,
                VehicleProfile.user_id == user_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile
    
    if vin:
        # Try to find by VIN
        result = await db.execute(
            select(VehicleProfile).where(
                VehicleProfile.vin == vin.upper().strip(),
                VehicleProfile.user_id == user_id,
            )
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile
        
        # Create new profile with VIN
        profile = VehicleProfile(
            user_id=user_id,
            vin=vin.upper().strip(),
        )
        db.add(profile)
        await db.flush()
        return profile
    
    # Auto-create profile if none specified
    profile = VehicleProfile(user_id=user_id)
    db.add(profile)
    await db.flush()
    return profile


def _safe_int(value) -> Optional[int]:
    """Safely convert value to int."""
    try:
        return int(float(value)) if value is not None else None
    except (ValueError, TypeError):
        return None


def _safe_float(value) -> Optional[float]:
    """Safely convert value to float."""
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


# Telemetry router for separate prefix
telemetry_router = APIRouter()

@telemetry_router.post("/upload")
async def upload_telemetry_telemetry(
    request: TelemetryUploadRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Telemetry upload at /api/telemetry/upload."""
    return await upload_telemetry(request, current_user, db)
