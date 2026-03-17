"""
Vehicle data API routes - ported from legacy OBD server.

Endpoints:
- POST /api/obd - Receive OBD data from Android
- GET /api/vehicle/{vehicle_id}/data - Get recent vehicle data
- GET /api/vehicle/{vehicle_id}/data/latest - Get latest reading
- GET /api/vehicle/{vehicle_id}/data/history - Get historical data
- POST /api/v1/telemetry - Receive telemetry snapshot
- GET /api/vehicle/{vehicle_id}/stats - Get vehicle statistics
- GET /api/vehicle/{vehicle_id}/sensors - Get available sensor list

Legacy endpoints for Android compatibility:
- POST /api/vehicle_data - Main data ingestion
- GET /api/vehicle_data/latest/{profile_id}
- GET /api/vehicle_data/history/{profile_id}
- GET /api/vehicle_data/stats/{profile_id}
"""

import logging
import time
import json
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user, get_optional_user
from predict.core.db.models.vehicle import VehicleData, VehicleProfile, OBDRecord, TelemetryRecord
from predict.core.db.repositories.vehicle_repo import VehicleDataRepository, VehicleProfileRepository
from predict.core.middleware.validation import OBD_RANGES, validate_vin
from predict.core.middleware.error_handler import APIError, ErrorCode
from predict.core.services.obd_processor import OBDProcessor, OBDDataPoint, DataQuality
from predict.core.services.prediction_service import PredictionService
from predict.core.services.websocket_service import ws_manager
from predict.core.ai.vehicle_learner import VehicleLearner
from predict.core.db.session import get_db_session

logger = logging.getLogger(__name__)

# =============================================================================
# Routers
# =============================================================================

router = APIRouter(prefix="/vehicle", tags=["Vehicle Data"])
telemetry_router = APIRouter(tags=["Telemetry"])
legacy_router = APIRouter(tags=["Legacy Vehicle Data"])

# Global OBD processor instance
obd_processor = OBDProcessor()

# In-memory live data cache (same as old server)
live_data_cache: Dict[int, Dict[str, Any]] = {}
online_profiles: Dict[int, float] = {}
ONLINE_TIMEOUT = 30  # seconds


# =============================================================================
# Request/Response Models (from old server)
# =============================================================================

class OBDPacket(BaseModel):
    """Single OBD packet from Android app."""
    device_id: str = Field(..., min_length=8, max_length=64)
    timestamp: float = Field(..., gt=0)
    data: Dict[str, Any] = Field(..., description="OBD data: pid, name, value, unit")
    
    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8 or len(v) > 64:
            raise ValueError("Device ID must be 8-64 characters")
        # Allow alphanumeric, dashes, underscores
        if not all(c.isalnum() or c in '-_' for c in v):
            raise ValueError("Device ID must be alphanumeric with optional - or _")
        return v
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: float) -> float:
        now = time.time()
        one_year_ago = now - (365 * 24 * 60 * 60)
        one_hour_future = now + (60 * 60)
        if v < one_year_ago:
            raise ValueError("Timestamp too old: must be within the past year")
        if v > one_hour_future:
            raise ValueError("Timestamp too far in future: max 1 hour ahead")
        return v
    
    @field_validator('data')
    @classmethod
    def validate_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Data cannot be empty")
        # Limit data size to prevent abuse
        if len(json.dumps(v)) > 10000:
            raise ValueError("Data payload too large (max 10KB)")
        return v


