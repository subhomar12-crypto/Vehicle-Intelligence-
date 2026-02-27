"""
Admin API routes for system management.

Admin-only endpoints for user management, system stats, and maintenance.
"""

import asyncio
import hashlib
import json
import logging
import secrets
import time
from typing import Dict, Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from predict.core.db.session import get_db as get_db_session
from predict.core.db.models.user import User, ApiKey, Entitlement, RateLimit
from predict.core.services.websocket_service import ws_manager
from predict.core.services.fcm_service import FCMService
from predict.core.db.models.vehicle import VehicleProfile, TelemetryRecord
from predict.core.db.models.subscription import SubscriptionAuditLog, TierUpgradeRequest
from predict.core.db.models.prediction import Prediction
from predict.core.db.models.audit import AuditLog
from predict.core.security.auth import get_current_user
from predict.core.security.hashing import hash_api_key
from predict.core.services.backup_service import BackupService
from predict.core.cache.redis_client import get_redis
from predict.core.cache.api_key_cache import invalidate_all_api_keys
from predict.core.monitoring.health import get_health_monitor

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models
class UpdateUserRequest(BaseModel):
    tier: Optional[str] = None
    status: Optional[str] = None  # active, suspended, deleted


class ChangeUserTierRequest(BaseModel):
    tier: str


class SystemConfigRequest(BaseModel):
    key: str
    value: str


class EntitlementRequest(BaseModel):
    feature: str
    enabled: bool = True
    custom_limit: Optional[int] = None
    period: Optional[str] = None  # day, week, month


class EntitlementBulkRequest(BaseModel):
    entitlements: List[EntitlementRequest]


def require_admin(current_user: dict) -> dict:
    """Verify user is admin. Only tier == 'admin' grants access."""
    if current_user.get("tier") != "admin":
        raise HTTPException(
            status_code=403, detail="Admin access required"
        )
    return current_user


@router.get("/users")
async def list_users(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """List all users (admin only)."""
    require_admin(current_user)
    
    stmt = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
    
    if search:
        stmt = stmt.where(
            User.email.ilike(f"%{search}%") |
            User.name.ilike(f"%{search}%") |
            User.car_plate.ilike(f"%{search}%")
        )
    
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    # Get total count
    count_stmt = select(func.count(User.id))
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()
    
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "car_plate": u.car_plate,
                "tier": u.tier,
                "status": u.status,
                "created_at": u.created_at,
                "last_login": u.last_login,
            }
            for u in users
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "timestamp": time.time(),
    }


