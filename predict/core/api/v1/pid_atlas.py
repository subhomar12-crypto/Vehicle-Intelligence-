"""
PID Atlas API — Community manufacturer PID database.

GET  /api/pids/atlas       — Download known PIDs for a make/model/year
POST /api/pids/atlas/upload — Upload discovered PIDs from a scan
"""

import json
import logging
import time

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select, and_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.pid_atlas import PIDAtlas

logger = logging.getLogger(__name__)
router = APIRouter()


# ===== Request/Response Models =====

class PIDAtlasEntry(BaseModel):
    service: int
    pid_hex: str
    ecu_address: str = ""
    data_byte_count: int = 0
    is_dynamic: bool = False
    semantic_type: str = "unknown"
    name: Optional[str] = None
    unit: Optional[str] = None
    formula: Optional[str] = None
    is_verified: bool = False
    discovery_count: int = 0

class AtlasResponse(BaseModel):
    success: bool = True
    pids: List[PIDAtlasEntry]
    count: int

class UploadPIDEntry(BaseModel):
    service: int
    pid_hex: str
    ecu_address: str = ""
    data_byte_count: int = 0
    is_dynamic: bool = False
    semantic_type: str = "unknown"
    data_bytes: str = ""          # sample hex value
    response_time_ms: int = 0

class UploadRequest(BaseModel):
    profile_id: int
    make: str
    model: str
    year: int
    pids: List[UploadPIDEntry]

class UploadResponse(BaseModel):
    success: bool = True
    uploaded: int
    new_discoveries: int


class AtlasVehicleEntry(BaseModel):
    make: str
    model: str
    year_min: int
    year_max: int
    pid_count: int
    dynamic_count: int
    verified_count: int
    named_count: int

class AtlasVehiclesResponse(BaseModel):
    success: bool = True
    vehicles: List[AtlasVehicleEntry]
    count: int

class AtlasDetailEntry(BaseModel):
    service: int
    pid_hex: str
    ecu_address: str = ""
    data_byte_count: int = 0
    is_dynamic: bool = False
    semantic_type: str = "unknown"
    name: Optional[str] = None
    unit: Optional[str] = None
    formula: Optional[str] = None
    is_verified: bool = False
    discovery_count: int = 0
    sample_values: Optional[str] = None
    first_discovered_at: Optional[float] = None
    last_seen_at: Optional[float] = None

class AtlasDetailResponse(BaseModel):
    success: bool = True
    make: str
    model: str
    pids: List[AtlasDetailEntry]
    count: int


# ===== Endpoints =====