class TelemetryPacket(BaseModel):
    """Telemetry snapshot from Android app."""
    device_id: str = Field(..., min_length=8, max_length=64)
    timestamp: float = Field(..., gt=0)
    vin: Optional[str] = Field(None, max_length=17)
    mileage_km: Optional[float] = Field(None, ge=0, le=2000000)
    fuel_level: Optional[float] = Field(None, ge=0, le=100)
    predictions: Optional[Dict[str, Any]] = None
    sensors: Optional[Dict[str, Any]] = None
    
    @field_validator('device_id')
    @classmethod
    def validate_device_id(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8 or len(v) > 64:
            raise ValueError("Device ID must be 8-64 characters")
        return v
    
    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        is_valid, error = validate_vin(v)
        if not is_valid:
            raise ValueError(error)
        return v.upper()


class VehicleDataPayload(BaseModel):
    """Complete vehicle data payload from Android app (main endpoint)."""
    profile_id: Optional[int] = None
    vehicle_id: Optional[str] = None
    timestamp: Optional[float] = None
    
    # OBD Data
    rpm: Optional[float] = None
    speed: Optional[float] = None
    coolant_temp: Optional[float] = None
    battery_voltage: Optional[float] = None
    engine_load: Optional[float] = None
    throttle_pos: Optional[float] = None
    fuel_level: Optional[float] = None
    fuel_pressure: Optional[float] = None
    intake_temp: Optional[float] = None
    maf_rate: Optional[float] = None
    oil_temp: Optional[float] = None
    short_term_fuel_trim: Optional[float] = None
    long_term_fuel_trim: Optional[float] = None
    timing_advance: Optional[float] = None

    # GPS Data
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Vibration
    vibration_rms: Optional[float] = None
    vibration_peak: Optional[float] = None

    # Odometer (km, from Android OdometerTracker)
    odometer: Optional[float] = None

    # Extended PIDs — optional, ECU-dependent
    ambient_temp: Optional[float] = None
    boost_pressure: Optional[float] = None
    fuel_rate: Optional[float] = None
    torque: Optional[float] = None
    obd_odometer: Optional[float] = None

    # Mode 06 ECU test results (JSON-serialized list)
    mode06_results: Optional[str] = None

    # Metadata
    source: Optional[str] = "android"
    obd: Optional[Dict[str, Any]] = None


class BulkUploadRequest(BaseModel):
    """Bulk upload request for multiple readings."""
    readings: List[VehicleDataPayload]


# =============================================================================
# Batch V2 Models (generic sensor payload — future-proof)
# =============================================================================

class GenericSensorReading(BaseModel):
    """Single sensor reading with arbitrary sensor keys."""
    timestamp: float = Field(..., gt=0)
    sensors: Dict[str, float]

class GenericBatchUploadRequest(BaseModel):
    """Generic batch upload: trip-based, sensor-agnostic."""
    batch_id: str = Field(..., min_length=1, max_length=128)
    profile_id: int = Field(..., gt=0)
    trip_id: Optional[str] = None
    readings: List[GenericSensorReading] = Field(..., max_length=1000)
    source: str = "android"
    app_version: Optional[str] = None

class HeartbeatRequest(BaseModel):
    """Lightweight heartbeat — keeps Guardian live, no DB write."""
    profile_id: int = Field(..., gt=0)
    rpm: Optional[float] = None
    speed: Optional[float] = None
    coolant_temp: Optional[float] = None
    battery_voltage: Optional[float] = None
    engine_load: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# Map generic sensor names → VehicleData column names
SENSOR_FIELD_MAP = {
    "rpm": "rpm",
    "speed": "speed",
    "coolant_temp": "coolant_temp",
    "battery_voltage": "battery_voltage",
    "engine_load": "engine_load",
    "throttle_pos": "throttle_pos",
    "throttle_position": "throttle_pos",  # alias: OBDReading uses this name
    "fuel_level": "fuel_level",
    "fuel_pressure": "fuel_pressure",
    "intake_temp": "intake_temp",
    "maf_rate": "maf_rate",
    "oil_temp": "oil_temp",
    "short_term_fuel_trim": "short_term_fuel_trim",
    "long_term_fuel_trim": "long_term_fuel_trim",
    "timing_advance": "timing_advance",
    "ambient_temp": "ambient_temp",
    "boost_pressure": "boost_pressure",
    "fuel_rate": "fuel_rate",
    "torque": "torque",
    "obd_odometer": "obd_odometer",
    "odometer": "odometer",
    "latitude": "latitude",
    "longitude": "longitude",
    "vibration_rms": "vibration_rms",
    "vibration_peak": "vibration_peak",
    # Extended PIDs for AI training
    "intake_manifold_pressure": "intake_manifold_pressure",
    "baro_pressure": "baro_pressure",
    "o2_sensor_b1s1": "o2_sensor_b1s1",
    "o2_sensor_b1s2": "o2_sensor_b1s2",
    "catalyst_temp_b1s1": "catalyst_temp_b1s1",
    "catalyst_temp_b1s2": "catalyst_temp_b1s2",
    "oil_pressure": "oil_pressure",
    # DTC event counts (AI timeline correlation)
    "dtc_active_count": "dtc_active_count",
    "dtc_pending_count": "dtc_pending_count",
    # Mode 06 summary counts
    "mode06_total": "mode06_total",
    "mode06_passed": "mode06_passed",
    "mode06_failed": "mode06_failed",
    # Consult-II extended sensors (Pi5 edge unit)
    "injector_ms": "injector_ms",
    "fuel_trim_b2": "fuel_trim_b2",
    "accel_pedal": "accel_pedal",
}


class DataRangeResponse(BaseModel):
    """Response for data range query."""
    vehicle_id: int
    records: List[Dict[str, Any]]
    count: int
    timestamp: str
    timestamp_unix: float


# =============================================================================
# Helper Functions
# =============================================================================

def format_record_response(record: VehicleData) -> Dict[str, Any]:
    """Format a VehicleData record for API response."""
    return {
        "id": record.id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.timestamp)) if record.timestamp else None,
        "timestamp_unix": record.timestamp,
        "rpm": record.rpm,
        "speed": record.speed,
        "coolant_temp": record.coolant_temp,
        "battery_voltage": record.battery_voltage,
        "engine_load": record.engine_load,
        "throttle_pos": record.throttle_pos,
        "fuel_level": record.fuel_level,
        "fuel_pressure": record.fuel_pressure,
        "maf_rate": record.maf_rate,
        "intake_temp": record.intake_temp,
        "oil_temp": record.oil_temp,
        "short_term_fuel_trim": record.short_term_fuel_trim,
        "long_term_fuel_trim": record.long_term_fuel_trim,
        "timing_advance": record.timing_advance,
        "ambient_temp": record.ambient_temp,
        "boost_pressure": record.boost_pressure,
        "fuel_rate": record.fuel_rate,
        "torque": record.torque,
        "obd_odometer": record.obd_odometer,
        "odometer": record.odometer,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "vibration_rms": record.vibration_rms,
        "source": record.source,
    }


async def store_vehicle_data(
    session: AsyncSession,
    profile_id: int,
    data: VehicleDataPayload,
    raw_json: Optional[str] = None,
) -> VehicleData:
    """Store vehicle data to database."""
    current_time = time.time()
    
    record = VehicleData(
        profile_id=profile_id,
        vehicle_id=data.vehicle_id,
        timestamp=data.timestamp or current_time,
        rpm=data.rpm,
        speed=data.speed,
        coolant_temp=data.coolant_temp,
        battery_voltage=data.battery_voltage,
        engine_load=data.engine_load,
        throttle_pos=data.throttle_pos,
        fuel_level=data.fuel_level,
        fuel_pressure=data.fuel_pressure,
        intake_temp=data.intake_temp,
        maf_rate=data.maf_rate,
        oil_temp=data.oil_temp,
        short_term_fuel_trim=data.short_term_fuel_trim,
        long_term_fuel_trim=data.long_term_fuel_trim,
        timing_advance=data.timing_advance,
        latitude=data.latitude,
        longitude=data.longitude,
        vibration_rms=data.vibration_rms,
        vibration_peak=data.vibration_peak,
        odometer=data.odometer,
        ambient_temp=data.ambient_temp,
        boost_pressure=data.boost_pressure,
        fuel_rate=data.fuel_rate,
        torque=data.torque,
        obd_odometer=data.obd_odometer,
        mode06_results=data.mode06_results,
        source=data.source or "android",
        raw_json=raw_json,
        created_at=current_time,
    )
    
    session.add(record)
    await session.flush()
    return record


