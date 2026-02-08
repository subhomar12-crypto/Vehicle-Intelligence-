"""
AI Prediction endpoints.

Handles:
- Failure predictions
- Health scores
- RUL (Remaining Useful Life) estimates
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user, require_permission
from predict.core.db.models.prediction import Prediction
from predict.core.db.models.vehicle import VehicleProfile
from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================
# Response Models
# ========================

class PredictionResponse(BaseModel):
    id: int
    prediction_type: str
    component: str
    failure_probability: float
    estimated_rul_days: Optional[int]
    confidence_score: float
    model_version: str
    feature_importance: dict
    explanation: Optional[str]
    created_at: str


class HealthScoreResponse(BaseModel):
    overall_score: int
    engine_score: int
    transmission_score: int
    electrical_score: int
    cooling_score: int
    fuel_system_score: int
    last_updated: str


class ComponentStatus(BaseModel):
    component: str
    status: str  # good, fair, poor, critical
    health_percentage: int
    predictions: List[PredictionResponse]


# ========================
# Endpoints
# ========================

@router.get("/vehicle/{profile_id}", response_model=List[PredictionResponse])
async def get_predictions(
    profile_id: int,
    component: Optional[str] = None,
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI predictions for a vehicle."""
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
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    query = select(Prediction).where(
        Prediction.profile_id == profile_id
    ).order_by(desc(Prediction.created_at))
    
    if component:
        query = query.where(Prediction.component == component.lower())
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    predictions = result.scalars().all()
    
    return [
        PredictionResponse(
            id=p.id,
            prediction_type=p.prediction_type,
            component=p.component,
            failure_probability=float(p.failure_probability),
            estimated_rul_days=p.estimated_rul_days,
            confidence_score=float(p.confidence_score),
            model_version=p.model_version,
            feature_importance=p.feature_importance or {},
            explanation=p.explanation,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in predictions
    ]


@router.get("/vehicle/{profile_id}/health", response_model=HealthScoreResponse)
async def get_health_score(
    profile_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get overall health score for a vehicle.
    
    TODO Phase 6: Implement actual AI-based health scoring
    """
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
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    # Placeholder - will be replaced with actual AI scoring
    return HealthScoreResponse(
        overall_score=85,
        engine_score=90,
        transmission_score=88,
        electrical_score=82,
        cooling_score=85,
        fuel_system_score=87,
        last_updated=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/vehicle/{profile_id}/request")
async def request_prediction(
    profile_id: int,
    prediction_type: str,
    current_user: dict = Depends(require_permission("predict")),
    db: AsyncSession = Depends(get_db),
):
    """
    Request a new prediction for a vehicle.
    
    TODO Phase 6: Implement actual prediction pipeline
    """
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
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    # Placeholder
    return {
        "success": True,
        "message": "Prediction requested",
        "status": "processing",
    }


@router.post("/{prediction_id}/feedback")
async def submit_prediction_feedback(
    prediction_id: int,
    outcome: str,  # confirmed, false_positive
    notes: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback on a prediction (for model improvement)."""
    result = await db.execute(
        select(Prediction).where(Prediction.id == prediction_id)
    )
    prediction = result.scalar_one_or_none()
    
    if not prediction:
        raise APIError(
            status_code=404,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message="Prediction not found",
        )
    
    # Verify ownership through vehicle profile
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == prediction.profile_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    if not result.scalar_one_or_none():
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Not authorized to provide feedback for this prediction",
        )
    
    prediction.is_feedback_provided = True
    prediction.feedback_outcome = outcome
    prediction.feedback_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"success": True, "message": "Feedback recorded"}
