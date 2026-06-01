"""
Driving behavior API routes.

Handles driving score calculation, trip tracking, and safety recommendations.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func

from predict.core.db.session import get_db as get_db_session
from predict.core.security.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models
class DrivingEventRequest(BaseModel):
    event_type: str  # harsh_brake, rapid_acceleration, speeding, sharp_turn
    severity: str  # low, medium, high
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[float] = None


@router.post("/event/{vehicle_id}")
async def record_driving_event(
    vehicle_id: int,
    request: DrivingEventRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Record a driving event (harsh brake, rapid acceleration, etc.)."""
    user_id = current_user.get("id")
    
    # Verify vehicle ownership
    from predict.core.db.models.vehicle import VehicleProfile
    
    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == vehicle_id,
        VehicleProfile.owner_user_id == user_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(
            status_code=403, detail="Vehicle not found or not authorized"
        )
    
    from predict.core.db.models.guardian import DrivingEvent
    
    current_time = time.time()
    
    event = DrivingEvent(
        vehicle_id=vehicle_id,
        event_type=request.event_type,
        severity=request.severity,
        latitude=request.latitude,
        longitude=request.longitude,
        speed=request.speed,
        timestamp=current_time,
        created_at=current_time,
        updated_at=current_time,
    )
    
    session.add(event)
    await session.flush()
    
    logger.info(
        f"Driving event recorded: {request.event_type} for vehicle {vehicle_id}"
    )
    
    return {
        "status": "success",
        "event_id": event.id,
        "timestamp": current_time,
    }