async def trigger_ai_analysis(
    profile_id: int,
    user_id: int,
    session: AsyncSession,
) -> None:
    """Trigger AI analysis on new data (background task)."""
    try:
        prediction_service = PredictionService()
        result = await prediction_service.get_vehicle_prediction(profile_id, session)
        logger.info(f"AI analysis triggered for profile {profile_id}: {result.get('status', 'unknown')}")
    except Exception as e:
        logger.error(f"AI analysis failed for profile {profile_id}: {e}")


async def _run_vehicle_learner(profile_id: int, readings: List[Dict]) -> None:
    """Background task: update per-vehicle AI baseline with new batch data."""
    try:
        learner = VehicleLearner()
        async with get_db_session() as session:
            await learner.process_batch(session, profile_id, readings)
    except Exception as e:
        logger.error(f"VehicleLearner background task failed for {profile_id}: {e}")


async def broadcast_vehicle_data(profile_id: int, data: Dict[str, Any]) -> None:
    """Broadcast vehicle data to WebSocket clients."""
    try:
        await ws_manager.broadcast({
            "type": "vehicle_data",
            "profile_id": profile_id,
            "data": data,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast error (ignored): {e}")


# =============================================================================
# NEW API ENDPOINTS
# =============================================================================

@router.post("/{vehicle_id}/data", response_model=Dict[str, Any])
async def receive_vehicle_data(
    vehicle_id: int,
    payload: VehicleDataPayload,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Receive vehicle data from Android/Desktop apps.
    
    This is the PRIMARY endpoint for vehicle data ingestion.
    Validates data, stores to database, triggers AI analysis.
    """
    # Validate vehicle exists and user has access
    profile_repo = VehicleProfileRepository(session)
    profile = await profile_repo.get_by_id(vehicle_id)
    
    if not profile:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message=f"Vehicle {vehicle_id} not found",
        )
    
    # Ensure profile_id in payload matches URL
    payload.profile_id = vehicle_id
    
    # Add timestamp if not provided
    if not payload.timestamp:
        payload.timestamp = time.time()
    
    # Store raw JSON for debugging
    raw_json = json.dumps(payload.model_dump(exclude_none=True))
    
    # Process through OBD processor for validation
    processed = obd_processor.process_record(payload.model_dump(exclude_none=True))
    
    # Store to database
    try:
        record = await store_vehicle_data(session, vehicle_id, payload, raw_json)
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to store vehicle data: {e}")
        raise APIError(
            status_code=500,
            code=ErrorCode.DATABASE_ERROR,
            message="Failed to store vehicle data",
        )
    
    # Update live data cache
    live_data_cache[vehicle_id] = {
        "timestamp": payload.timestamp,
        "rpm": payload.rpm,
        "speed": payload.speed,
        "coolant_temp": payload.coolant_temp,
        "battery_voltage": payload.battery_voltage,
        "engine_load": payload.engine_load,
        "throttle_pos": payload.throttle_pos,
        "fuel_level": payload.fuel_level,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "vibration_rms": payload.vibration_rms,
        "source": payload.source,
        "quality": processed.quality_level.value if processed else None,
    }
    
    # Update online status
    online_profiles[vehicle_id] = time.time()
    
    # Broadcast to WebSocket clients
    await broadcast_vehicle_data(vehicle_id, live_data_cache[vehicle_id])
    
    # Trigger AI analysis in background
    user_id = current_user.get("user_id")
    if user_id:
        background_tasks.add_task(trigger_ai_analysis, vehicle_id, user_id, session)
    
    logger.info(f"Vehicle data received for profile {vehicle_id}, record_id={record.id}")
    
    return {
        "success": True,
        "status": "ok",
        "stored": True,
        "record_id": record.id,
        "profile_id": vehicle_id,
        "timestamp": payload.timestamp,
        "quality_score": processed.quality_score if processed else 0,
    }


@router.get("/{vehicle_id}/data", response_model=Dict[str, Any])
async def get_vehicle_data(
    vehicle_id: int,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get recent vehicle data for a vehicle."""
    repo = VehicleDataRepository(session)
    records = await repo.get_latest(vehicle_id, limit=limit)
    
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "records": [format_record_response(r) for r in records],
        "count": len(records),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }


@router.get("/{vehicle_id}/data/latest", response_model=Dict[str, Any])
async def get_latest_vehicle_data_endpoint(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the latest vehicle data reading for a vehicle."""
    # Check live cache first (most recent)
    if vehicle_id in live_data_cache:
        return {
            "success": True,
            "source": "cache",
            "vehicle_id": vehicle_id,
            "data": live_data_cache[vehicle_id],
        }
    
    # Fall back to database
    repo = VehicleDataRepository(session)
    records = await repo.get_latest(vehicle_id, limit=1)
    
    if records:
        return {
            "success": True,
            "source": "database",
            "vehicle_id": vehicle_id,
            "data": format_record_response(records[0]),
        }
    
    raise APIError(
        status_code=404,
        code=ErrorCode.DATA_NOT_FOUND,
        message="No vehicle data found for this vehicle",
    )


@router.get("/{vehicle_id}/data/history", response_model=Dict[str, Any])
async def get_vehicle_data_history_endpoint(
    vehicle_id: int,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
    limit: int = 1000,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get historical vehicle data with pagination.
    
    Args:
        start_ts: Start timestamp (Unix float)
        end_ts: End timestamp (Unix float)
        limit: Max records to return
        offset: Pagination offset
    """
    if not start_ts:
        start_ts = time.time() - (7 * 24 * 60 * 60)  # Default: last 7 days
    if not end_ts:
        end_ts = time.time()
    
    repo = VehicleDataRepository(session)
    records = await repo.get_history(vehicle_id, start_ts, end_ts)
    
    # Apply pagination
    total = len(records)
    paginated = records[offset:offset + limit]
    
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "start_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_ts)),
        "start_time_unix": start_ts,
        "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end_ts)),
        "end_time_unix": end_ts,
        "records": [format_record_response(r) for r in paginated],
        "count": len(paginated),
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/{vehicle_id}/stats", response_model=Dict[str, Any])
async def get_vehicle_stats(
    vehicle_id: int,
    hours: int = 24,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get vehicle data statistics for a time period.
    
    Returns aggregated statistics including:
    - Min/max/average for each sensor
    - Data point count
    - Quality metrics
    """
    cutoff_time = time.time() - (hours * 3600)
    
    # Get records from repository
    repo = VehicleDataRepository(session)
    records = await repo.get_history(vehicle_id, cutoff_time, time.time())
    
    if not records:
        return {
            "success": True,
            "vehicle_id": vehicle_id,
            "hours": hours,
            "statistics": None,
            "message": "No data available for this time period",
        }
    
    # Calculate statistics
    def calc_stats(values: List[float]) -> Dict[str, Any]:
        if not values:
            return None
        return {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(sum(values) / len(values), 2),
            "count": len(values),
        }
    
    rpm_values = [r.rpm for r in records if r.rpm is not None]
    speed_values = [r.speed for r in records if r.speed is not None]
    temp_values = [r.coolant_temp for r in records if r.coolant_temp is not None]
    voltage_values = [r.battery_voltage for r in records if r.battery_voltage is not None]
    load_values = [r.engine_load for r in records if r.engine_load is not None]
    
    stats = {
        "period_hours": hours,
        "total_records": len(records),
        "first_record_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(records[0].timestamp)) if records else None,
        "last_record_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(records[-1].timestamp)) if records else None,
        "rpm": calc_stats(rpm_values),
        "speed_kmh": calc_stats(speed_values),
        "coolant_temp_c": calc_stats(temp_values),
        "battery_voltage": calc_stats(voltage_values),
        "engine_load_pct": calc_stats(load_values),
    }
    
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "hours": hours,
        "statistics": stats,
    }


@router.get("/{vehicle_id}/sensors", response_model=Dict[str, Any])
async def get_available_sensors(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get list of available sensors for a vehicle based on recent data.
    
    Returns which sensors have reported data recently.
    """
    # Get recent records to determine available sensors
    repo = VehicleDataRepository(session)
    records = await repo.get_latest(vehicle_id, limit=100)
    
    # Check which fields have data
    available_sensors = set()
    for record in records:
        if record.rpm is not None:
            available_sensors.add("rpm")
        if record.speed is not None:
            available_sensors.add("speed")
        if record.coolant_temp is not None:
            available_sensors.add("coolant_temp")
        if record.battery_voltage is not None:
            available_sensors.add("battery_voltage")
        if record.engine_load is not None:
            available_sensors.add("engine_load")
        if record.throttle_pos is not None:
            available_sensors.add("throttle_pos")
        if record.fuel_level is not None:
            available_sensors.add("fuel_level")
        if record.intake_temp is not None:
            available_sensors.add("intake_temp")
        if record.maf_rate is not None:
            available_sensors.add("maf_rate")
        if record.oil_temp is not None:
            available_sensors.add("oil_temp")
        if record.latitude is not None and record.longitude is not None:
            available_sensors.add("gps")
        if record.vibration_rms is not None:
            available_sensors.add("vibration")
    
    # Build sensor info with ranges
    sensor_info = []
    for sensor in sorted(available_sensors):
        range_info = OBD_RANGES.get(sensor.upper(), {})
        sensor_info.append({
            "name": sensor,
            "min": range_info.get("min"),
            "max": range_info.get("max"),
            "unit": range_info.get("unit"),
        })
    
    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "available_sensors": list(available_sensors),
        "sensor_details": sensor_info,
        "last_data_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(records[0].timestamp)) if records else None,
    }


# =============================================================================
# MODE 06 ECU TEST ENDPOINTS
# =============================================================================

@router.get("/{vehicle_id}/mode06", response_model=Dict[str, Any])
async def get_mode06_results(
    vehicle_id: int,
    limit: int = 1,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    GET /api/vehicle/{vehicle_id}/mode06 — Retrieve Mode 06 ECU test results.

    Returns the most recent Mode 06 test data for a vehicle.
    The mode06_results field is a JSON array of test result objects.
    """
    user_id = current_user.get("user_id")
    user_tier = current_user.get("tier", "free")

    # Verify ownership (admin bypass)
    vehicle_repo = VehicleProfileRepository(session)
    profile = await vehicle_repo.get_by_id(vehicle_id)
    if not profile:
        raise APIError(status_code=404, code=ErrorCode.VEHICLE_NOT_FOUND, message="Vehicle not found")
    if profile.owner_user_id != user_id and user_tier != "admin":
        raise APIError(status_code=403, code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS, message="Not authorized")

    # Query records that have mode06_results
    stmt = (
        select(VehicleData)
        .where(
            and_(
                VehicleData.profile_id == vehicle_id,
                VehicleData.mode06_results.isnot(None),
                VehicleData.mode06_results != "",
            )
        )
        .order_by(desc(VehicleData.timestamp))
        .limit(limit)
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    results = []
    for record in records:
        try:
            parsed = json.loads(record.mode06_results)
        except (json.JSONDecodeError, TypeError):
            parsed = []
        results.append({
            "timestamp": record.timestamp,
            "tests": parsed,
        })

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "count": len(results),
        "results": results,
    }


# =============================================================================
# TELEMETRY ENDPOINTS
# =============================================================================

@telemetry_router.post("/v1/telemetry", response_model=Dict[str, Any])
async def receive_telemetry(
    payload: TelemetryPacket,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """
    Receive telemetry snapshot from Android app.
    
    Stores telemetry record for tracking vehicle state over time.
    """
    # Create telemetry record
    record = TelemetryRecord(
        device_id=payload.device_id,
        ts=payload.timestamp,
        vin=payload.vin,
        mileage_km=payload.mileage_km,
        fuel_level=payload.fuel_level,
        raw_json=json.dumps({
            "predictions": payload.predictions,
            "sensors": payload.sensors,
        }),
    )
    
    session.add(record)
    await session.flush()
    await session.commit()
    
    logger.info(f"Telemetry received from device {payload.device_id}")
    
    return {
        "success": True,
        "status": "ok",
        "stored": True,
        "telemetry_id": record.id,
    }


# =============================================================================
# OBD ENDPOINTS (Legacy format compatibility)
# =============================================================================

@legacy_router.post("/api/obd", response_model=Dict[str, Any])
async def receive_obd(
    packet: OBDPacket,
    session: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """
    Receive a single OBD packet from the Android app.
    
    Legacy endpoint for simple OBD data ingestion.
    """
    # Create OBD record
    record = OBDRecord(
        device_id=packet.device_id,
        ts=packet.timestamp,
        pid=packet.data.get("pid"),
        name=packet.data.get("name"),
        value=packet.data.get("value"),
        unit=packet.data.get("unit"),
    )
    
    session.add(record)
    await session.flush()
    await session.commit()
    
    # Broadcast to WebSocket clients
    processed = {
        "device_id": packet.device_id,
        "timestamp": packet.timestamp,
        "pid": packet.data.get("pid"),
        "name": packet.data.get("name"),
        "value": packet.data.get("value"),
        "unit": packet.data.get("unit"),
    }
    
    try:
        await ws_manager.broadcast({
            "type": "obd_packet",
            "data": processed,
        })
    except Exception:
        pass  # Ignore websocket errors
    
    return {
        "success": True,
        "status": "ok",
        "stored": True,
    }


# =============================================================================
# LEGACY VEHICLE DATA ENDPOINTS (for Android compatibility)
# =============================================================================

@legacy_router.post("/api/vehicle_data", response_model=Dict[str, Any])
async def legacy_receive_vehicle_data(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Legacy endpoint: Receive complete vehicle data payload.
    
    Primary endpoint for Android → Server → Desktop data flow.
    Maintains exact same format as old server for compatibility.
    """
    # Extract API key from header
    api_key = x_api_key
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "").strip()
    
    if not api_key:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_MISSING_HEADER,
            message="Missing API key",
        )
    
    # Validate API key
    from predict.core.middleware.api_key import validate_api_key as validate_key
    key_data = await validate_key(request)
    
    if not key_data:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_INVALID_KEY,
            message="Invalid API key",
        )
    
    # Parse JSON body
    try:
        body = await request.json()
    except Exception as e:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid JSON: {str(e)}",
        )
    
    # Get profile_id from API key or payload
    profile_id = body.get("profile_id") or key_data.get("profile_id")
    if not profile_id:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Profile ID required",
        )
    
    # If body contains "readings" array, extract and store each reading individually
    # (prevents batch-format payloads from being stored as single NULL-column row)
    if "readings" in body and isinstance(body.get("readings"), list):
        readings = body["readings"]
        stored = 0
        for reading in readings:
            try:
                ts = reading.get("timestamp", time.time())
                record_kwargs = {
                    "profile_id": profile_id,
                    "timestamp": ts,
                    "source": body.get("source", "android"),
                    "raw_json": json.dumps(reading),
                    "created_at": time.time(),
                }
                for sensor_key, column_name in SENSOR_FIELD_MAP.items():
                    val = reading.get(sensor_key)
                    if val is not None:
                        record_kwargs[column_name] = val
                record = VehicleData(**record_kwargs)
                session.add(record)
                stored += 1
            except Exception:
                pass
        await session.commit()
        online_profiles[profile_id] = time.time()
        return {"success": True, "status": "ok", "stored": stored}

    # Add timestamp if not provided
    if "timestamp" not in body:
        body["timestamp"] = time.time()

    # Convert to VehicleDataPayload
    try:
        payload = VehicleDataPayload(**body)
    except Exception as e:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Invalid payload: {str(e)}",
        )

    # Store raw JSON
    raw_json = json.dumps(body)

    # Store to database
    try:
        record = await store_vehicle_data(session, profile_id, payload, raw_json)
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to save vehicle data: {e}")
        raise APIError(
            status_code=500,
            code=ErrorCode.DATABASE_ERROR,
            message="Database error",
        )
    
    # Update live cache
    live_data_cache[profile_id] = {
        "timestamp": payload.timestamp,
        "rpm": payload.rpm,
        "speed": payload.speed,
        "coolant_temp": payload.coolant_temp,
        "battery_voltage": payload.battery_voltage,
        "engine_load": payload.engine_load,
        "throttle_pos": payload.throttle_pos,
        "fuel_level": payload.fuel_level,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "vibration_rms": payload.vibration_rms,
        "source": payload.source,
    }
    
    # Update online status
    online_profiles[profile_id] = time.time()
    
    # Broadcast
    await broadcast_vehicle_data(profile_id, live_data_cache[profile_id])
    
    # Trigger AI analysis
    user_id = key_data.get("user_id")
    if user_id:
        background_tasks.add_task(trigger_ai_analysis, profile_id, user_id, session)
    
    # Update daily stats aggregation
    try:
        from datetime import datetime
        from predict.core.db.models.vehicle import DailyVehicleStats
        from sqlalchemy import and_
        
        today = datetime.now().strftime("%Y-%m-%d")
        current_time = time.time()
        
        # Try to get existing daily stats for today
        stats_result = await session.execute(
            select(DailyVehicleStats).where(
                and_(
                    DailyVehicleStats.profile_id == profile_id,
                    DailyVehicleStats.date == today,
                )
            )
        )
        daily_stats = stats_result.scalar_one_or_none()
        
        if daily_stats is None:
            daily_stats = DailyVehicleStats(
                profile_id=profile_id,
                date=today,
                max_speed_kmh=0.0,
                max_coolant_temp_c=0.0,
                avg_speed_kmh=0.0,
                total_distance_km=0.0,
                data_points=0,
                created_at=current_time,
                updated_at=current_time,
            )
            session.add(daily_stats)
        
        # Update max values
        speed = payload.speed or 0
        coolant_temp = payload.coolant_temp or 0
        
        if speed > daily_stats.max_speed_kmh:
            daily_stats.max_speed_kmh = speed
        if coolant_temp > daily_stats.max_coolant_temp_c:
            daily_stats.max_coolant_temp_c = coolant_temp
        
        # Update running average speed
        old_total = daily_stats.avg_speed_kmh * daily_stats.data_points
        daily_stats.data_points += 1
        daily_stats.avg_speed_kmh = (old_total + speed) / daily_stats.data_points
        
        daily_stats.updated_at = current_time
        await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update daily stats: {e}")
        # Don't fail the request if daily stats update fails
    
    return {
        "status": "ok",
        "stored": True,
        "row_id": record.id,
        "profile_id": profile_id,
        "timestamp": payload.timestamp,
    }