@router.get("/atlas", response_model=AtlasResponse)
async def get_atlas(
    make: str = Query(..., description="Vehicle make (e.g. Nissan)"),
    model: str = Query(..., description="Vehicle model (e.g. Patrol)"),
    year: int = Query(0, description="Vehicle year (optional, filters by range)"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Download all known PIDs for a make/model, optionally filtered by year."""
    make_norm = make.strip().upper()
    model_norm = model.strip().upper()

    conditions = [
        PIDAtlas.make == make_norm,
        PIDAtlas.model == model_norm,
    ]
    if year > 0:
        conditions.append(PIDAtlas.year_min <= year)
        conditions.append(PIDAtlas.year_max >= year)

    result = await db.execute(
        select(PIDAtlas).where(and_(*conditions)).order_by(PIDAtlas.service, PIDAtlas.pid_hex)
    )
    entries = result.scalars().all()

    pids = [
        PIDAtlasEntry(
            service=e.service,
            pid_hex=e.pid_hex,
            ecu_address=e.ecu_address,
            data_byte_count=e.data_byte_count,
            is_dynamic=e.is_dynamic,
            semantic_type=e.semantic_type,
            name=e.name,
            unit=e.unit,
            formula=e.formula,
            is_verified=e.is_verified,
            discovery_count=e.discovery_count,
        )
        for e in entries
    ]

    return AtlasResponse(pids=pids, count=len(pids))


@router.post("/atlas/upload", response_model=UploadResponse)
async def upload_atlas(
    request: UploadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upload discovered manufacturer PIDs from a scan. Upserts into atlas."""
    make_norm = request.make.strip().upper()
    model_norm = request.model.strip().upper()
    new_count = 0

    for pid in request.pids:
        pid_hex_norm = pid.pid_hex.strip().upper()

        # Check if entry already exists
        result = await db.execute(
            select(PIDAtlas).where(and_(
                PIDAtlas.make == make_norm,
                PIDAtlas.model == model_norm,
                PIDAtlas.service == pid.service,
                PIDAtlas.pid_hex == pid_hex_norm,
                PIDAtlas.ecu_address == pid.ecu_address,
            ))
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Increment discovery count and update metadata
            existing.discovery_count += 1
            existing.last_seen_at = time.time()
            # Update dynamic/semantic if more confident (more data)
            if pid.is_dynamic and not existing.is_dynamic:
                existing.is_dynamic = True
            if pid.semantic_type != "unknown" and existing.semantic_type == "unknown":
                existing.semantic_type = pid.semantic_type
            # Merge sample values (keep last 10)
            samples = []
            if existing.sample_values:
                try:
                    samples = json.loads(existing.sample_values)
                except (json.JSONDecodeError, TypeError):
                    samples = []
            if pid.data_bytes and pid.data_bytes not in samples:
                samples.append(pid.data_bytes)
                samples = samples[-10:]  # Keep last 10
            existing.sample_values = json.dumps(samples)
        else:
            # New discovery
            new_entry = PIDAtlas(
                make=make_norm,
                model=model_norm,
                year_min=max(1990, request.year - 5),
                year_max=min(2035, request.year + 5),
                service=pid.service,
                pid_hex=pid_hex_norm,
                ecu_address=pid.ecu_address,
                data_byte_count=pid.data_byte_count,
                is_dynamic=pid.is_dynamic,
                semantic_type=pid.semantic_type,
                discovery_count=1,
                sample_values=json.dumps([pid.data_bytes]) if pid.data_bytes else None,
            )
            db.add(new_entry)
            new_count += 1

    await db.commit()
    logger.info(f"PID Atlas upload: {make_norm} {model_norm} — {len(request.pids)} PIDs ({new_count} new)")

    return UploadResponse(uploaded=len(request.pids), new_discoveries=new_count)


@router.get("/atlas/vehicles", response_model=AtlasVehiclesResponse)
async def get_atlas_vehicles(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all make/model combinations in the atlas with PID counts. For desktop browser."""
    # Group by make+model, aggregate counts
    stmt = (
        select(
            PIDAtlas.make,
            PIDAtlas.model,
            func.min(PIDAtlas.year_min).label("year_min"),
            func.max(PIDAtlas.year_max).label("year_max"),
            func.count().label("pid_count"),
            func.sum(case((PIDAtlas.is_dynamic == True, 1), else_=0)).label("dynamic_count"),
            func.sum(case((PIDAtlas.is_verified == True, 1), else_=0)).label("verified_count"),
            func.sum(case((PIDAtlas.name.isnot(None), 1), else_=0)).label("named_count"),
        )
        .group_by(PIDAtlas.make, PIDAtlas.model)
        .order_by(PIDAtlas.make, PIDAtlas.model)
    )
    result = await db.execute(stmt)
    rows = result.all()

    vehicles = [
        AtlasVehicleEntry(
            make=r.make,
            model=r.model,
            year_min=r.year_min,
            year_max=r.year_max,
            pid_count=r.pid_count,
            dynamic_count=int(r.dynamic_count or 0),
            verified_count=int(r.verified_count or 0),
            named_count=int(r.named_count or 0),
        )
        for r in rows
    ]

    return AtlasVehiclesResponse(vehicles=vehicles, count=len(vehicles))


@router.get("/atlas/detail", response_model=AtlasDetailResponse)
async def get_atlas_detail(
    make: str = Query(..., description="Vehicle make"),
    model: str = Query(..., description="Vehicle model"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get full PID details for a specific make/model. For desktop detail view."""
    make_norm = make.strip().upper()
    model_norm = model.strip().upper()

    result = await db.execute(
        select(PIDAtlas)
        .where(and_(PIDAtlas.make == make_norm, PIDAtlas.model == model_norm))
        .order_by(PIDAtlas.service, PIDAtlas.pid_hex)
    )
    entries = result.scalars().all()

    pids = [
        AtlasDetailEntry(
            service=e.service,
            pid_hex=e.pid_hex,
            ecu_address=e.ecu_address,
            data_byte_count=e.data_byte_count,
            is_dynamic=e.is_dynamic,
            semantic_type=e.semantic_type,
            name=e.name,
            unit=e.unit,
            formula=e.formula,
            is_verified=e.is_verified,
            discovery_count=e.discovery_count,
            sample_values=e.sample_values,
            first_discovered_at=e.first_discovered_at,
            last_seen_at=e.last_seen_at,
        )
        for e in entries
    ]

    return AtlasDetailResponse(
        make=make_norm,
        model=model_norm,
        pids=pids,
        count=len(pids),
    )
