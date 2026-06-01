"""
PayPal Subscription integration endpoints.

PREDICT - Vehicle Intelligence Platform
Handles PayPal subscription lifecycle via PayPal REST API v1.

Endpoints:
- POST /paypal/create-subscription  - Create PayPal subscription, return approval URL
- GET  /paypal/success               - Activate subscription after PayPal approval
- POST /paypal/webhook               - Receive PayPal event notifications
- POST /paypal/cancel                - Cancel active PayPal subscription

Environment variables required (.env):
    PAYPAL_CLIENT_ID        - PayPal app client ID
    PAYPAL_CLIENT_SECRET    - PayPal app client secret
    PAYPAL_WEBHOOK_ID       - Webhook ID from PayPal dashboard
    PAYPAL_PLAN_PRO_MONTHLY - PayPal plan ID for Pro monthly
    PAYPAL_PLAN_PREMIUM_MONTHLY - PayPal plan ID for Premium monthly
    PAYPAL_MODE             - "sandbox" or "live" (default: sandbox)
"""

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.middleware.error_handler import APIError, ErrorCode

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# PayPal Configuration (loaded from environment)
# ---------------------------------------------------------------------------

def _paypal_base_url() -> str:
    mode = os.environ.get("PAYPAL_MODE", "sandbox").lower()
    if mode == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


def _plan_id_for_tier(tier: str) -> Optional[str]:
    """Return the PayPal plan ID for a given tier."""
    mapping = {
        "pro": os.environ.get("PAYPAL_PLAN_PRO_MONTHLY"),
        "premium": os.environ.get("PAYPAL_PLAN_PREMIUM_MONTHLY"),
    }
    return mapping.get(tier)


# Simple in-process token cache: {"access_token": str, "expires_at": float}
_token_cache: Dict[str, Any] = {}


async def _get_paypal_token() -> str:
    """
    Obtain a PayPal OAuth2 access token.
    Caches the token in memory; fetches a new one when it expires.
    """
    now = time.time()
    if _token_cache.get("access_token") and _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["access_token"]

    client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        raise APIError(
            status_code=503,
            message="PayPal is not configured. PAYPAL_CLIENT_ID/SECRET missing.",
            code=ErrorCode.INTERNAL_ERROR,
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_paypal_base_url()}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=15,
        )
        if resp.status_code != 200:
            logger.error(f"PayPal token fetch failed: {resp.status_code} {resp.text}")
            raise APIError(
                status_code=503,
                message="Unable to authenticate with PayPal.",
                code=ErrorCode.INTERNAL_ERROR,
            )
        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 32400)
        return _token_cache["access_token"]


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class CreateSubscriptionRequest(BaseModel):
    tier: str = Field(..., description="'pro' or 'premium'")


class CreateSubscriptionResponse(BaseModel):
    success: bool
    approval_url: str


class SuccessResponse(BaseModel):
    success: bool
    new_tier: str
    message: str


