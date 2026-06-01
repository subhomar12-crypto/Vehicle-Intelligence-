"""
User profile management endpoints.

Handles:
- User profile CRUD
- Vehicle profile management
- Profile preferences
- Vehicle image uploads

Ported from: Previlium_OBD_Server/main.py
"""

import asyncio
import logging
import time
import re
import os
import uuid
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user, require_permission
from predict.core.db.models.user import User, DriverAssignment
from predict.core.db.models.vehicle import VehicleProfile, VehicleResearch, ServiceRecord
from predict.core.db.models.guardian import Guardian, VehicleGuardian
from predict.core.db.repositories.user_repo import UserRepository
from predict.core.db.repositories.vehicle_repo import VehicleProfileRepository
from predict.core.middleware.error_handler import APIError, ErrorCode
from predict.core.middleware.validation import validate_vin
from predict.core.services.vehicle_research_service import get_research_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================
# Request/Response Models
# ========================

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class UserProfileResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    phone: Optional[str]
    tier: str
    is_verified: bool
    created_at: str


class VehicleProfileCreate(BaseModel):
    vin: Optional[str] = Field(None, min_length=17, max_length=17)
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = Field(None, ge=1900, le=2100)
    engine_type: Optional[str] = None
    mileage: Optional[int] = None
    nickname: Optional[str] = None
    color: Optional[str] = None
    license_plate: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    displacement: Optional[str] = None  # e.g., "3.5L"
    cylinders: Optional[int] = Field(None, ge=1, le=16)
    mileage_km: Optional[int] = Field(None, ge=0, le=2000000)
    component_ages: Optional[dict] = None


class VehicleProfileUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = Field(None, ge=1900, le=2100)
    engine_type: Optional[str] = None
    mileage: Optional[int] = None
    nickname: Optional[str] = None
    color: Optional[str] = None
    license_plate: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    displacement: Optional[str] = None
    cylinders: Optional[int] = Field(None, ge=1, le=16)
    mileage_km: Optional[int] = Field(None, ge=0, le=2000000)
    component_ages: Optional[dict] = None
    calibration_id: Optional[str] = None
    ecu_name: Optional[str] = None
    cvn: Optional[str] = None


class VehicleProfileResponse(BaseModel):
    id: int
    vin: Optional[str]
    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    engine_type: Optional[str]
    mileage: Optional[int]
    nickname: Optional[str]
    color: Optional[str]
    license_plate: Optional[str]
    fuel_type: Optional[str]
    transmission: Optional[str]
    displacement: Optional[str] = None
    cylinders: Optional[int] = None
    calibration_id: Optional[str] = None
    ecu_name: Optional[str] = None
    cvn: Optional[str] = None
    image_url: Optional[str] = None
    created_at: str
    updated_at: Optional[str]


class VinDecodeRequest(BaseModel):
    vin: str = Field(..., min_length=17, max_length=17)
    profile_id: Optional[int] = None  # If set, auto-update the profile


class VehicleImageUploadResponse(BaseModel):
    success: bool
    message: str
    vehicle_id: int
    image_url: Optional[str] = None


class ServiceRecordCreate(BaseModel):
    service_type: str
    description: Optional[str] = None
    mileage_at_service: Optional[int] = None
    cost: Optional[float] = None
    service_date: str
    next_service_date: Optional[str] = None
    next_service_mileage: Optional[int] = None
    provider: Optional[str] = None
    notes: Optional[str] = None


class ServiceRecordResponse(BaseModel):
    id: int
    service_type: str
    description: Optional[str]
    mileage_at_service: Optional[int]
    cost: Optional[float]
    service_date: str
    next_service_date: Optional[str]
    next_service_mileage: Optional[int]
    provider: Optional[str]
    created_at: str


class SuccessResponse(BaseModel):
    success: bool
    message: str


# ========================
# Helper Functions
# ========================

def _fmt_ts(ts) -> str:
    """Format a float timestamp to ISO string."""
    if ts is None:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(ts)))


