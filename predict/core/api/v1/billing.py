"""
Google Play Billing verification endpoints.

PREDICT - Vehicle Intelligence Platform
Handles subscription management via Google Play Billing.
Server verifies purchase tokens via Google Play Developer API.

Endpoints:
- POST /billing/verify-purchase - Verify Google Play purchase and upgrade tier
- GET /billing/subscription - Current subscription status
- POST /billing/cancel - Cancel subscription
- GET /billing/tiers - List available tiers
- GET /billing/history - Payment history
"""

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db as get_db_session
from predict.core.api.deps import get_db, get_current_user
from predict.core.middleware.error_handler import APIError, ErrorCode
from predict.core.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Plan Configuration
# ---------------------------------------------------------------------------

PLANS = {
    "predict_pro_monthly": {
        "name": "Pro Monthly",
        "tier": "pro",
        "interval": "monthly",
        "price_usd": 10,
    },
    "predict_pro_annual": {
        "name": "Pro Annual",
        "tier": "pro",
        "interval": "annual",
        "price_usd": 100,
    },
    "predict_premium_monthly": {
        "name": "Premium Monthly",
        "tier": "premium",
        "interval": "monthly",
        "price_usd": 25,
    },
    "predict_premium_annual": {
        "name": "Premium Annual",
        "tier": "premium",
        "interval": "annual",
        "price_usd": 250,
    },
}

TIER_INFO = {
    "free": {
        "name": "Free",
        "price": 0,
        "features": ["OBD Gauges", "Unlimited OBD Data Upload", "1 Vehicle"],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 10,
        "price_annual": 100,
        "features": [
            "Everything in Free",
            "DTC Reader (Unlimited)",
            "AI Predictions (2/day)",
            "AI Chat (15/day)",
            "PDF Reports (1/week)",
            "1 Vehicle",
        ],
    },
    "premium": {
        "name": "Premium",
        "price_monthly": 25,
        "price_annual": 250,
        "features": [
            "Everything in Pro (5x limits)",
            "Guardian Mode",
            "AI Predictions (10/day)",
            "AI Chat (75/day)",
            "PDF Reports (5/week)",
            "5 Vehicles",
        ],
    },
}


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class VerifyPurchaseRequest(BaseModel):
    """Request to verify a Google Play purchase."""
    purchase_token: str = Field(..., description="Google Play purchase token")
    product_id: str = Field(..., description="Google Play product ID (e.g., predict_pro_monthly)")
    order_id: Optional[str] = Field(None, description="Google Play order ID")


class VerifyPurchaseResponse(BaseModel):
    """Response after verifying purchase."""
    success: bool
    tier: str
    message: str
    subscription_id: Optional[int] = None


class SubscriptionStatusResponse(BaseModel):
    """Current subscription status."""
    success: bool
    tier: str
    status: str  # "active", "cancelled", "expired", "none"
    product_id: Optional[str] = None
    expires_at: Optional[float] = None


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""
    reason: Optional[str] = None


class TierListResponse(BaseModel):
    """Available tiers response."""
    success: bool
    tiers: Dict[str, Any]
    plans: Dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/verify-purchase", response_model=VerifyPurchaseResponse)
