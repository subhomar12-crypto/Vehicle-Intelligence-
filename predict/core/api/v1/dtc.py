"""
Diagnostic Trouble Code (DTC) endpoints.

Handles:
- DTC lookup
- DTC history tracking
- Active DTCs for vehicles
"""

import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.dtc import DTCCode, DTCHistory
from predict.core.db.models.vehicle import VehicleProfile
from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================
# Response Models
# ========================

class DTCCodesResponse(BaseModel):
    id: int
    code: str
    category: str
    severity: str
    description: str
    meaning: Optional[str]
    symptoms: List[str]
    causes: List[str]
    solutions: List[str]


class DTCHistoryResponse(BaseModel):
    id: int
    dtc_code: str
    dtc_description: str
    status: str
    first_seen_at: str
    last_seen_at: str
    cleared_at: Optional[str]
    mileage_at_detection: Optional[int]


class DTCCreateRequest(BaseModel):
    code: str = Field(..., min_length=5, max_length=5)
    status: str = "active"  # active, pending, cleared
    mileage_at_detection: Optional[int] = None
    freeze_frame: Optional[dict] = None


# ========================
# DTC Lookup
# ========================

@router.get("/lookup/{code}", response_model=DTCCodesResponse)
async def lookup_dtc(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Look up a DTC code by its identifier (e.g., P0300)."""
    code = code.upper().strip()
    
    result = await db.execute(
        select(DTCCode).where(DTCCode.code == code)
    )
    dtc = result.scalar_one_or_none()
    
    if not dtc:
        raise APIError(
            status_code=404,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"DTC code '{code}' not found",
        )
    
    return DTCCodesResponse(
        id=dtc.id,
        code=dtc.code,
        category=dtc.category,
        severity=dtc.severity,
        description=dtc.description,
        meaning=dtc.meaning,
        symptoms=dtc.symptoms or [],
        causes=dtc.causes or [],
        solutions=dtc.solutions or [],
    )


@router.get("/search")
async def search_dtc(
    query: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Search DTC codes by description or code."""
    from sqlalchemy import or_
    
    result = await db.execute(
        select(DTCCode).where(
            or_(
                DTCCode.code.ilike(f"%{query.upper()}%"),
                DTCCode.description.ilike(f"%{query}%"),
            )
        ).limit(limit)
    )
    codes = result.scalars().all()
    
    return [
        {
            "code": c.code,
            "description": c.description,
            "severity": c.severity,
        }
        for c in codes
    ]


# ========================
# Vehicle DTC History
# ========================

@router.get("/vehicle/{profile_id}", response_model=List[DTCHistoryResponse])
async def get_vehicle_dtc_history(
    profile_id: int,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get DTC history for a vehicle."""
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
    
    query = select(DTCHistory, DTCCode).join(
        DTCCode, DTCHistory.dtc_code_id == DTCCode.id
    ).where(
        DTCHistory.profile_id == profile_id
    ).order_by(desc(DTCHistory.last_seen_at))
    
    if status:
        query = query.where(DTCHistory.status == status)
    
    result = await db.execute(query)
    records = result.all()
    
    return [
        DTCHistoryResponse(
            id=history.id,
            dtc_code=dtc.code,
            dtc_description=dtc.description,
            status=history.status,
            first_seen_at=history.first_seen_at.isoformat() if history.first_seen_at else None,
            last_seen_at=history.last_seen_at.isoformat() if history.last_seen_at else None,
            cleared_at=history.cleared_at.isoformat() if history.cleared_at else None,
            mileage_at_detection=history.mileage_at_detection,
        )
        for history, dtc in records
    ]


@router.post("/vehicle/{profile_id}")
async def report_dtc(
    profile_id: int,
    request: DTCCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Report a DTC for a vehicle."""
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
    
    # Get or create DTC code
    code = request.code.upper().strip()
    result = await db.execute(
        select(DTCCode).where(DTCCode.code == code)
    )
    dtc_code = result.scalar_one_or_none()
    
    if not dtc_code:
        # Create unknown DTC code
        category = code[0] + code[1] if len(code) >= 2 else "P0"
        dtc_code = DTCCode(
            code=code,
            category=category,
            severity="unknown",
            description=f"Unknown code: {code}",
        )
        db.add(dtc_code)
        await db.flush()
    
    # Check for existing active entry
    result = await db.execute(
        select(DTCHistory).where(
            DTCHistory.profile_id == profile_id,
            DTCHistory.dtc_code_id == dtc_code.id,
            DTCHistory.status.in_(["active", "pending"]),
        )
    )
    existing = result.scalar_one_or_none()
    
    now = datetime.now(timezone.utc)
    
    if existing:
        # Update existing
        existing.last_seen_at = now
        if request.mileage_at_detection:
            existing.mileage_at_detection = request.mileage_at_detection
    else:
        # Create new entry
        history = DTCHistory(
            profile_id=profile_id,
            dtc_code_id=dtc_code.id,
            status=request.status,
            first_seen_at=now,
            last_seen_at=now,
            mileage_at_detection=request.mileage_at_detection,
            freeze_frame=request.freeze_frame or {},
        )
        db.add(history)
    
    await db.commit()
    
    return {"success": True, "message": f"DTC {code} recorded"}


@router.post("/vehicle/{profile_id}/clear/{code}")
async def clear_dtc(
    profile_id: int,
    code: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a DTC as cleared for a vehicle."""
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
    
    # Get DTC code
    code = code.upper().strip()
    result = await db.execute(
        select(DTCCode).where(DTCCode.code == code)
    )
    dtc_code = result.scalar_one_or_none()
    
    if not dtc_code:
        raise APIError(
            status_code=404,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            message=f"DTC code '{code}' not found",
        )
    
    # Clear active entries
    result = await db.execute(
        select(DTCHistory).where(
            DTCHistory.profile_id == profile_id,
            DTCHistory.dtc_code_id == dtc_code.id,
            DTCHistory.status.in_(["active", "pending"]),
        )
    )
    
    for history in result.scalars():
        history.status = "cleared"
        history.cleared_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    return {"success": True, "message": f"DTC {code} cleared"}