async def _user_can_access_vehicle(
    db: AsyncSession, user_id: int, vehicle: VehicleProfile,
    user_tier: str = None,
) -> bool:
    """Check if user can access vehicle as owner, co-guardian, driver, or admin."""
    if user_tier in ("admin", "enterprise"):
        return True
    if vehicle.owner_user_id == user_id:
        return True

    profile_id = vehicle.profile_id

    # Co-guardian: direct user_id lookup on VehicleGuardian
    stmt = (
        select(VehicleGuardian.id)
        .where(
            VehicleGuardian.user_id == user_id,
            VehicleGuardian.profile_id == profile_id,
            VehicleGuardian.is_active.is_(True),
        )
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        return True

    # Legacy fallback: User.email → Guardian.email → VehicleGuardian
    # (for records created before user_id was added to VehicleGuardian)
    stmt_legacy = (
        select(VehicleGuardian.id)
        .join(Guardian, Guardian.guardian_id == VehicleGuardian.guardian_id)
        .join(User, User.email == Guardian.email)
        .where(
            User.id == user_id,
            VehicleGuardian.profile_id == profile_id,
            VehicleGuardian.is_active.is_(True),
            VehicleGuardian.user_id.is_(None),  # Only for legacy records
        )
    )
    result_legacy = await db.execute(stmt_legacy)
    if result_legacy.scalar_one_or_none() is not None:
        return True

    # Driver assignment
    stmt = select(DriverAssignment.id).where(
        DriverAssignment.driver_user_id == user_id,
        DriverAssignment.profile_id == profile_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


def get_vehicle_image_path(vehicle_id: int, filename: str, upload_dir: str = "uploads/vehicles") -> Path:
    """Get the storage path for vehicle images.

    Args:
        vehicle_id: The vehicle profile ID (used for directory organisation).
        filename: The randomised filename (caller is responsible for generating it).
        upload_dir: Base upload directory.
    """
    base_path = Path(upload_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / filename


def validate_image_file(file: UploadFile) -> tuple[bool, Optional[str]]:
    """Validate uploaded image file."""
    # Check file extension
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    file_ext = Path(file.filename or '').suffix.lower()
    
    if file_ext not in allowed_extensions:
        return False, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
    
    # Check content type
    allowed_content_types = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/octet-stream'  # Some browsers send this
    }
    
    content_type = file.content_type or ''
    if content_type not in allowed_content_types and not content_type.startswith('image/'):
        return False, f"Invalid content type: {content_type}"
    
    return True, None


# ========================
# User Profile Endpoints
# ========================

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/users/me - Get current user's profile.
    
    Returns the authenticated user's profile information.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(current_user['user_id'])
    
    if not user:
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="User profile not found",
        )
    
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        tier=user.tier,
        is_verified=user.verified,
        created_at=_fmt_ts(user.created_at),
    )


@router.put("/me", response_model=SuccessResponse)
async def update_my_profile(
    request: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    PUT /api/users/me - Update user profile.
    
    Updates the current user's profile information.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(current_user['user_id'])
    
    if not user:
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="User profile not found",
        )
    
    # Build update data
    update_data = {}
    if request.name is not None:
        update_data['name'] = request.name
    if request.phone is not None:
        update_data['phone'] = request.phone
    
    if update_data:
        # Update timestamp
        update_data['updated_at'] = time.time()
        await user_repo.update(user, **update_data)
        await db.commit()
    
    logger.info(f"User profile updated: user_id={current_user['user_id']}")
    
    return SuccessResponse(success=True, message="Profile updated successfully")


@router.delete("/me", response_model=SuccessResponse)
async def delete_my_account(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    DELETE /api/users/me - Delete user account.
    
    Permanently deletes the current user's account and all associated data.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(current_user['user_id'])
    
    if not user:
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="User profile not found",
        )
    
    # Soft delete - mark as deleted
    await user_repo.update(user, status="deleted", updated_at=time.time())
    await db.commit()
    
    logger.info(f"User account deleted: user_id={current_user['user_id']}, email={user.email}")
    
    return SuccessResponse(
        success=True,
        message="Account deleted successfully. Your data will be permanently removed within 30 days."
    )


# ========================
# Legacy Android Endpoints
# ========================

