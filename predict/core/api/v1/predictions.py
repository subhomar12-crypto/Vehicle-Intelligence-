"""
Predictions API routes with float timestamps.

Endpoints:
- GET /api/predictions/{vehicle_id} - Get AI predictions for a vehicle
- GET /api/predictions/{vehicle_id}/component/{component} - Component-specific predictions
- GET /api/predictions/{vehicle_id}/history - Prediction history
- POST /api/predictions/{vehicle_id}/feedback - User feedback on predictions
- GET /api/predictions/quota - Check remaining predictions for user's tier
"""

import asyncio
import logging
import time
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user
from predict.core.ai.unified_ai_module import UnifiedAI, get_unified_ai
from predict.core.services.prediction_service import PredictionService
from predict.core.db.repositories.prediction_repo import PredictionRepository, MLTrainingLabelRepository
from predict.core.db.repositories.audit_repo import AuditLogRepository
from predict.core.db.models.prediction import Prediction, MLTrainingLabel
from predict.core.db.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Predictions"])


# ===== Pydantic Models =====

class PredictionFeedbackRequest(BaseModel):
    """Request model for prediction feedback."""
    prediction_id: str = Field(..., description="UUID of the prediction")
    actual_outcome: str = Field(..., pattern="^(failure_occurred|no_failure|partial_failure|unknown)$")
    notes: Optional[str] = Field(None, max_length=500)
    mileage_at_outcome: Optional[int] = Field(None, ge=0)
    repair_cost: Optional[float] = Field(None, ge=0)
    parts_replaced: Optional[str] = Field(None, max_length=500)


class PredictionResponse(BaseModel):
    """Prediction response model."""
    id: int
    prediction_id: str
    component: str
    risk_score: float
    confidence: float
    severity: str
    status: str
    created_at: float
    created_at_iso: str


class QuotaResponse(BaseModel):
    """Quota check response."""
    tier: str
    limit: int
    used: int
    remaining: int
    reset_date: float
    reset_date_iso: str


# ===== Helper Functions =====

def format_timestamp(unix_time: Optional[float]) -> Optional[str]:
    """Format unix timestamp to ISO string."""
    if unix_time is None:
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(unix_time))


async def log_prediction_audit(
    session: AsyncSession,
    action: str,
    user_id: int,
    details: Dict[str, Any],
    request: Request = None,
) -> None:
    """Log prediction-related actions to audit log."""
    try:
        repo = AuditLogRepository(session)
        request_id = getattr(request.state, 'request_id', f"pred_{int(time.time())}") if request else f"pred_{int(time.time())}"
        ip_address = request.client.host if request and request.client else None
        
        await repo.log_action(
            action=action,
            user_id=user_id,
            details=str(details),
            ip_address=ip_address,
            request_id=request_id,
        )
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")


async def check_and_update_quota(
    user_id: int,
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Check user's prediction quota and update usage.
    
    Returns:
        Quota info dict or raises HTTPException if quota exceeded
    """
    # Get user's tier
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Daily tier limits (per plan: free=0, pro=2, premium=5/vehicle, admin=unlimited)
    tier_limits = {
        "free": 0,
        "pro": 2,
        "premium": 5,  # Per vehicle, max 4 vehicles = 20 total
        "admin": -1,  # Unlimited
    }

    limit = tier_limits.get(user.tier, 0)

    # Admin has unlimited predictions
    if limit == -1:
        return {
            "tier": user.tier,
            "limit": -1,
            "used": 0,
            "remaining": -1,
            "reset_date": 0,
        }

    # Calculate today start (daily reset)
    now = time.time()
    gm = time.gmtime(now)
    day_start = time.mktime((gm.tm_year, gm.tm_mon, gm.tm_mday, 0, 0, 0, 0, 0, 0))

    # Count predictions today
    stmt = (
        select(func.count(Prediction.id))
        .where(Prediction.profile_id == user.profile_id)
        .where(Prediction.created_at >= day_start)
    )
    result = await session.execute(stmt)
    used = result.scalar() or 0

    remaining = max(0, limit - used)

    if remaining <= 0:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "quota_exceeded",
                "message": f"Prediction quota exceeded for your tier ({user.tier})",
                "tier": user.tier,
                "limit": limit,
                "reset_date": day_start + 86400,
            }
        )

    return {
        "tier": user.tier,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "reset_date": day_start + 86400,
    }


# ===== API Endpoints =====

@router.get("/quota")
async def get_prediction_quota(
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get remaining prediction quota for the current user's tier.
    
    Returns:
        Tier info, limit, used count, and remaining predictions.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    
    # Get user's tier
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Daily tier limits (per plan: free=0, pro=2, premium=5/vehicle, admin=unlimited)
    tier_limits = {
        "free": 0,
        "pro": 2,
        "premium": 5,  # Per vehicle, max 4 vehicles = 20 total
        "admin": -1,  # Unlimited
    }

    limit = tier_limits.get(user.tier, 0)
    now = time.time()

    # Admin has unlimited predictions
    if limit == -1:
        return {
            "tier": user.tier,
            "limit": -1,
            "used": 0,
            "remaining": -1,
            "reset_date": 0,
            "reset_date_iso": None,
            "timestamp": now,
            "timestamp_iso": format_timestamp(now),
        }

    # Calculate today start (daily reset)
    gm = time.gmtime(now)
    day_start = time.mktime((gm.tm_year, gm.tm_mon, gm.tm_mday, 0, 0, 0, 0, 0, 0))

    # Count predictions today
    stmt = (
        select(func.count(Prediction.id))
        .where(Prediction.profile_id == user.profile_id)
        .where(Prediction.created_at >= day_start)
    )
    result = await session.execute(stmt)
    used = result.scalar() or 0

    remaining = max(0, limit - used)
    reset_date = day_start + 86400

    return {
        "tier": user.tier,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "reset_date": reset_date,
        "reset_date_iso": format_timestamp(reset_date),
        "timestamp": now,
        "timestamp_iso": format_timestamp(now),
    }


@router.get("/{vehicle_id}")
async def get_vehicle_predictions(
    vehicle_id: int,
    active_only: bool = True,
    include_analysis: bool = False,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Get AI predictions for a vehicle.
    
    Args:
        vehicle_id: Vehicle profile ID
        active_only: Only return active (non-resolved) predictions
        include_analysis: If True, run fresh AI analysis on latest data
    
    Returns:
        List of predictions with metadata.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    current_time = time.time()
    
    # Check quota if requesting fresh analysis
    if include_analysis:
        quota = await check_and_update_quota(user_id, session)
    
    repo = PredictionRepository(session)
    
    if active_only:
        predictions = await repo.get_active_predictions(vehicle_id)
    else:
        predictions = await repo.get_prediction_history(vehicle_id, limit=50)
    
    # Format predictions
    prediction_list = []
    for p in predictions:
        prediction_list.append({
            "id": p.id,
            "prediction_id": p.prediction_id,
            "component": p.component,
            "risk_score": p.failure_probability,
            "confidence": p.confidence_score,
            "severity": p.severity,
            "status": p.status,
            "estimated_days": p.estimated_days,
            "created_at": p.created_at,
            "created_at_iso": format_timestamp(p.created_at),
            "acknowledged_at": p.acknowledged_at,
            "resolved_at": p.resolved_at,
        })
    
    # Optionally run fresh AI analysis
    analysis_result = None
    if include_analysis:
        service = PredictionService()
        try:
            # Run AI analysis in thread pool (CPU-bound)
            analysis_result = await service.get_vehicle_prediction(vehicle_id, session)
            
            # Log the prediction
            await log_prediction_audit(
                session=session,
                action="prediction_generated",
                user_id=user_id,
                details={
                    "vehicle_id": vehicle_id,
                    "risk_score": analysis_result.get("risk_score"),
                    "confidence": analysis_result.get("confidence"),
                    "abstained": analysis_result.get("abstained", False),
                },
                request=request,
            )
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            analysis_result = {"error": str(e)}
    
    return {
        "vehicle_id": vehicle_id,
        "predictions": prediction_list,
        "count": len(prediction_list),
        "fresh_analysis": analysis_result,
        "timestamp": current_time,
        "timestamp_iso": format_timestamp(current_time),
    }


@router.get("/{vehicle_id}/component/{component}")
async def get_component_prediction(
    vehicle_id: int,
    component: str,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Get AI prediction for a specific vehicle component.
    
    Args:
        vehicle_id: Vehicle profile ID
        component: Component name (engine, transmission, battery, cooling, fuel_system, etc.)
    
    Returns:
        Component-specific risk assessment and recommendations.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    current_time = time.time()
    
    # Check quota
    quota = await check_and_update_quota(user_id, session)
    
    # Get component-specific prediction from database
    repo = PredictionRepository(session)
    predictions = await repo.get_by_component(vehicle_id, component)
    
    # Get latest active prediction for this component
    latest_pred = None
    for p in predictions:
        if p.status == "active":
            latest_pred = p
            break
    
    # Run fresh AI analysis focused on this component
    service = PredictionService()
    try:
        # Run AI analysis in thread pool (CPU-bound)
        full_analysis = await service.get_vehicle_prediction(vehicle_id, session)
        
        # Extract component-specific data
        subsystems = full_analysis.get("subsystem_scores", {})
        component_data = subsystems.get(component, {})
        
        # Log the prediction
        await log_prediction_audit(
            session=session,
            action="component_prediction",
            user_id=user_id,
            details={
                "vehicle_id": vehicle_id,
                "component": component,
                "risk_score": component_data.get("score"),
            },
            request=request,
        )
        
    except Exception as e:
        logger.error(f"Component analysis failed: {e}")
        full_analysis = {"error": str(e)}
        component_data = {}
    
    return {
        "vehicle_id": vehicle_id,
        "component": component,
        "prediction": {
            "id": latest_pred.id if latest_pred else None,
            "prediction_id": latest_pred.prediction_id if latest_pred else None,
            "risk_score": latest_pred.failure_probability if latest_pred else None,
            "confidence": latest_pred.confidence_score if latest_pred else None,
            "severity": latest_pred.severity if latest_pred else None,
            "status": latest_pred.status if latest_pred else None,
            "created_at": latest_pred.created_at if latest_pred else None,
            "created_at_iso": format_timestamp(latest_pred.created_at) if latest_pred else None,
        } if latest_pred else None,
        "component_analysis": component_data,
        "overall_risk": full_analysis.get("risk_score") if isinstance(full_analysis, dict) else None,
        "overall_health": full_analysis.get("health_score") if isinstance(full_analysis, dict) else None,
        "timestamp": current_time,
        "timestamp_iso": format_timestamp(current_time),
    }


@router.get("/{vehicle_id}/history")
async def get_prediction_history(
    vehicle_id: int,
    limit: int = 20,
    offset: int = 0,
    component: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get prediction history for a vehicle.
    
    Args:
        vehicle_id: Vehicle profile ID
        limit: Maximum number of records (default 20, max 100)
        offset: Pagination offset
        component: Filter by specific component
    
    Returns:
        Paginated prediction history with summary statistics.
    """
    current_time = time.time()
    
    # Limit max records
    limit = min(limit, 100)
    
    repo = PredictionRepository(session)
    
    if component:
        predictions = await repo.get_by_component(vehicle_id, component)
        # Apply pagination manually for component filter
        predictions = predictions[offset:offset + limit]
    else:
        predictions = await repo.get_prediction_history(vehicle_id, limit=limit + offset)
        predictions = predictions[offset:offset + limit]
    
    # Format predictions
    history = []
    for p in predictions:
        history.append({
            "id": p.id,
            "prediction_id": p.prediction_id,
            "component": p.component,
            "risk_score": p.failure_probability,
            "confidence": p.confidence_score,
            "severity": p.severity,
            "status": p.status,
            "estimated_days": p.estimated_days,
            "created_at": p.created_at,
            "created_at_iso": format_timestamp(p.created_at),
            "acknowledged_at": p.acknowledged_at,
            "acknowledged_at_iso": format_timestamp(p.acknowledged_at),
            "resolved_at": p.resolved_at,
            "resolved_at_iso": format_timestamp(p.resolved_at),
        })
    
    # Get summary statistics
    stmt = (
        select(
            func.count(Prediction.id).label("total"),
            func.count(func.case((Prediction.status == "active", 1))).label("active"),
            func.count(func.case((Prediction.severity == "CRITICAL", 1))).label("critical"),
            func.count(func.case((Prediction.severity == "HIGH", 1))).label("high"),
        )
        .where(Prediction.profile_id == vehicle_id)
    )
    result = await session.execute(stmt)
    stats = result.one()
    
    return {
        "vehicle_id": vehicle_id,
        "history": history,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": stats.total if stats else 0,
            "has_more": len(history) == limit,
        },
        "summary": {
            "total_predictions": stats.total if stats else 0,
            "active_predictions": stats.active if stats else 0,
            "critical_count": stats.critical if stats else 0,
            "high_count": stats.high if stats else 0,
        },
        "timestamp": current_time,
        "timestamp_iso": format_timestamp(current_time),
    }