@legacy_router.get("/api/vehicle_data/latest/{profile_id}", response_model=Dict[str, Any])
async def legacy_get_latest_vehicle_data(
    profile_id: int,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Legacy endpoint: Get latest vehicle data for a profile."""
    if not x_api_key:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_MISSING_HEADER,
            message="Missing X-API-Key header",
        )
    
    # Check live cache first
    if profile_id in live_data_cache:
        return {
            "success": True,
            "source": "cache",
            "data": live_data_cache[profile_id],
        }
    
    # Fall back to database
    repo = VehicleDataRepository(session)
    records = await repo.get_latest(profile_id, limit=1)
    
    if records:
        return {
            "success": True,
            "source": "database",
            "data": format_record_response(records[0]),
        }
    
    return {
        "success": False,
        "error": "No vehicle data found for this profile",
    }


@legacy_router.get("/api/vehicle_data/history/{profile_id}", response_model=Dict[str, Any])
async def legacy_get_vehicle_data_history(
    profile_id: int,
    limit: int = 100,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Legacy endpoint: Get vehicle data history for a profile."""
    if not x_api_key:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_MISSING_HEADER,
            message="Missing X-API-Key header",
        )
    
    repo = VehicleDataRepository(session)
    records = await repo.get_latest(profile_id, limit=limit)
    
    return {
        "success": True,
        "profile_id": profile_id,
        "count": len(records),
        "data": [format_record_response(r) for r in records],
    }