async def verify_purchase(
    request: VerifyPurchaseRequest,
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Verify a Google Play purchase and upgrade user tier.

    Flow:
    1. Receive purchase token from Android app
    2. Verify with Google Play Developer API
    3. Update user tier in database
    4. Create subscription record
    """
    # Validate product ID
    plan = PLANS.get(request.product_id)
    if not plan:
        raise APIError(
            status_code=400,
            message=f"Unknown product ID: {request.product_id}",
            code=ErrorCode.INVALID_PARAMETER,
        )

    target_tier = plan["tier"]
    user_id = current_user["user_id"]

    # TODO: Verify purchase token with Google Play Developer API
    # For now, trust the client (implement server-side verification before production)
    # from google.oauth2 import service_account
    # from googleapiclient.discovery import build
    # credentials = service_account.Credentials.from_service_account_file(...)
    # service = build('androidpublisher', 'v3', credentials=credentials)
    # result = service.purchases().subscriptions().get(
    #     packageName='com.predict.app',
    #     subscriptionId=request.product_id,
    #     token=request.purchase_token
    # ).execute()

    try:
        from predict.core.db.models.user import User

        # Update user tier
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise APIError(
                status_code=404,
                message="User not found",
                code=ErrorCode.RESOURCE_NOT_FOUND,
            )

        user.tier = target_tier

        # Create subscription record
        from predict.core.db.models.subscription import Subscription

        subscription = Subscription(
            user_id=user_id,
            tier=target_tier,
            google_purchase_token=request.purchase_token,
            google_product_id=request.product_id,
            google_order_id=request.order_id,
            status="active",
            started_at=time.time(),
            created_at=time.time(),
        )
        session.add(subscription)
        await session.flush()

        logger.info(f"User {user_id} upgraded to {target_tier} via {request.product_id}")

        return VerifyPurchaseResponse(
            success=True,
            tier=target_tier,
            message=f"Successfully upgraded to {plan['name']}",
            subscription_id=subscription.id,
        )

    except APIError:
        raise
    except Exception as e:
        logger.error(f"Purchase verification failed: {e}")
        raise APIError(
            status_code=500,
            message="Failed to process purchase",
            code=ErrorCode.INTERNAL_ERROR,
        )


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription(
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get current subscription status."""
    user_id = current_user["user_id"]
    tier = current_user.get("tier", "free")

    try:
        from predict.core.db.models.subscription import Subscription

        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .order_by(desc(Subscription.created_at))
            .limit(1)
        )
        sub = result.scalar_one_or_none()

        if sub:
            return SubscriptionStatusResponse(
                success=True,
                tier=sub.tier,
                status=sub.status,
                product_id=sub.google_product_id,
                expires_at=sub.expires_at,
            )

        return SubscriptionStatusResponse(
            success=True,
            tier=tier,
            status="none" if tier == "free" else "active",
        )

    except Exception as e:
        logger.error(f"Failed to get subscription: {e}")
        return SubscriptionStatusResponse(
            success=True,
            tier=tier,
            status="unknown",
        )


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Cancel active subscription."""
    user_id = current_user["user_id"]

    try:
        from predict.core.db.models.subscription import Subscription

        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
            )
            .order_by(desc(Subscription.created_at))
            .limit(1)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            return {"success": False, "message": "No active subscription found"}

        sub.status = "cancelled"
        sub.cancelled_at = time.time()
        await session.flush()

        # Note: User keeps their tier until the subscription period ends
        # A cron job should downgrade expired subscriptions

        logger.info(f"Subscription cancelled for user {user_id}")
        return {
            "success": True,
            "message": "Subscription cancelled. Access continues until end of billing period.",
        }

    except Exception as e:
        logger.error(f"Cancel failed: {e}")
        raise APIError(
            status_code=500,
            message="Failed to cancel subscription",
            code=ErrorCode.INTERNAL_ERROR,
        )


@router.get("/tiers", response_model=TierListResponse)
async def get_tiers():
    """List available tiers and pricing."""
    return TierListResponse(
        success=True,
        tiers=TIER_INFO,
        plans=PLANS,
    )


@router.get("/history")
async def get_payment_history(
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get payment/subscription history."""
    user_id = current_user["user_id"]

    try:
        from predict.core.db.models.subscription import Subscription

        result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(desc(Subscription.created_at))
            .limit(50)
        )
        subs = result.scalars().all()

        return {
            "success": True,
            "history": [
                {
                    "id": s.id,
                    "tier": s.tier,
                    "product_id": s.google_product_id,
                    "status": s.status,
                    "started_at": s.started_at,
                    "expires_at": s.expires_at,
                    "cancelled_at": s.cancelled_at,
                }
                for s in subs
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return {"success": True, "history": []}
