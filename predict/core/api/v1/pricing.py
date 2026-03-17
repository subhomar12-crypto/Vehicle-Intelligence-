"""
Pricing API — CRUD for parts and service prices (Qatar market).

Admin endpoints: full CRUD + verify web-scraped prices.
Customer endpoints: /estimate/{component_id} returns min/max QAR range.
Mechanic feedback: auto-create price entry from driver service logs.
"""

import logging
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.pricing import PartsPrice, ServicePrice

logger = logging.getLogger(__name__)
router = APIRouter()


# ========================
# Request / Response Models
# ========================

class PartsPriceCreate(BaseModel):
    category: str
    component_id: Optional[str] = None
    name: str
    brand: Optional[str] = None
    part_number: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_qar: float = Field(..., gt=0)
    price_type: str = "retail"
    supplier: Optional[str] = None
    source: str = "admin"
    price_date: Optional[str] = None  # YYYY-MM-DD, defaults to today


class PartsPriceUpdate(BaseModel):
    category: Optional[str] = None
    component_id: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    part_number: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    price_qar: Optional[float] = Field(None, gt=0)
    price_type: Optional[str] = None
    supplier: Optional[str] = None
    source: Optional[str] = None
    price_date: Optional[str] = None


class ServicePriceCreate(BaseModel):
    service_type: str
    component_id: Optional[str] = None
    description: Optional[str] = None
    labor_qar: Optional[float] = None
    parts_qar: Optional[float] = None
    total_qar: float = Field(..., gt=0)
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    provider: Optional[str] = None
    location: Optional[str] = None
    source: str = "admin"
    price_date: Optional[str] = None


class ServicePriceUpdate(BaseModel):
    service_type: Optional[str] = None
    component_id: Optional[str] = None
    description: Optional[str] = None
    labor_qar: Optional[float] = None
    parts_qar: Optional[float] = None
    total_qar: Optional[float] = Field(None, gt=0)
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    provider: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    price_date: Optional[str] = None


class FeedbackPriceRequest(BaseModel):
    component_id: str
    total_cost: float = Field(..., gt=0)
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None


# ========================
# Helpers
# ========================

def _require_admin(current_user: dict) -> None:
    """Verify user is admin. Only tier == 'admin' grants access."""
    if current_user.get("tier") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


def _parse_date(date_str: Optional[str]) -> date:
    """Parse YYYY-MM-DD string or return today."""
    if not date_str:
        return date.today()
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


def _part_to_dict(p: PartsPrice) -> dict:
    return {
        "id": p.id,
        "category": p.category,
        "component_id": p.component_id,
        "name": p.name,
        "brand": p.brand,
        "part_number": p.part_number,
        "vehicle_make": p.vehicle_make,
        "vehicle_model": p.vehicle_model,
        "year_min": p.year_min,
        "year_max": p.year_max,
        "price_qar": p.price_qar,
        "price_type": p.price_type,
        "supplier": p.supplier,
        "source": p.source,
        "source_url": p.source_url,
        "confidence": p.confidence,
        "is_verified": p.is_verified,
        "price_date": str(p.price_date) if p.price_date else None,
    }


def _service_to_dict(s: ServicePrice) -> dict:
    return {
        "id": s.id,
        "service_type": s.service_type,
        "component_id": s.component_id,
        "description": s.description,
        "labor_qar": s.labor_qar,
        "parts_qar": s.parts_qar,
        "total_qar": s.total_qar,
        "vehicle_make": s.vehicle_make,
        "vehicle_model": s.vehicle_model,
        "year_min": s.year_min,
        "year_max": s.year_max,
        "provider": s.provider,
        "location": s.location,
        "source": s.source,
        "source_url": s.source_url,
        "confidence": s.confidence,
        "is_verified": s.is_verified,
        "price_date": str(s.price_date) if s.price_date else None,
    }


# ========================
# Admin — Parts Prices
# ========================

