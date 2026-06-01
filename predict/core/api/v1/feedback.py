"""
Prediction feedback API — mechanic validation after service.
POST /api/predictions/feedback — submit validation result
"""

import logging
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.prediction_feedback import PredictionFeedback

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    vehicle_id: int
    component: str
    predicted_score: int
    actual_outcome: str              # confirmed_bad / confirmed_good / unknown
    service_record_id: Optional[int] = None


class FeedbackResponse(BaseModel):
    success: bool = True
    message: str = "Feedback recorded"


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit mechanic validation feedback after service."""
    from predict.core.db.models.vehicle import VehicleProfile
    from sqlalchemy import select

    profile = None
    try:
        result = await session.execute(
            select(VehicleProfile).where(VehicleProfile.profile_id == request.vehicle_id)
        )
        profile = result.scalar_one_or_none()
    except Exception:
        pass

    feedback = PredictionFeedback(
        vehicle_id=request.vehicle_id,
        component=request.component,
        predicted_score=request.predicted_score,
        actual_outcome=request.actual_outcome,
        service_record_id=request.service_record_id,
        feedback_date=time.time(),
        make=profile.make if profile else None,
        model=profile.model if profile else None,
        year=profile.year if profile else None,
    )
    session.add(feedback)
    await session.commit()

    logger.info(
        f"Prediction feedback: vehicle={request.vehicle_id} "
        f"component={request.component} outcome={request.actual_outcome}"
    )

    return FeedbackResponse()