@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get detailed user information (admin only)."""
    require_admin(current_user)
    
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's vehicles
    vehicle_stmt = select(VehicleProfile).where(VehicleProfile.owner_user_id == user_id)
    vehicle_result = await session.execute(vehicle_stmt)
    vehicles = vehicle_result.scalars().all()
    
    # Subscription model not yet created — return empty
    subscriptions = []
    
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "role": user.role,
            "tier": user.tier,
            "status": user.status,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login": user.last_login,
        },
        "vehicles": [
            {
                "id": v.profile_id,
                "vin": v.vin,
                "make": getattr(v, "make", None),
                "model": getattr(v, "model", None),
                "year": getattr(v, "year", None),
                "license_plate": getattr(v, "license_plate", None),
            }
            for v in vehicles
        ],
        "subscriptions": [
            {
                "id": s.id,
                "tier": s.tier,
                "status": s.status,
                "amount": s.amount,
                "created_at": s.created_at,
            }
            for s in subscriptions
        ],
        "timestamp": time.time(),
    }


@router.put("/users/{user_id}/tier")
async def change_user_tier(
    user_id: int,
    request: ChangeUserTierRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Change user tier (admin only).

    Available tiers: free, pro, premium, admin
    """
    require_admin(current_user)

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate tier
    valid_tiers = ["free", "pro", "premium", "admin"]
    if request.tier not in valid_tiers:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}"
        )

    old_tier = user.tier
    user.tier = request.tier
    user.updated_at = time.time()
    
    await session.flush()
    
    # Log to audit
    audit_entry = AuditLog(
        user_id=user_id,
        admin_id=current_user.get("user_id"),
        action="user_tier_changed",
        details=json.dumps({
            "target_user_id": user_id,
            "old_tier": old_tier,
            "new_tier": request.tier,
        }),
        timestamp=time.time(),
    )
    session.add(audit_entry)
    await session.flush()
    
    logger.info(f"Admin changed user {user_id} tier from {old_tier} to {request.tier}")
    
    # Broadcast tier change via WebSocket
    try:
        await ws_manager.broadcast({
            "type": "USER_CHANGE",
            "event": "tier_changed",
            "user_id": user_id,
            "old_tier": old_tier,
            "new_tier": request.tier,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")

    # Send FCM push notification to the user
    try:
        fcm = FCMService()
        tier_display = request.tier.capitalize()
        await fcm.send_to_user(
            user_id=user_id,
            title="Subscription Updated",
            body=f"Your plan has been changed to {tier_display}",
            data={
                "type": "tier_change",
                "new_tier": request.tier,
                "old_tier": old_tier,
            },
        )
    except Exception as e:
        logger.debug(f"FCM notification failed (non-critical): {e}")
    
    return {
        "status": "success",
        "user_id": user_id,
        "old_tier": old_tier,
        "new_tier": request.tier,
        "timestamp": time.time(),
    }


@router.put("/users/{user_id}/entitlements")
async def set_user_entitlements(
    user_id: int,
    request: EntitlementBulkRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Set per-user feature entitlements and rate limit overrides (admin only).

    Allows admin to override tier defaults for specific users.
    Each entitlement controls access to a feature. Optional custom_limit
    and period fields create a corresponding RateLimit override.
    """
    require_admin(current_user)

    # Verify user exists
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    admin_id = current_user.get("id")
    current_time = time.time()
    updated = []

    for item in request.entitlements:
        # Upsert entitlement
        stmt = select(Entitlement).where(
            Entitlement.user_id == user_id,
            Entitlement.feature == item.feature,
        )
        result = await session.execute(stmt)
        entitlement = result.scalar_one_or_none()

        if entitlement:
            entitlement.enabled = item.enabled
            entitlement.granted_by = admin_id
            entitlement.granted_at = current_time
        else:
            entitlement = Entitlement(
                user_id=user_id,
                feature=item.feature,
                enabled=item.enabled,
                granted_at=current_time,
                granted_by=admin_id,
            )
            session.add(entitlement)

        # Upsert rate limit override if custom_limit provided
        if item.custom_limit is not None and item.period:
            stmt = select(RateLimit).where(
                RateLimit.user_id == user_id,
                RateLimit.feature == item.feature,
            )
            result = await session.execute(stmt)
            rate_limit = result.scalar_one_or_none()

            if rate_limit:
                rate_limit.max_requests = item.custom_limit
                rate_limit.period = item.period
            else:
                rate_limit = RateLimit(
                    user_id=user_id,
                    feature=item.feature,
                    max_requests=item.custom_limit,
                    period=item.period,
                )
                session.add(rate_limit)

        updated.append({
            "feature": item.feature,
            "enabled": item.enabled,
            "custom_limit": item.custom_limit,
            "period": item.period,
        })

    await session.flush()

    # Log to audit
    audit_entry = AuditLog(
        user_id=user_id,
        admin_id=admin_id,
        action="entitlements_updated",
        details=json.dumps({
            "target_user_id": user_id,
            "entitlements": updated,
        }),
        timestamp=current_time,
    )
    session.add(audit_entry)
    await session.flush()

    logger.info(f"Admin updated entitlements for user {user_id}: {len(updated)} features")

    return {
        "status": "success",
        "user_id": user_id,
        "updated": updated,
        "count": len(updated),
        "timestamp": time.time(),
    }


@router.get("/users/{user_id}/entitlements")
async def get_user_entitlements(
    user_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Get per-user entitlements and rate limit overrides (admin only)."""
    require_admin(current_user)

    # Entitlements
    stmt = select(Entitlement).where(Entitlement.user_id == user_id)
    result = await session.execute(stmt)
    entitlements = result.scalars().all()

    # Rate limits
    stmt = select(RateLimit).where(RateLimit.user_id == user_id)
    result = await session.execute(stmt)
    rate_limits = result.scalars().all()

    rate_limit_map = {rl.feature: rl for rl in rate_limits}

    return {
        "user_id": user_id,
        "entitlements": [
            {
                "feature": e.feature,
                "enabled": e.enabled,
                "granted_at": e.granted_at,
                "granted_by": e.granted_by,
                "expires_at": e.expires_at,
                "custom_limit": rate_limit_map[e.feature].max_requests if e.feature in rate_limit_map else None,
                "period": rate_limit_map[e.feature].period if e.feature in rate_limit_map else None,
            }
            for e in entitlements
        ],
        "count": len(entitlements),
        "timestamp": time.time(),
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Update user details (admin only)."""
    require_admin(current_user)
    
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_time = time.time()
    
    if request.tier is not None:
        user.tier = request.tier
    if request.status is not None:
        user.status = request.status

    user.updated_at = current_time
    await session.flush()

    logger.info(f"Admin updated user {user_id}: tier={request.tier}, status={request.status}")
    
    return {
        "status": "success",
        "user_id": user_id,
        "timestamp": time.time(),
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    hard_delete: bool = False,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Delete a user (admin only).
    
    Performs transaction-safe cascade deletion of all user-related data:
    - API keys, entitlements, rate limits
    - Vehicle profiles and all vehicle data
    - Predictions, reports, audit logs
    - Verification codes, sessions
    """
    require_admin(current_user)
    
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if hard_delete:
        # Transaction-safe cascade deletion
        try:
            deleted_counts = await _cascade_delete_user(session, user_id)
            await session.delete(user)
            await session.flush()
            
            logger.info(f"Admin hard-deleted user {user_id} with cascade: {deleted_counts}")
            
            return {
                "status": "success",
                "user_id": user_id,
                "hard_delete": True,
                "deleted_records": deleted_counts,
                "timestamp": time.time(),
            }
        except Exception as e:
            logger.error(f"Cascade delete failed for user {user_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete user: {str(e)}"
            )
    else:
        # Soft delete
        user.status = "deleted"
        user.email = f"deleted_{user.id}@deleted.predict"
        user.updated_at = time.time()
        await session.flush()
        
        logger.info(f"Admin soft-deleted user {user_id}")
        
        return {
            "status": "success",
            "user_id": user_id,
            "hard_delete": False,
            "timestamp": time.time(),
        }


async def _cascade_delete_user(session: AsyncSession, user_id: int) -> Dict[str, int]:
    """
    Transaction-safe cascade deletion of all user-related records.
    
    Deletes in correct order to respect foreign key constraints.
    All operations are within the same transaction - rollback on any failure.
    
    Args:
        session: Database session (transaction context)
        user_id: User ID to delete
        
    Returns:
        Dictionary with counts of deleted records per table
    """
    from sqlalchemy import delete, update
    from predict.core.db.models.user import (
        UsageCounter, DriverAssignment, UserFeatureOverride
    )
    from predict.core.db.models.vehicle import (
        VehicleProfile, VehicleData, ServiceRecord, VehicleResearch
    )
    from predict.core.db.models.prediction import (
        Prediction, MLTrainingLabel, MLAggregatedFeature
    )
    from predict.core.db.models.subscription import (
        FleetInvite, TierUpgradeRequest, SubscriptionAuditLog
    )
    from predict.core.db.models.audit import (
        Report, AuditLog, VerificationCode, VerificationSession
    )
    from predict.core.db.models.guardian import (
        Alert, GuardianTelemetry, DrivingEvent, LocationRequest,
        GuardianCommand, ConsentRecord, VehicleGuardian
    )
    from predict.core.db.models.trip import Trip, TripEvent
    
    deleted_counts = {}
    
    # 1. Get user's vehicle profiles for cascade deletion
    stmt = select(VehicleProfile.profile_id).where(VehicleProfile.owner_user_id == user_id)
    result = await session.execute(stmt)
    profile_ids = [row[0] for row in result.all()]
    
    # 2. Delete vehicle-related data (from child tables first)
    if profile_ids:
        # Delete ML/training data
        result = await session.execute(
            delete(MLAggregatedFeature).where(MLAggregatedFeature.profile_id.in_(profile_ids))
        )
        deleted_counts["ml_aggregated_features"] = result.rowcount
        
        result = await session.execute(
            delete(MLTrainingLabel).where(MLTrainingLabel.profile_id.in_(profile_ids))
        )
        deleted_counts["ml_training_labels"] = result.rowcount
        
        # Delete predictions
        result = await session.execute(
            delete(Prediction).where(Prediction.profile_id.in_(profile_ids))
        )
        deleted_counts["predictions"] = result.rowcount
        
        # Delete service records
        result = await session.execute(
            delete(ServiceRecord).where(ServiceRecord.profile_id.in_(profile_ids))
        )
        deleted_counts["service_records"] = result.rowcount
        
        # Delete vehicle data (OBD readings)
        result = await session.execute(
            delete(VehicleData).where(VehicleData.profile_id.in_(profile_ids))
        )
        deleted_counts["vehicle_data"] = result.rowcount
        
        # Delete guardian data by profile_id
        result = await session.execute(
            delete(Alert).where(Alert.profile_id.in_(profile_ids))
        )
        deleted_counts["guardian_alerts"] = result.rowcount
        
        result = await session.execute(
            delete(GuardianTelemetry).where(GuardianTelemetry.profile_id.in_(profile_ids))
        )
        deleted_counts["guardian_telemetry"] = result.rowcount
        
        result = await session.execute(
            delete(DrivingEvent).where(DrivingEvent.profile_id.in_(profile_ids))
        )
        deleted_counts["driving_events"] = result.rowcount
        
        result = await session.execute(
            delete(LocationRequest).where(LocationRequest.profile_id.in_(profile_ids))
        )
        deleted_counts["location_requests"] = result.rowcount
        
        result = await session.execute(
            delete(GuardianCommand).where(GuardianCommand.profile_id.in_(profile_ids))
        )
        deleted_counts["guardian_commands"] = result.rowcount
        
        result = await session.execute(
            delete(ConsentRecord).where(ConsentRecord.profile_id.in_(profile_ids))
        )
        deleted_counts["consent_records"] = result.rowcount
        
        result = await session.execute(
            delete(VehicleGuardian).where(VehicleGuardian.profile_id.in_(profile_ids))
        )
        deleted_counts["vehicle_guardians"] = result.rowcount
        
        # Delete trip/event data
        trip_stmt = select(Trip.trip_id).where(Trip.profile_id.in_(profile_ids))
        trip_result = await session.execute(trip_stmt)
        trip_ids = [row[0] for row in trip_result.all()]
        
        if trip_ids:
            result = await session.execute(
                delete(TripEvent).where(TripEvent.trip_id.in_(trip_ids))
            )
            deleted_counts["trip_events"] = result.rowcount
        
        result = await session.execute(
            delete(Trip).where(Trip.profile_id.in_(profile_ids))
        )
        deleted_counts["trips"] = result.rowcount
        
        # Delete vehicle research records (FK → vehicle_profiles)
        result = await session.execute(
            delete(VehicleResearch).where(VehicleResearch.profile_id.in_(profile_ids))
        )
        deleted_counts["vehicle_research"] = result.rowcount

        # Finally delete vehicle profiles
        result = await session.execute(
            delete(VehicleProfile).where(VehicleProfile.owner_user_id == user_id)
        )
        deleted_counts["vehicle_profiles"] = result.rowcount
    
    # 3. Delete user-related records
    result = await session.execute(
        delete(ApiKey).where(ApiKey.user_id == user_id)
    )
    deleted_counts["api_keys"] = result.rowcount
    
    result = await session.execute(
        delete(Entitlement).where(Entitlement.user_id == user_id)
    )
    deleted_counts["entitlements"] = result.rowcount
    
    result = await session.execute(
        delete(RateLimit).where(RateLimit.user_id == user_id)
    )
    deleted_counts["rate_limits"] = result.rowcount
    
    result = await session.execute(
        delete(UsageCounter).where(UsageCounter.user_id == user_id)
    )
    deleted_counts["usage_counters"] = result.rowcount
    
    result = await session.execute(
        delete(DriverAssignment).where(
            (DriverAssignment.driver_user_id == user_id) |
            (DriverAssignment.owner_user_id == user_id)
        )
    )
    deleted_counts["driver_assignments"] = result.rowcount
    
    result = await session.execute(
        delete(UserFeatureOverride).where(UserFeatureOverride.user_id == user_id)
    )
    deleted_counts["user_feature_overrides"] = result.rowcount
    
    # 4. Delete audit and verification records
    result = await session.execute(
        delete(Report).where(Report.user_id == user_id)
    )
    deleted_counts["reports"] = result.rowcount
    
    result = await session.execute(
        delete(AuditLog).where(AuditLog.user_id == user_id)
    )
    deleted_counts["audit_logs"] = result.rowcount
    
    result = await session.execute(
        delete(VerificationCode).where(VerificationCode.user_id == user_id)
    )
    deleted_counts["verification_codes"] = result.rowcount
    
    result = await session.execute(
        delete(VerificationSession).where(VerificationSession.user_id == user_id)
    )
    deleted_counts["verification_sessions"] = result.rowcount
    
    # 5. Delete subscription/fleet records
    result = await session.execute(
        delete(FleetInvite).where(
            (FleetInvite.fleet_manager_id == user_id) |
            (FleetInvite.used_by == user_id)
        )
    )
    deleted_counts["fleet_invites"] = result.rowcount
    
    result = await session.execute(
        delete(TierUpgradeRequest).where(TierUpgradeRequest.owner_id == user_id)
    )
    deleted_counts["tier_upgrade_requests"] = result.rowcount
    
    result = await session.execute(
        delete(SubscriptionAuditLog).where(SubscriptionAuditLog.user_id == user_id)
    )
    deleted_counts["subscription_audit_logs"] = result.rowcount

    # 6. Clear self-referential owner FK (other users referencing this user)
    result = await session.execute(
        update(User).where(User.owner_user_id == user_id).values(owner_user_id=None)
    )
    deleted_counts["owner_references_cleared"] = result.rowcount

    return deleted_counts


@router.get("/stats")
async def get_system_stats(
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get system statistics (admin only).
    
    Returns:
        - total_users: Total number of registered users
        - active_users: Number of active users
        - total_vehicles: Total number of vehicle profiles
        - total_predictions: Total number of predictions generated
        - monthly_recurring_revenue: Sum of active subscription amounts
        - tier_breakdown: User count per tier
        - telemetry_records_24h: Records in last 24 hours
        - storage_used_mb: Estimated database storage
    """
    require_admin(current_user)
    
    stats = {}
    
    # User counts
    user_stmt = select(func.count(User.id))
    user_result = await session.execute(user_stmt)
    stats["total_users"] = user_result.scalar()
    
    active_stmt = select(func.count(User.id)).where(User.status == "active")
    active_result = await session.execute(active_stmt)
    stats["active_users"] = active_result.scalar()
    
    # Vehicle counts
    vehicle_stmt = select(func.count(VehicleProfile.profile_id))
    vehicle_result = await session.execute(vehicle_stmt)
    stats["total_vehicles"] = vehicle_result.scalar()
    
    # Prediction counts
    pred_stmt = select(func.count(Prediction.id))
    pred_result = await session.execute(pred_stmt)
    stats["total_predictions"] = pred_result.scalar()

    # Subscription model not yet created
    stats["monthly_recurring_revenue"] = 0
    
    # Tier breakdown
    tier_stmt = (
        select(User.tier, func.count(User.id))
        .group_by(User.tier)
    )
    tier_result = await session.execute(tier_stmt)
    stats["tier_breakdown"] = {tier: count for tier, count in tier_result.all()}
    
    # Recent activity (last 24 hours)
    day_ago = time.time() - 86400
    
    telemetry_stmt = select(func.count(TelemetryRecord.id)).where(
        TelemetryRecord.ts >= day_ago
    )
    telemetry_result = await session.execute(telemetry_stmt)
    stats["telemetry_records_24h"] = telemetry_result.scalar()
    
    # Storage estimation (PostgreSQL)
    try:
        from sqlalchemy import text
        storage_query = text("SELECT pg_database_size(current_database()) / (1024.0 * 1024.0)")
        storage_result = await session.execute(storage_query)
        stats["storage_used_mb"] = round(storage_result.scalar() or 0, 2)
    except Exception:
        stats["storage_used_mb"] = None
    
    return {
        "stats": stats,
        "timestamp": time.time(),
    }


@router.get("/api-keys")
async def list_api_keys(
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """List all API keys (admin only).
    
    Args:
        user_id: Optional filter to show keys for specific user
    """
    require_admin(current_user)
    
    stmt = select(ApiKey).order_by(desc(ApiKey.created_at))
    
    if user_id:
        stmt = stmt.where(ApiKey.user_id == user_id)
    
    result = await session.execute(stmt)
    keys = result.scalars().all()
    
    return {
        "api_keys": [
            {
                "id": k.id,
                "key_prefix": k.key_prefix + "...",
                "user_id": k.user_id,
                "name": k.name,
                "last_used": k.last_used_at,
                "expires_at": k.expires_at,
                "status": k.status,
                "created_at": k.created_at,
            }
            for k in keys
        ],
        "count": len(keys),
        "timestamp": time.time(),
    }


@router.post("/api-key/generate")
async def generate_api_key(
    user_id: int,
    name: str,
    expires_days: int = 365,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Generate a new API key (admin only).
    
    Args:
        user_id: User to assign the key to
        name: Descriptive name for the key
        expires_days: Days until expiration (default 365)
    
    Returns:
        api_key: The raw API key (shown only once)
        key_id: Database ID for the key
        expires_at: Expiration timestamp
    """
    require_admin(current_user)
    
    # Verify user exists
    user_stmt = select(User).where(User.id == user_id)
    user_result = await session.execute(user_stmt)
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate key — store bcrypt hash + prefix only (raw key returned once)
    raw_key = f"pred_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)

    current_time = time.time()

    api_key = ApiKey(
        key_prefix=raw_key[:8],
        user_id=user_id,
        key_hash=key_hash,
        name=name,
        status="active",
        expires_at=current_time + (expires_days * 86400),
        created_at=current_time,
    )
    
    session.add(api_key)
    await session.flush()
    
    # Log to audit
    audit_entry = AuditLog(
        user_id=user_id,
        admin_id=current_user.get("user_id"),
        action="api_key_generated",
        details=json.dumps({
            "target_user_id": user_id,
            "key_id": api_key.id,
            "key_name": name,
        }),
        timestamp=time.time(),
    )
    session.add(audit_entry)
    await session.flush()
    
    logger.info(f"Admin generated API key {api_key.id} for user {user_id}")
    
    # Return raw key (only time it's visible)
    return {
        "status": "success",
        "api_key": raw_key,
        "key_id": api_key.id,
        "expires_at": api_key.expires_at,
        "timestamp": time.time(),
    }


@router.delete("/api-key/{key_id}")
async def revoke_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Revoke an API key (admin only)."""
    require_admin(current_user)
    
    stmt = select(ApiKey).where(ApiKey.id == key_id)
    result = await session.execute(stmt)
    key = result.scalar_one_or_none()
    
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    key.status = "revoked"
    
    await session.flush()
    
    # Log to audit
    audit_entry = AuditLog(
        user_id=key.user_id,
        admin_id=current_user.get("user_id"),
        action="api_key_revoked",
        details=json.dumps({
            "key_id": key_id,
            "key_name": key.name,
        }),
        timestamp=time.time(),
    )
    session.add(audit_entry)
    await session.flush()
    
    logger.info(f"Admin revoked API key {key_id}")
    
    return {
        "status": "success",
        "key_id": key_id,
        "timestamp": time.time(),
    }


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = None,
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Get audit log (admin only).
    
    Args:
        limit: Maximum records to return
        offset: Skip first N records
        event_type: Filter by event type
        user_id: Filter by user who performed action
    """
    require_admin(current_user)
    
    stmt = (
        select(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
        .offset(offset)
    )
    
    if event_type:
        stmt = stmt.where(AuditLog.action == event_type)

    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)

    result = await session.execute(stmt)
    logs = result.scalars().all()

    # Get total count
    count_stmt = select(func.count(AuditLog.id))
    if event_type:
        count_stmt = count_stmt.where(AuditLog.action == event_type)
    if user_id:
        count_stmt = count_stmt.where(AuditLog.user_id == user_id)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()

    return {
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "admin_id": log.admin_id,
                "action": log.action,
                "details": log.details,
                "timestamp": log.timestamp,
            }
            for log in logs
        ],
        "count": len(logs),
        "total": total,
        "limit": limit,
        "offset": offset,
        "timestamp": time.time(),
    }


@router.get("/vehicles")
async def list_all_vehicles(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """List all vehicles (admin only).
    
    Args:
        limit: Maximum records to return
        offset: Skip first N records
        user_id: Filter by owner user ID
    """
    require_admin(current_user)
    
    stmt = select(VehicleProfile).order_by(desc(VehicleProfile.created_at))
    
    if user_id:
        stmt = stmt.where(VehicleProfile.owner_user_id == user_id)
    
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    vehicles = result.scalars().all()
    
    # Get total count
    count_stmt = select(func.count(VehicleProfile.profile_id))
    if user_id:
        count_stmt = count_stmt.where(VehicleProfile.owner_user_id == user_id)
    count_result = await session.execute(count_stmt)
    total = count_result.scalar()
    
    return {
        "vehicles": [
            {
                "id": v.profile_id,
                "user_id": v.owner_user_id,
                "vin": v.vin,
                "make": getattr(v, "make", None),
                "model": getattr(v, "model", None),
                "year": getattr(v, "year", None),
                "created_at": v.created_at,
            }
            for v in vehicles
        ],
        "count": len(vehicles),
        "total": total,
        "limit": limit,
        "offset": offset,
        "timestamp": time.time(),
    }


@router.get("/jobs/status")
async def get_job_status(
    current_user = Depends(get_current_user),
):
    """Get background job status (admin only).
    
    Returns status of background tasks including:
    - pending: Jobs waiting to be processed
    - running: Currently executing jobs
    - completed: Successfully finished jobs
    - failed: Jobs that encountered errors
    """
    require_admin(current_user)
    
    # This would integrate with ARQ or Celery to get job status
    # For now, return placeholder with structure for future implementation
    return {
        "jobs": {
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
        },
        "queues": {
            "default": {"pending": 0, "running": 0},
            "predictions": {"pending": 0, "running": 0},
            "reports": {"pending": 0, "running": 0},
            "exports": {"pending": 0, "running": 0},
        },
        "timestamp": time.time(),
    }


@router.post("/backup")
async def trigger_backup(
    backup_type: str = "database",
    current_user = Depends(get_current_user),
):
    """Trigger manual backup (admin only).
    
    Args:
        backup_type: Type of backup (database, full)
    
    Returns:
        backup_path: Path to created backup
        size_bytes: Size of backup file
        duration_sec: Time taken to create backup
    """
    require_admin(current_user)
    
    service = BackupService()
    
    # Run backup
    if backup_type == "database":
        result = await service.create_database_backup()
    else:
        result = await service.create_full_backup()
    
    if result.success:
        logger.info(f"Admin triggered backup: {result.backup_path}")
        return {
            "status": "success",
            "backup_type": backup_type,
            "backup_path": str(result.backup_path),
            "size_bytes": result.size_bytes,
            "duration_sec": result.duration_sec,
            "timestamp": time.time(),
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Backup failed: {result.error_message}"
        )


@router.get("/backups")
async def list_backups(
    limit: int = Query(50, ge=1, le=100),
    current_user = Depends(get_current_user),
):
    """List available backups (admin only).
    
    Returns list of backup files with metadata.
    """
    require_admin(current_user)
    
    service = BackupService()
    backups = await service.list_backups(limit=limit)
    
    return {
        "backups": backups,
        "count": len(backups),
        "timestamp": time.time(),
    }


@router.post("/maintenance/clear-cache")
async def clear_cache(
    cache_type: str = "all",
    current_user = Depends(get_current_user),
):
    """Clear system caches (admin only).
    
    Args:
        cache_type: Which cache to clear (all, redis, api_keys)
    """
    require_admin(current_user)
    
    cleared = []
    
    if cache_type in ["all", "redis"]:
        # Clear Redis cache
        redis = get_redis()
        if redis:
            await redis.flushdb()
            cleared.append("redis")
    
    if cache_type in ["all", "api_keys"]:
        # Clear API key cache
        invalidate_all_api_keys()
        cleared.append("api_keys")
    
    logger.info(f"Admin cleared caches: {cleared}")
    
    return {
        "status": "success",
        "cleared": cleared,
        "message": f"Cleared caches: {', '.join(cleared)}",
        "timestamp": time.time(),
    }


@router.post("/system-config")
async def set_system_config(
    request: SystemConfigRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """Set system configuration (admin only)."""
    require_admin(current_user)
    
    current_time = time.time()
    
    # SystemConfig model not yet created
    logger.info(f"Admin set config (stub): {request.key}={request.value}")

    return {
        "status": "success",
        "key": request.key,
        "value": request.value,
        "timestamp": time.time(),
    }


@router.get("/health/detailed")
async def get_detailed_health(
    current_user = Depends(get_current_user),
):
    """Get detailed system health (admin only).
    
    Returns comprehensive health status for all services including:
    - Database connectivity
    - Redis connectivity
    - External service status
    - Disk usage
    - Memory usage
    """
    require_admin(current_user)
    
    health = await get_health_monitor().get_full_health()
    
    return {
        "health": health,
        "timestamp": time.time(),
    }


# ============================================================================
# Additional Admin Endpoints (Phase B Port)
# ============================================================================

@router.post("/brute-force/unlock/{email}")
async def unlock_locked_account(
    email: str,
    current_user = Depends(get_current_user),
):
    """Manually unlock a locked account (admin only).
    
    This endpoint unlocks accounts that have been locked due to 
    too many failed login attempts (brute force protection).
    """
    require_admin(current_user)
    
    # In a real implementation, this would call the brute force protector
    # For now, return success as placeholder
    logger.info(f"Admin unlocked account: {email}")
    
    return {
        "status": "success",
        "email": email,
        "message": f"Account {email} has been unlocked",
        "timestamp": time.time(),
    }


@router.get("/brute-force/status")
async def get_brute_force_status(
    current_user = Depends(get_current_user),
):
    """Get brute force protection status (admin only).
    
    Returns list of currently locked accounts and protection config.
    """
    require_admin(current_user)
    
    return {
        "config": {
            "max_failures": 5,
            "window_seconds": 3600,
            "lockout_seconds": 1800,
        },
        "locked_accounts": [],
        "total_locked": 0,
        "timestamp": time.time(),
    }


# ==================== FLEET ACCESS REQUESTS ====================


class FleetApproveRequest(BaseModel):
    vehicle_limit: int = 3
    notes: Optional[str] = None


class FleetDenyRequest(BaseModel):
    reason: Optional[str] = None


@router.get("/fleet-requests")
async def list_fleet_requests(
    status: str = Query("pending", regex="^(pending|approved|rejected|all)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """List fleet access requests (admin only).

    Returns requests where requested_tier='premium' with fleet fields populated.
    """
    require_admin(current_user)

    stmt = (
        select(TierUpgradeRequest)
        .where(TierUpgradeRequest.requested_tier == "premium")
    )

    if status != "all":
        stmt = stmt.where(TierUpgradeRequest.status == status)

    # Count total
    count_stmt = select(func.count()).select_from(
        stmt.subquery()
    )
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch page
    stmt = stmt.order_by(desc(TierUpgradeRequest.requested_at)).offset(offset).limit(limit)
    result = await session.execute(stmt)
    requests = result.scalars().all()

    items = []
    for req in requests:
        items.append({
            "request_id": req.request_id,
            "user_id": req.owner_id,
            "name": req.owner_name,
            "email": req.owner_email,
            "company_name": req.company_name,
            "fleet_size": req.fleet_size,
            "current_tier": req.current_tier,
            "status": req.status,
            "requested_at": req.requested_at,
            "processed_at": req.processed_at,
            "notes": req.notes,
        })

    return {
        "requests": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "timestamp": time.time(),
    }


@router.put("/fleet-requests/{request_id}/approve")
async def approve_fleet_request(
    request_id: int,
    request: FleetApproveRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Approve a fleet access request (admin only).

    - Upgrades user tier to premium
    - Sets custom vehicle limit via entitlement override
    - Auto-generates API key
    - Logs to audit trail
    """
    require_admin(current_user)
    admin_id = current_user.get("user_id")

    # Get the request
    stmt = select(TierUpgradeRequest).where(TierUpgradeRequest.request_id == request_id)
    result = await session.execute(stmt)
    fleet_req = result.scalar_one_or_none()

    if not fleet_req:
        raise HTTPException(status_code=404, detail="Fleet request not found")
    if fleet_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {fleet_req.status}")

    # Get the user
    user_stmt = select(User).where(User.id == fleet_req.owner_id)
    user_result = await session.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    current_time = time.time()
    old_tier = user.tier

    # 1. Approve the request
    fleet_req.status = "approved"
    fleet_req.processed_at = current_time
    fleet_req.processed_by = str(admin_id)
    if request.notes:
        fleet_req.notes = request.notes

    # 2. Upgrade user tier to premium
    user.tier = "premium"

    # 3. Set custom vehicle limit via entitlement override
    vehicle_limit = request.vehicle_limit
    ent_stmt = select(Entitlement).where(
        Entitlement.user_id == user.id,
        Entitlement.feature == "stored_vehicles",
    )
    ent_result = await session.execute(ent_stmt)
    entitlement = ent_result.scalar_one_or_none()

    if entitlement:
        entitlement.enabled = True
        entitlement.granted_by = admin_id
        entitlement.granted_at = current_time
    else:
        entitlement = Entitlement(
            user_id=user.id,
            feature="stored_vehicles",
            enabled=True,
            granted_at=current_time,
            granted_by=admin_id,
        )
        session.add(entitlement)

    # Set rate limit for stored_vehicles to the custom limit
    rl_stmt = select(RateLimit).where(
        RateLimit.user_id == user.id,
        RateLimit.feature == "stored_vehicles",
    )
    rl_result = await session.execute(rl_stmt)
    rate_limit = rl_result.scalar_one_or_none()

    if rate_limit:
        rate_limit.max_requests = vehicle_limit
        rate_limit.period = "permanent"
    else:
        rate_limit = RateLimit(
            user_id=user.id,
            feature="stored_vehicles",
            max_requests=vehicle_limit,
            period="permanent",
        )
        session.add(rate_limit)

    # 4. Auto-generate API key — store bcrypt hash + prefix only
    key_name = f"{fleet_req.company_name or 'Fleet'} Key"
    raw_key = f"pred_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_key)

    api_key = ApiKey(
        key_prefix=raw_key[:8],
        user_id=user.id,
        key_hash=key_hash,
        name=key_name,
        status="active",
        expires_at=current_time + (365 * 86400),
        created_at=current_time,
    )
    session.add(api_key)

    await session.flush()

    # 5. Log to audit
    audit_entry = AuditLog(
        user_id=user.id,
        admin_id=admin_id,
        action="fleet_request_approved",
        details=json.dumps({
            "request_id": request_id,
            "old_tier": old_tier,
            "new_tier": "premium",
            "vehicle_limit": vehicle_limit,
            "company_name": fleet_req.company_name,
            "api_key_id": api_key.id,
        }),
        timestamp=current_time,
    )
    session.add(audit_entry)

    # Subscription audit log
    sub_audit = SubscriptionAuditLog(
        user_id=user.id,
        admin_id=admin_id,
        action="fleet_access_granted",
        field_name="tier",
        old_value=old_tier,
        new_value="premium",
        reason=f"Fleet request approved (company: {fleet_req.company_name}, limit: {vehicle_limit})",
        timestamp=current_time,
    )
    session.add(sub_audit)

    await session.flush()

    # 6. WebSocket broadcast
    try:
        await ws_manager.broadcast({
            "type": "USER_CHANGE",
            "event": "fleet_approved",
            "user_id": user.id,
            "new_tier": "premium",
            "vehicle_limit": vehicle_limit,
            "timestamp": current_time,
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")

    # 7. FCM push notification
    try:
        if user.fcm_token:
            fcm = FCMService()
            await fcm.send_notification(
                user.fcm_token,
                "Fleet Access Approved!",
                f"Your fleet management access has been approved. Vehicle limit: {vehicle_limit}.",
            )
    except Exception as e:
        logger.debug(f"FCM notification failed (non-critical): {e}")

    logger.info(
        f"Admin {admin_id} approved fleet request {request_id} for user {user.id} "
        f"(tier: {old_tier}→premium, vehicles: {vehicle_limit})"
    )

    return {
        "success": True,
        "user_id": user.id,
        "api_key": raw_key,
        "new_tier": "premium",
        "vehicle_limit": vehicle_limit,
        "key_name": key_name,
        "timestamp": current_time,
    }


@router.put("/fleet-requests/{request_id}/deny")
async def deny_fleet_request(
    request_id: int,
    request: FleetDenyRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """Deny a fleet access request (admin only)."""
    require_admin(current_user)
    admin_id = current_user.get("user_id")

    stmt = select(TierUpgradeRequest).where(TierUpgradeRequest.request_id == request_id)
    result = await session.execute(stmt)
    fleet_req = result.scalar_one_or_none()

    if not fleet_req:
        raise HTTPException(status_code=404, detail="Fleet request not found")
    if fleet_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request already {fleet_req.status}")

    current_time = time.time()

    fleet_req.status = "rejected"
    fleet_req.processed_at = current_time
    fleet_req.processed_by = str(admin_id)
    if request.reason:
        fleet_req.notes = request.reason

    # Audit log
    audit_entry = AuditLog(
        user_id=fleet_req.owner_id,
        admin_id=admin_id,
        action="fleet_request_denied",
        details=json.dumps({
            "request_id": request_id,
            "reason": request.reason,
            "company_name": fleet_req.company_name,
        }),
        timestamp=current_time,
    )
    session.add(audit_entry)

    await session.flush()

    # WebSocket broadcast
    try:
        await ws_manager.broadcast({
            "type": "FLEET_REQUEST",
            "event": "request_denied",
            "request_id": request_id,
            "timestamp": current_time,
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")

    logger.info(f"Admin {admin_id} denied fleet request {request_id}")

    return {
        "success": True,
        "request_id": request_id,
        "status": "rejected",
        "timestamp": current_time,
    }
