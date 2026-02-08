"""
User profile management endpoints.

Handles:
- User profile CRUD
- Vehicle profile management
- Profile preferences
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user, require_permission
from predict.core.db.models.user import User
from predict.core.db.models.vehicle import VehicleProfile, ServiceRecord
from predict.core.middleware.error_handler import APIError, ErrorCode
from predict.core.middleware.validation import validate_vin

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
    created_at: str
    updated_at: Optional[str]


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


# ========================
# User Profile
# ========================

@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's profile."""
    result = await db.execute(
        select(User).where(User.id == current_user['user_id'])
    )
    user = result.scalar_one_or_none()
    
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
        is_verified=user.is_verified,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.patch("/me")
async def update_my_profile(
    request: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's profile."""
    result = await db.execute(
        select(User).where(User.id == current_user['user_id'])
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise APIError(
            status_code=404,
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="User profile not found",
        )
    
    if request.name is not None:
        user.name = request.name
    if request.phone is not None:
        user.phone = request.phone
    
    await db.commit()
    
    return {"success": True, "message": "Profile updated"}


# ========================
# Vehicle Profiles
# ========================

@router.get("/vehicles", response_model=List[VehicleProfileResponse])
async def list_vehicles(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all vehicle profiles for current user."""
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.user_id == current_user['user_id']
        ).order_by(desc(VehicleProfile.created_at))
    )
    vehicles = result.scalars().all()
    
    return [
        VehicleProfileResponse(
            id=v.id,
            vin=v.vin,
            make=v.make,
            model=v.model,
            year=v.year,
            engine_type=v.engine_type,
            mileage=v.mileage,
            nickname=v.nickname,
            color=v.color,
            license_plate=v.license_plate,
            fuel_type=v.fuel_type,
            transmission=v.transmission,
            created_at=v.created_at.isoformat() if v.created_at else None,
            updated_at=v.updated_at.isoformat() if v.updated_at else None,
        )
        for v in vehicles
    ]


@router.post("/vehicles", response_model=VehicleProfileResponse)
async def create_vehicle(
    request: VehicleProfileCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new vehicle profile."""
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
        result = await db.execute(
            select(VehicleProfile).where(
                VehicleProfile.vin == request.vin.upper().strip(),
                VehicleProfile.user_id == current_user['user_id'],
            )
        )
        if result.scalar_one_or_none():
            raise APIError(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                message="Vehicle with this VIN already exists",
            )
    
    vehicle = VehicleProfile(
        user_id=current_user['user_id'],
        vin=request.vin.upper().strip() if request.vin else None,
        make=request.make,
        model=request.model,
        year=request.year,
        engine_type=request.engine_type,
        mileage=request.mileage,
        nickname=request.nickname,
        color=request.color,
        license_plate=request.license_plate,
        fuel_type=request.fuel_type,
        transmission=request.transmission,
    )
    
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    
    logger.info(f"Vehicle profile created: {vehicle.id} for user {current_user['user_id']}")
    
    return VehicleProfileResponse(
        id=vehicle.id,
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        engine_type=vehicle.engine_type,
        mileage=vehicle.mileage,
        nickname=vehicle.nickname,
        color=vehicle.color,
        license_plate=vehicle.license_plate,
        fuel_type=vehicle.fuel_type,
        transmission=vehicle.transmission,
        created_at=vehicle.created_at.isoformat() if vehicle.created_at else None,
        updated_at=vehicle.updated_at.isoformat() if vehicle.updated_at else None,
    )


@router.get("/vehicles/{vehicle_id}", response_model=VehicleProfileResponse)
async def get_vehicle(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific vehicle profile."""
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == vehicle_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    vehicle = result.scalar_one_or_none()
    
    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    return VehicleProfileResponse(
        id=vehicle.id,
        vin=vehicle.vin,
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        engine_type=vehicle.engine_type,
        mileage=vehicle.mileage,
        nickname=vehicle.nickname,
        color=vehicle.color,
        license_plate=vehicle.license_plate,
        fuel_type=vehicle.fuel_type,
        transmission=vehicle.transmission,
        created_at=vehicle.created_at.isoformat() if vehicle.created_at else None,
        updated_at=vehicle.updated_at.isoformat() if vehicle.updated_at else None,
    )


@router.patch("/vehicles/{vehicle_id}")
async def update_vehicle(
    vehicle_id: int,
    request: VehicleProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a vehicle profile."""
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == vehicle_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    vehicle = result.scalar_one_or_none()
    
    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    # Update fields
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    
    await db.commit()
    
    return {"success": True, "message": "Vehicle profile updated"}


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a vehicle profile."""
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == vehicle_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    vehicle = result.scalar_one_or_none()
    
    if not vehicle:
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    await db.delete(vehicle)
    await db.commit()
    
    logger.info(f"Vehicle profile deleted: {vehicle_id}")
    
    return {"success": True, "message": "Vehicle profile deleted"}


# ========================
# Service Records
# ========================

@router.get("/vehicles/{vehicle_id}/service-records", response_model=List[ServiceRecordResponse])
async def list_service_records(
    vehicle_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List service records for a vehicle."""
    # Verify ownership
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == vehicle_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    if not result.scalar_one_or_none():
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    result = await db.execute(
        select(ServiceRecord).where(
            ServiceRecord.profile_id == vehicle_id
        ).order_by(desc(ServiceRecord.service_date))
    )
    records = result.scalars().all()
    
    return [
        ServiceRecordResponse(
            id=r.id,
            service_type=r.service_type,
            description=r.description,
            mileage_at_service=r.mileage_at_service,
            cost=float(r.cost) if r.cost else None,
            service_date=r.service_date.isoformat() if r.service_date else None,
            next_service_date=r.next_service_date.isoformat() if r.next_service_date else None,
            next_service_mileage=r.next_service_mileage,
            provider=r.provider,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in records
    ]


@router.post("/vehicles/{vehicle_id}/service-records")
async def create_service_record(
    vehicle_id: int,
    request: ServiceRecordCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a service record for a vehicle."""
    # Verify ownership
    result = await db.execute(
        select(VehicleProfile).where(
            VehicleProfile.id == vehicle_id,
            VehicleProfile.user_id == current_user['user_id'],
        )
    )
    if not result.scalar_one_or_none():
        raise APIError(
            status_code=404,
            code=ErrorCode.VEHICLE_NOT_FOUND,
            message="Vehicle profile not found",
        )
    
    from datetime import date
    
    record = ServiceRecord(
        profile_id=vehicle_id,
        service_type=request.service_type,
        description=request.description,
        mileage_at_service=request.mileage_at_service,
        cost=request.cost,
        service_date=date.fromisoformat(request.service_date),
        next_service_date=date.fromisoformat(request.next_service_date) if request.next_service_date else None,
        next_service_mileage=request.next_service_mileage,
        provider=request.provider,
        notes=request.notes,
    )
    
    db.add(record)
    await db.commit()
    
    return {"success": True, "message": "Service record added"}