@legacy_router.get("/api/vehicle_data/stats/{profile_id}", response_model=Dict[str, Any])
async def legacy_get_vehicle_data_stats(
    profile_id: int,
    hours: int = 24,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Legacy endpoint: Get vehicle data statistics for a profile."""
    if not x_api_key:
        raise APIError(
            status_code=401,
            code=ErrorCode.AUTH_MISSING_HEADER,
            message="Missing X-API-Key header",
        )
    
    cutoff_time = time.time() - (hours * 3600)
    repo = VehicleDataRepository(session)
    records = await repo.get_history(profile_id, cutoff_time, time.time())
    
    # Calculate statistics (same as new endpoint)
    def calc_stats(values: List[float]) -> Dict[str, Any]:
        if not values:
            return None
        return {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(sum(values) / len(values), 2),
            "count": len(values),
        }
    
    rpm_values = [r.rpm for r in records if r.rpm is not None]
    speed_values = [r.speed for r in records if r.speed is not None]
    temp_values = [r.coolant_temp for r in records if r.coolant_temp is not None]
    
    return {
        "success": True,
        "profile_id": profile_id,
        "hours": hours,
        "statistics": {
            "rpm": calc_stats(rpm_values),
            "speed": calc_stats(speed_values),
            "coolant_temp": calc_stats(temp_values),
            "record_count": len(records),
        },
    }


@legacy_router.post("/api/vehicle_data/bulk", response_model=Dict[str, Any])
async def bulk_upload_vehicle_data(
    request: BulkUploadRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Bulk upload multiple vehicle data readings.
    
    Efficient for syncing offline-collected data.
    """
    profile_id = None
    if request.readings:
        profile_id = request.readings[0].profile_id
    
    if not profile_id:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Profile ID required in first reading",
        )
    
    # Process in batches
    stored_count = 0
    errors = []
    
    for i, reading in enumerate(request.readings):
        try:
            reading.profile_id = profile_id
            if not reading.timestamp:
                reading.timestamp = time.time()
            
            raw_json = json.dumps(reading.model_dump(exclude_none=True))
            record = await store_vehicle_data(session, profile_id, reading, raw_json)
            stored_count += 1
            
            # Commit every 50 records to avoid large transactions
            if stored_count % 50 == 0:
                await session.commit()
                
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    
    # Final commit
    await session.commit()
    
    # Trigger AI analysis once for the batch
    user_id = current_user.get("user_id")
    if user_id and stored_count > 0:
        background_tasks.add_task(trigger_ai_analysis, profile_id, user_id, session)
    
    return {
        "success": True,
        "stored": stored_count,
        "errors": errors,
        "profile_id": profile_id,
    }


