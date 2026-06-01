"""
Dashboard API routes with float timestamps.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Dashboard"])


@router.get("/summary")
async def get_dashboard_summary(
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get dashboard summary data."""
    # Get vehicle count
    from predict.core.db.models.vehicle import VehicleProfile
    from sqlalchemy import select, func
    
    stmt = select(func.count(VehicleProfile.profile_id))
    result = await session.execute(stmt)
    vehicle_count = result.scalar() or 0
    
    # Get active DTC count
    from predict.core.db.models.dtc import DTCCodes

    stmt = select(func.count(DTCCodes.id)).where(DTCCodes.is_active == 1)
    result = await session.execute(stmt)
    active_dtc_count = result.scalar() or 0
    
    # Get recent predictions
    from predict.core.db.models.prediction import Prediction
    
    stmt = (
        select(func.count(Prediction.id))
        .where(Prediction.created_at > time.time() - 86400)  # Last 24 hours
    )
    result = await session.execute(stmt)
    predictions_24h = result.scalar() or 0
    
    return {
        "vehicles": {
            "total": vehicle_count,
            "active": vehicle_count,
        },
        "dtcs": {
            "active": active_dtc_count,
        },
        "predictions": {
            "last_24h": predictions_24h,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }


@router.get("/alerts")
async def get_dashboard_alerts(
    limit: int = 10,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get recent alerts for dashboard."""
    # Get high-risk predictions
    from predict.core.db.models.prediction import Prediction
    from sqlalchemy import select
    
    stmt = (
        select(Prediction)
        .where(Prediction.failure_probability > 0.7)
        .where(Prediction.status == "active")
        .order_by(Prediction.created_at.desc())
        .limit(limit)
    )
    
    result = await session.execute(stmt)
    predictions = result.scalars().all()
    
    alerts = []
    for pred in predictions:
        alerts.append({
            "id": pred.id,
            "vehicle_id": pred.profile_id,
            "component": pred.component,
            "risk_score": pred.failure_probability,
            "detected_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(pred.created_at)
            ) if pred.created_at else None,
            "detected_at_unix": pred.created_at,
        })
    
    return {
        "alerts": alerts,
        "count": len(alerts),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_unix": time.time(),
    }