@router.get("/list")
async def profile_list_legacy(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/profile/list — Legacy Android endpoint.

    Returns user profile + vehicles + API key info in the format
    the Android app expects on the profile screen.
    """
    user_id = current_user['user_id']

    # Get user
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)

    if not user:
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="User profile not found",
        )

    # Get vehicles
    stmt = (
        select(VehicleProfile)
        .where(VehicleProfile.owner_user_id == user_id)
        .order_by(desc(VehicleProfile.created_at))
    )
    result = await db.execute(stmt)
    vehicles = result.scalars().all()

    # Get API key
    from predict.core.db.models.user import ApiKey
    stmt = select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.status == "active").order_by(desc(ApiKey.created_at)).limit(1)
    result = await db.execute(stmt)
    api_key = result.scalars().first()

    # Build profile list in the format Android VehicleProfile model expects
    profile_list = [
        {
            "profile_id": v.profile_id,
            "name": f"{v.make or ''} {v.model or ''}".strip() or "Vehicle",
            "make": v.make or "",
            "model": v.model or "",
            "year": v.year or 0,
            "license_plate": v.license_plate or "",
            "vin": v.vin or "",
            "color": v.color or "",
            "engine_type": v.engine_type or "",
            "transmission": v.transmission or "",
            "fuel_type": v.fuel_type or "",
            "drivetrain": v.drivetrain or "",
            "displacement": v.displacement or "",
            "cylinders": v.cylinders or 0,
            "calibration_id": v.calibration_id,
            "ecu_name": v.ecu_name,
            "cvn": v.cvn,
            "image_url": v.image_url,
            "api_key": api_key.key_prefix + "..." if api_key else None,
        }
        for v in vehicles
    ]

    return {
        "success": True,
        "profiles": profile_list,
        "count": len(profile_list),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone or "",
            "tier": user.tier,
            "verified": user.verified,
            "car_plate": user.car_plate or "",
            "registered_at": _fmt_ts(user.created_at),
        },
        "vehicles": profile_list,
        "api_key": api_key.key_prefix + "..." if api_key else None,
        "tier": user.tier,
    }


# ========================
# Vehicle Profile Endpoints
# ========================

@router.get("/vehicles", response_model=List[VehicleProfileResponse])
async def list_vehicles(
    user_id: Optional[int] = Query(None, description="Admin override: list vehicles for this user"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/vehicles - List user's vehicles.

    Returns vehicles the user owns, co-guards, or is assigned to drive.
    Admins can pass ?user_id= to view any user's vehicles.
    """
    # Admin can override user_id to view any user's vehicles
    if user_id and current_user.get('tier') == 'admin':
        pass  # Use the provided user_id
    else:
        user_id = current_user['user_id']

    # Subquery: co-guardian vehicles (direct user_id lookup)
    guardian_sub = (
        select(VehicleGuardian.profile_id)
        .where(VehicleGuardian.user_id == user_id, VehicleGuardian.is_active.is_(True))
    )

    # Subquery: driver-assigned vehicles
    driver_sub = select(DriverAssignment.profile_id).where(
        DriverAssignment.driver_user_id == user_id,
    )

    stmt = (
        select(VehicleProfile)
        .where(
            or_(
                VehicleProfile.owner_user_id == user_id,
                VehicleProfile.profile_id.in_(guardian_sub),
                VehicleProfile.profile_id.in_(driver_sub),
            )
        )
        .order_by(desc(VehicleProfile.created_at))
    )
    result = await db.execute(stmt)
    vehicles = result.scalars().all()
    
    return [
        VehicleProfileResponse(
            id=v.profile_id,
            vin=v.vin,
            make=v.make,
            model=v.model,
            year=v.year,
            engine_type=v.engine_type,
            mileage=None,  # Not in model, derived from data
            nickname=v.name,
            color=v.color,
            license_plate=v.license_plate,
            fuel_type=v.fuel_type,
            transmission=v.transmission,
            displacement=v.displacement,
            cylinders=v.cylinders,
            calibration_id=v.calibration_id,
            ecu_name=v.ecu_name,
            cvn=v.cvn,
            image_url=v.image_url,
            created_at=_fmt_ts(v.created_at),
            updated_at=_fmt_ts(v.updated_at) if v.updated_at else None,
        )
        for v in vehicles
    ]


@router.post("/vehicles")
async def create_vehicle(
    request: VehicleProfileCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/vehicles - Create vehicle profile.
    
    Creates a new vehicle profile for the current user.
    """
    vehicle_repo = VehicleProfileRepository(db)
    
    # Validate VIN if provided
    if request.vin:
        is_valid, error = validate_vin(request.vin)
        if not is_valid:
            raise APIError(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                message=error,
            )
        
        # Check for duplicate VIN
        existing = await vehicle_repo.get_by_vin(request.vin.upper().strip())
        if existing:
            raise APIError(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                message="Vehicle with this VIN already exists",
            )
    
    # Check for duplicate vehicle (same user, same make/model/year/plate)
    user_id = current_user['user_id']
    existing_vehicles = await db.execute(
        select(VehicleProfile).where(VehicleProfile.owner_user_id == user_id)
    )
    for existing in existing_vehicles.scalars().all():
        if (existing.make and request.make and
            existing.make.strip().lower() == request.make.strip().lower() and
            existing.model and request.model and
            existing.model.strip().lower() == request.model.strip().lower() and
            existing.year == request.year and
            (existing.license_plate or "") == (request.license_plate or "")):
            raise APIError(
                status_code=409,
                code=ErrorCode.VALIDATION_ERROR,
                message=f"You already have a {request.year} {request.make} {request.model} in your garage",
            )

    # Create vehicle profile with current user as owner
    now = time.time()
    vehicle = await vehicle_repo.create(
        owner_user_id=current_user['user_id'],
        vin=request.vin.upper().strip() if request.vin else None,
        make=request.make,
        model=request.model,
        year=request.year,
        engine_type=request.engine_type,
        name=request.nickname,
        color=request.color,
        license_plate=request.license_plate.upper().strip() if request.license_plate else None,
        fuel_type=request.fuel_type,
        transmission=request.transmission,
        displacement=request.displacement,
        cylinders=request.cylinders,
        mileage_km=request.mileage_km,
        component_ages=request.component_ages,
        created_at=now,
        updated_at=now,
    )
    await db.commit()
    await db.refresh(vehicle)

    logger.info(f"Vehicle profile created: profile_id={vehicle.profile_id} for user={current_user['user_id']}")

    # Trigger background research if we have enough vehicle info
    if vehicle.make and vehicle.model and vehicle.year:
        asyncio.create_task(
            _run_vehicle_research(vehicle.profile_id)
        )

    # Return format matching Android CreateProfileResponse
    return {
        "success": True,
        "profile_id": vehicle.profile_id,
        "message": "Profile created successfully",
    }


@router.get("/vehicles/{vehicle_id}", response_model=VehicleProfileResponse)
async def get_vehicle(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/vehicles/{vehicle_id} - Get vehicle details.

    Returns detailed information about a specific vehicle.
    Accessible to owner, co-guardian, or assigned driver.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if not await _user_can_access_vehicle(db, current_user['user_id'], vehicle, current_user.get('tier')):
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="You do not have access to this vehicle",
        )

    return VehicleProfileResponse(
        id=vehicle.profile_id,
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        engine_type=vehicle.engine_type,
        mileage=None,
        nickname=vehicle.name,
        color=vehicle.color,
        license_plate=vehicle.license_plate,
        fuel_type=vehicle.fuel_type,
        transmission=vehicle.transmission,
        displacement=vehicle.displacement,
        cylinders=vehicle.cylinders,
        calibration_id=vehicle.calibration_id,
        ecu_name=vehicle.ecu_name,
        cvn=vehicle.cvn,
        image_url=vehicle.image_url,
        created_at=_fmt_ts(vehicle.created_at),
        updated_at=_fmt_ts(vehicle.updated_at) if vehicle.updated_at else None,
    )


@router.put("/vehicles/{vehicle_id}", response_model=SuccessResponse)
async def update_vehicle(
    vehicle_id: int,
    request: VehicleProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    PUT /api/vehicles/{vehicle_id} - Update vehicle.

    Updates an existing vehicle profile. Owner only.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if vehicle.owner_user_id != current_user['user_id']:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Only the vehicle owner can update this vehicle",
        )

    # Build update data from request
    update_data = request.model_dump(exclude_unset=True)
    
    # Map nickname to name field
    if 'nickname' in update_data:
        update_data['name'] = update_data.pop('nickname')
    
    if update_data:
        update_data['updated_at'] = time.time()
        await vehicle_repo.update(vehicle, **update_data)
        await db.commit()
    
    logger.info(f"Vehicle profile updated: profile_id={vehicle_id}")
    
    return SuccessResponse(success=True, message="Vehicle profile updated")


@router.delete("/vehicles/{vehicle_id}", response_model=SuccessResponse)
async def delete_vehicle(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    DELETE /api/vehicles/{vehicle_id} - Delete vehicle.

    Permanently deletes a vehicle profile and all associated data. Owner only.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if vehicle.owner_user_id != current_user['user_id']:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Only the vehicle owner can delete this vehicle",
        )

    # Cascade delete all related data before deleting the profile
    from sqlalchemy import delete as sql_delete, select as sql_select
    from predict.core.db.models.vehicle import VehicleData, ServiceRecord, VehicleResearch, DailyVehicleStats, FailureEvent
    from predict.core.db.models.prediction import Prediction, MLTrainingLabel, MLAggregatedFeature
    from predict.core.db.models.guardian import (
        Alert, GuardianTelemetry, DrivingEvent, LocationRequest,
        GuardianCommand, ConsentRecord, VehicleGuardian
    )
    from predict.core.db.models.trip import Trip, TripEvent

    pid = vehicle_id
    deleted = {}

    # ML/training data
    r = await db.execute(sql_delete(MLAggregatedFeature).where(MLAggregatedFeature.profile_id == pid))
    deleted["ml_aggregated_features"] = r.rowcount
    r = await db.execute(sql_delete(MLTrainingLabel).where(MLTrainingLabel.profile_id == pid))
    deleted["ml_training_labels"] = r.rowcount

    # Predictions
    r = await db.execute(sql_delete(Prediction).where(Prediction.profile_id == pid))
    deleted["predictions"] = r.rowcount

    # Service records
    r = await db.execute(sql_delete(ServiceRecord).where(ServiceRecord.profile_id == pid))
    deleted["service_records"] = r.rowcount

    # Vehicle data (OBD telemetry)
    r = await db.execute(sql_delete(VehicleData).where(VehicleData.profile_id == pid))
    deleted["vehicle_data"] = r.rowcount

    # Guardian data
    r = await db.execute(sql_delete(Alert).where(Alert.profile_id == pid))
    deleted["alerts"] = r.rowcount
    r = await db.execute(sql_delete(GuardianTelemetry).where(GuardianTelemetry.profile_id == pid))
    deleted["guardian_telemetry"] = r.rowcount
    r = await db.execute(sql_delete(DrivingEvent).where(DrivingEvent.profile_id == pid))
    deleted["driving_events"] = r.rowcount
    r = await db.execute(sql_delete(LocationRequest).where(LocationRequest.profile_id == pid))
    deleted["location_requests"] = r.rowcount
    r = await db.execute(sql_delete(GuardianCommand).where(GuardianCommand.profile_id == pid))
    deleted["guardian_commands"] = r.rowcount
    r = await db.execute(sql_delete(ConsentRecord).where(ConsentRecord.profile_id == pid))
    deleted["consent_records"] = r.rowcount
    r = await db.execute(sql_delete(VehicleGuardian).where(VehicleGuardian.profile_id == pid))
    deleted["vehicle_guardians"] = r.rowcount

    # Trip data
    trip_result = await db.execute(sql_select(Trip.trip_id).where(Trip.profile_id == pid))
    trip_ids = [row[0] for row in trip_result.all()]
    if trip_ids:
        r = await db.execute(sql_delete(TripEvent).where(TripEvent.trip_id.in_(trip_ids)))
        deleted["trip_events"] = r.rowcount
    r = await db.execute(sql_delete(Trip).where(Trip.profile_id == pid))
    deleted["trips"] = r.rowcount

    # Daily stats and failure events
    r = await db.execute(sql_delete(DailyVehicleStats).where(DailyVehicleStats.profile_id == pid))
    deleted["daily_stats"] = r.rowcount
    r = await db.execute(sql_delete(FailureEvent).where(FailureEvent.profile_id == pid))
    deleted["failure_events"] = r.rowcount

    # Vehicle research
    r = await db.execute(sql_delete(VehicleResearch).where(VehicleResearch.profile_id == pid))
    deleted["vehicle_research"] = r.rowcount

    # Finally delete the vehicle profile itself
    await vehicle_repo.delete(vehicle)
    await db.commit()

    total_deleted = sum(v for v in deleted.values())
    logger.info(f"Vehicle profile deleted: profile_id={vehicle_id}, cascade deleted {total_deleted} related records: {deleted}")

    return SuccessResponse(success=True, message="Vehicle profile and all associated data deleted")


@router.post("/vehicles/{vehicle_id}/upload-image", response_model=VehicleImageUploadResponse)
async def upload_vehicle_image(
    vehicle_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/vehicles/{vehicle_id}/upload-image - Upload vehicle image.

    Uploads an image for a vehicle profile. Owner only.
    Supports jpg, png, gif, webp. Max file size: 5MB.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    user_tier = current_user.get('tier', 'free')
    if vehicle.owner_user_id != current_user['user_id'] and user_tier != 'admin':
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Only the vehicle owner can upload images",
        )

    # Validate file
    is_valid, error = validate_image_file(file)
    if not is_valid:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=error,
        )
    
    # Read and validate file size
    contents = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB

    if len(contents) > max_size:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(
            status_code=413,
            detail="File too large (max 5MB)",
        )

    # Randomise filename to prevent path traversal and enumeration attacks
    original_ext = Path(file.filename or "").suffix.lower() or ".jpg"
    random_filename = f"{uuid.uuid4().hex}{original_ext}"

    # Save file
    try:
        file_path = get_vehicle_image_path(vehicle_id, random_filename)
        with open(file_path, "wb") as f:
            f.write(contents)

        # Process photo (background removal + EXIF strip)
        from predict.core.services.photo_service import process_vehicle_photo
        await asyncio.to_thread(process_vehicle_photo, str(file_path))

        # Store the randomised URL in the vehicle record for later retrieval
        image_url = f"/uploads/vehicles/{random_filename}"

        # Save image URL to vehicle profile
        vehicle.image_url = image_url
        await db.commit()

        logger.info(f"Vehicle image uploaded: profile_id={vehicle_id}, size={len(contents)} bytes")

        return VehicleImageUploadResponse(
            success=True,
            message="Image uploaded successfully",
            vehicle_id=vehicle_id,
            image_url=image_url,
        )
    
    except Exception as e:
        logger.error(f"Failed to save vehicle image: {e}")
        raise APIError(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message="Failed to save image file",
        )


# ========================
# Pre-Registration Photo Upload
# ========================

@router.post("/vehicles/photos/upload-preregistered")
async def upload_preregistered_photo(
    file: UploadFile = File(...),
    make: str = Form(""),
    model: str = Form(""),
    year: int = Form(0),
    color: str = Form(""),
    vin: str = Form(""),
    license_plate: str = Form(""),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a vehicle photo before the vehicle is registered. Admin only."""
    user_tier = current_user.get('tier', 'free')
    if user_tier != 'admin':
        raise APIError(status_code=403, code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS, message="Admin only")

    is_valid, error = validate_image_file(file)
    if not is_valid:
        raise APIError(status_code=400, code=ErrorCode.VALIDATION_ERROR, message=error)

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=413, detail="File too large (max 5MB)")

    original_ext = Path(file.filename or "").suffix.lower() or ".jpg"
    random_filename = f"{uuid.uuid4().hex}{original_ext}"

    file_path = get_vehicle_image_path(0, random_filename)
    with open(file_path, "wb") as f:
        f.write(contents)

    # Process photo
    from predict.core.services.photo_service import process_vehicle_photo
    await asyncio.to_thread(process_vehicle_photo, str(file_path))

    image_url = f"/uploads/vehicles/{random_filename}"

    # Save to VehiclePhoto table
    from predict.core.db.models.vehicle import VehiclePhoto
    photo = VehiclePhoto(
        vin=vin or None,
        license_plate=license_plate or None,
        make=make or None,
        model=model or None,
        year=year or None,
        color=color or None,
        image_url=image_url,
        original_url=image_url,
        uploaded_by="admin",
    )
    db.add(photo)
    await db.commit()

    return {"success": True, "message": "Photo uploaded", "photo_id": photo.id, "image_url": image_url}


@router.get("/vehicles/photos/unmatched")
async def get_unmatched_photos(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pre-uploaded photos not yet assigned to a vehicle profile. Admin only."""
    user_tier = current_user.get('tier', 'free')
    if user_tier != 'admin':
        raise APIError(status_code=403, code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS, message="Admin only")

    from predict.core.db.models.vehicle import VehiclePhoto

    stmt = select(VehiclePhoto).where(VehiclePhoto.assigned_to_profile_id.is_(None)).order_by(VehiclePhoto.id.desc())
    result = await db.execute(stmt)
    photos = result.scalars().all()

    return {
        "success": True,
        "photos": [
            {
                "id": p.id,
                "make": p.make,
                "model": p.model,
                "year": p.year,
                "color": p.color,
                "vin": p.vin,
                "license_plate": p.license_plate,
                "image_url": p.image_url,
                "uploaded_by": p.uploaded_by,
                "created_at": str(p.created_at) if p.created_at else None,
            }
            for p in photos
        ],
        "count": len(photos),
    }


@router.delete("/vehicles/photos/{photo_id}")
async def delete_vehicle_photo(
    photo_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a pre-uploaded vehicle photo. Admin only."""
    user_tier = current_user.get('tier', 'free')
    if user_tier != 'admin':
        raise APIError(status_code=403, code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS, message="Admin only")

    from predict.core.db.models.vehicle import VehiclePhoto

    stmt = select(VehiclePhoto).where(VehiclePhoto.id == photo_id)
    result = await db.execute(stmt)
    photo = result.scalar_one_or_none()

    if not photo:
        raise APIError(status_code=404, code=ErrorCode.VEHICLE_NOT_FOUND, message="Photo not found")

    # Delete file from disk
    file_path = Path(photo.image_url.lstrip("/"))
    if file_path.exists():
        file_path.unlink()

    await db.delete(photo)
    await db.commit()

    return {"success": True, "message": "Photo deleted"}


# ========================
# Last Known Location
# ========================

class LastLocationRequest(BaseModel):
    """Payload sent by driver app on OBD disconnect."""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: Optional[float] = None  # Unix timestamp; defaults to server time


@router.post("/vehicles/{vehicle_id}/last-location")
async def update_last_location(
    vehicle_id: int,
    payload: LastLocationRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/vehicles/{vehicle_id}/last-location

    Called by driver app when OBD disconnects. Silently saves GPS snapshot.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    # Only the vehicle owner can update location
    if vehicle.owner_user_id != current_user["user_id"]:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Only the vehicle owner can update location",
        )

    vehicle.last_latitude = payload.latitude
    vehicle.last_longitude = payload.longitude
    vehicle.last_location_accuracy = payload.accuracy
    vehicle.last_location_at = payload.timestamp or time.time()
    await db.commit()

    return {"success": True, "message": "Location saved"}


# ========================
# Service Records (kept for compatibility)
# ========================

@router.get("/vehicles/{vehicle_id}/service-records", response_model=List[ServiceRecordResponse])
async def list_service_records(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List service records for a vehicle. Owner, co-guardian, or driver."""
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if not await _user_can_access_vehicle(db, current_user['user_id'], vehicle, current_user.get('tier')):
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="You do not have access to this vehicle",
        )

    stmt = (
        select(ServiceRecord)
        .where(ServiceRecord.profile_id == vehicle_id)
        .order_by(desc(ServiceRecord.service_date))
    )
    result = await db.execute(stmt)
    records = result.scalars().all()
    
    return [
        ServiceRecordResponse(
            id=r.id,
            service_type=r.service_type,
            description=r.notes,
            mileage_at_service=r.service_km,
            cost=r.cost,
            service_date=r.service_date,
            next_service_date=None,
            next_service_mileage=None,
            provider=r.technician,
            created_at=_fmt_ts(r.created_at),
        )
        for r in records
    ]


@router.post("/vehicles/{vehicle_id}/service-records", response_model=SuccessResponse)
async def create_service_record(
    vehicle_id: int,
    request: ServiceRecordCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a service record for a vehicle. Owner, co-guardian, or driver."""
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if not await _user_can_access_vehicle(db, current_user['user_id'], vehicle, current_user.get('tier')):
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="You do not have access to this vehicle",
        )
    
    # Calculate next service due mileage based on standard intervals
    _SERVICE_INTERVALS_KM = {
        "oil_change": 10000, "oil_filter": 10000, "air_filter": 20000,
        "brake_pads": 40000, "brake_fluid": 40000, "coolant_flush": 60000,
        "transmission": 80000, "spark_plugs": 50000, "battery": 80000,
    }
    interval = _SERVICE_INTERVALS_KM.get(request.service_type, 10000)
    next_due_km = request.next_service_mileage or ((request.mileage_at_service or 0) + interval)

    record = ServiceRecord(
        profile_id=vehicle_id,
        service_type=request.service_type,
        notes=request.notes or request.description,
        service_km=request.mileage_at_service or 0,
        cost=request.cost,
        service_date=request.service_date,
        technician=request.provider,
        created_at=time.time(),
    )

    db.add(record)
    await db.commit()

    # Track prediction accuracy (non-blocking)
    try:
        from predict.core.ai.accuracy_tracker import get_accuracy_tracker
        tracker = get_accuracy_tracker()
        await tracker.on_service_record_created(
            vehicle_id=vehicle_id,
            service_type=request.service_type,
            component_type=getattr(request, "component_type", None),
            session=db,
        )
        await db.commit()
    except Exception as e:
        logger.debug("Accuracy tracking failed (non-fatal): %s", e)

    # Reset component age on service (non-blocking)
    _SERVICE_TO_COMPONENT = {
        "oil_change": "engine_oil",
        "oil_filter": "engine_oil",
        "air_filter": "air_filter",
        "cabin_filter": "cabin_filter",
        "brake_pads": "brakes",
        "brake_fluid": "brakes",
        "coolant_flush": "coolant",
        "transmission": "transmission",
        "spark_plugs": "spark_plugs",
        "battery": "battery",
        "timing_belt": "timing_belt",
        "timing_chain": "timing_belt",
    }
    try:
        component_name = _SERVICE_TO_COMPONENT.get(request.service_type)
        if component_name and vehicle:
            import json as _json
            ages = {}
            if vehicle.component_ages:
                ages = (
                    _json.loads(vehicle.component_ages)
                    if isinstance(vehicle.component_ages, str)
                    else dict(vehicle.component_ages)
                )
            from datetime import datetime as _dt
            ages[component_name] = {
                "replaced_date": _dt.now().isoformat()[:10],
                "replaced_km": vehicle.mileage_km or 0,
            }
            vehicle.component_ages = ages
            await db.commit()
            logger.info(
                "Component age reset: vehicle=%d component=%s",
                vehicle_id, component_name,
            )
    except Exception as e:
        logger.debug("Component age reset failed (non-fatal): %s", e)

    return SuccessResponse(success=True, message="Service record added")


# ========================
# Background Research Helper
# ========================

async def _run_vehicle_research(profile_id: int):
    """Fire-and-forget background research for a vehicle."""
    try:
        service = get_research_service()
        await service.research_vehicle(profile_id)
    except Exception as e:
        logger.error(f"Background research failed for profile {profile_id}: {e}")


# ========================
# Vehicle Research Endpoints
# ========================

@router.get("/vehicles/{vehicle_id}/research")
async def get_vehicle_research(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/vehicles/{vehicle_id}/research — Get research data for a vehicle.

    Returns common problems, recalls, TSBs, reliability score, etc.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if not await _user_can_access_vehicle(db, current_user['user_id'], vehicle, current_user.get('tier')):
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="You do not have access to this vehicle",
        )

    service = get_research_service()
    data = await service.get_research(db, vehicle_id)

    if not data:
        return {"success": True, "research": None, "status": "none"}

    return {"success": True, "research": data, "status": data.get("research_status", "none")}


@router.post("/vehicles/{vehicle_id}/research/refresh")
async def refresh_vehicle_research(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/vehicles/{vehicle_id}/research/refresh — Re-run research.

    Marks existing research as stale and triggers a new background research task.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if vehicle.owner_user_id != current_user['user_id']:
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="Only the vehicle owner can refresh research",
        )

    if not (vehicle.make and vehicle.model and vehicle.year):
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="Vehicle must have make, model, and year to run research",
        )

    # Run in background
    asyncio.create_task(_run_vehicle_research(vehicle_id))

    return {"success": True, "message": "Research refresh started", "status": "pending"}


@router.get("/vehicles/{vehicle_id}/research/status")
async def get_research_status(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/vehicles/{vehicle_id}/research/status — Poll research status.

    Returns: pending, researching, completed, failed, stale, or none.
    """
    vehicle_repo = VehicleProfileRepository(db)
    vehicle = await vehicle_repo.get_by_id(vehicle_id)

    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )

    if not await _user_can_access_vehicle(db, current_user['user_id'], vehicle, current_user.get('tier')):
        raise APIError(
            status_code=403,
            code=ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS,
            message="You do not have access to this vehicle",
        )

    service = get_research_service()
    status = await service.get_research_status(db, vehicle_id)
    return {"success": True, **status}


# ========================
# VIN Decode Endpoint
# ========================

@router.post("/vehicles/vin-decode")
async def decode_vin_endpoint(
    request: VinDecodeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    POST /api/vehicles/vin-decode — Decode a VIN and return vehicle specs.

    If profile_id is provided, auto-updates that vehicle profile with decoded data.
    """
    vin = request.vin.upper().strip()

    is_valid, error = validate_vin(vin)
    if not is_valid:
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=error,
        )

    # Decode VIN using existing VIN decoder
    try:
        import sys
        project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from vin_decoder import VINDecoder
        decoder = VINDecoder()
        decoded = await asyncio.to_thread(decoder.decode_vin, vin)
    except Exception as e:
        logger.error(f"VIN decode failed: {e}")
        raise APIError(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message="VIN decode service unavailable",
        )

    if decoded.get("error"):
        raise APIError(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=decoded["error"],
        )

    # If profile_id given, update that vehicle profile
    if request.profile_id:
        vehicle_repo = VehicleProfileRepository(db)
        vehicle = await vehicle_repo.get_by_id(request.profile_id)

        if vehicle and vehicle.owner_user_id == current_user['user_id']:
            update_fields = {}
            if decoded.get("make") and not vehicle.make:
                update_fields["make"] = decoded["make"]
            if decoded.get("model") and not vehicle.model:
                update_fields["model"] = decoded["model"]
            if decoded.get("year") and not vehicle.year:
                update_fields["year"] = int(decoded["year"])
            if decoded.get("engine_type") and not vehicle.engine_type:
                update_fields["engine_type"] = decoded["engine_type"]
            if decoded.get("fuel_type") and not vehicle.fuel_type:
                update_fields["fuel_type"] = decoded["fuel_type"]
            if decoded.get("displacement") and not vehicle.displacement:
                update_fields["displacement"] = decoded["displacement"]
            if decoded.get("cylinders") and not vehicle.cylinders:
                update_fields["cylinders"] = int(decoded["cylinders"])
            if not vehicle.vin:
                update_fields["vin"] = vin

            if update_fields:
                update_fields["updated_at"] = time.time()
                await vehicle_repo.update(vehicle, **update_fields)
                await db.commit()
                logger.info(f"VIN decode auto-updated profile {request.profile_id}: {list(update_fields.keys())}")

    return {
        "success": True,
        "vin": vin,
        "decoded": decoded,
    }
