"""
Subscription tier endpoints.

Handles:
- Tier information
- Feature lists
- Upgrade paths
"""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.models.user import TierPreset

router = APIRouter()


# ========================
# Response Models
# ========================

class TierResponse(BaseModel):
    name: str
    display_name: str
    price_monthly: float
    price_yearly: float
    features: dict
    limits: dict


class TierComparisonResponse(BaseModel):
    tiers: List[TierResponse]
    recommended: str


# ========================
# Tier Data (can be moved to DB)
# ========================

DEFAULT_TIERS = [
    {
        "name": "free",
        "display_name": "Free",
        "price_monthly": 0,
        "price_yearly": 0,
        "features": {
            "obd_reading": True,
            "dtc_reading": True,
            "basic_predictions": True,
            "ai_chat": False,
            "guardian_mode": False,
            "pdf_reports": False,
            "fleet_management": False,
        },
        "limits": {
            "daily_obd_requests": 50,
            "stored_vehicles": 1,
            "prediction_history_days": 7,
        },
    },
    {
        "name": "basic",
        "display_name": "Basic",
        "price_monthly": 9.99,
        "price_yearly": 99.99,
        "features": {
            "obd_reading": True,
            "dtc_reading": True,
            "basic_predictions": True,
            "ai_chat": False,
            "guardian_mode": False,
            "pdf_reports": False,
            "fleet_management": False,
        },
        "limits": {
            "daily_obd_requests": 500,
            "stored_vehicles": 3,
            "prediction_history_days": 30,
        },
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "price_monthly": 19.99,
        "price_yearly": 199.99,
        "features": {
            "obd_reading": True,
            "dtc_reading": True,
            "basic_predictions": True,
            "ai_chat": True,
            "guardian_mode": False,
            "pdf_reports": True,
            "fleet_management": False,
        },
        "limits": {
            "daily_obd_requests": 2000,
            "stored_vehicles": 10,
            "prediction_history_days": 90,
        },
    },
    {
        "name": "premium",
        "display_name": "Premium",
        "price_monthly": 39.99,
        "price_yearly": 399.99,
        "features": {
            "obd_reading": True,
            "dtc_reading": True,
            "basic_predictions": True,
            "ai_chat": True,
            "guardian_mode": True,
            "pdf_reports": True,
            "fleet_management": True,
        },
        "limits": {
            "daily_obd_requests": 10000,
            "stored_vehicles": 50,
            "prediction_history_days": 365,
        },
    },
]


# ========================
# Endpoints
# ========================

@router.get("/", response_model=List[TierResponse])
async def list_tiers(
    db: AsyncSession = Depends(get_db),
):
    """List all available subscription tiers."""
    # Try to get from database first
    result = await db.execute(
        select(TierPreset).where(TierPreset.is_active == True)
    )
    db_tiers = result.scalars().all()
    
    if db_tiers:
        return [
            TierResponse(
                name=t.name,
                display_name=t.display_name,
                price_monthly=float(t.price_monthly),
                price_yearly=float(t.price_yearly),
                features=t.features or {},
                limits=t.limits or {},
            )
            for t in db_tiers
        ]
    
    # Fallback to defaults
    return [TierResponse(**tier) for tier in DEFAULT_TIERS]


@router.get("/current")
async def get_current_tier(
    current_user: dict = Depends(get_current_user),
):
    """Get current user's tier information."""
    return {
        "tier": current_user.get('tier', 'free'),
        "permissions": current_user.get('permissions', []),
    }


@router.get("/features")
async def get_tier_features(
    tier: Optional[str] = None,
):
    """Get features available for a tier (or all tiers)."""
    if tier:
        for t in DEFAULT_TIERS:
            if t["name"] == tier.lower():
                return {
                    "tier": t["name"],
                    "features": t["features"],
                    "limits": t["limits"],
                }
        return {"error": "Tier not found"}
    
    return {
        t["name"]: {
            "features": t["features"],
            "limits": t["limits"],
        }
        for t in DEFAULT_TIERS
    }