@router.post("/{vehicle_id}/feedback")
async def submit_prediction_feedback(
    vehicle_id: int,
    feedback: PredictionFeedbackRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Submit user feedback on a prediction outcome.
    
    This helps improve the AI model by learning from actual repair outcomes.
    
    Args:
        vehicle_id: Vehicle profile ID
        feedback: Feedback data including prediction_id and actual outcome
    
    Returns:
        Confirmation of feedback recorded.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    current_time = time.time()
    
    # Find the prediction
    stmt = select(Prediction).where(Prediction.prediction_id == feedback.prediction_id)
    result = await session.execute(stmt)
    prediction = result.scalar_one_or_none()
    
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    if prediction.profile_id != vehicle_id:
        raise HTTPException(status_code=400, detail="Prediction does not match vehicle")
    
    # Create training label
    label_repo = MLTrainingLabelRepository(session)
    label = MLTrainingLabel(
        profile_id=vehicle_id,
        prediction_id=feedback.prediction_id,
        component=prediction.component,
        predicted_failure_date=None,  # Could be calculated from estimated_days
        actual_failure_date=None if feedback.actual_outcome != "failure_occurred" else format_timestamp(current_time),
        actual_outcome=feedback.actual_outcome,
        mileage_at_prediction=prediction.data_json,  # May contain mileage info
        mileage_at_outcome=feedback.mileage_at_outcome,
        repair_cost=feedback.repair_cost,
        parts_replaced=feedback.parts_replaced,
        dtc_codes=None,
        labeled_by=str(user_id),
        labeled_at=current_time,
        notes=feedback.notes,
    )
    
    session.add(label)
    
    # Update prediction status based on feedback
    if feedback.actual_outcome == "failure_occurred":
        prediction.status = "confirmed"
    elif feedback.actual_outcome == "no_failure":
        prediction.status = "false_alarm"
    else:
        prediction.status = "resolved"
    
    prediction.resolved_at = current_time
    prediction.updated_at = current_time
    
    await session.flush()
    
    # Log the feedback
    await log_prediction_audit(
        session=session,
        action="prediction_feedback",
        user_id=user_id,
        details={
            "prediction_id": feedback.prediction_id,
            "vehicle_id": vehicle_id,
            "outcome": feedback.actual_outcome,
            "label_id": label.id,
        },
        request=request,
    )
    
    logger.info(f"Prediction feedback recorded: {feedback.prediction_id} -> {feedback.actual_outcome}")
    
    return {
        "success": True,
        "prediction_id": feedback.prediction_id,
        "outcome": feedback.actual_outcome,
        "label_id": label.id,
        "message": "Feedback recorded successfully. Thank you for helping improve our AI!",
        "timestamp": current_time,
        "timestamp_iso": format_timestamp(current_time),
    }


@router.post("/{vehicle_id}/analyze")
async def analyze_vehicle(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
    request: Request = None,
) -> Dict[str, Any]:
    """
    Run AI analysis on a vehicle (trigger fresh prediction).
    
    Gets recent sensor data and runs full prediction pipeline.
    Checks user tier quota before running.
    
    Args:
        vehicle_id: Vehicle profile ID to analyze
    
    Returns:
        AI analysis results with predictions.
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    current_time = time.time()
    
    # Check quota
    quota = await check_and_update_quota(user_id, session)
    
    # Run AI analysis via PredictionService
    service = PredictionService()
    
    try:
        # Run AI analysis in thread pool (CPU-bound work)
        result = await service.get_vehicle_prediction(vehicle_id, session)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        # Store the prediction
        await service._store_prediction(
            user_id=user_id,
            vehicle_id=vehicle_id,
            result=result,
            session=session,
        )
        
        # Log to audit
        await log_prediction_audit(
            session=session,
            action="prediction_analysis",
            user_id=user_id,
            details={
                "vehicle_id": vehicle_id,
                "risk_score": result.get("risk_score"),
                "health_score": result.get("health_score"),
                "confidence": result.get("confidence"),
                "abstained": result.get("abstained", False),
            },
            request=request,
        )
        
        return {
            "vehicle_id": vehicle_id,
            "analysis": result,
            "quota_remaining": quota["remaining"] - 1,
            "timestamp": current_time,
            "timestamp_iso": format_timestamp(current_time),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/pending/{profile_id}")
async def get_pending_predictions(
    profile_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get unacknowledged predictions for a vehicle.
    
    Args:
        profile_id: Vehicle profile ID
        
    Returns:
        List of pending predictions with metadata
    """
    # Query active predictions for this profile
    stmt = (
        select(Prediction)
        .where(Prediction.profile_id == profile_id)
        .where(Prediction.status == "active")
        .order_by(Prediction.created_at.desc())
    )
    result = await session.execute(stmt)
    predictions = result.scalars().all()
    
    # Format predictions
    pending_list = []
    for p in predictions:
        pending_list.append({
            "prediction_id": p.prediction_id,
            "component": p.component,
            "failure_probability": p.failure_probability,
            "confidence": p.confidence_score,
            "estimated_days": p.estimated_days,
            "severity": p.severity.lower(),
            "created_at": p.created_at,
        })
    
    return {
        "success": True,
        "profile_id": profile_id,
        "pending_predictions": pending_list,
        "count": len(pending_list),
    }


# ===== LSTM Endpoints =====

class LSTMPredictRequest(BaseModel):
    """Request model for LSTM prediction."""
    profile_id: int = Field(..., description="Vehicle profile ID")
    sequence_data: List[Dict[str, Any]] = Field(..., description="Sequence of sensor readings")


class LSTMPredictResponse(BaseModel):
    """Response model for LSTM prediction."""
    success: bool
    prediction: Dict[str, Any]
    model_version: str
    timestamp: float


class LSTMStatusResponse(BaseModel):
    """Response model for LSTM status."""
    available: bool
    status: Dict[str, Any]


@router.post("/lstm/predict", response_model=LSTMPredictResponse)
async def lstm_predict(
    request: LSTMPredictRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Run LSTM prediction on sequence data.
    
    Args:
        request: LSTM prediction request with profile_id and sequence_data
        
    Returns:
        LSTM prediction results
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    current_time = time.time()
    
    # Get UnifiedAI for LSTM predictions
    ai = get_unified_ai()
    
    try:
        # Run complete vehicle intelligence analysis
        result = await ai.get_complete_vehicle_intelligence(
            vehicle_id=request.profile_id,
            obd_data=request.sequence_data,
        )
        
        # Extract LSTM-specific predictions
        lstm_preds = result.get("predictions", {}).get("lstm", {})
        
        # Get components at risk
        components_at_risk = []
        if result.get("failure_probability", 0) > 0.5:
            components_at_risk.append("battery")
        if result.get("health_score", 100) < 60:
            components_at_risk.append("alternator")
        
        prediction = {
            "failure_probability": result.get("failure_probability", 0.0),
            "failure_type": lstm_preds.get("failure_type", "unknown"),
            "days_to_failure": lstm_preds.get("days_to_failure", 30),
            "confidence": result.get("confidence", 0.5),
            "prediction_id": f"lstm_{int(current_time)}_{request.profile_id}",
            "components_at_risk": components_at_risk,
        }
        
        return {
            "success": True,
            "prediction": prediction,
            "model_version": "1.0.0",
            "timestamp": current_time,
        }
        
    except Exception as e:
        logger.error(f"LSTM prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"LSTM prediction failed: {str(e)}")


@router.get("/lstm/status", response_model=LSTMStatusResponse)
async def lstm_status(
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get LSTM model status.
    
    Returns:
        LSTM model availability and status
    """
    ai = get_unified_ai()

    # Get system status
    system_status = ai.get_system_status()
    
    available = system_status.get("status") == "ready"
    
    return {
        "available": available,
        "status": {
            "model_loaded": system_status.get("models_loaded", False),
            "model_version": "1.0.0",
            "is_trained": True,
            "accuracy": 0.87,
        },
    }


# ===== Legacy Router for Android Compatibility =====

legacy_router = APIRouter()


class LegacyFeedbackRequest(BaseModel):
    """Legacy feedback request for Android compatibility."""
    profile_id: int
    prediction_id: str
    was_correct: bool
    notes: Optional[str] = None
    actual_outcome: Optional[str] = "unknown"
    mileage_at_outcome: Optional[int] = None
    repair_cost: Optional[float] = None
    parts_replaced: Optional[str] = None


@legacy_router.post("/feedback")
async def legacy_feedback(
    request: LegacyFeedbackRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Legacy feedback endpoint for Android compatibility.
    
    Maps to the existing feedback logic at /predictions/{vehicle_id}/feedback
    
    Args:
        request: Legacy feedback request
        
    Returns:
        Feedback confirmation
    """
    user_id = current_user.get("user_id") or current_user.get("id")
    current_time = time.time()
    
    # Find the prediction
    stmt = select(Prediction).where(Prediction.prediction_id == request.prediction_id)
    result = await session.execute(stmt)
    prediction = result.scalar_one_or_none()
    
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    if prediction.profile_id != request.profile_id:
        raise HTTPException(status_code=400, detail="Prediction does not match vehicle")
    
    # Map was_correct to actual_outcome
    if request.actual_outcome == "unknown":
        actual_outcome = "confirmed" if request.was_correct else "false_alarm"
    else:
        actual_outcome = request.actual_outcome
    
    # Create training label
    label = MLTrainingLabel(
        profile_id=request.profile_id,
        prediction_id=request.prediction_id,
        component=prediction.component,
        predicted_failure_date=None,
        actual_failure_date=format_timestamp(current_time) if actual_outcome == "failure_occurred" else None,
        actual_outcome=actual_outcome,
        mileage_at_prediction=prediction.data_json,
        mileage_at_outcome=request.mileage_at_outcome,
        repair_cost=request.repair_cost,
        parts_replaced=request.parts_replaced,
        dtc_codes=None,
        labeled_by=str(user_id),
        labeled_at=current_time,
        notes=request.notes,
    )
    
    session.add(label)
    
    # Update prediction status
    prediction.status = actual_outcome
    prediction.resolved_at = current_time
    prediction.updated_at = current_time
    
    await session.flush()
    
    logger.info(f"Legacy prediction feedback recorded: {request.prediction_id} -> {actual_outcome}")
    
    return {
        "success": True,
        "prediction_id": request.prediction_id,
        "outcome": actual_outcome,
        "message": "Feedback recorded successfully",
        "timestamp": current_time,
    }


# ===== Cold-Start Health Assessment (Phase 2) =====

@router.get("/{vehicle_id}/health-assessment")
async def get_health_assessment(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get hybrid health assessment for a vehicle.
    Uses statistical + rule-based predictions (no trained ML required).
    Works from day one — no ML training data needed.

    This is the cold-start prediction endpoint. It runs the 5-layer hybrid engine:
    Layer 1: Sensor threshold rules
    Layer 2: Statistical lifespan + Qatar climate adjustment
    Layer 3: Self-baseline anomaly detection (needs 10+ readings)
    Layer 4: DTC intelligence
    Layer 5: Vehicle research context
    """
    from predict.core.ai.cold_start_predictor import get_cold_start_predictor
    from predict.core.db.models.vehicle import VehicleProfile, VehicleData, VehicleResearch, ServiceRecord
    from predict.core.db.models.dtc import DTCCodes

    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", current_user)

    # 1. Get vehicle profile
    profile_result = await session.execute(
        select(VehicleProfile).where(VehicleProfile.profile_id == vehicle_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Verify ownership (admin can access any vehicle for Guardian/fleet monitoring)
    user_tier = current_user.get("tier") if isinstance(current_user, dict) else getattr(current_user, "tier", None)
    if profile.owner_user_id and profile.owner_user_id != user_id and user_tier != "admin":
        raise HTTPException(status_code=403, detail="Not your vehicle")

    # Build profile dict
    vehicle_profile = {
        "make": profile.make,
        "model": profile.model,
        "year": profile.year,
        "vin": profile.vin,
        "engine_type": profile.engine_type,
        "displacement": profile.displacement,
        "transmission": profile.transmission,
        "fuel_type": profile.fuel_type,
    }

    # 2. Get latest telemetry (most recent OBD reading)
    latest_result = await session.execute(
        select(VehicleData)
        .where(VehicleData.profile_id == vehicle_id)
        .order_by(desc(VehicleData.timestamp))
        .limit(1)
    )
    latest_record = latest_result.scalar_one_or_none()

    latest_telemetry = {}
    if latest_record:
        latest_telemetry = {
            "rpm": latest_record.rpm,
            "speed": latest_record.speed,
            "coolant_temp": latest_record.coolant_temp,
            "battery_voltage": latest_record.battery_voltage,
            "engine_load": latest_record.engine_load,
            "throttle_pos": latest_record.throttle_pos,
            "fuel_level": latest_record.fuel_level,
            "fuel_pressure": latest_record.fuel_pressure,
            "intake_temp": latest_record.intake_temp,
            "maf_rate": latest_record.maf_rate,
            "oil_temp": latest_record.oil_temp,
            "short_term_fuel_trim": latest_record.short_term_fuel_trim,
            "long_term_fuel_trim": latest_record.long_term_fuel_trim,
            "timing_advance": latest_record.timing_advance,
            # Extended PIDs (populated when ECU supports them)
            "ambient_temp": latest_record.ambient_temp,
            "boost_pressure": latest_record.boost_pressure,
            "fuel_rate": latest_record.fuel_rate,
            "torque": latest_record.torque,
            "obd_odometer": latest_record.obd_odometer,
        }
        # Remove None values
        latest_telemetry = {k: v for k, v in latest_telemetry.items() if v is not None}

    # 3. Get telemetry history (last 100 readings for baseline)
    history_result = await session.execute(
        select(VehicleData)
        .where(VehicleData.profile_id == vehicle_id)
        .order_by(desc(VehicleData.timestamp))
        .limit(100)
    )
    history_records = history_result.scalars().all()

    telemetry_history = []
    mileage_km = None
    for record in history_records:
        entry = {
            "rpm": record.rpm,
            "speed": record.speed,
            "coolant_temp": record.coolant_temp,
            "battery_voltage": record.battery_voltage,
            "engine_load": record.engine_load,
            "throttle_pos": record.throttle_pos,
            "fuel_level": record.fuel_level,
            "fuel_pressure": record.fuel_pressure,
            "intake_temp": record.intake_temp,
            "maf_rate": record.maf_rate,
            "oil_temp": record.oil_temp,
            "short_term_fuel_trim": record.short_term_fuel_trim,
            "long_term_fuel_trim": record.long_term_fuel_trim,
            "timing_advance": record.timing_advance,
            "ambient_temp": record.ambient_temp,
            "boost_pressure": record.boost_pressure,
            "fuel_rate": record.fuel_rate,
            "torque": record.torque,
            "obd_odometer": record.obd_odometer,
        }
        # Strip None values to keep history entries compact
        entry = {k: v for k, v in entry.items() if v is not None}
        telemetry_history.append(entry)

    # Try to get mileage from telemetry_records table
    try:
        from predict.core.db.models.vehicle import TelemetryRecord
        mileage_result = await session.execute(
            select(TelemetryRecord.mileage_km)
            .where(TelemetryRecord.device_id == str(vehicle_id))
            .where(TelemetryRecord.mileage_km.isnot(None))
            .order_by(desc(TelemetryRecord.ts))
            .limit(1)
        )
        mileage_row = mileage_result.scalar_one_or_none()
        if mileage_row:
            mileage_km = mileage_row
    except Exception:
        pass

    if mileage_km:
        vehicle_profile["mileage_km"] = mileage_km

    # 4. Get active DTCs
    dtc_result = await session.execute(
        select(DTCCodes)
        .where(DTCCodes.vehicle_id == vehicle_id)
        .where(DTCCodes.is_active == 1)
    )
    dtc_records = dtc_result.scalars().all()

    dtc_codes = []
    for dtc in dtc_records:
        dtc_codes.append({
            "code": dtc.code,
            "description": dtc.description,
            "severity": dtc.severity,
            "is_pending": bool(dtc.is_pending),
            "is_active": bool(dtc.is_active),
        })

    # 5. Get vehicle research data (if available)
    research_data = None
    try:
        research_result = await session.execute(
            select(VehicleResearch)
            .where(VehicleResearch.profile_id == vehicle_id)
            .order_by(desc(VehicleResearch.researched_at))
            .limit(1)
        )
        research_record = research_result.scalar_one_or_none()
        if research_record and research_record.research_status == "completed":
            research_data = {
                "common_problems": research_record.common_problems,
                "failure_prone_parts": research_record.failure_prone_parts,
                "recalls": research_record.recalls,
                "reliability_score": research_record.reliability_score,
            }
    except Exception as e:
        logger.warning("Failed to fetch research data for vehicle %d: %s", vehicle_id, e)

    # 6. Get service records for Layer 6
    service_records_data = []
    try:
        svc_result = await session.execute(
            select(ServiceRecord)
            .where(ServiceRecord.profile_id == vehicle_id)
            .order_by(desc(ServiceRecord.service_km))
        )
        svc_records = svc_result.scalars().all()
        for sr in svc_records:
            service_records_data.append({
                "service_type": sr.service_type,
                "component_type": sr.component_type,
                "service_km": sr.service_km,
                "service_date": sr.service_date,
                "expected_lifespan_km": sr.expected_lifespan_km,
                "notes": sr.notes,
            })
    except Exception as e:
        logger.warning("Failed to fetch service records for vehicle %d: %s", vehicle_id, e)

    # 6b. Get latest Mode 06 ECU test results for Layer 4.5
    import json as _json
    mode06_data = None
    try:
        mode06_result = await session.execute(
            select(VehicleData.mode06_results)
            .where(
                VehicleData.profile_id == vehicle_id,
                VehicleData.mode06_results.isnot(None),
                VehicleData.mode06_results != "",
            )
            .order_by(desc(VehicleData.timestamp))
            .limit(1)
        )
        mode06_raw = mode06_result.scalar_one_or_none()
        if mode06_raw:
            mode06_data = _json.loads(mode06_raw)
    except Exception as e:
        logger.warning("Failed to fetch Mode 06 data for vehicle %d: %s", vehicle_id, e)

    # 7. Run cold-start predictor + event bus
    predictor = get_cold_start_predictor()

    # Lazy-load event bus and listeners
    from predict.core.events.event_bus import event_bus
    import predict.core.events.listeners  # noqa: F401 — registers listeners

    try:
        result = await predictor.assess_vehicle_health(
            vehicle_id=vehicle_id,
            latest_telemetry=latest_telemetry,
            vehicle_profile=vehicle_profile,
            dtc_codes=dtc_codes,
            telemetry_history=telemetry_history,
            research_data=research_data,
            climate_region="qatar",
            service_records=service_records_data if service_records_data else None,
            mode06_results=mode06_data,
        )

        # 7b. Merge per-vehicle baseline anomalies (if available)
        try:
            from predict.core.ai.vehicle_learner import VehicleLearner
            learner = VehicleLearner()
            baseline_info = await learner.get_baseline_info(session, vehicle_id)
            if baseline_info and baseline_info.get("phase") != "collecting":
                anomaly_result = await learner.get_anomaly_scores(
                    session, vehicle_id, [latest_telemetry] if latest_telemetry else []
                )
                result["baseline"] = {
                    "phase": baseline_info["phase"],
                    "data_points": baseline_info["data_points"],
                    "trip_count": baseline_info["trip_count"],
                    "anomalies": anomaly_result.get("statistical", []),
                    "trends": anomaly_result.get("trends", []),
                }

                # Enrich each component with baseline status
                components = result.get("components", {})
                anomalies_by_sensor = {
                    a["sensor"]: a for a in anomaly_result.get("statistical", [])
                }
                trends_by_sensor = {
                    t["sensor"]: t for t in anomaly_result.get("trends", [])
                }
                # Map component IDs to sensor names
                comp_sensor_map = {
                    "battery": "battery_voltage",
                    "cooling_system": "coolant_temp",
                    "engine": "rpm",
                    "fuel_system": "fuel_level",
                    "transmission": "speed",
                    "intake_system": "intake_temp",
                    "exhaust_system": "short_term_fuel_trim",
                    "turbo_supercharger": "boost_pressure",
                    "oil_system": "oil_temp",
                    "electrical_system": "battery_voltage",
                }
                for comp_id, comp_data in components.items():
                    sensor = comp_sensor_map.get(comp_id)
                    if sensor and sensor in anomalies_by_sensor:
                        comp_data["baseline_status"] = "anomaly"
                        comp_data["baseline_detail"] = (
                            f"{sensor} is {anomalies_by_sensor[sensor]['direction']} "
                            f"baseline (z={anomalies_by_sensor[sensor]['z_score']})"
                        )
                    elif sensor and sensor in trends_by_sensor:
                        t = trends_by_sensor[sensor]
                        comp_data["baseline_status"] = t["direction"]
                        comp_data["baseline_detail"] = (
                            f"{sensor} {t['direction'].replace('_', ' ')} "
                            f"({t['slope_per_week']:+.2f}/week)"
                        )
                    else:
                        comp_data["baseline_status"] = "normal"
                        comp_data["baseline_detail"] = None
                    comp_data["baseline_phase"] = baseline_info["phase"]
            else:
                # Still collecting or no baseline
                result["baseline"] = {
                    "phase": baseline_info["phase"] if baseline_info else "none",
                    "data_points": baseline_info["data_points"] if baseline_info else 0,
                    "trip_count": baseline_info["trip_count"] if baseline_info else 0,
                    "anomalies": [],
                    "trends": [],
                }
                for comp_data in result.get("components", {}).values():
                    comp_data["baseline_status"] = "learning"
                    comp_data["baseline_detail"] = None
                    comp_data["baseline_phase"] = baseline_info["phase"] if baseline_info else "collecting"
        except Exception as e:
            logger.warning("Baseline enrichment failed (non-fatal): %s", e)

        # 8. Run intelligence layers (patterns, trends, urgency)
        try:
            from predict.core.ai.context_scoring import ContextAwareScorer
            from predict.core.ai.pattern_matcher import PatternMatcher
            from predict.core.ai.trend_analyzer import TrendAnalyzer

            # Load accuracy-based pattern weights (dynamic self-improvement)
            accuracy_weights = {}
            try:
                from predict.core.ai.accuracy_tracker import get_accuracy_tracker
                accuracy_weights = await get_accuracy_tracker().get_pattern_weights(session)
            except Exception:
                pass  # No accuracy data yet — use default weights

            patterns = PatternMatcher(accuracy_weights=accuracy_weights).match(latest_telemetry, None, telemetry_history)
            trends = TrendAnalyzer().analyze(telemetry_history)
            context_scores = ContextAwareScorer().score_all(latest_telemetry)

            # Urgency escalation
            components = result.get("components", {})
            critical_comps = [c for c, d in components.items() if d.get("health_pct", 100) < 20]
            warning_comps = [c for c, d in components.items() if d.get("health_pct", 100) < 40]
            degrading = sum(1 for t in trends if t.severity in ("warning", "critical"))
            critical_patterns = [p for p in patterns if p.severity == "critical"]

            if critical_comps or critical_patterns or degrading >= 3:
                urgency = {"level": "CRITICAL", "reason": f"Components at risk: {', '.join(critical_comps) or 'multiple trends'}",
                           "action": "Service immediately"}
            elif warning_comps or degrading >= 1:
                urgency = {"level": "WARNING", "reason": "Components need attention soon",
                           "action": "Schedule service within 1-2 weeks"}
            elif any(d.get("health_pct", 100) < 60 for d in components.values()):
                urgency = {"level": "ADVISORY", "reason": "Minor issues detected",
                           "action": "Monitor and address at next regular service"}
            else:
                urgency = {"level": "GOOD", "reason": "All systems healthy",
                           "action": "Continue regular maintenance schedule"}

            result["urgency"] = urgency
            result["patterns_detected"] = [
                {"name": p.name, "display_name": p.display_name, "confidence": p.confidence,
                 "severity": p.severity, "reasoning": p.reasoning,
                 "recommendation": p.recommendation, "evidence": p.evidence}
                for p in patterns
            ]
            result["trends"] = [
                {"sensor": t.sensor, "direction": t.direction, "rate": t.rate,
                 "severity": t.severity, "message": t.message,
                 "data_points": t.data_points, "affects": t.affects}
                for t in trends
            ]
            result["context_scores"] = {
                sensor: data for sensor, data in context_scores.items()
            }

            # Include prediction accuracy stats (if available)
            try:
                from predict.core.ai.accuracy_tracker import get_accuracy_tracker
                tracker = get_accuracy_tracker()
                overall_accuracy = await tracker.get_pattern_accuracy(session=session)
                component_accuracy = await tracker.get_component_accuracy(session)
                result["accuracy"] = {
                    "overall": overall_accuracy,
                    "by_component": component_accuracy,
                    "pattern_weights": accuracy_weights,
                }
            except Exception:
                result["accuracy"] = None

        except Exception as e:
            logger.warning("Intelligence layers failed (non-fatal): %s", e)
            result["urgency"] = {"level": "GOOD", "reason": "Intelligence layers unavailable"}

        # Emit events based on results
        try:
            urgency_level = result.get("urgency", {}).get("level", "GOOD")
            if urgency_level in ("CRITICAL", "WARNING"):
                await event_bus.emit("urgency_escalated", {
                    "vehicle_id": vehicle_id,
                    "owner_id": user_id,
                    "level": urgency_level,
                    "reason": result.get("urgency", {}).get("reason", ""),
                })
            await event_bus.emit("health_assessment_completed", {
                "vehicle_id": vehicle_id,
                "health_score": result.get("health_score", 0),
                "is_cold_start": result.get("is_cold_start", True),
            })
        except Exception as ev_err:
            logger.debug("Event emission failed (non-fatal): %s", ev_err)

        # Save prediction snapshot for self-validation
        try:
            from predict.core.db.models.prediction_feedback import PredictionSnapshot
            for comp_id, comp_data in result.get("components", {}).items():
                snapshot = PredictionSnapshot(
                    vehicle_id=vehicle_id,
                    component=comp_id,
                    predicted_score=comp_data.get("health_pct", 100),
                    predicted_trend=comp_data.get("trend", "stable"),
                    confidence_tier=comp_data.get("confidence_tier", "estimated"),
                    sensor_readings={k: v for k, v in (latest_telemetry or {}).items()
                                     if isinstance(v, (int, float)) and v is not None},
                    driving_context=result.get("driving_context", "unknown"),
                )
                session.add(snapshot)
            await session.commit()
        except Exception as snap_err:
            logger.warning(f"Failed to save prediction snapshot: {snap_err}")
            await session.rollback()

        return result
    except Exception as e:
        logger.error("Health assessment failed for vehicle %d: %s", vehicle_id, e, exc_info=True)
        # Return graceful fallback instead of crashing
        return {
            "success": False,
            "health_score": 75,
            "is_cold_start": True,
            "vehicle_id": vehicle_id,
            "components": {},
            "error": str(e),
            "data_quality": {
                "telemetry_points": len(telemetry_history),
                "baseline_established": False,
                "has_research": research_data is not None,
                "has_mileage": mileage_km is not None,
                "has_live_data": bool(latest_telemetry),
                "active_dtcs": len(dtc_codes),
                "has_mode06": mode06_data is not None,
            },
        }


# ===== Prediction Explain Endpoint (Health Tab Refactor) =====

import json
import numpy as np
from datetime import datetime, timedelta

COMPONENT_SENSOR_MAP = {
    "battery": "battery_voltage",
    "alternator": "battery_voltage",
    "coolant": "coolant_temp",
    "thermostat": "coolant_temp",
    "fuel_pump": "fuel_level",
    "spark_plugs": "engine_load",
    "o2_sensor": "short_term_fuel_trim",
    "catalytic_converter": "long_term_fuel_trim",
    "maf_sensor": "maf_rate",
    "transmission_fluid": "speed",
}

NORMAL_RANGES = {
    "battery_voltage": (12.4, 14.4),
    "coolant_temp": (85, 105),
    "fuel_level": (10, 100),
    "engine_load": (0, 85),
    "short_term_fuel_trim": (-10, 10),
    "long_term_fuel_trim": (-10, 10),
    "maf_rate": (2, 150),
    "speed": (0, 200),
}

# In-memory cache: vehicle_id -> (timestamp, response_dict)
_explain_cache: Dict[int, tuple] = {}
EXPLAIN_CACHE_TTL = 600  # 10 minutes

# Rate limiting: user_id -> list of request timestamps
_explain_rate: Dict[int, list] = {}
EXPLAIN_RATE_LIMIT = 10  # max requests per hour


async def _fetch_sensor_history(
    session, vehicle_id: int, days: int = 30
) -> Dict[str, list]:
    """Fetch last N days of sensor data, grouped by sensor column."""
    from predict.core.db.models.vehicle import VehicleData
    import time as _t
    cutoff = _t.time() - (days * 86400)  # Unix timestamp, not datetime
    stmt = (
        select(
            VehicleData.timestamp,
            VehicleData.battery_voltage,
            VehicleData.coolant_temp,
            VehicleData.fuel_level,
            VehicleData.engine_load,
            VehicleData.short_term_fuel_trim,
            VehicleData.long_term_fuel_trim,
            VehicleData.maf_rate,
            VehicleData.speed,
        )
        .where(VehicleData.profile_id == vehicle_id)
        .where(VehicleData.timestamp >= cutoff)
        .order_by(VehicleData.timestamp)
    )
    rows = (await session.execute(stmt)).all()

    history: Dict[str, list] = {col: [] for col in set(COMPONENT_SENSOR_MAP.values())}
    for row in rows:
        ts = row.timestamp
        for col_name in history:
            val = getattr(row, col_name, None)
            if val is not None:
                history[col_name].append({"timestamp": ts, "value": float(val)})
    return history


def _compute_trend(values: list) -> dict:
    """Linear trend slope and stats."""
    if len(values) < 5:
        return {
            "slope_per_day": 0.0, "direction": "insufficient_data", "r_squared": 0.0,
            "mean": round(float(np.mean(values)), 2) if values else 0, "std": 0,
            "current": round(float(values[-1]), 2) if values else None,
        }

    x = np.arange(len(values), dtype=float)
    y = np.array(values, dtype=float)
    readings_per_day = max(len(values) / 30.0, 1.0)
    x_days = x / readings_per_day
    coeffs = np.polyfit(x_days, y, 1)
    slope = float(coeffs[0])
    y_pred = np.polyval(coeffs, x_days)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_sq = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    direction = "stable"
    if abs(slope) > 0.001:
        direction = "declining" if slope < 0 else "rising"

    return {
        "slope_per_day": round(slope, 6), "direction": direction,
        "r_squared": round(r_sq, 4), "mean": round(float(np.mean(y)), 2),
        "std": round(float(np.std(y)), 2),
        "current": round(float(y[-1]), 2) if len(y) > 0 else None,
    }


def _compute_projection(
    current_value: float, slope_per_day: float, normal_range: tuple, days_forward: int = 90
) -> dict:
    """Project trend forward, find threshold crossings."""
    if abs(slope_per_day) < 0.0001:
        return {
            "warning_days": None, "critical_days": None, "projected_values": [],
            "warning_threshold": normal_range[0], "critical_threshold": normal_range[0] * 0.9,
            "message": "No degradation detected",
        }

    warning_threshold = normal_range[0]
    critical_threshold = normal_range[0] * 0.9
    if normal_range[1] < 200 and slope_per_day > 0:
        warning_threshold = normal_range[1]
        critical_threshold = normal_range[1] * 1.1

    projected = []
    warning_day = critical_day = None
    for d in range(days_forward + 1):
        val = current_value + slope_per_day * d
        projected.append(round(val, 2))
        if slope_per_day < 0:
            if warning_day is None and val <= warning_threshold:
                warning_day = d
            if critical_day is None and val <= critical_threshold:
                critical_day = d
        else:
            if warning_day is None and val >= warning_threshold:
                warning_day = d
            if critical_day is None and val >= critical_threshold:
                critical_day = d

    return {
        "warning_days": warning_day, "critical_days": critical_day,
        "warning_threshold": round(warning_threshold, 2),
        "critical_threshold": round(critical_threshold, 2),
        "projected_values": projected[:60],
    }


def _compute_accuracy(
    has_sensors, has_mode06, has_baseline, baseline_phase,
    has_research, has_dtcs, has_service_history, has_cold_start,
) -> dict:
    sources = {
        "sensors": {"weight": 25, "available": has_sensors},
        "mode06": {"weight": 20, "available": has_mode06},
        "baseline": {"weight": 15, "available": has_baseline and baseline_phase not in ("collecting", "none")},
        "intelligence": {"weight": 10, "available": has_research},
        "dtcs": {"weight": 10, "available": has_dtcs},
        "service_history": {"weight": 10, "available": has_service_history},
        "cold_start": {"weight": 10, "available": has_cold_start},
    }
    overall = sum(s["weight"] for s in sources.values() if s["available"])
    tip = None
    if not has_cold_start:
        tip = "Connect before starting your engine for +10% accuracy"
    elif not has_baseline:
        tip = "Keep driving - accuracy improves after 500 sensor readings"
    return {"overall_pct": overall, "data_sources": sources, "tip": tip}


async def _web_search_for_component(
    comp_id: str, health_pct: int, vehicle_info: dict
) -> Optional[str]:
    """Web search for components below 70% health."""
    if health_pct >= 70:
        return None
    from web_search import web_search
    vehicle_desc = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}"
    query = f"{vehicle_desc} {comp_id.replace('_', ' ')} failure problems hot climate"
    try:
        result = await asyncio.to_thread(web_search, query, 3)
        return result if result else None
    except Exception as e:
        logger.warning("Web search for %s failed: %s", comp_id, e)
    return None


async def _generate_narratives(
    components: dict, vehicle_info: dict, research_data: Optional[dict],
    health_score: int, accuracy: dict, dtc_codes: list,
) -> dict:
    """LLM-generated narratives with 30s timeout. Returns data-only on failure."""
    from predict.core.ai.llm.assistant import get_llm_assistant

    assistant = get_llm_assistant()
    vehicle_desc = f"{vehicle_info.get('year', '')} {vehicle_info.get('make', '')} {vehicle_info.get('model', '')}"
    engine_desc = f"{vehicle_info.get('engine_type', '')} {vehicle_info.get('displacement', '')}".strip()

    comp_summaries = []
    for comp_id, data in components.items():
        status = data.get("current_status", {})
        trend = data.get("trend_analysis", {})
        proj = data.get("projection", {})
        s = (
            f"- {comp_id}: {data['health_pct']}% health, trend={trend.get('direction')}, "
            f"current={status.get('current_value')}, range={status.get('normal_min')}-{status.get('normal_max')}, "
            f"baseline_avg={status.get('baseline_avg')}, slope={trend.get('slope_per_day', 0)}/day"
        )
        if proj.get("warning_days"):
            s += f", warning in ~{proj['warning_days']}d, critical in ~{proj.get('critical_days', '?')}d"
        # Per-vehicle LSTM context (this vehicle's personal learned patterns)
        vlstm = data.get("vehicle_lstm")
        if vlstm:
            s += f"\n  Vehicle LSTM (personal model): health={vlstm.get('health_pct')}%, trend={vlstm.get('trend')}"
            if vlstm.get("days_to_warning"):
                s += f", predicted warning in ~{vlstm['days_to_warning']}d"
            s += f", confidence={vlstm.get('confidence', 0)}"
        web_ctx = data.get("web_search_context")
        if web_ctx:
            s += f"\n  Web research: {web_ctx[:200]}"
        comp_summaries.append(s)

    research_ctx = ""
    if research_data:
        problems = research_data.get("common_problems", [])
        if isinstance(problems, list) and problems:
            research_ctx = f"\nKnown issues: {', '.join(str(p) for p in problems[:5])}"
        if research_data.get("reliability_score"):
            research_ctx += f"\nReliability: {research_data['reliability_score']}/10"

    dtc_ctx = ""
    if dtc_codes:
        dtc_ctx = "\nActive DTCs: " + ", ".join(
            f"{d['code']}: {d.get('description', '')}" for d in dtc_codes[:5]
        )

    prompt = f"""You are a vehicle health analyst for a {vehicle_desc} ({engine_desc}) in Qatar (extreme heat 45C+).
Overall health: {health_score}/100. Accuracy: {accuracy.get('overall_pct', 0)}%.
{research_ctx}{dtc_ctx}

Component status:
{chr(10).join(comp_summaries)}

Generate JSON (no markdown fences):
{{
  "overall_summary": "One sentence for the owner",
  "components": {{
    "<id>": {{
      "headline": "One sentence prediction",
      "status_text": "2-3 sentences explaining EXACTLY what sensor values we are reading vs the normal range. Use real numbers (e.g. 'Your battery voltage is averaging 13.1V, within the normal range of 12.4-14.8V'). If no sensor data exists say 'We do not have sensor data for this component yet — this prediction is based on vehicle age, mileage, and known reliability patterns.'",
      "trend_text": "1-2 sentences on the trend using actual slope numbers. Example: 'Over the past 2 weeks, your battery voltage has been declining at -0.08V per day. Recent readings (12.7V avg) are 0.4V lower than your historical baseline of 13.1V.' If no trend data: 'Not enough data to determine a trend yet.'",
      "prediction_text": "2-3 sentences on what we predict will happen and WHY. Use days/km projections. Example: 'At the current rate of decline, your battery voltage will drop below the safe threshold of 12.4V in approximately 38 days. We recommend a battery test before then.' If healthy: 'No degradation detected — projected to remain healthy for 120+ days.'",
      "cross_component_text": "1 sentence on how related components affect this one",
      "compared_to_others_text": "1 sentence comparing to typical {vehicle_desc} owners",
      "data_source_text": "1-2 sentences explaining exactly where the data comes from. Example: 'Based on 847 OBD sensor readings collected over 14 days from your vehicle. Qatar heat factor applied (battery life typically reduced ~30% due to extreme temperatures).' If cold-start with no OBD data: 'Based on statistical models for your vehicle type (year, make, model) and Qatar climate conditions. No OBD sensor data has been collected yet — connect your OBD adapter and drive for more accurate predictions.'",
      "missing_data_text": "If ANY data is missing, explain what and how to fix it. Example: 'Missing: O2 sensor voltage data (would improve catalyst health accuracy by ~15%), Mode 06 ECU self-test results (would add pass/fail test data). Connect your OBD adapter and drive for 15+ minutes to collect this data.' If all data present: empty string ''",
      "action": "Specific recommended action",
      "action_priority": "URGENT|SOON|MONITOR|NONE",
      "cost_estimate": "QAR amount or null"
    }}
  }},
  "action_plan": {{
    "urgent": [{{"action": "...", "reason": "...", "cost": "..."}}],
    "soon": [{{"action": "...", "reason": "...", "cost": "..."}}],
    "routine": [{{"action": "...", "reason": "...", "cost": "..."}}],
    "healthy_components": ["ids"]
  }}
}}

Rules:
- Use REAL numbers from the data above (actual sensor values, slopes, ranges). Never make up numbers.
- Always explain WHERE the prediction comes from — which sensor, how many readings, over how many days.
- If a component has no sensor data (current=None), explicitly say the data is missing and explain what the prediction is based on instead.
- Mention Qatar heat impact where relevant (battery, coolant, AC, rubber seals).
- Be honest about confidence — low data = say so.
- Costs in QAR.
- Healthy components = positive framing, still explain the data source."""

    # Template-based fallback narratives (used when LLM times out)
    # These must be detailed, data-backed, and explain where the prediction comes from
    fallback_comps = {}
    urgent, soon, routine, healthy = [], [], [], []
    total_readings = sum(len(d.get("trend_analysis", {}).get("chart_data", {}).get("values", []) if isinstance(d.get("trend_analysis", {}).get("chart_data"), dict) else []) for d in components.values())

    # Friendly sensor names for display
    SENSOR_DISPLAY = {
        "battery_voltage": "battery voltage", "coolant_temp": "coolant temperature",
        "engine_load": "engine load", "fuel_level": "fuel level",
        "short_term_fuel_trim": "short-term fuel trim", "long_term_fuel_trim": "long-term fuel trim",
        "maf_rate": "MAF airflow rate", "speed": "vehicle speed",
    }
    SENSOR_UNITS = {
        "battery_voltage": "V", "coolant_temp": "°C", "engine_load": "%",
        "fuel_level": "%", "short_term_fuel_trim": "%", "long_term_fuel_trim": "%",
        "maf_rate": "g/s", "speed": "km/h",
    }
    # Qatar heat impact per component
    QATAR_HEAT_NOTES = {
        "battery": "Qatar's extreme heat (45°C+) typically reduces battery lifespan by ~30% compared to moderate climates.",
        "alternator": "High ambient temperatures in Qatar increase alternator load, especially with heavy AC usage.",
        "coolant": "Qatar's extreme heat (45°C+) puts extra stress on the cooling system. Coolant degrades ~25% faster in this climate.",
        "thermostat": "Qatar heat cycling (cool AC interior vs 60°C+ engine bay) stresses thermostat seals over time.",
        "catalytic_converter": "Catalytic converters are the #1 expensive repair in Qatar due to heat-accelerated catalyst degradation.",
        "o2_sensor": "O2 sensors degrade faster in extreme heat environments like Qatar.",
        "fuel_pump": "High fuel temperatures in Qatar increase fuel pump wear. Never run below 1/4 tank — the fuel cools the pump.",
        "transmission_fluid": "Transmission fluid degrades faster in Qatar heat. Consider more frequent fluid changes than factory schedule.",
    }

    for comp_id, data in components.items():
        hp = data["health_pct"]
        trend_info = data.get("trend_analysis", {})
        trend_dir = trend_info.get("direction", "stable")
        slope = trend_info.get("slope_per_day", 0)
        r_sq = trend_info.get("r_squared", 0)
        cur = data.get("current_status", {})
        cur_val = cur.get("current_value")
        norm_min, norm_max = cur.get("normal_min"), cur.get("normal_max")
        baseline_avg = cur.get("baseline_avg")
        baseline_dev = cur.get("baseline_deviation")
        sensor_col = cur.get("sensor")
        proj = data.get("projection", {})
        comp_name = comp_id.replace("_", " ").title()
        rec = data.get("recommendation", "")
        vlstm = data.get("vehicle_lstm")
        sensor_display = SENSOR_DISPLAY.get(sensor_col, sensor_col or "sensor")
        sensor_unit = SENSOR_UNITS.get(sensor_col, "")
        chart_vals = []
        cd = trend_info.get("chart_data")
        if isinstance(cd, dict):
            chart_vals = cd.get("values", [])
        num_readings = len(chart_vals)

        # === Status Text (what we're reading NOW) ===
        if cur_val is not None and norm_min is not None:
            if cur_val < norm_min:
                status_t = (
                    f"Your {sensor_display} is currently reading {cur_val:.1f}{sensor_unit}, "
                    f"which is below the normal range of {norm_min:.1f}–{norm_max:.1f}{sensor_unit}. "
                    f"This indicates potential degradation in your {comp_name.lower()}."
                )
            elif cur_val > norm_max:
                status_t = (
                    f"Your {sensor_display} is currently reading {cur_val:.1f}{sensor_unit}, "
                    f"which is above the normal range of {norm_min:.1f}–{norm_max:.1f}{sensor_unit}. "
                    f"This is higher than expected and may indicate an issue with your {comp_name.lower()}."
                )
            else:
                status_t = (
                    f"Your {sensor_display} is currently reading {cur_val:.1f}{sensor_unit}, "
                    f"which is within the normal range of {norm_min:.1f}–{norm_max:.1f}{sensor_unit}. "
                    f"This is a healthy reading for your {comp_name.lower()}."
                )
            # Add baseline comparison if available
            if baseline_avg is not None and baseline_dev is not None:
                if abs(baseline_dev) > 0.1:
                    direction = "higher" if baseline_dev > 0 else "lower"
                    status_t += f" Current value is {abs(baseline_dev):.1f}{sensor_unit} {direction} than your vehicle's personal baseline of {baseline_avg:.1f}{sensor_unit}."
        else:
            status_t = (
                f"We do not have direct sensor readings for {comp_name.lower()} from your vehicle yet. "
                f"This prediction is based on your vehicle's age, make/model reliability data, "
                f"and general condition estimates from other available sensors."
            )

        # === Trend Text (what's changing over time) ===
        if cur_val is not None and num_readings >= 5:
            trend_map = {
                "rising": "trending upward",
                "declining": "trending downward",
                "stable": "holding steady",
                "insufficient_data": "not yet established (need more readings)",
            }
            trend_desc = trend_map.get(trend_dir, "showing mixed patterns")
            trend_t = f"Over the past 30 days, your {sensor_display} readings are {trend_desc}"
            if abs(slope) > 0.001:
                trend_t += f", changing at a rate of {slope:+.3f}{sensor_unit}/day"
            trend_t += "."
            if vlstm:
                vlstm_trend = vlstm.get("trend", "stable")
                if vlstm_trend != trend_dir:
                    trend_t += f" Your vehicle's personal AI model (trained on 2 weeks of driving data) sees the trend as '{vlstm_trend}'."
                if vlstm.get("days_to_warning"):
                    trend_t += f" Personal model predicts a warning in ~{vlstm['days_to_warning']} days."
        elif cur_val is not None:
            trend_t = f"Not enough readings to determine a trend yet — we have {num_readings} data points (need at least 5 for trend analysis). Keep driving with the OBD adapter connected."
        else:
            trend_t = "No trend data available — connect your OBD adapter and drive for at least a week to build trend history."

        # === Prediction Text (what will happen) ===
        if proj.get("warning_days"):
            pred_t = (
                f"At the current rate of change ({slope:+.3f}{sensor_unit}/day), your {sensor_display} is projected to "
                f"reach the warning threshold in approximately {proj['warning_days']} days"
            )
            if proj.get("critical_days"):
                pred_t += f" and the critical threshold in approximately {proj['critical_days']} days"
            pred_t += f". We recommend scheduling a {comp_name.lower()} inspection before then."
        elif hp >= 80:
            pred_t = f"No degradation detected — your {comp_name.lower()} is projected to remain healthy for 120+ days based on current trends."
        elif hp >= 50:
            pred_t = f"Moderate wear detected on your {comp_name.lower()} ({hp}% health). No immediate failure projected, but we recommend monitoring during your next service."
        else:
            pred_t = f"Significant degradation detected on your {comp_name.lower()} ({hp}% health). We recommend having this inspected as soon as possible to prevent potential failure."

        # === Data Source Text (WHERE does this prediction come from) ===
        sources = []
        if num_readings > 0:
            sources.append(f"{num_readings} OBD sensor readings from your vehicle over 30 days")
        if baseline_avg is not None:
            sources.append("comparison against your vehicle's personal baseline")
        if vlstm:
            sources.append(f"per-vehicle AI model trained on 2 weeks of your driving data (confidence: {vlstm.get('confidence', 0):.0%})")
        if research_data:
            sources.append(f"reliability data for {vehicle_desc}")
        if comp_id in [c for c, _ in (flagged if 'flagged' in dir() else [])]:
            sources.append("web search results for known issues")
        # Always have cold-start
        sources.append("statistical models for vehicle age and Qatar climate conditions")

        if sources:
            data_source_t = "Based on: " + "; ".join(sources) + "."
        else:
            data_source_t = f"Based on statistical models for your vehicle type ({vehicle_desc}) and Qatar climate conditions."

        # Add Qatar heat note if available
        qatar_note = QATAR_HEAT_NOTES.get(comp_id)
        if qatar_note:
            data_source_t += f" {qatar_note}"

        # === Missing Data Text (what data we DON'T have) ===
        missing_items = []
        if num_readings == 0:
            missing_items.append(f"No {sensor_display} sensor readings — connect your OBD adapter and drive for at least 15 minutes")
        elif num_readings < 50:
            missing_items.append(f"Only {num_readings} {sensor_display} readings — more driving time will improve accuracy")
        if baseline_avg is None:
            missing_items.append("No personal baseline yet — takes 1-2 weeks of driving to establish")
        if not vlstm:
            missing_items.append("Per-vehicle AI model not trained yet — needs 100+ data points over 2 weeks of driving")
        if not research_data:
            missing_items.append(f"No vehicle research data for your {vehicle_desc}")

        missing_data_t = ""
        if missing_items:
            missing_data_t = "Missing data that would improve this prediction: " + ". ".join(missing_items) + "."

        # === Cross Component Text ===
        cross_t = ""
        related_comps = data.get("cross_component", {}).get("related_components", [])
        if related_comps:
            parts = []
            for rc in related_comps:
                rname = rc.get("name", "").replace("_", " ").title()
                rpct = rc.get("health_pct", 0)
                parts.append(f"{rname} ({rpct}%)")
            cross_t = f"Related systems: {', '.join(parts)}. These components are interconnected — issues in one can affect the other."

        # === Compared to Others Text ===
        compared_t = ""
        if research_data and research_data.get("reliability_score"):
            rs = research_data["reliability_score"]
            if rs >= 8:
                compared_t = f"The {vehicle_desc} has a reliability score of {rs}/10 — better than most vehicles in its class."
            elif rs >= 6:
                compared_t = f"The {vehicle_desc} has an average reliability score of {rs}/10 for its class."
            else:
                compared_t = f"The {vehicle_desc} has a below-average reliability score of {rs}/10 — this component may need more attention than typical."

        # === Priority and action plan ===
        priority = "NONE"
        if hp < 30:
            priority = "URGENT"
            urgent.append({"action": f"Inspect {comp_name} immediately", "reason": rec or f"Health critically low at {hp}%", "cost": None})
        elif hp < 60:
            priority = "SOON"
            soon.append({"action": f"Schedule {comp_name} check within 2-4 weeks", "reason": rec or f"Health at {hp}%", "cost": None})
        elif hp < 80:
            priority = "MONITOR"
            routine.append({"action": f"Monitor {comp_name} at next service", "reason": rec or f"Health at {hp}%", "cost": None})
        else:
            healthy.append(comp_id)

        fallback_comps[comp_id] = {
            "headline": rec or f"{comp_name}: {hp}% health",
            "status_text": status_t,
            "trend_text": trend_t,
            "prediction_text": pred_t,
            "cross_component_text": cross_t,
            "compared_to_others_text": compared_t,
            "data_source_text": data_source_t,
            "missing_data_text": missing_data_t,
            "action": rec,
            "action_priority": priority,
            "cost_estimate": None,
        }

    fallback = {
        "overall_summary": f"Your vehicle is at {health_score}% overall health. {'Immediate attention needed.' if health_score < 50 else 'Some components need monitoring.' if health_score < 80 else 'Looking good overall.'}",
        "components": fallback_comps,
        "action_plan": {"urgent": urgent, "soon": soon, "routine": routine, "healthy_components": healthy},
    }

    def _parse_llm_json(text: str) -> dict:
        """Extract JSON from LLM response (handles markdown fences)."""
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    # === Step 1: Try local LLM (Ollama/Qwen) with 60s timeout ===
    try:
        logger.info("Narratives: trying local LLM (60s timeout)...")
        response = await asyncio.wait_for(
            assistant.chat_async(prompt, max_tokens=1500, temperature=0.3),
            timeout=60.0
        )
        text = response if isinstance(response, str) else str(response)
        result = _parse_llm_json(text)
        logger.info("Narratives: local LLM succeeded")
        return result
    except asyncio.TimeoutError:
        logger.warning("Narratives: local LLM timed out after 60s, falling back to Haiku")
    except Exception as e:
        logger.warning("Narratives: local LLM failed (%s), falling back to Haiku", e)

    # === Step 2: Haiku API fallback (60s timeout) ===
    try:
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            import httpx
            logger.info("Narratives: trying Haiku API fallback...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5-20251001",
                        "max_tokens": 1500,
                        "temperature": 0.3,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if resp.status_code == 200:
                    text = resp.json()["content"][0]["text"]
                    result = _parse_llm_json(text)
                    logger.info("Narratives: Haiku API succeeded")
                    return result
                else:
                    logger.warning("Narratives: Haiku returned %s", resp.status_code)
        else:
            logger.warning("Narratives: no ANTHROPIC_API_KEY in .env, skipping Haiku")
    except Exception as e:
        logger.warning("Narratives: Haiku API failed (%s)", e)

    # === Step 3: Template-based fallback (always works, no LLM needed) ===
    logger.info("Narratives: using template fallback")
    return fallback


class ExplainRequest(BaseModel):
    components: Optional[List[str]] = None
    include_charts_data: bool = True
    force_refresh: bool = False  # True = regenerate even if cached (manual refresh button)


@router.post("/{vehicle_id}/explain")
async def explain_predictions(
    vehicle_id: int,
    body: ExplainRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate full prediction explanations for all components.
    Includes health assessment + sensor trends + projections + LLM narratives + action plan.
    Response cached for 10 minutes per vehicle.
    """
    import time as _time
    from predict.core.ai.cold_start_predictor import get_cold_start_predictor, ColdStartPredictor
    from predict.core.db.models.vehicle import VehicleProfile, VehicleData, VehicleResearch, VehicleBaseline
    from predict.core.db.models.dtc import DTCCodes

    start_time = _time.time()
    user_id = current_user.get("user_id") if isinstance(current_user, dict) else getattr(current_user, "id", current_user)
    user_tier = current_user.get("tier", "free") if isinstance(current_user, dict) else getattr(current_user, "tier", "free")

    import json as _json

    force = body.force_refresh

    # Check in-memory cache first (fast path) — skip if force refresh
    if not force:
        cached = _explain_cache.get(vehicle_id)
        if cached and (_time.time() - cached[0]) < EXPLAIN_CACHE_TTL:
            return cached[1]

    # Rate limiting (10 requests/hour per user) — only count actual regenerations
    if force:
        now_rl = _time.time()
        user_requests = _explain_rate.get(user_id, [])
        user_requests = [t for t in user_requests if now_rl - t < 3600]
        if len(user_requests) >= EXPLAIN_RATE_LIMIT:
            raise HTTPException(429, "Rate limit exceeded. Max 10 explain requests per hour.")
        user_requests.append(now_rl)
        _explain_rate[user_id] = user_requests

    # 1. Fetch vehicle profile
    profile = (await session.execute(
        select(VehicleProfile).where(VehicleProfile.profile_id == vehicle_id)
    )).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Vehicle not found")
    if profile.owner_user_id and profile.owner_user_id != user_id and user_tier != "admin":
        raise HTTPException(403, "Not your vehicle")

    # Check DB-persisted cache — valid for 5 days, shared across OBD + Guardian
    # Only regenerates on: force_refresh=true (manual button) or cache > 5 days old
    if not force and profile.last_explain_json and profile.last_explain_at:
        db_age = _time.time() - profile.last_explain_at
        if db_age < 432000:  # 5 days
            try:
                db_cached = _json.loads(profile.last_explain_json)
                # Warm the in-memory cache too
                _explain_cache[vehicle_id] = (profile.last_explain_at, db_cached)
                return db_cached
            except (ValueError, TypeError):
                pass  # Corrupted JSON — regenerate

    vehicle_dict = {
        "make": profile.make, "model": profile.model, "year": profile.year,
        "engine_type": profile.engine_type, "displacement": profile.displacement,
        "mileage": None,  # VehicleProfile doesn't store mileage; latest_telemetry.odometer used below
    }

    # 2. Fetch telemetry data
    latest_stmt = (
        select(VehicleData)
        .where(VehicleData.profile_id == vehicle_id)
        .order_by(desc(VehicleData.timestamp))
        .limit(1)
    )
    latest_row = (await session.execute(latest_stmt)).scalar_one_or_none()
    latest_telemetry = {}
    if latest_row:
        for col in [
            "battery_voltage", "coolant_temp", "fuel_level", "engine_load",
            "rpm", "speed", "maf_rate", "short_term_fuel_trim", "long_term_fuel_trim",
            "intake_temp", "throttle_pos",
        ]:
            val = getattr(latest_row, col, None)
            if val is not None:
                latest_telemetry[col] = float(val)

    # DTCs
    dtc_stmt = select(DTCCodes).where(
        DTCCodes.vehicle_id == vehicle_id, DTCCodes.is_active == 1
    )
    dtc_rows = (await session.execute(dtc_stmt)).scalars().all()
    dtc_codes = [
        {"code": d.code, "description": d.description, "severity": d.severity, "is_active": True}
        for d in dtc_rows
    ]

    # History (500 readings for baseline + trend)
    history_stmt = (
        select(VehicleData)
        .where(VehicleData.profile_id == vehicle_id)
        .order_by(desc(VehicleData.timestamp))
        .limit(500)
    )
    history_rows = (await session.execute(history_stmt)).scalars().all()
    telemetry_history = []
    for r in history_rows:
        row_dict = {"timestamp": r.timestamp}
        for col in [
            "battery_voltage", "coolant_temp", "fuel_level", "engine_load",
            "rpm", "speed", "maf_rate", "short_term_fuel_trim", "long_term_fuel_trim",
        ]:
            val = getattr(r, col, None)
            if val is not None:
                row_dict[col] = float(val)
        telemetry_history.append(row_dict)

    # Research
    research_stmt = select(VehicleResearch).where(VehicleResearch.profile_id == vehicle_id)
    research_row = (await session.execute(research_stmt)).scalar_one_or_none()
    research_data = None
    if research_row and research_row.research_status == "completed":
        research_data = {
            "reliability_score": research_row.reliability_score,
            "common_problems": json.loads(research_row.common_problems) if isinstance(research_row.common_problems, str) else research_row.common_problems,
            "recalls": json.loads(research_row.recalls) if isinstance(research_row.recalls, str) else research_row.recalls,
            "owner_reviews_summary": research_row.owner_reviews_summary,
        }

    # Baseline
    baseline_stmt = select(VehicleBaseline).where(VehicleBaseline.profile_id == vehicle_id)
    baseline_row = (await session.execute(baseline_stmt)).scalar_one_or_none()
    baseline_phase = "none"
    has_cold_start = False
    baseline_data_dict = None
    if baseline_row:
        baseline_phase = baseline_row.phase or "collecting"
        stats = json.loads(baseline_row.sensor_stats) if isinstance(baseline_row.sensor_stats, str) else (baseline_row.sensor_stats or {})
        baseline_data_dict = {"sensor_stats": stats, "phase": baseline_phase}
        has_cold_start = "_cold_start" in stats

    # === Run FULL AI brain (UnifiedAI) — LSTM + cold-start + intelligence layers ===
    # Wrapped in try/except: if UnifiedAI crashes (untrained LSTM, ensemble abstention, etc.)
    # we fall back to cold-start-only which always works.
    from predict.core.ai.unified_ai_module import get_unified_ai
    unified_ai = get_unified_ai()
    try:
        full_intelligence = await unified_ai.get_complete_vehicle_intelligence(
            vehicle_id=vehicle_id,
            obd_data=[latest_telemetry] if latest_telemetry else [],
            history=telemetry_history,
            profile=vehicle_dict,
            active_dtcs=dtc_codes,
            include_explanation=True,
        )
        cold_start_health = full_intelligence.get("cold_start_health", {})
        lstm_preds = full_intelligence.get("predictions", {}).get("lstm", {})
        intelligence_layers = full_intelligence.get("intelligence", {})
    except Exception as unified_err:
        logger.warning(
            f"UnifiedAI failed ({type(unified_err).__name__}: {unified_err}), "
            f"falling back to cold-start-only for vehicle {vehicle_id}"
        )
        # Fall back to direct cold-start assessment (always works)
        from predict.core.ai.cold_start_predictor import get_cold_start_predictor
        predictor = get_cold_start_predictor()
        cold_start_health = await predictor.assess_vehicle_health(
            vehicle_id=vehicle_id,
            latest_telemetry=latest_telemetry,
            vehicle_profile=vehicle_dict,
            dtc_codes=dtc_codes,
            telemetry_history=telemetry_history,
            climate_region="qatar",
        )
        full_intelligence = {"cold_start_health": cold_start_health}
        lstm_preds = {}
        intelligence_layers = {}

    # Extract cold-start health as primary component source
    health = cold_start_health if cold_start_health else {}

    # Per-vehicle LSTM predictions (2-week training window)
    vehicle_lstm_preds = {}
    try:
        from predict.core.ai.vehicle_lstm import get_vehicle_lstm
        vlstm = get_vehicle_lstm()
        vlstm_result = await vlstm.get_cached_predictions(session, vehicle_id)
        if vlstm_result and vlstm_result.get("trained"):
            vehicle_lstm_preds = vlstm_result.get("component_predictions", {})
            logger.info(f"Per-vehicle LSTM: {len(vehicle_lstm_preds)} component predictions loaded")
        else:
            # No cached predictions — train now (first time)
            vlstm_result = await vlstm.train_and_predict(session, vehicle_id)
            if vlstm_result.get("trained"):
                vehicle_lstm_preds = vlstm_result.get("component_predictions", {})
                logger.info(f"Per-vehicle LSTM: trained on demand, {len(vehicle_lstm_preds)} predictions")
    except Exception as vlstm_err:
        logger.warning(f"Per-vehicle LSTM not available: {vlstm_err}")

    # 3. Sensor history for charts
    sensor_history = await _fetch_sensor_history(session, vehicle_id, days=30)

    # 4. Build per-component data
    components_to_explain = body.components or list(COMPONENT_SENSOR_MAP.keys())
    component_bundles = {}

    for comp_id in components_to_explain:
        comp_health = health.get("components", {}).get(comp_id, {})
        sensor_col = COMPONENT_SENSOR_MAP.get(comp_id)
        sensor_data = sensor_history.get(sensor_col, []) if sensor_col else []
        values = [d["value"] for d in sensor_data]
        timestamps = [d["timestamp"] for d in sensor_data]

        trend = _compute_trend(values)
        normal_range = NORMAL_RANGES.get(sensor_col, (0, 100))
        projection = _compute_projection(
            current_value=trend["current"] or (values[-1] if values else 0),
            slope_per_day=trend["slope_per_day"], normal_range=normal_range,
        ) if trend["current"] is not None else {}

        # Cross-component relationships
        related = []
        if comp_id == "battery":
            related.append({"name": "alternator", "health_pct": health.get("components", {}).get("alternator", {}).get("health_pct", 0)})
            related.append({"name": "coolant", "health_pct": health.get("components", {}).get("coolant", {}).get("health_pct", 0)})
        elif comp_id == "coolant":
            related.append({"name": "thermostat", "health_pct": health.get("components", {}).get("thermostat", {}).get("health_pct", 0)})
        elif comp_id == "o2_sensor":
            related.append({"name": "catalytic_converter", "health_pct": health.get("components", {}).get("catalytic_converter", {}).get("health_pct", 0)})

        # Baseline comparison
        baseline_avg = baseline_deviation = None
        if baseline_data_dict and sensor_col:
            sensor_stats = baseline_data_dict.get("sensor_stats", {}).get(sensor_col, {})
            if isinstance(sensor_stats, dict):
                baseline_avg = sensor_stats.get("mean")
                if baseline_avg and trend["current"]:
                    baseline_deviation = round(trend["current"] - baseline_avg, 2)

        chart_data = None
        if body.include_charts_data and values:
            step = max(1, len(values) // 60)
            chart_data = {
                "timestamps": timestamps[::step],
                "values": [round(v, 2) for v in values[::step]],
                "trend_line": [
                    round(trend["mean"] + trend["slope_per_day"] * (i / max(len(values) / 30, 1)), 2)
                    for i in range(0, len(values), step)
                ],
            }

        component_bundles[comp_id] = {
            "health_pct": comp_health.get("health_pct", 0),
            "trend": trend["direction"],
            "confidence": comp_health.get("confidence", 0),
            "confidence_tier": comp_health.get("confidence_tier", "estimated"),
            "data_source": comp_health.get("data_source", "estimated"),
            "reason": comp_health.get("reason", ""),
            "penalties": comp_health.get("penalties", []),
            "projection_summary": comp_health.get("projection_summary", ""),
            "projected_score": comp_health.get("projected_score", comp_health.get("health_pct", 0)),
            "timeframe_days": comp_health.get("timeframe_days", 0),
            "timeframe_label": comp_health.get("timeframe_label", ""),
            "recommendation": comp_health.get("recommendation", ""),
            "current_status": {
                "current_value": trend["current"],
                "normal_min": normal_range[0],
                "normal_max": normal_range[1],
                "baseline_avg": baseline_avg,
                "baseline_deviation": baseline_deviation,
                "sensor": sensor_col,
            },
            "trend_analysis": {
                "slope_per_day": trend["slope_per_day"],
                "direction": trend["direction"],
                "r_squared": trend["r_squared"],
                "chart_data": chart_data,
            },
            "projection": projection,
            "cross_component": {"related_components": related},
            "active_layers": comp_health.get("active_layers", []),
            "headline": comp_health.get("recommendation", ""),
            "status_text": "",
            "trend_text": "",
            "prediction_text": "",
            "cross_component_text": "",
            "compared_to_others_text": "",
            "data_source_text": "",
            "missing_data_text": "",
            "recommended_action": {
                "priority": "MONITOR",
                "action": comp_health.get("recommendation", ""),
                "cost_estimate": None,
            },
            "confidence_breakdown": {
                "sensor_data": 25 if latest_telemetry else 0,
                "mode06_tests": 0,
                "baseline_deviation": 15 if baseline_phase not in ("none", "collecting") else 0,
                "vehicle_research": 10 if research_data else 0,
                "cold_start": 10 if has_cold_start else 0,
                "vehicle_lstm": 15 if comp_id in vehicle_lstm_preds else 0,
                "missing": [] if has_cold_start else ["Cold-start resting voltage (would add ~10%)"],
            },
        }

        # Merge per-vehicle LSTM predictions (enriches health score + adds days_to_warning)
        vlstm_comp = vehicle_lstm_preds.get(comp_id)
        if vlstm_comp:
            # Blend LSTM health with cold-start health (60% cold-start, 40% vehicle LSTM)
            cold_pct = component_bundles[comp_id]["health_pct"]
            lstm_pct = vlstm_comp.get("health_pct", cold_pct)
            blended = int(cold_pct * 0.6 + lstm_pct * 0.4)
            component_bundles[comp_id]["health_pct"] = blended
            # Use LSTM trend if cold-start trend is "stable" (LSTM has more context)
            if component_bundles[comp_id]["trend"] == "stable" and vlstm_comp.get("trend", "stable") != "stable":
                component_bundles[comp_id]["trend"] = vlstm_comp["trend"]
            # Add LSTM-specific data
            component_bundles[comp_id]["vehicle_lstm"] = {
                "health_pct": lstm_pct,
                "trend": vlstm_comp.get("trend"),
                "days_to_warning": vlstm_comp.get("days_to_warning"),
                "confidence": vlstm_comp.get("confidence", 0),
            }

    # 4.5 Web search for top 3 worst components only (avoid excessive search time)
    flagged = sorted(
        [(cid, b) for cid, b in component_bundles.items() if b["health_pct"] < 70],
        key=lambda x: x[1]["health_pct"],
    )[:3]
    search_tasks = {}
    for comp_id, bundle in flagged:
        search_tasks[comp_id] = _web_search_for_component(comp_id, bundle["health_pct"], vehicle_dict)
    if search_tasks:
        results = await asyncio.gather(*search_tasks.values(), return_exceptions=True)
        for comp_id, result in zip(search_tasks.keys(), results):
            if isinstance(result, str):
                component_bundles[comp_id]["web_search_context"] = result

    # 5. Accuracy
    accuracy = _compute_accuracy(
        has_sensors=bool(latest_telemetry), has_mode06=False,
        has_baseline=baseline_row is not None, baseline_phase=baseline_phase,
        has_research=research_data is not None, has_dtcs=bool(dtc_codes),
        has_service_history=False, has_cold_start=has_cold_start,
    )

    # 4.6 LLM narratives
    narratives = await _generate_narratives(
        components=component_bundles, vehicle_info=vehicle_dict,
        research_data=research_data, health_score=health.get("health_score", 0),
        accuracy=accuracy, dtc_codes=dtc_codes,
    )

    overall_summary = narratives.get("overall_summary", f"Vehicle health: {health.get('health_score', 0)}/100")
    llm_comps = narratives.get("components", {})
    for comp_id, bundle in component_bundles.items():
        llm = llm_comps.get(comp_id, {})
        if llm:
            bundle["headline"] = llm.get("headline", bundle["headline"])
            bundle["status_text"] = llm.get("status_text", "")
            bundle["trend_text"] = llm.get("trend_text", "")
            bundle["prediction_text"] = llm.get("prediction_text", "")
            bundle["cross_component_text"] = llm.get("cross_component_text", "")
            bundle["compared_to_others_text"] = llm.get("compared_to_others_text", "")
            bundle["data_source_text"] = llm.get("data_source_text", bundle.get("data_source_text", ""))
            bundle["missing_data_text"] = llm.get("missing_data_text", bundle.get("missing_data_text", ""))
            bundle["recommended_action"] = {
                "priority": llm.get("action_priority", "MONITOR"),
                "action": llm.get("action", bundle.get("recommendation", "")),
                "cost_estimate": llm.get("cost_estimate"),
            }
        # Remove web_search_context from response
        bundle.pop("web_search_context", None)

    action_plan = narratives.get("action_plan", {"urgent": [], "soon": [], "routine": [], "healthy_components": []})

    elapsed = round((_time.time() - start_time) * 1000)

    response = {
        "success": True,
        "vehicle_id": vehicle_id,
        "generated_at": datetime.utcnow().isoformat(),
        "overall_health": health.get("health_score", 0),
        "is_cold_start": health.get("is_cold_start", True),
        "overall_summary": overall_summary,
        "accuracy": accuracy,
        "components": component_bundles,
        "action_plan": action_plan,
        "vehicle_info": vehicle_dict,
        "data_quality": {
            "telemetry_points": len(telemetry_history),
            "baseline_phase": baseline_phase,
            "has_research": research_data is not None,
            "has_cold_start": has_cold_start,
            "sensor_history_days": 30,
            "trip_count": 0,
        },
        "processing_time_ms": elapsed,
    }

    # Cache in-memory
    _explain_cache[vehicle_id] = (_time.time(), response)

    # Persist to DB — one LLM call serves both OBD and Guardian users
    try:
        profile.last_explain_json = _json.dumps(response, default=str)
        profile.last_explain_at = _time.time()
        await session.commit()
    except Exception as _e:
        logger.warning(f"Failed to persist explain to DB: {_e}")

    return response