# =============================================================================
# COLD-START INFERENCE — Retroactive detection from sensor data
# =============================================================================

def _infer_cold_start(readings: list, last_reading_time=None) -> dict:
    """
    Retroactively infer cold-start from sensor data.
    Returns {"is_cold_start": bool, "resting_voltage": float|None, "reason": str}
    """
    if not readings:
        return {"is_cold_start": False, "resting_voltage": None, "reason": "no_readings"}

    first = readings[0].get("sensors", {}) if isinstance(readings[0], dict) else {}
    coolant = first.get("coolant_temp")
    intake = first.get("intake_temp")
    oil_temp = first.get("oil_temp")
    battery = first.get("battery_voltage")
    ambient = first.get("ambient_temp")

    reasons = []

    if coolant is not None and coolant < 60.0:
        reasons.append(f"coolant_cold:{coolant:.1f}C")

    if oil_temp is not None and ambient is not None and abs(oil_temp - ambient) < 5.0:
        reasons.append(f"oil_near_ambient:{oil_temp:.1f}C_vs_{ambient:.1f}C")

    if intake is not None and ambient is not None and abs(intake - ambient) < 8.0:
        reasons.append(f"intake_near_ambient:{intake:.1f}C")

    if last_reading_time is not None:
        first_ts = readings[0].get("timestamp")
        if first_ts:
            try:
                from datetime import datetime as dt
                if isinstance(first_ts, (int, float)):
                    first_dt = dt.fromtimestamp(first_ts)
                else:
                    first_dt = dt.fromisoformat(str(first_ts).replace("Z", "+00:00"))
                gap_hours = (first_dt - last_reading_time).total_seconds() / 3600
                if gap_hours >= 6.0:
                    reasons.append(f"gap:{gap_hours:.1f}h")
            except Exception:
                pass

    is_cold = len(reasons) >= 1
    resting_voltage = battery if is_cold and battery is not None else None
    return {
        "is_cold_start": is_cold,
        "resting_voltage": resting_voltage,
        "reason": ",".join(reasons) if reasons else "warm_start",
    }