@router.get("/parts")
async def list_parts(
    category: Optional[str] = None,
    component_id: Optional[str] = None,
    vehicle_make: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List / search parts prices (admin only)."""
    _require_admin(current_user)

    stmt = select(PartsPrice)
    if category:
        stmt = stmt.where(PartsPrice.category == category)
    if component_id:
        stmt = stmt.where(PartsPrice.component_id == component_id)
    if vehicle_make:
        stmt = stmt.where(PartsPrice.vehicle_make == vehicle_make)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                PartsPrice.name.ilike(pattern),
                PartsPrice.brand.ilike(pattern),
                PartsPrice.part_number.ilike(pattern),
            )
        )

    # Total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    # Paginated results
    stmt = stmt.order_by(PartsPrice.id.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    parts = [_part_to_dict(p) for p in result.scalars().all()]

    return {"success": True, "parts": parts, "total": total}


@router.post("/parts", status_code=201)
async def create_part(
    body: PartsPriceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a part price (admin only)."""
    _require_admin(current_user)

    part = PartsPrice(
        category=body.category,
        component_id=body.component_id,
        name=body.name,
        brand=body.brand,
        part_number=body.part_number,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        year_min=body.year_min,
        year_max=body.year_max,
        price_qar=body.price_qar,
        price_type=body.price_type,
        supplier=body.supplier,
        source=body.source,
        confidence=1.0,
        is_verified=True,
        price_date=_parse_date(body.price_date),
    )
    session.add(part)
    await session.commit()
    await session.refresh(part)

    logger.info("Admin created part price id=%d name=%s", part.id, part.name)
    return {"success": True, "part": _part_to_dict(part)}


@router.put("/parts/{part_id}")
async def update_part(
    part_id: int,
    body: PartsPriceUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a part price (admin only)."""
    _require_admin(current_user)

    result = await session.execute(
        select(PartsPrice).where(PartsPrice.id == part_id)
    )
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part price not found")

    updates = body.model_dump(exclude_unset=True)
    if "price_date" in updates:
        updates["price_date"] = _parse_date(updates["price_date"])

    for key, value in updates.items():
        setattr(part, key, value)

    await session.commit()
    await session.refresh(part)

    logger.info("Admin updated part price id=%d", part.id)
    return {"success": True, "part": _part_to_dict(part)}


@router.delete("/parts/{part_id}")
async def delete_part(
    part_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a part price (admin only)."""
    _require_admin(current_user)

    result = await session.execute(
        select(PartsPrice).where(PartsPrice.id == part_id)
    )
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(status_code=404, detail="Part price not found")

    await session.delete(part)
    await session.commit()

    logger.info("Admin deleted part price id=%d", part_id)
    return {"success": True}


# ========================
# Admin — Service Prices
# ========================

@router.get("/services")
async def list_services(
    service_type: Optional[str] = None,
    component_id: Optional[str] = None,
    vehicle_make: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List / search service prices (admin only)."""
    _require_admin(current_user)

    stmt = select(ServicePrice)
    if service_type:
        stmt = stmt.where(ServicePrice.service_type == service_type)
    if component_id:
        stmt = stmt.where(ServicePrice.component_id == component_id)
    if vehicle_make:
        stmt = stmt.where(ServicePrice.vehicle_make == vehicle_make)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                ServicePrice.service_type.ilike(pattern),
                ServicePrice.description.ilike(pattern),
                ServicePrice.provider.ilike(pattern),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(ServicePrice.id.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    services = [_service_to_dict(s) for s in result.scalars().all()]

    return {"success": True, "services": services, "total": total}


@router.post("/services", status_code=201)
async def create_service(
    body: ServicePriceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Add a service price (admin only)."""
    _require_admin(current_user)

    svc = ServicePrice(
        service_type=body.service_type,
        component_id=body.component_id,
        description=body.description,
        labor_qar=body.labor_qar,
        parts_qar=body.parts_qar,
        total_qar=body.total_qar,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        year_min=body.year_min,
        year_max=body.year_max,
        provider=body.provider,
        location=body.location,
        source=body.source,
        confidence=1.0,
        is_verified=True,
        price_date=_parse_date(body.price_date),
    )
    session.add(svc)
    await session.commit()
    await session.refresh(svc)

    logger.info("Admin created service price id=%d type=%s", svc.id, svc.service_type)
    return {"success": True, "service": _service_to_dict(svc)}


@router.put("/services/{service_id}")
async def update_service(
    service_id: int,
    body: ServicePriceUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a service price (admin only)."""
    _require_admin(current_user)

    result = await session.execute(
        select(ServicePrice).where(ServicePrice.id == service_id)
    )
    svc = result.scalar_one_or_none()
    if not svc:
        raise HTTPException(status_code=404, detail="Service price not found")

    updates = body.model_dump(exclude_unset=True)
    if "price_date" in updates:
        updates["price_date"] = _parse_date(updates["price_date"])

    for key, value in updates.items():
        setattr(svc, key, value)

    await session.commit()
    await session.refresh(svc)

    logger.info("Admin updated service price id=%d", svc.id)
    return {"success": True, "service": _service_to_dict(svc)}


# ========================
# Admin — Verify web-scraped price
# ========================

@router.post("/verify/{price_id}")
async def verify_price(
    price_id: int,
    price_type: str = Query("parts", pattern="^(parts|services)$"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mark a web-scraped price as verified (admin only).

    Query param `price_type` selects the table: 'parts' or 'services'.
    """
    _require_admin(current_user)

    model = PartsPrice if price_type == "parts" else ServicePrice
    result = await session.execute(select(model).where(model.id == price_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"{price_type.title()} price not found")

    record.is_verified = True
    await session.commit()

    logger.info("Admin verified %s price id=%d", price_type, price_id)
    return {"success": True}


# ========================
# Customer — Price Estimate
# ========================

@router.get("/estimate/{component_id}")
async def get_estimate(
    component_id: str,
    make: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get price estimate for a component.

    Fallback cascade: exact vehicle match -> make-only match -> universal prices.
    Returns min/max QAR range, individual parts, services, and sources.
    """
    parts_rows: List[PartsPrice] = []
    service_rows: List[ServicePrice] = []

    # ---------- parts: try exact → make-only → universal ----------
    parts_rows = await _cascading_parts_lookup(
        session, component_id, make, model, year
    )

    # ---------- services: same cascade ----------
    service_rows = await _cascading_service_lookup(
        session, component_id, make, model, year
    )

    if not parts_rows and not service_rows:
        return {
            "available": False,
            "min_qar": None,
            "max_qar": None,
            "parts": [],
            "services": [],
            "sources": [],
        }

    # Aggregate
    all_prices: List[float] = (
        [p.price_qar for p in parts_rows]
        + [s.total_qar for s in service_rows]
    )
    sources: List[str] = list({
        p.supplier or p.source for p in parts_rows
    } | {
        s.provider or s.source for s in service_rows
    })

    return {
        "available": True,
        "min_qar": round(min(all_prices), 2),
        "max_qar": round(max(all_prices), 2),
        "parts": [
            {"name": p.name, "price": p.price_qar, "supplier": p.supplier}
            for p in parts_rows
        ],
        "services": [
            {"type": s.service_type, "total": s.total_qar, "provider": s.provider}
            for s in service_rows
        ],
        "sources": sources,
    }


async def _cascading_parts_lookup(
    session: AsyncSession,
    component_id: str,
    make: Optional[str],
    model: Optional[str],
    year: Optional[int],
) -> List[PartsPrice]:
    """Cascading lookup: exact vehicle -> make-only -> universal."""
    # 1. Exact vehicle match (make + model + year in range)
    if make and model and year:
        stmt = (
            select(PartsPrice)
            .where(
                PartsPrice.component_id == component_id,
                PartsPrice.vehicle_make == make,
                PartsPrice.vehicle_model == model,
                or_(PartsPrice.year_min.is_(None), PartsPrice.year_min <= year),
                or_(PartsPrice.year_max.is_(None), PartsPrice.year_max >= year),
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        if rows:
            return list(rows)

    # 2. Make-only match
    if make:
        stmt = (
            select(PartsPrice)
            .where(
                PartsPrice.component_id == component_id,
                PartsPrice.vehicle_make == make,
                PartsPrice.vehicle_model.is_(None),
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        if rows:
            return list(rows)

    # 3. Universal (no vehicle fitment)
    stmt = (
        select(PartsPrice)
        .where(
            PartsPrice.component_id == component_id,
            PartsPrice.vehicle_make.is_(None),
            PartsPrice.vehicle_model.is_(None),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _cascading_service_lookup(
    session: AsyncSession,
    component_id: str,
    make: Optional[str],
    model: Optional[str],
    year: Optional[int],
) -> List[ServicePrice]:
    """Cascading lookup: exact vehicle -> make-only -> universal."""
    if make and model and year:
        stmt = (
            select(ServicePrice)
            .where(
                ServicePrice.component_id == component_id,
                ServicePrice.vehicle_make == make,
                ServicePrice.vehicle_model == model,
                or_(ServicePrice.year_min.is_(None), ServicePrice.year_min <= year),
                or_(ServicePrice.year_max.is_(None), ServicePrice.year_max >= year),
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        if rows:
            return list(rows)

    if make:
        stmt = (
            select(ServicePrice)
            .where(
                ServicePrice.component_id == component_id,
                ServicePrice.vehicle_make == make,
                ServicePrice.vehicle_model.is_(None),
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        if rows:
            return list(rows)

    stmt = (
        select(ServicePrice)
        .where(
            ServicePrice.component_id == component_id,
            ServicePrice.vehicle_make.is_(None),
            ServicePrice.vehicle_model.is_(None),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ========================
# Mechanic Feedback → Price Entry
# ========================

@router.post("/from-feedback", status_code=201)
async def create_from_feedback(
    body: FeedbackPriceRequest,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Auto-create a service price entry from a driver's service record.

    Source is 'mechanic_feedback', confidence 0.9.
    """
    svc = ServicePrice(
        service_type=f"{body.component_id}_replacement",
        component_id=body.component_id,
        description=f"Reported by driver via service log",
        total_qar=body.total_cost,
        vehicle_make=body.vehicle_make,
        vehicle_model=body.vehicle_model,
        year_min=body.vehicle_year,
        year_max=body.vehicle_year,
        source="mechanic_feedback",
        confidence=0.9,
        is_verified=False,
        price_date=date.today(),
    )
    session.add(svc)
    await session.commit()
    await session.refresh(svc)

    logger.info(
        "Price from feedback: component=%s cost=%.2f QAR make=%s",
        body.component_id, body.total_cost, body.vehicle_make,
    )
    return {"success": True, "service": _service_to_dict(svc)}