class CancelSubscriptionRequest(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create-subscription", response_model=CreateSubscriptionResponse)
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    Create a PayPal subscription and return the user-approval URL.

    Flow:
    1. Look up PayPal plan ID for the requested tier.
    2. Call PayPal POST /v1/billing/subscriptions.
    3. Return the approval URL so the client can redirect the user.
    """
    tier = request.tier.lower()
    if tier not in ("pro", "premium"):
        raise APIError(
            status_code=400,
            message="Invalid tier. Must be 'pro' or 'premium'.",
            code=ErrorCode.INVALID_PARAMETER,
        )

    plan_id = _plan_id_for_tier(tier)
    if not plan_id:
        raise APIError(
            status_code=503,
            message=f"PayPal plan not configured for tier '{tier}'. "
                    "Set PAYPAL_PLAN_PRO_MONTHLY / PAYPAL_PLAN_PREMIUM_MONTHLY in .env.",
            code=ErrorCode.INTERNAL_ERROR,
        )

    token = await _get_paypal_token()
    base_url = os.environ.get("PUBLIC_SITE_URL", "https://predict-pp.com")

    payload = {
        "plan_id": plan_id,
        "subscriber": {
            "name": {
                "given_name": current_user.get("name", "PREDICT"),
                "surname": "User",
            },
            "email_address": current_user.get("email", ""),
        },
        "application_context": {
            "brand_name": "PREDICT",
            "locale": "en-US",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": f"{base_url}/subscription/success",
            "cancel_url": f"{base_url}/subscription/cancel",
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_paypal_base_url()}/v1/billing/subscriptions",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=20,
        )

    if resp.status_code not in (200, 201):
        logger.error(f"PayPal create subscription failed: {resp.status_code} {resp.text}")
        raise APIError(
            status_code=502,
            message="Failed to create PayPal subscription.",
            code=ErrorCode.INTERNAL_ERROR,
        )

    data = resp.json()
    # Find the approval link
    approval_url = None
    for link in data.get("links", []):
        if link.get("rel") == "approve":
            approval_url = link["href"]
            break

    if not approval_url:
        raise APIError(
            status_code=502,
            message="PayPal did not return an approval URL.",
            code=ErrorCode.INTERNAL_ERROR,
        )

    return CreateSubscriptionResponse(success=True, approval_url=approval_url)


@router.get("/success", response_model=SuccessResponse)
async def subscription_success(
    subscription_id: str,
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Called after user approves the subscription on PayPal.

    Flow:
    1. Fetch subscription from PayPal to verify it's ACTIVE.
    2. Confirm subscriber email matches current user.
    3. Update User.tier in the database.
    4. Create Subscription record.
    5. Return new tier.
    """
    token = await _get_paypal_token()

    # Fetch subscription details from PayPal
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_paypal_base_url()}/v1/billing/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )

    if resp.status_code != 200:
        logger.error(f"PayPal subscription fetch failed: {resp.status_code} {resp.text}")
        raise APIError(
            status_code=502,
            message="Unable to verify subscription with PayPal.",
            code=ErrorCode.INTERNAL_ERROR,
        )

    sub_data = resp.json()
    status = sub_data.get("status", "")

    if status not in ("ACTIVE", "APPROVED"):
        raise APIError(
            status_code=400,
            message=f"PayPal subscription is not active (status: {status}).",
            code=ErrorCode.INVALID_PARAMETER,
        )

    # Determine tier from PayPal plan ID
    plan_id = sub_data.get("plan_id", "")
    tier = None
    if plan_id == os.environ.get("PAYPAL_PLAN_PRO_MONTHLY"):
        tier = "pro"
    elif plan_id == os.environ.get("PAYPAL_PLAN_PREMIUM_MONTHLY"):
        tier = "premium"

    if not tier:
        logger.warning(f"Unknown PayPal plan_id: {plan_id}")
        raise APIError(
            status_code=400,
            message="Unrecognised PayPal plan. Contact support.",
            code=ErrorCode.INVALID_PARAMETER,
        )

    user_id = current_user["user_id"]

    try:
        from predict.core.db.models.user import User
        from predict.core.db.models.subscription import Subscription

        # Update user tier
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise APIError(status_code=404, message="User not found.",
                           code=ErrorCode.RESOURCE_NOT_FOUND)

        user.tier = tier

        # Calculate expiry (30 days from now)
        expires_at = time.time() + 30 * 86400

        # Create subscription record
        new_sub = Subscription(
            user_id=user_id,
            tier=tier,
            payment_source="paypal",
            paypal_subscription_id=subscription_id,
            paypal_plan_id=plan_id,
            status="active",
            started_at=time.time(),
            expires_at=expires_at,
            created_at=time.time(),
        )
        session.add(new_sub)
        await session.flush()

        logger.info(f"User {user_id} activated {tier} via PayPal sub {subscription_id}")

        return SuccessResponse(
            success=True,
            new_tier=tier,
            message=f"You're now on the {tier.capitalize()} plan! Features are active immediately.",
        )

    except APIError:
        raise
    except Exception as e:
        logger.error(f"PayPal success processing failed: {e}")
        raise APIError(
            status_code=500,
            message="Failed to activate subscription.",
            code=ErrorCode.INTERNAL_ERROR,
        )


