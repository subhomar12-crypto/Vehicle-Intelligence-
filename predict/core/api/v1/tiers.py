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

from predict.core.api.deps import get_current_user

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
            "daily_obd_requests": -1,  # unlimited
            "stored_vehicles": 1,
            "dtc_checks_total": 2,
            "predictions_per_day": 0,
            "llm_chat_per_day": 0,
            "pdfs_per_week": 0,
            "prediction_history_days": 7,
        },
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "price_monthly": 10,
        "price_yearly": 100,
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
            "daily_obd_requests": -1,  # unlimited
            "stored_vehicles": 1,
            "dtc_checks_total": -1,  # unlimited
            "predictions_per_day": 2,
            "llm_chat_per_day": 15,
            "pdfs_per_week": 1,
            "prediction_history_days": 90,
        },
    },
    {
        "name": "premium",
        "display_name": "Premium",
        "price_monthly": 25,
        "price_yearly": 250,
        "features": {
            "obd_reading": True,
            "dtc_reading": True,
            "basic_predictions": True,
            "ai_chat": True,
            "guardian_mode": True,
            "pdf_reports": True,
            "fleet_management": False,
        },
        "limits": {
            "daily_obd_requests": -1,  # unlimited
            "stored_vehicles": 3,  # 3 vehicles (including registered vehicle)
            "dtc_checks_total": -1,  # unlimited
            "predictions_per_day": 5,  # per vehicle
            "llm_chat_per_day": 25,  # per vehicle
            "pdfs_per_week": 2,  # per vehicle
            "prediction_history_days": 365,
        },
    },
    {
        "name": "admin",
        "display_name": "Admin",
        "price_monthly": 0,
        "price_yearly": 0,
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
            "daily_obd_requests": -1,  # unlimited
            "stored_vehicles": -1,  # unlimited
            "dtc_checks_total": -1,  # unlimited
            "predictions_per_day": -1,  # unlimited
            "llm_chat_per_day": -1,  # unlimited
            "pdfs_per_week": -1,  # unlimited
            "prediction_history_days": -1,  # unlimited
        },
    },
]


# ========================
# Endpoints
# ========================

@router.get("/", response_model=List[TierResponse])
async def list_tiers():
    """List all available subscription tiers."""
    return [TierResponse(**tier) for tier in DEFAULT_TIERS]


@router.get("/list", response_model=List[TierResponse])
async def list_tiers_alias():
    """Alias for list_tiers - Android compatibility."""
    return await list_tiers()


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
