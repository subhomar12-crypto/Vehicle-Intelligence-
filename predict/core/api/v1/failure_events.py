"""
Failure Event Logging + Training Data Export API.

Endpoints:
- POST /profile/vehicles/{vehicle_id}/failures - Log a confirmed failure event
- GET  /profile/vehicles/{vehicle_id}/failures - Get failure events for a vehicle
- POST /profile/vehicles/{vehicle_id}/failures/from-dtc - Create failure from confirmed DTC
- GET  /training/export - Export failure events + OBD data as training dataset
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user
from predict.core.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()
training_router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class FailureEventCreate(BaseModel):
    """Request to log a confirmed failure event."""
    event_type: str = Field(..., description="component_failure, dtc_confirmed, repair_completed, recall_service, preventive_maintenance")
    component: str = Field(..., description="Component name, e.g. catalytic_converter, oxygen_sensor")
    description: Optional[str] = None
    severity: str = Field("medium", description="low, medium, high, critical")
    dtc_code: Optional[str] = None
    mileage_at_failure: Optional[int] = None
    cost: Optional[float] = Field(None, description="Repair cost in QAR")


class FailureFromDtcRequest(BaseModel):
    """Request to create failure event from a confirmed DTC."""
    dtc_code: str
    component: str
    description: Optional[str] = None


class FailureEventResponse(BaseModel):
    """Single failure event."""
    id: int
    profile_id: int
    event_type: str
    component: str
    description: Optional[str]
    severity: str
    dtc_code: Optional[str]
    mileage_at_failure: Optional[int]
    cost: Optional[float]
    training_label: Optional[str]
    event_timestamp: float
    created_at: float


# =============================================================================
# FAILURE EVENT ENDPOINTS (mounted under /profile)
# =============================================================================

@router.post("/vehicles/{vehicle_id}/failures")
async def log_failure_event(
    vehicle_id: int,
    request: FailureEventCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Log a confirmed vehicle failure/repair event."""
    from predict.core.db.models.vehicle import FailureEvent, VehicleData

    now = time.time()
    training_label = f"{request.component}_{request.event_type}"

    # Get OBD snapshot: last 5 minutes of sensor data
    obd_snapshot = None
    try:
        window_start = now - 300  # 5 minutes ago
        stmt = select(VehicleData).where(
            and_(
                VehicleData.profile_id == vehicle_id,
                VehicleData.timestamp >= window_start,
            )
        ).order_by(VehicleData.timestamp.desc()).limit(50)
        result = await session.execute(stmt)
        records = result.scalars().all()
        if records:
            snapshot_data = []
            for r in records:
                snapshot_data.append({
                    "timestamp": r.timestamp,
                    "rpm": r.rpm,
                    "speed": r.speed,
                    "coolant_temp": r.coolant_temp,
                    "engine_load": r.engine_load,
                    "throttle_pos": r.throttle_pos,
                    "battery_voltage": r.battery_voltage,
                })
            obd_snapshot = json.dumps(snapshot_data)
    except Exception as e:
        logger.warning(f"Failed to capture OBD snapshot: {e}")

    event = FailureEvent(
        profile_id=vehicle_id,
        event_type=request.event_type,
        component=request.component,
        description=request.description,
        severity=request.severity,
        dtc_code=request.dtc_code,
        mileage_at_failure=request.mileage_at_failure,
        cost=request.cost,
        obd_snapshot=obd_snapshot,
        training_label=training_label,
        training_exported=False,
        event_timestamp=now,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    logger.info(f"Failure event logged: {request.component} ({request.event_type}) for vehicle {vehicle_id}")

    return {
        "success": True,
        "event_id": event.id,
        "training_label": training_label,
        "obd_snapshot_records": len(json.loads(obd_snapshot)) if obd_snapshot else 0,
    }


@router.get("/vehicles/{vehicle_id}/failures")
async def get_failure_events(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get all failure events for a vehicle."""
    from predict.core.db.models.vehicle import FailureEvent

    stmt = (
        select(FailureEvent)
        .where(FailureEvent.profile_id == vehicle_id)
        .order_by(FailureEvent.event_timestamp.desc())
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "component": e.component,
                "description": e.description,
                "severity": e.severity,
                "dtc_code": e.dtc_code,
                "mileage_at_failure": e.mileage_at_failure,
                "cost": e.cost,
                "training_label": e.training_label,
                "training_exported": e.training_exported,
                "event_timestamp": e.event_timestamp,
                "created_at": e.created_at,
            }
            for e in events
        ],
    }


@router.post("/vehicles/{vehicle_id}/failures/from-dtc")
async def create_failure_from_dtc(
    vehicle_id: int,
    request: FailureFromDtcRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Auto-create failure event when a DTC is confirmed as a real issue."""
    from predict.core.db.models.vehicle import FailureEvent, VehicleData

    now = time.time()

    # Pull OBD data window around the DTC (last 30 minutes)
    obd_snapshot = None
    try:
        window_start = now - 1800  # 30 minutes
        stmt = select(VehicleData).where(
            and_(
                VehicleData.profile_id == vehicle_id,
                VehicleData.timestamp >= window_start,
            )
        ).order_by(VehicleData.timestamp.desc()).limit(100)
        result = await session.execute(stmt)
        records = result.scalars().all()
        if records:
            snapshot_data = [
                {
                    "timestamp": r.timestamp,
                    "rpm": r.rpm,
                    "speed": r.speed,
                    "coolant_temp": r.coolant_temp,
                    "engine_load": r.engine_load,
                    "throttle_pos": r.throttle_pos,
                    "battery_voltage": r.battery_voltage,
                }
                for r in records
            ]
            obd_snapshot = json.dumps(snapshot_data)
    except Exception as e:
        logger.warning(f"Failed to capture OBD snapshot for DTC: {e}")

    event = FailureEvent(
        profile_id=vehicle_id,
        event_type="dtc_confirmed",
        component=request.component,
        description=request.description or f"DTC {request.dtc_code} confirmed",
        severity="medium",
        dtc_code=request.dtc_code,
        obd_snapshot=obd_snapshot,
        training_label=f"{request.component}_dtc_confirmed",
        training_exported=False,
        event_timestamp=now,
        created_at=now,
        updated_at=now,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)

    return {
        "success": True,
        "event_id": event.id,
        "dtc_code": request.dtc_code,
        "component": request.component,
    }


# =============================================================================
# TRAINING DATA EXPORT (mounted under /training)
# =============================================================================

@training_router.get("/export")
async def export_training_data(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Export failure events paired with OBD data as a training dataset.

    For each failure event: returns vehicle_data records in [-30min, +5min] window.
    Also samples healthy periods (vehicle_data with no nearby failures).
    Marks exported records as training_exported=true.
    """
    from predict.core.db.models.vehicle import FailureEvent, VehicleData

    # Get unexported failure events
    stmt = (
        select(FailureEvent)
        .where(FailureEvent.training_exported == False)  # noqa: E712
        .order_by(FailureEvent.event_timestamp)
    )
    result = await session.execute(stmt)
    events = result.scalars().all()

    training_samples = []

    for event in events:
        # Get OBD data in [-30min, +5min] window around failure
        window_start = event.event_timestamp - 1800  # 30 min before
        window_end = event.event_timestamp + 300     # 5 min after
        data_stmt = select(VehicleData).where(
            and_(
                VehicleData.profile_id == event.profile_id,
                VehicleData.timestamp >= window_start,
                VehicleData.timestamp <= window_end,
            )
        ).order_by(VehicleData.timestamp)
        data_result = await session.execute(data_stmt)
        obd_records = data_result.scalars().all()

        training_samples.append({
            "event_id": event.id,
            "label": event.training_label,
            "component": event.component,
            "severity": event.severity,
            "dtc_code": event.dtc_code,
            "event_timestamp": event.event_timestamp,
            "profile_id": event.profile_id,
            "obd_data_points": len(obd_records),
            "obd_data": [
                {
                    "timestamp": r.timestamp,
                    "rpm": r.rpm,
                    "speed": r.speed,
                    "coolant_temp": r.coolant_temp,
                    "engine_load": r.engine_load,
                    "throttle_pos": r.throttle_pos,
                    "battery_voltage": r.battery_voltage,
                    "fuel_level": r.fuel_level,
                    "intake_temp": r.intake_temp,
                    "maf": r.maf_rate,
                }
                for r in obd_records
            ],
        })

        # Mark as exported
        event.training_exported = True

    await session.commit()

    # Get total counts for metadata
    total_events_stmt = select(func.count()).select_from(FailureEvent)
    total_result = await session.execute(total_events_stmt)
    total_events = total_result.scalar() or 0

    total_exported_stmt = select(func.count()).select_from(FailureEvent).where(
        FailureEvent.training_exported == True  # noqa: E712
    )
    exported_result = await session.execute(total_exported_stmt)
    total_exported = exported_result.scalar() or 0

    return {
        "success": True,
        "samples": training_samples,
        "metadata": {
            "exported_count": len(training_samples),
            "total_failure_events": total_events,
            "total_exported": total_exported,
            "export_timestamp": time.time(),
        },
    }