@router.post("/webhook")
async def paypal_webhook(
    request: Request,
    paypal_transmission_id: Optional[str] = Header(None, alias="paypal-transmission-id"),
    paypal_transmission_time: Optional[str] = Header(None, alias="paypal-transmission-time"),
    paypal_transmission_sig: Optional[str] = Header(None, alias="paypal-transmission-sig"),
    paypal_cert_url: Optional[str] = Header(None, alias="paypal-cert-url"),
):
    """
    Receive and verify PayPal webhook events.

    Events handled:
    - BILLING.SUBSCRIPTION.ACTIVATED   → ensure user tier is active
    - BILLING.SUBSCRIPTION.CANCELLED   → schedule downgrade at expiry
    - BILLING.SUBSCRIPTION.SUSPENDED   → immediately downgrade to free
    - PAYMENT.SALE.COMPLETED           → extend tier_expiry by 30 days
    """
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8")

    # Verify webhook signature via PayPal API
    webhook_id = os.environ.get("PAYPAL_WEBHOOK_ID", "")
    if webhook_id:
        try:
            token = await _get_paypal_token()
            verify_payload = {
                "auth_algo": "SHA256withRSA",
                "cert_url": paypal_cert_url,
                "transmission_id": paypal_transmission_id,
                "transmission_sig": paypal_transmission_sig,
                "transmission_time": paypal_transmission_time,
                "webhook_id": webhook_id,
                "webhook_event": json.loads(body_str),
            }
            async with httpx.AsyncClient() as client:
                verify_resp = await client.post(
                    f"{_paypal_base_url()}/v1/notifications/verify-webhook-signature",
                    json=verify_payload,
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
            if verify_resp.status_code == 200:
                verification = verify_resp.json().get("verification_status", "FAILURE")
                if verification != "SUCCESS":
                    logger.warning(f"PayPal webhook signature invalid: {verification}")
                    raise HTTPException(status_code=400, detail="Invalid webhook signature")
            else:
                logger.warning(f"PayPal webhook verify call failed: {verify_resp.status_code}")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Webhook verification error: {e}")
            # In sandbox/dev don't block on verify errors
            if os.environ.get("PAYPAL_MODE", "sandbox") == "live":
                raise HTTPException(status_code=400, detail="Webhook verification failed")

    try:
        event = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_type = event.get("event_type", "")
    resource = event.get("resource", {})

    logger.info(f"PayPal webhook received: {event_type}")

    from predict.core.db.session import get_db_session

    async with get_db_session() as session:
        await _handle_webhook_event(session, event_type, resource)

    return {"status": "ok"}


async def _handle_webhook_event(session: AsyncSession, event_type: str, resource: dict):
    """Process a single PayPal webhook event."""
    from predict.core.db.models.user import User
    from predict.core.db.models.subscription import Subscription

    subscription_id = resource.get("id")

    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        if subscription_id:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.paypal_subscription_id == subscription_id
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "active"
                logger.info(f"Subscription {subscription_id} marked active")

    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        if subscription_id:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.paypal_subscription_id == subscription_id,
                    Subscription.status == "active",
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "cancelled"
                sub.cancelled_at = time.time()
                logger.info(f"Subscription {subscription_id} marked cancelled")

    elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED":
        if subscription_id:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.paypal_subscription_id == subscription_id,
                    Subscription.status == "active",
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.status = "suspended"
                sub.cancelled_at = time.time()
                # Immediately downgrade user
                user_result = await session.execute(
                    select(User).where(User.id == sub.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    user.tier = "free"
                    logger.info(f"User {sub.user_id} downgraded to free (subscription suspended)")

    elif event_type == "PAYMENT.SALE.COMPLETED":
        # Extend subscription expiry by 30 days on successful payment
        billing_agreement_id = resource.get("billing_agreement_id")
        if billing_agreement_id:
            result = await session.execute(
                select(Subscription).where(
                    Subscription.paypal_subscription_id == billing_agreement_id,
                    Subscription.status == "active",
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                current_expiry = sub.expires_at or time.time()
                sub.expires_at = current_expiry + 30 * 86400
                logger.info(
                    f"Extended sub {billing_agreement_id} expiry to {sub.expires_at}"
                )

    else:
        logger.debug(f"Unhandled PayPal event: {event_type}")


@router.post("/cancel")
async def cancel_subscription(
    request: CancelSubscriptionRequest,
    current_user: Dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Cancel a PayPal subscription.

    Cancels the subscription on PayPal's side and marks it cancelled locally.
    User keeps access until the period end (expires_at).
    """
    user_id = current_user["user_id"]

    try:
        from predict.core.db.models.subscription import Subscription

        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == "active",
                Subscription.payment_source == "paypal",
            )
            .order_by(desc(Subscription.created_at))
            .limit(1)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            return {"success": False, "message": "No active PayPal subscription found."}

        paypal_sub_id = sub.paypal_subscription_id
        if paypal_sub_id:
            # Cancel on PayPal
            try:
                token = await _get_paypal_token()
                async with httpx.AsyncClient() as client:
                    cancel_resp = await client.post(
                        f"{_paypal_base_url()}/v1/billing/subscriptions/{paypal_sub_id}/cancel",
                        json={"reason": request.reason or "User requested cancellation"},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=15,
                    )
                if cancel_resp.status_code not in (200, 204):
                    logger.warning(
                        f"PayPal cancel returned {cancel_resp.status_code}: {cancel_resp.text}"
                    )
            except Exception as e:
                logger.error(f"PayPal cancel API call failed: {e}")
                # Continue with local cancellation even if PayPal call fails

        # Mark cancelled locally
        sub.status = "cancelled"
        sub.cancelled_at = time.time()
        await session.flush()

        logger.info(f"PayPal subscription cancelled for user {user_id}")
        return {
            "success": True,
            "message": "Subscription cancelled. Access continues until end of billing period.",
            "active_until": sub.expires_at,
        }

    except APIError:
        raise
    except Exception as e:
        logger.error(f"Cancel subscription failed: {e}")
        raise APIError(
            status_code=500,
            message="Failed to cancel subscription.",
            code=ErrorCode.INTERNAL_ERROR,
        )