@router.get("/score/{vehicle_id}")
async def get_driving_score(
    vehicle_id: int,
    period_days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get driving behavior score for a vehicle."""
    user_id = current_user.get("id")
    user_tier = current_user.get("tier", "free")

    # Verify vehicle ownership (admin can view any vehicle in their fleet)
    from predict.core.db.models.vehicle import VehicleProfile

    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == vehicle_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()

    if not vehicle:
        raise HTTPException(
            status_code=404, detail="Vehicle not found"
        )

    # Non-admin users can only view their own vehicles
    if vehicle.owner_user_id != user_id and user_tier not in ("admin", "premium"):
        raise HTTPException(
            status_code=403, detail="Vehicle not found or not authorized"
        )
    
    # Calculate score from events
    from predict.core.db.models.guardian import DrivingEvent
    
    cutoff_time = time.time() - (period_days * 86400)
    
    # Count events by type and severity
    stmt = (
        select(
            DrivingEvent.event_type,
            DrivingEvent.severity,
            func.count(DrivingEvent.id)
        )
        .where(DrivingEvent.vehicle_id == vehicle_id)
        .where(DrivingEvent.timestamp >= cutoff_time)
        .group_by(DrivingEvent.event_type, DrivingEvent.severity)
    )
    
    result = await session.execute(stmt)
    event_counts = result.all()
    
    # Calculate score (100 - penalties)
    score = 100
    penalties = {
        ("harsh_brake", "low"): 1,
        ("harsh_brake", "medium"): 3,
        ("harsh_brake", "high"): 5,
        ("rapid_acceleration", "low"): 1,
        ("rapid_acceleration", "medium"): 3,
        ("rapid_acceleration", "high"): 5,
        ("speeding", "low"): 2,
        ("speeding", "medium"): 5,
        ("speeding", "high"): 10,
        ("sharp_turn", "low"): 1,
        ("sharp_turn", "medium"): 2,
        ("sharp_turn", "high"): 4,
    }
    
    event_summary = {}
    for event_type, severity, count in event_counts:
        penalty = penalties.get((event_type, severity), 1) * count
        score -= penalty
        event_summary[f"{event_type}_{severity}"] = count
    
    score = max(0, min(100, score))
    
    # Get grade
    if score >= 90:
        grade = "A"
        rating = "Excellent"
    elif score >= 80:
        grade = "B"
        rating = "Good"
    elif score >= 70:
        grade = "C"
        rating = "Average"
    elif score >= 60:
        grade = "D"
        rating = "Below Average"
    else:
        grade = "F"
        rating = "Needs Improvement"
    
    return {
        "vehicle_id": vehicle_id,
        "score": score,
        "grade": grade,
        "rating": rating,
        "period_days": period_days,
        "event_summary": event_summary,
        "timestamp": time.time(),
    }


@router.get("/trips/{vehicle_id}")
async def get_trips(
    vehicle_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get trip history for a vehicle."""
    user_id = current_user.get("id")
    
    # Verify vehicle ownership
    from predict.core.db.models.vehicle import VehicleProfile
    
    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == vehicle_id,
        VehicleProfile.owner_user_id == user_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(
            status_code=403, detail="Vehicle not found or not authorized"
        )
    
    from predict.core.db.models.trip import Trip
    
    stmt = (
        select(Trip)
        .where(Trip.profile_id == vehicle_id)
        .order_by(desc(Trip.start_time))
        .limit(limit)
        .offset(offset)
    )
    
    result = await session.execute(stmt)
    trips = result.scalars().all()
    
    # Get total count
    count_stmt = select(func.count(Trip.id)).where(Trip.profile_id == vehicle_id)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()
    
    return {
        "trips": [
            {
                "id": t.id,
                "start_time": t.start_time,
                "end_time": getattr(t, "end_time", None),
                "distance_km": getattr(t, "distance_km", None),
                "duration_minutes": (
                    (t.end_time - t.start_time) / 60
                    if getattr(t, "end_time", None) else None
                ),
                "score": getattr(t, "safety_score", None),
                "start_location": getattr(t, "start_location", None),
                "end_location": getattr(t, "end_location", None),
            }
            for t in trips
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "timestamp": time.time(),
    }


@router.get("/trip/{trip_id}")
async def get_trip_details(
    trip_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get detailed trip information."""
    user_id = current_user.get("id")
    
    from predict.core.db.models.trip import Trip
    
    stmt = select(Trip).where(Trip.id == trip_id)
    result = await session.execute(stmt)
    trip = result.scalar_one_or_none()
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Verify ownership
    from predict.core.db.models.vehicle import VehicleProfile
    
    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == trip.profile_id,
        VehicleProfile.owner_user_id == user_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this trip"
        )
    
    # Get driving events for this trip
    from predict.core.db.models.guardian import DrivingEvent
    
    events_stmt = (
        select(DrivingEvent)
        .where(DrivingEvent.vehicle_id == trip.profile_id)
        .where(DrivingEvent.timestamp >= trip.start_time)
        .where(DrivingEvent.timestamp <= (trip.end_time or time.time()))
        .order_by(DrivingEvent.timestamp)
    )
    events_result = await session.execute(events_stmt)
    events = events_result.scalars().all()
    
    return {
        "trip": {
            "id": trip.id,
            "vehicle_id": trip.profile_id,
            "start_time": trip.start_time,
            "end_time": getattr(trip, "end_time", None),
            "distance_km": getattr(trip, "distance_km", None),
            "fuel_consumed_l": getattr(trip, "fuel_consumed_l", None),
            "avg_speed_kmh": getattr(trip, "avg_speed_kmh", None),
            "max_speed_kmh": getattr(trip, "max_speed_kmh", None),
            "score": getattr(trip, "score", None),
            "start_location": getattr(trip, "start_location", None),
            "end_location": getattr(trip, "end_location", None),
        },
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "latitude": e.latitude,
                "longitude": e.longitude,
                "speed": e.speed,
                "timestamp": e.timestamp,
            }
            for e in events
        ],
        "event_count": len(events),
        "timestamp": time.time(),
    }


@router.get("/behavior-summary/{vehicle_id}")
async def get_behavior_summary(
    vehicle_id: int,
    period_days: int = Query(30, ge=1, le=90),
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get comprehensive driving behavior summary."""
    user_id = current_user.get("id")
    
    # Verify vehicle ownership
    from predict.core.db.models.vehicle import VehicleProfile
    
    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == vehicle_id,
        VehicleProfile.owner_user_id == user_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(
            status_code=403, detail="Vehicle not found or not authorized"
        )
    
    from predict.core.db.models.trip import Trip
    from predict.core.db.models.guardian import DrivingEvent
    
    cutoff_time = time.time() - (period_days * 86400)
    
    # Trip stats
    trip_stmt = (
        select(
            func.count(Trip.id),
            func.sum(Trip.distance_km),
            func.avg(Trip.safety_score),
        )
        .where(Trip.profile_id == vehicle_id)
        .where(Trip.start_time >= cutoff_time)
    )
    trip_result = await session.execute(trip_stmt)
    trip_count, total_distance, avg_score = trip_result.one()
    
    # Event stats
    event_stmt = (
        select(
            DrivingEvent.event_type,
            func.count(DrivingEvent.id)
        )
        .where(DrivingEvent.vehicle_id == vehicle_id)
        .where(DrivingEvent.timestamp >= cutoff_time)
        .group_by(DrivingEvent.event_type)
    )
    event_result = await session.execute(event_stmt)
    event_breakdown = {event_type: count for event_type, count in event_result.all()}
    
    # Calculate trend (compare to previous period)
    previous_cutoff = cutoff_time - (period_days * 86400)
    
    prev_stmt = (
        select(func.avg(Trip.safety_score))
        .where(Trip.profile_id == vehicle_id)
        .where(Trip.start_time >= previous_cutoff)
        .where(Trip.start_time < cutoff_time)
    )
    prev_result = await session.execute(prev_stmt)
    prev_avg_score = prev_result.scalar()
    
    trend = None
    if avg_score and prev_avg_score:
        diff = avg_score - prev_avg_score
        trend = "improving" if diff > 5 else "declining" if diff < -5 else "stable"
    
    return {
        "vehicle_id": vehicle_id,
        "period_days": period_days,
        "trips": {
            "count": trip_count or 0,
            "total_distance_km": round(total_distance, 2) if total_distance else 0,
            "avg_score": round(avg_score, 1) if avg_score else None,
        },
        "events": event_breakdown,
        "total_events": sum(event_breakdown.values()),
        "trend": trend,
        "timestamp": time.time(),
    }


@router.get("/safety-recommendations/{vehicle_id}")
async def get_safety_recommendations(
    vehicle_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get personalized safety recommendations based on driving behavior."""
    user_id = current_user.get("id")
    
    # Verify vehicle ownership
    from predict.core.db.models.vehicle import VehicleProfile
    
    vehicle_stmt = select(VehicleProfile).where(
        VehicleProfile.profile_id == vehicle_id,
        VehicleProfile.owner_user_id == user_id,
    )
    vehicle_result = await session.execute(vehicle_stmt)
    vehicle = vehicle_result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(
            status_code=403, detail="Vehicle not found or not authorized"
        )
    
    from predict.core.db.models.guardian import DrivingEvent
    
    # Get recent events
    cutoff_time = time.time() - (30 * 86400)
    
    stmt = (
        select(DrivingEvent.event_type, func.count(DrivingEvent.id))
        .where(DrivingEvent.vehicle_id == vehicle_id)
        .where(DrivingEvent.timestamp >= cutoff_time)
        .group_by(DrivingEvent.event_type)
    )
    
    result = await session.execute(stmt)
    events = {event_type: count for event_type, count in result.all()}
    
    # Generate recommendations
    recommendations = []
    
    harsh_brakes = events.get("harsh_brake", 0)
    if harsh_brakes > 5:
        recommendations.append({
            "priority": "high",
            "category": "braking",
            "message": f"You've had {harsh_brakes} harsh braking events. Try to anticipate stops earlier and brake gradually.",
            "tip": "Maintain a 3-second following distance to reduce sudden braking.",
        })
    
    rapid_accels = events.get("rapid_acceleration", 0)
    if rapid_accels > 5:
        recommendations.append({
            "priority": "high",
            "category": "acceleration",
            "message": f"{rapid_accels} rapid acceleration events detected. Smooth acceleration improves fuel efficiency and safety.",
            "tip": "Press the accelerator gently and increase speed gradually.",
        })
    
    speeding = events.get("speeding", 0)
    if speeding > 3:
        recommendations.append({
            "priority": "high",
            "category": "speed",
            "message": f"{speeding} speeding events recorded. Obeying speed limits significantly reduces accident risk.",
            "tip": "Use cruise control on highways to maintain steady speed.",
        })
    
    sharp_turns = events.get("sharp_turn", 0)
    if sharp_turns > 3:
        recommendations.append({
            "priority": "medium",
            "category": "cornering",
            "message": f"{sharp_turns} sharp turning events. Slow down before entering turns.",
            "tip": "Reduce speed before the turn, not during it.",
        })
    
    if not recommendations:
        recommendations.append({
            "priority": "info",
            "category": "general",
            "message": "Great driving! No concerning behavior patterns detected.",
            "tip": "Continue maintaining safe driving habits.",
        })
    
    return {
        "vehicle_id": vehicle_id,
        "recommendations": recommendations,
        "event_summary": events,
        "timestamp": time.time(),
    }
