"""
Diagnostic Trouble Code (DTC) endpoints.

Endpoints (all mounted under /api/dtc via router.py):
- POST /api/dtc/report?vehicle_id=N  - Report DTC codes from OBD scan (Android)
- GET  /api/dtc/{vehicle_id}          - Get all DTC records for a vehicle
- GET  /api/dtc/{vehicle_id}/active   - Get only active DTCs
- GET  /api/dtc/{vehicle_id}/summary  - Count summary of active/pending DTCs
- GET  /api/dtc/lookup/{code}         - Basic lookup (from stored records)
"""

import logging
import time
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class DTCReportRequest(BaseModel):
    """Body for POST /report — submitted by Android OBD scanner."""
    codes: List[str] = Field(..., description="List of DTC code strings e.g. ['P0301', 'P0420']")
    is_pending: bool = Field(False, description="True = Mode 07 pending, False = Mode 03 stored")
    freeze_frame: Optional[Dict[str, Any]] = None


class DTCReportResponse(BaseModel):
    success: bool
    vehicle_id: int
    codes_submitted: int
    new_codes: int
    message: str


# =============================================================================
# HELPERS
# =============================================================================

def _get_dtc_info(code: str):
    """Return (description, category, severity) for a DTC code string."""
    code = code.upper()
    system = code[0] if code else "P"
    category_map = {"P": "powertrain", "C": "chassis", "B": "body", "U": "network"}
    category = category_map.get(system, "unknown")

    severity_map = {
        "P0": "medium", "P1": "high", "P2": "medium", "P3": "low",
        "C0": "high", "B0": "medium", "U0": "high",
    }
    prefix = code[:2] if len(code) >= 2 else "P0"
    severity = severity_map.get(prefix, "medium")
    description = f"OBD-II code {code}"
    return description, category, severity


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/report", response_model=DTCReportResponse)
async def report_dtc_codes(
    vehicle_id: int,
    request: DTCReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Report DTC codes detected during OBD scan.

    Called by Android TelemetryManager every ~60 data cycles.
    vehicle_id is the profile_id from vehicle_profiles.
    """
    from predict.core.db.models.dtc import DTCCodes, DTCHistory

    if not request.codes:
        return DTCReportResponse(
            success=True, vehicle_id=vehicle_id,
            codes_submitted=0, new_codes=0, message="No codes to submit"
        )

    now = time.time()
    new_count = 0

    for raw_code in request.codes:
        code = raw_code.strip().upper()
        if not code:
            continue

        # Upsert: check if this code is already active for this vehicle
        stmt = select(DTCCodes).where(
            and_(
                DTCCodes.vehicle_id == vehicle_id,
                DTCCodes.code == code,
                DTCCodes.is_pending == int(request.is_pending),
                DTCCodes.is_active == 1,
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.last_seen = now
            existing.occurrence_count = (existing.occurrence_count or 1) + 1
        else:
            description, category, severity = _get_dtc_info(code)
            dtc = DTCCodes(
                vehicle_id=vehicle_id,
                code=code,
                description=description,
                category=category,
                severity=severity,
                is_pending=int(request.is_pending),
                first_seen=now,
                last_seen=now,
                occurrence_count=1,
                is_active=1,
                cleared_at=None,
                freeze_frame_json=str(request.freeze_frame) if request.freeze_frame else None,
            )
            db.add(dtc)
            new_count += 1

        # Always log to history
        history = DTCHistory(
            vehicle_id=vehicle_id,
            code=code,
            event_type="detected_pending" if request.is_pending else "detected_stored",
            timestamp=now,
        )
        db.add(history)

    await db.commit()

    return DTCReportResponse(
        success=True,
        vehicle_id=vehicle_id,
        codes_submitted=len(request.codes),
        new_codes=new_count,
        message=f"Reported {len(request.codes)} DTC codes ({new_count} new)",
    )


@router.get("/{vehicle_id}/active")
async def get_active_dtcs(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get currently active DTC codes for a vehicle."""
    from predict.core.db.models.dtc import DTCCodes

    stmt = (
        select(DTCCodes)
        .where(
            and_(
                DTCCodes.vehicle_id == vehicle_id,
                DTCCodes.is_active == 1,
            )
        )
        .order_by(DTCCodes.last_seen.desc())
    )
    result = await db.execute(stmt)
    codes = result.scalars().all()

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "count": len(codes),
        "codes": [
            {
                "id": c.id,
                "code": c.code,
                "description": c.description,
                "category": c.category,
                "severity": c.severity,
                "is_pending": c.is_pending,
                "first_seen": c.first_seen,
                "last_seen": c.last_seen,
                "occurrence_count": c.occurrence_count,
            }
            for c in codes
        ],
    }


@router.get("/{vehicle_id}")
async def get_dtc_history(
    vehicle_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get DTC history for a vehicle (both active and cleared)."""
    from predict.core.db.models.dtc import DTCCodes

    stmt = (
        select(DTCCodes)
        .where(DTCCodes.vehicle_id == vehicle_id)
        .order_by(DTCCodes.last_seen.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    codes = result.scalars().all()

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "count": len(codes),
        "codes": [
            {
                "id": c.id,
                "code": c.code,
                "description": c.description,
                "category": c.category,
                "severity": c.severity,
                "is_pending": c.is_pending,
                "is_active": bool(c.is_active),
                "first_seen": c.first_seen,
                "last_seen": c.last_seen,
                "occurrence_count": c.occurrence_count,
                "cleared_at": c.cleared_at,
            }
            for c in codes
        ],
    }


@router.get("/{vehicle_id}/summary")
async def get_dtc_summary(
    vehicle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get DTC count summary for a vehicle."""
    from predict.core.db.models.dtc import DTCCodes

    total_stmt = select(func.count()).select_from(DTCCodes).where(
        DTCCodes.vehicle_id == vehicle_id
    )
    active_stmt = select(func.count()).select_from(DTCCodes).where(
        and_(DTCCodes.vehicle_id == vehicle_id, DTCCodes.is_active == 1)
    )
    pending_stmt = select(func.count()).select_from(DTCCodes).where(
        and_(DTCCodes.vehicle_id == vehicle_id, DTCCodes.is_active == 1, DTCCodes.is_pending == 1)
    )

    total = (await db.execute(total_stmt)).scalar() or 0
    active = (await db.execute(active_stmt)).scalar() or 0
    pending = (await db.execute(pending_stmt)).scalar() or 0

    return {
        "success": True,
        "vehicle_id": vehicle_id,
        "total": total,
        "active": active,
        "pending": pending,
        "stored": active - pending,
    }


@router.get("/lookup/{code}")
async def lookup_dtc(
    code: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Look up basic info for a DTC code string."""
    from predict.core.db.models.dtc import DTCCodes

    code = code.upper().strip()
    description, category, severity = _get_dtc_info(code)

    # Check if this code has been seen on any vehicle
    stmt = select(DTCCodes).where(DTCCodes.code == code).limit(1)
    result = await db.execute(stmt)
    sample = result.scalar_one_or_none()

    return {
        "code": code,
        "description": sample.description if sample else description,
        "category": category,
        "severity": severity,
        "seen_on_vehicles": sample is not None,
    }