# =============================================================================
# BATCH V2 — Generic sensor payload (future-proof)
# =============================================================================

@legacy_router.post("/api/vehicle_data/batch_v2", response_model=Dict[str, Any])
async def batch_v2_upload(
    request: GenericBatchUploadRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Generic batch upload — sensor-agnostic, trip-based.

    Accepts arbitrary sensor keys in each reading's ``sensors`` dict.
    Known sensors are extracted into typed VehicleData columns;
    the full payload is preserved in ``raw_json`` for future use.

    Idempotent: if ``batch_id`` already exists, returns 409.
    """
    from sqlalchemy import text as sa_text
    from datetime import datetime

    profile_id = request.profile_id

    # --- Verify profile exists ---
    profile_repo = VehicleProfileRepository(session)
    profile = await profile_repo.get_by_id(profile_id)
    if not profile:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message=f"Vehicle {profile_id} not found",
        )

    # --- Idempotency: check batch_id ---
    dup_check = await session.execute(
        select(VehicleData.id)
        .where(VehicleData.profile_id == profile_id)
        .where(VehicleData.raw_json.contains(f'"batch_id": "{request.batch_id}"'))
        .limit(1)
    )
    if dup_check.scalar_one_or_none() is not None:
        return {
            "success": True,
            "batch_id": request.batch_id,
            "stored": 0,
            "duplicate": True,
            "message": "Batch already processed",
        }

    # --- Process readings ---
    stored_count = 0
    errors = []
    current_time = time.time()

    # Track aggregates for DailyVehicleStats
    max_speed = 0.0
    max_coolant = 0.0
    speed_sum = 0.0
    speed_count = 0

    for i, reading in enumerate(request.readings):
        try:
            # Build VehicleData record from known sensors
            record_kwargs = {
                "profile_id": profile_id,
                "timestamp": reading.timestamp,
                "source": request.source or "android",
                "raw_json": json.dumps({
                    "batch_id": request.batch_id,
                    "trip_id": request.trip_id,
                    "app_version": request.app_version,
                    "sensors": reading.sensors,
                }),
                "created_at": current_time,
            }

            # Extract known sensor columns
            for sensor_key, column_name in SENSOR_FIELD_MAP.items():
                val = reading.sensors.get(sensor_key)
                if val is not None:
                    record_kwargs[column_name] = val

            record = VehicleData(**record_kwargs)
            session.add(record)
            stored_count += 1

            # Aggregate for daily stats
            spd = reading.sensors.get("speed", 0)
            ct = reading.sensors.get("coolant_temp", 0)
            if spd > max_speed:
                max_speed = spd
            if ct > max_coolant:
                max_coolant = ct
            if spd > 0:
                speed_sum += spd
                speed_count += 1

            # Commit every 50 records
            if stored_count % 50 == 0:
                await session.flush()

        except Exception as e:
            errors.append({"index": i, "error": str(e)})

    # Final commit
    await session.commit()

    # --- Update live data cache with LAST reading ---
    if request.readings:
        last = request.readings[-1]
        live_data_cache[profile_id] = {
            "timestamp": last.timestamp,
            "rpm": last.sensors.get("rpm"),
            "speed": last.sensors.get("speed"),
            "coolant_temp": last.sensors.get("coolant_temp"),
            "battery_voltage": last.sensors.get("battery_voltage"),
            "engine_load": last.sensors.get("engine_load"),
            "throttle_pos": last.sensors.get("throttle_pos"),
            "fuel_level": last.sensors.get("fuel_level"),
            "latitude": last.sensors.get("latitude"),
            "longitude": last.sensors.get("longitude"),
            "source": request.source,
        }
        online_profiles[profile_id] = time.time()
        await broadcast_vehicle_data(profile_id, live_data_cache[profile_id])

    # --- Update DailyVehicleStats (loop ALL readings for correct aggregates) ---
    try:
        from predict.core.db.models.vehicle import DailyVehicleStats

        today = datetime.now().strftime("%Y-%m-%d")
        stats_result = await session.execute(
            select(DailyVehicleStats).where(
                and_(
                    DailyVehicleStats.profile_id == profile_id,
                    DailyVehicleStats.date == today,
                )
            )
        )
        daily_stats = stats_result.scalar_one_or_none()

        if daily_stats is None:
            daily_stats = DailyVehicleStats(
                profile_id=profile_id,
                date=today,
                max_speed_kmh=0.0,
                max_coolant_temp_c=0.0,
                avg_speed_kmh=0.0,
                total_distance_km=0.0,
                data_points=0,
                created_at=current_time,
                updated_at=current_time,
            )
            session.add(daily_stats)

        if max_speed > daily_stats.max_speed_kmh:
            daily_stats.max_speed_kmh = max_speed
        if max_coolant > daily_stats.max_coolant_temp_c:
            daily_stats.max_coolant_temp_c = max_coolant

        # Update running average
        old_total = daily_stats.avg_speed_kmh * daily_stats.data_points
        daily_stats.data_points += stored_count
        if daily_stats.data_points > 0:
            daily_stats.avg_speed_kmh = (old_total + speed_sum) / daily_stats.data_points

        daily_stats.updated_at = current_time
        await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update daily stats for batch: {e}")

    # --- Trigger AI analysis once for batch ---
    user_id = current_user.get("user_id")
    if user_id and stored_count > 0:
        background_tasks.add_task(trigger_ai_analysis, profile_id, user_id, session)

    # --- Trigger per-vehicle baseline learning ---
    if stored_count > 0:
        readings_dicts = [
            {"sensors": r.sensors, "timestamp": r.timestamp}
            for r in request.readings
        ]
        background_tasks.add_task(
            _run_vehicle_learner, profile_id, readings_dicts
        )

    # --- Cold-start inference ---
    try:
        last_reading_stmt = select(VehicleData.timestamp).where(
            VehicleData.vehicle_id == profile_id
        ).order_by(desc(VehicleData.timestamp)).limit(1).offset(stored_count)
        last_row = (await session.execute(last_reading_stmt)).scalar_one_or_none()

        cold_start_info = _infer_cold_start(
            [r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in request.readings],
            last_row,
        )
        if cold_start_info["is_cold_start"]:
            logger.info("Cold-start inferred for vehicle %d: %s", profile_id, cold_start_info["reason"])
            from predict.core.db.models.vehicle import VehicleBaseline
            baseline_stmt = select(VehicleBaseline).where(VehicleBaseline.vehicle_id == profile_id)
            baseline = (await session.execute(baseline_stmt)).scalar_one_or_none()
            if baseline:
                stats = json.loads(baseline.sensor_stats) if isinstance(baseline.sensor_stats, str) else (baseline.sensor_stats or {})
                stats["_cold_start"] = {
                    "resting_voltage": cold_start_info["resting_voltage"],
                    "reason": cold_start_info["reason"],
                    "timestamp": request.readings[0].timestamp if request.readings else None,
                }
                baseline.sensor_stats = json.dumps(stats) if isinstance(baseline.sensor_stats, str) else stats
                await session.commit()
    except Exception as e:
        logger.warning("Cold-start inference failed (non-fatal): %s", e)

    # --- Clear in-memory explain cache only (fast path invalidation) ---
    # DB-persisted explain is NOT cleared on OBD upload — it persists for 5 days.
    # Only manual "Refresh" (force_refresh=true) regenerates with new data.
    try:
        from predict.core.api.v1.predictions import _explain_cache
        _explain_cache.pop(profile_id, None)
    except (ImportError, AttributeError):
        pass

    logger.info(
        f"Batch V2 uploaded: batch_id={request.batch_id}, "
        f"profile={profile_id}, stored={stored_count}, errors={len(errors)}"
    )

    return {
        "success": True,
        "batch_id": request.batch_id,
        "stored": stored_count,
        "errors": errors if errors else None,
    }


# =============================================================================
# HEARTBEAT — Lightweight, no DB write
# =============================================================================

@legacy_router.post("/api/vehicle_data/heartbeat", response_model=Dict[str, Any])
async def heartbeat(
    request: HeartbeatRequest,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Lightweight heartbeat — keeps vehicle 'online' for Guardian.

    NO database write. Updates only:
    - live_data_cache (for /latest endpoints)
    - online_profiles (for online/offline status)
    - WebSocket broadcast (for Guardian live monitoring)
    """
    profile_id = request.profile_id

    live_data_cache[profile_id] = {
        "timestamp": time.time(),
        "rpm": request.rpm,
        "speed": request.speed,
        "coolant_temp": request.coolant_temp,
        "battery_voltage": request.battery_voltage,
        "engine_load": request.engine_load,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "source": "heartbeat",
    }

    online_profiles[profile_id] = time.time()

    await broadcast_vehicle_data(profile_id, live_data_cache[profile_id])

    return {"success": True, "profile_id": profile_id}


# =============================================================================
# CONNECT SNAPSHOT — Mode 06/07/0A/03 captured once per OBD session
# =============================================================================

@legacy_router.post("/api/vehicle_data/connect-snapshot", response_model=Dict[str, Any])
async def connect_snapshot(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Receive a connect snapshot from Android — captured once per OBD session start.

    Contains Mode 06 test results, pending/permanent/stored DTCs, calibration ID.
    Stored as JSON in VehicleData with source='connect_snapshot' for trend analysis.
    """
    body = await request.json()
    vehicle_id = body.get("vehicle_id", 0)
    if not vehicle_id:
        raise HTTPException(status_code=400, detail="vehicle_id required")

    timestamp = body.get("timestamp", time.time())
    if isinstance(timestamp, (int, float)) and timestamp > 1e12:
        timestamp = timestamp / 1000.0  # Convert millis to seconds

    mode06_results = body.get("mode06_results", [])
    pending_dtcs = body.get("pending_dtcs", [])
    permanent_dtcs = body.get("permanent_dtcs", [])
    stored_dtcs = body.get("stored_dtcs", [])
    calibration_id = body.get("calibration_id")
    trip_id = body.get("trip_id")

    # Store as a VehicleData row with raw_json for snapshot data
    snapshot_data = VehicleData(
        profile_id=vehicle_id,
        timestamp=timestamp,
        source="connect_snapshot",
        raw_json=json.dumps({
            "mode06_results": mode06_results,
            "pending_dtcs": pending_dtcs,
            "permanent_dtcs": permanent_dtcs,
            "stored_dtcs": stored_dtcs,
            "calibration_id": calibration_id,
            "trip_id": trip_id,
            "mode06_count": len(mode06_results),
            "mode06_failed": sum(1 for t in mode06_results if not t.get("passed", True)),
        })
    )
    db.add(snapshot_data)
    await db.commit()

    logger.info(
        f"Connect snapshot stored: vehicle={vehicle_id}, "
        f"mode06={len(mode06_results)} tests ({sum(1 for t in mode06_results if not t.get('passed', True))} failed), "
        f"dtcs={len(stored_dtcs)}s/{len(pending_dtcs)}p/{len(permanent_dtcs)}perm, "
        f"calId={calibration_id}"
    )

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "mode06_tests": len(mode06_results),
        "dtcs_total": len(stored_dtcs) + len(pending_dtcs) + len(permanent_dtcs),
    }
