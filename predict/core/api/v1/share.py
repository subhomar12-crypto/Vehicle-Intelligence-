"""
Share endpoints — generate and consume time-limited public health snapshots.

POST /api/share/{vehicle_id}  → create token (authenticated, rate-limited)
GET  /api/share/{token}       → public, returns health snapshot or 410 Gone
"""

import json
import logging
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.share import ShareToken
from predict.core.db.models.vehicle import VehicleProfile

logger = logging.getLogger(__name__)

router = APIRouter()

# 72 hours in seconds
_TOKEN_TTL = 72 * 60 * 60
# 24 hours in seconds
_RATE_WINDOW = 24 * 60 * 60


@router.post("/{vehicle_id}")
async def create_share_token(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a temporary share token for a vehicle's health data.

    Rate limit: 1 share per vehicle per 24 hours.
    Token expires after 72 hours.
    """
    user_id = current_user.get("user_id") or current_user.get("id")

    # Verify ownership (or admin)
    result = await db.execute(
        select(VehicleProfile).where(VehicleProfile.profile_id == vehicle_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    user_tier = current_user.get("tier", "free")
    if profile.owner_user_id != user_id and user_tier != "admin":
        raise HTTPException(status_code=403, detail="Not your vehicle")

    # Rate limit: 1 share per vehicle per 24 hours
    cutoff = time.time() - _RATE_WINDOW
    count_result = await db.execute(
        select(func.count(ShareToken.id)).where(
            ShareToken.vehicle_id == vehicle_id,
            ShareToken.created_at > cutoff,
        )
    )
    if count_result.scalar() >= 1:
        raise HTTPException(
            status_code=429,
            detail="Share limit reached — 1 per vehicle per day",
        )

    # Build health snapshot
    health_data = await _build_health_snapshot(db, vehicle_id, profile)

    now = time.time()
    token = secrets.token_urlsafe(48)
    share = ShareToken(
        token=token,
        vehicle_id=vehicle_id,
        creator_user_id=user_id,
        health_data=json.dumps(health_data),
        created_at=now,
        expires_at=now + _TOKEN_TTL,
    )
    db.add(share)
    await db.commit()

    return {
        "success": True,
        "token": token,
        "expires_at": now + _TOKEN_TTL,
        "share_url": f"/api/share/{token}",
    }


@router.get("/{token}")
async def get_shared_health(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — returns health snapshot for a valid share token.

    Returns 410 Gone if expired, 404 if not found.
    """
    result = await db.execute(
        select(ShareToken).where(ShareToken.token == token)
    )
    share = result.scalar_one_or_none()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")

    if time.time() > share.expires_at:
        raise HTTPException(status_code=410, detail="Share link expired")

    try:
        health_data = json.loads(share.health_data)
    except (json.JSONDecodeError, TypeError):
        health_data = {}

    return {
        "success": True,
        "health_data": health_data,
        "created_at": share.created_at,
        "expires_at": share.expires_at,
    }


async def _build_health_snapshot(
    db: AsyncSession,
    vehicle_id: int,
    profile: VehicleProfile,
) -> dict:
    """Build a health snapshot from the latest health assessment + profile info."""
    from predict.core.db.models.health_snapshot import HealthSnapshot

    snapshot: dict = {
        "vehicle": {
            "make": profile.make,
            "model": profile.model,
            "year": profile.year,
            "engine_type": getattr(profile, "engine_type", None),
            "mileage_km": getattr(profile, "mileage_km", None),
        },
        "health_score": None,
        "components": {},
        "intelligence_level": None,
    }

    # Get latest health snapshot from DB
    result = await db.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.vehicle_id == vehicle_id)
        .order_by(HealthSnapshot.created_at.desc())
        .limit(1)
    )
    hs = result.scalar_one_or_none()
    if hs:
        snapshot["health_score"] = hs.health_score
        snapshot["intelligence_level"] = hs.intelligence_level
        try:
            snapshot["components"] = json.loads(hs.components) if hs.components else {}
        except (json.JSONDecodeError, TypeError):
            snapshot["components"] = {}

    # Try to run a fresh health assessment if no snapshot exists
    if snapshot["health_score"] is None:
        try:
            from predict.core.ai.cold_start_predictor import ColdStartPredictor

            predictor = ColdStartPredictor()
            result = await predictor.assess_vehicle_health(
                vehicle_id=vehicle_id, session=db
            )
            snapshot["health_score"] = result.get("health_score", 0)
            components = result.get("components", [])
            snapshot["components"] = {
                c.get("id", c.get("name", "unknown")): c.get("score", 0)
                for c in components
            }
        except Exception as e:
            logger.warning("Could not run health assessment for share: %s", e)

    return snapshot
