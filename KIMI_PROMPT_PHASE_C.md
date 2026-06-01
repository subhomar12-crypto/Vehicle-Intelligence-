# KIMI PROMPT — Phase C: Unified Auth + Google Play Billing + GaugeSmoother

---

## YOUR ROLE

You are a senior full-stack engineer working on the **PREDICT Vehicle Intelligence Platform**. You have two codebases:

- **Server**: `C:\D Drive\Predict` — FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL + Alembic
- **Android**: `C:\New APK` — Kotlin, Jetpack Compose, Retrofit 2, OkHttp

**Phase A** (server fixes) and **Phase B** (Android network refactor) are already complete. You are now executing **Phase C**: converting the dual-auth system (X-API-Key + Guardian JWT) into a single API-key system with tier-based feature gating, replacing Fatora billing with Google Play Billing, and refactoring all OBD gauges to use a low-pass filter smoothing engine.

---

## CRITICAL RULES

1. **Read a file BEFORE editing it** — always understand what's there first
2. **No new files** unless explicitly required — prefer editing existing files
3. **Preserve all existing imports** that are still used after your edits
4. **Do NOT delete** the `Guardian` DB model, the `guardians` table, or the `VehicleGuardian` table — they stay for data integrity
5. **Do NOT touch** OBD/Bluetooth files (`obd/` directory), theme files, or any UI screen not explicitly mentioned
6. **Do NOT add features** not listed in this prompt
7. **Execute steps in order** — some steps depend on earlier ones
8. Use error code `ErrorCode.FEATURE_NOT_AVAILABLE` for the 403 tier check (NOT `ErrorCode.FORBIDDEN` which doesn't exist)

---

## CONTEXT: Current Architecture

### Server Auth (BEFORE — what exists now):
- **Driver endpoints** (`/api/profile/*`, `/api/vehicle_data/*`, `/api/ai/*`, etc.): Use `X-API-Key` header → validated by `get_current_user()` in `predict/core/api/deps.py` → returns dict: `{"key_id", "user_id", "name", "tier", "permissions", "apps", "profile_id"}`
- **Guardian endpoints** (`/api/guardian/*`): Use `Authorization: Bearer <JWT>` → validated by `get_current_guardian()` in `predict/core/api/v1/guardian.py` (line 392) → decodes JWT, looks up `Guardian` table → returns dict: `{"id", "guardian_id", "email", "name", "role"}`
- **48 endpoint functions** in `guardian.py` use `current_guardian: Dict = Depends(get_current_guardian)`

### Server Auth (AFTER — what we want):
- **ALL endpoints** use `X-API-Key` header
- Guardian endpoints use a new `get_guardian_user()` dependency that calls `get_current_user()` AND checks tier is `premium`/`admin`/`enterprise`/`fleet_manager`
- No separate guardian registration/login — users upgrade to Premium via Google Play Billing to unlock Guardian features
- The `VehicleGuardian` table gets a new `user_id` column (links to `User.id`) for vehicle ownership queries

### Android Auth (BEFORE):
- `ApiKeyInterceptor.kt` adds `X-API-Key` to non-public requests
- `GuardianAuthInterceptor.kt` adds `Authorization: Bearer <JWT>` to `/api/guardian/*` requests
- `PredictConfig.kt` stores both `apiKey` and `guardianToken`
- `GuardianRepository.kt` has `guardianLogin()`, `guardianRegister()`, `getGuardianProfile()`, `guardianLogout()`
- `PredictApiService.kt` has `guardianRegister()`, `guardianLogin()`, `getGuardianProfile()` endpoints

### Android Auth (AFTER):
- Only `ApiKeyInterceptor.kt` — it already adds X-API-Key to ALL non-public paths
- `GuardianAuthInterceptor.kt` DELETED
- `guardianToken` REMOVED from PredictConfig
- Guardian auth methods REMOVED from GuardianRepository and PredictApiService
- Guardian mode access gated by `UserPermissions.hasGuardianAccess` (Premium tier)

### Tier System (desired):
| Feature | Free | Pro | Premium |
|---------|------|-----|---------|
| OBD Gauges (RPM, speed, temp) | Yes | Yes | Yes |
| OBD Data Upload | Unlimited | Unlimited | Unlimited |
| DTC Reader | No | Yes | Yes |
| Predictions | No | 2/day | 10/day (5x) |
| AI Chat | No | 15/day | 75/day (5x) |
| PDF Reports | No | 1/week | 5/week (5x) |
| Guardian Mode | No | No | Yes |
| Vehicles | 1 | 1 | 5 |

---

## PART 1: SERVER CHANGES

All files under `C:\D Drive\Predict`.

### STEP 1: Create `get_guardian_user` Dependency

**File**: `predict/core/api/v1/guardian.py`

Add this new function AFTER the existing `get_current_guardian()` function (ends around line 454). Do NOT delete `get_current_guardian`.

```python
async def get_guardian_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Dependency: Get current user via X-API-Key and verify premium tier for guardian access.
    Replaces JWT-based get_current_guardian for unified auth.
    Returns user dict with: key_id, user_id, name, tier, permissions, apps, profile_id
    """
    user = await get_current_user(request)

    tier = user.get("tier", "free")
    if tier not in ("premium", "admin", "enterprise", "fleet_manager"):
        raise APIError(
            status_code=403,
            message="Guardian mode requires Premium subscription. Please upgrade to access Guardian features.",
            error_code=ErrorCode.FEATURE_NOT_AVAILABLE,
        )

    return user
```

Note: `get_current_user` is already imported at the top of guardian.py from `predict.core.api.deps`. `Request` is already imported from `fastapi`.

### STEP 2: Add `user_id` Column to VehicleGuardian Model

**File**: `predict/core/db/models/guardian.py`

Current `VehicleGuardian` class (line 35):

```python
class VehicleGuardian(Base):
    __tablename__ = "vehicle_guardians"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guardian_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ...
```

Change to:

```python
class VehicleGuardian(Base):
    __tablename__ = "vehicle_guardians"
    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guardian_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)  # Legacy, kept for existing data
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NEW: links to User.id for unified auth
    relationship: Mapped[Optional[str]] = mapped_column(String(50))
    permissions: Mapped[str] = mapped_column(String(20), server_default="full")
    role: Mapped[str] = mapped_column(String(20), server_default="driver")
    linked_at: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    __table_args__ = (
        UniqueConstraint("profile_id", "guardian_id", name="uq_vehicle_guardian"),
    )
```

Make sure `Optional` is imported from `typing` at the top of the file.

### STEP 3: Replace All 48 `Depends(get_current_guardian)` Calls

**File**: `predict/core/api/v1/guardian.py`

Do a find-and-replace across the ENTIRE file:

**Find**: `current_guardian: Dict = Depends(get_current_guardian)`
**Replace with**: `current_user: Dict = Depends(get_guardian_user)`

Then find-and-replace ALL references to `current_guardian` inside those functions:

**Find**: `current_guardian`
**Replace with**: `current_user`

This is critical — there are exactly 48 occurrences of `Depends(get_current_guardian)` and many more uses of `current_guardian["id"]`, `current_guardian["email"]`, etc. inside those functions.

### STEP 4: Update Vehicle Ownership Queries

**File**: `predict/core/api/v1/guardian.py`

After Step 3, the code references `current_user` but the internal logic still tries to use Guardian-specific fields. The key change:

**BEFORE** (old pattern found in most endpoints):
```python
repo = GuardianRepository(session)
guardian = await repo.get_by_id(current_user["id"])  # WRONG - current_user["id"] is User.id, not Guardian.id
# Then later:
vehicles = await session.execute(
    select(VehicleGuardian).where(
        VehicleGuardian.guardian_id == guardian.guardian_id,
        VehicleGuardian.is_active == True
    )
)
```

**AFTER** (new pattern):
```python
user_id = current_user["user_id"]
# Query by user_id directly, no need to look up Guardian table
vehicles = await session.execute(
    select(VehicleGuardian).where(
        VehicleGuardian.user_id == user_id,
        VehicleGuardian.is_active == True
    )
)
```

Apply this pattern to EVERY endpoint that:
1. Calls `GuardianRepository(session)` then `repo.get_by_id(current_user["id"])` — remove these lines
2. Queries `VehicleGuardian.guardian_id == ...` — change to `VehicleGuardian.user_id == current_user["user_id"]`

**Key endpoints to update** (all are in guardian.py):
- `link_vehicle` (line ~850) — when creating VehicleGuardian record, set `user_id=current_user["user_id"]`
- `unlink_vehicle` (line ~910) — query by `user_id`
- `get_vehicles` (line ~950) — query by `user_id`
- `update_driver_role` (line ~994) — query by `user_id`
- `get_my_role` (line ~1036) — use `current_user` directly
- `get_fleet_members` (line ~1072) — query by `user_id`
- `get_dashboard` (line ~1128) — query by `user_id`
- `get_alerts` (line ~1191) — query by `user_id` (get all vehicle IDs first, then alerts)
- `mark_alert_read` (line ~1243) — verify ownership via `user_id`
- `acknowledge_alert` (line ~1273) — verify ownership via `user_id`
- `send_warning` (line ~1309) — verify ownership via `user_id`
- `request_location` (line ~1360) — verify ownership via `user_id`
- `send_command` (line ~1424) — verify ownership via `user_id`
- `get_command_history` (line ~1473) — query by `user_id`
- `create_command` (line ~1515) — verify ownership via `user_id`
- `get_pending_commands` (line ~1563) — verify ownership via `user_id`
- `acknowledge_command` (line ~1606) — verify ownership
- `complete_command` (line ~1638) — verify ownership
- `get_vehicle_live` (line ~1675) — verify ownership via `user_id`
- `get_vehicle_health` (line ~1735) — verify ownership via `user_id`
- `get_daily_stats` (line ~1892) — verify ownership via `user_id`
- `get_service_records` (line ~1950) — verify ownership via `user_id`
- `create_service_record` (line ~1999) — verify ownership via `user_id`
- `get_trips` (line ~2048) — verify ownership via `user_id`
- `get_trip_details` (line ~2108) — verify ownership
- `start_trip` (line ~2172) — verify ownership
- `end_trip` (line ~2205) — verify ownership
- `list_trips` (line ~2253) — verify ownership
- `get_predictions` (line ~2273) — verify ownership
- `get_prediction_details` (line ~2309) — verify ownership
- `acknowledge_prediction` (line ~2329) — verify ownership
- `report_false_alarm` (line ~2345) — verify ownership
- `get_notification_preferences` (line ~2365) — use `current_user["user_id"]`
- `update_notification_preferences` (line ~2385) — use `current_user["user_id"]`
- `get_action_log` (line ~2414) — query by `user_id`
- `guardian_chat` (line ~2438) — verify ownership
- `get_vehicle_context` (line ~2592) — verify ownership
- `get_fleet_drivers` (line ~2646) — query by `user_id`
- `compare_analytics` (line ~2692) — verify ownership
- `get_geofences` (line ~2758) — verify ownership
- `create_geofence` (line ~2810) — verify ownership
- `delete_geofence` (line ~2867) — verify ownership
- `post_telemetry` (line ~2917) — uses API key auth, no change needed
- `get_latest_telemetry` (line ~3041) — verify ownership
- `get_telemetry_history` (line ~3125) — verify ownership
- `get_events` (line ~3289) — verify ownership
- `get_location_remaining` (line ~3557) — use `current_user["user_id"]`
- `request_location_v2` (line ~3589) — verify ownership
- `get_recent_alerts` (line ~3670) — query by `user_id`
- `acknowledge_alert_v2` (line ~3685) — verify ownership

**Helper function** — Add this near the top (after `get_guardian_user`) to avoid repeating ownership checks:

```python
async def _verify_vehicle_ownership(
    session: AsyncSession,
    user_id: int,
    profile_id: int,
) -> VehicleGuardian:
    """Verify user has access to vehicle. Returns VehicleGuardian or raises 404."""
    result = await session.execute(
        select(VehicleGuardian).where(
            VehicleGuardian.user_id == user_id,
            VehicleGuardian.profile_id == profile_id,
            VehicleGuardian.is_active == True,
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise APIError(
            status_code=404,
            message="Vehicle not found or not linked to your account",
            error_code=ErrorCode.VEHICLE_NOT_FOUND,
        )
    return link
```

Then in endpoints that verify ownership, replace the old pattern with:
```python
user_id = current_user["user_id"]
link = await _verify_vehicle_ownership(session, user_id, profile_id)
```

### STEP 5: Remove Guardian Auth Endpoints

**File**: `predict/core/api/v1/guardian.py`

DELETE these 8 endpoint functions entirely (lines ~492 to ~844). These are the Guardian-specific auth endpoints that are no longer needed since users authenticate via the main `/api/auth/*` endpoints:

1. `POST /auth/register` — `register_guardian()` (line ~492-537)
2. `POST /auth/login` — `login_guardian()` (line ~540-602)
3. `GET /auth/me` — `get_guardian_me()` (line ~605-640)
4. `POST /auth/forgot-password` — `forgot_password()` (line ~642-671)
5. `POST /auth/reset-password` — `reset_password()` (line ~673-717)
6. `PUT /auth/profile` — `update_profile()` (line ~719-758)
7. `POST /auth/change-password` — `change_password()` (line ~760-800)
8. `POST /auth/delete-account` — `delete_account()` (line ~803-843)

Also delete the section header comment: `# AUTHENTICATION ENDPOINTS (8 endpoints)` (line ~488-490)

Keep everything else — the `get_current_guardian()` function stays (unused but harmless), and ALL non-auth endpoints stay.

### STEP 6: Update Tier Configuration

**File**: `predict/core/api/v1/usage.py`

Replace the `TIER_DEFAULTS` dict (starts at line 91) with:

```python
TIER_DEFAULTS = {
    "free": {
        "daily_obd_requests": -1,       # unlimited for ALL tiers
        "stored_vehicles": 1,
        "dtc_checks_total": 0,          # No DTC for free
        "predictions_per_day": 0,       # No predictions for free
        "llm_chat_per_day": 0,          # No chat for free
        "pdfs_per_week": 0,             # No PDFs for free
        "guardian_mode": False,
        "fleet_management": False,
        "ai_chat": False,
        "pdf_reports": False,
        "prediction_history_days": 0,
    },
    "pro": {
        "daily_obd_requests": -1,
        "stored_vehicles": 1,
        "dtc_checks_total": -1,         # unlimited
        "predictions_per_day": 2,
        "llm_chat_per_day": 15,
        "pdfs_per_week": 1,
        "guardian_mode": False,          # No guardian for Pro
        "fleet_management": False,
        "ai_chat": True,
        "pdf_reports": True,
        "prediction_history_days": 90,
    },
    "premium": {
        "daily_obd_requests": -1,
        "stored_vehicles": 5,           # 5 vehicles
        "dtc_checks_total": -1,
        "predictions_per_day": 10,      # 5x pro
        "llm_chat_per_day": 75,         # 5x pro
        "pdfs_per_week": 5,             # 5x pro
        "guardian_mode": True,           # Guardian for Premium only
        "fleet_management": False,
        "ai_chat": True,
        "pdf_reports": True,
        "prediction_history_days": 365,
    },
    "admin": {
        "daily_obd_requests": -1,
        "stored_vehicles": -1,
        "dtc_checks_total": -1,
        "predictions_per_day": -1,
        "llm_chat_per_day": -1,
        "pdfs_per_week": -1,
        "guardian_mode": True,
        "fleet_management": True,
        "ai_chat": True,
        "pdf_reports": True,
        "prediction_history_days": -1,
    },
}
```

**File**: `predict/core/middleware/api_key.py`

Replace the `TIER_PERMISSIONS` dict (line 55) with:

```python
TIER_PERMISSIONS: Dict[Tier, List[Permission]] = {
    Tier.FREE: [Permission.VEHICLE_DATA],
    Tier.PRO: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT,
               Permission.LLM_CHAT, Permission.REPORTS],
    Tier.PREMIUM: list(Permission),
    Tier.ADMIN: list(Permission),
    Tier.FLEET_DRIVER: [Permission.VEHICLE_DATA, Permission.DIAGNOSTIC, Permission.PREDICT],
    Tier.FLEET_MANAGER: list(Permission),
    Tier.ENTERPRISE: list(Permission),
}
```

Remove `Tier.BASIC` from the dict if it exists.

### STEP 7: Replace Fatora Billing with Google Play Billing Verification

**File**: `predict/core/api/v1/billing.py`

This file currently has full Fatora integration (~500 lines). Replace the ENTIRE file content with Google Play Billing verification:

```python
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
        "price_usd": 17,
    },
    "predict_pro_annual": {
        "name": "Pro Annual",
        "tier": "pro",
        "interval": "annual",
        "price_usd": 120,
    },
    "predict_premium_monthly": {
        "name": "Premium Monthly",
        "tier": "premium",
        "interval": "monthly",
        "price_usd": 29,
    },
    "predict_premium_annual": {
        "name": "Premium Annual",
        "tier": "premium",
        "interval": "annual",
        "price_usd": 200,
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
        "price_monthly": 17,
        "price_annual": 120,
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
        "price_monthly": 29,
        "price_annual": 200,
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
            error_code=ErrorCode.INVALID_PARAMETER,
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
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
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
            error_code=ErrorCode.INTERNAL_ERROR,
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
            error_code=ErrorCode.INTERNAL_ERROR,
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
```

### STEP 8: Create Subscription Model

**File**: `predict/core/db/models/subscription.py`

This file may already exist with `FleetInvite`, `Geofence`, and `GeofenceEvent` models. READ IT FIRST. If `Subscription` class already exists, update it. If not, ADD it to the existing file.

Add this class:

```python
class Subscription(Base):
    """User subscriptions via Google Play Billing."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    google_purchase_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    google_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    google_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="active")
    started_at: Mapped[float] = mapped_column(Float, nullable=False)
    expires_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cancelled_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False)
```

Make sure all required imports are present (`Optional` from typing, `Text`, `Float`, `String`, `Integer` from sqlalchemy, etc.).

### STEP 9: Run Alembic Migrations

```bash
cd "C:\D Drive\Predict"
alembic revision --autogenerate -m "add user_id to vehicle_guardians and subscriptions table"
alembic upgrade head
```

If Alembic complains about target database not being up to date, run `alembic stamp head` first, then retry.

### STEP 10: Delete billing_service.py Fatora Code

**File**: `predict/core/services/billing_service.py`

READ this file. If it contains only Fatora-specific code (Fatora API calls, webhook handlers), replace the entire content with:

```python
"""
Billing service - Google Play Billing verification.
Server-side purchase token verification will be added here.
"""

import logging

logger = logging.getLogger(__name__)


class BillingService:
    """Handles Google Play Billing verification."""

    @staticmethod
    async def verify_google_purchase(purchase_token: str, product_id: str) -> dict:
        """
        Verify a Google Play purchase token.
        TODO: Implement with Google Play Developer API.
        """
        # Placeholder - implement with google-api-python-client
        logger.info(f"Verifying purchase: {product_id}")
        return {"valid": True, "product_id": product_id}
```

---

## PART 2: ANDROID CHANGES

All files under `C:\New APK\app\src\main\java\com\predict\app`.

### STEP 11: Delete GuardianAuthInterceptor

**DELETE file**: `network/GuardianAuthInterceptor.kt`

### STEP 12: Remove GuardianAuthInterceptor from Retrofit Client

**File**: `network/PredictRetrofitClient.kt`

Find and DELETE the line that adds the guardian interceptor:
```kotlin
.addInterceptor(GuardianAuthInterceptor { config.guardianToken })
```

Also remove the import:
```kotlin
import com.predict.app.network.GuardianAuthInterceptor
```

### STEP 13: Remove guardianToken from PredictConfig

**File**: `network/PredictConfig.kt`

Find and DELETE the `guardianToken` property and any getter/setter related to it. Search for `guardianToken` and remove all occurrences.

### STEP 14: Remove Guardian Auth Endpoints from PredictApiService

**File**: `network/PredictApiService.kt`

DELETE these endpoint declarations:
```kotlin
@POST("/api/guardian/auth/register")
suspend fun guardianRegister(...)

@POST("/api/guardian/auth/login")
suspend fun guardianLogin(...)

@GET("/api/guardian/auth/me")
suspend fun getGuardianProfile(...)
```

### STEP 15: Remove Guardian Auth Methods from GuardianRepository

**File**: `data/repository/GuardianRepository.kt`

DELETE these methods:
- `guardianLogin()`
- `guardianRegister()`
- `getGuardianProfile()`
- `guardianLogout()`

Keep all other methods (vehicle endpoints, telemetry, etc.).

### STEP 16: Remove Guardian Auth from ApiKeyInterceptor Public Endpoints

**File**: `network/ApiKeyInterceptor.kt`

Remove these from `PUBLIC_ENDPOINTS`:
- `"/api/guardian/auth/register"`
- `"/api/guardian/auth/login"`

### STEP 17: Remove Guardian Auth Models from UnifiedApiModels

**File**: `data/models/UnifiedApiModels.kt`

Search for and DELETE these data classes (if they exist):
- `GuardianRegisterRequest`
- `GuardianLoginRequest`
- `GuardianAuthResponse`

Be careful not to break other classes that may be nearby.

### STEP 18: Add Google Play Billing Dependency

**File**: `app/build.gradle.kts` (at `C:\New APK\app\build.gradle.kts`)

Add to the `dependencies` block:
```kotlin
implementation("com.android.billingclient:billing-ktx:7.0.0")
```

### STEP 19: Add Google Play Billing to SubscriptionManager

**File**: `managers/SubscriptionManager.kt`

Add Google Play Billing integration. Keep ALL existing code (tier management, feature gating, usage tracking, caching). ADD the following:

1. Add imports at top:
```kotlin
import android.app.Activity
import com.android.billingclient.api.*
```

2. Add billing fields in the class:
```kotlin
private var billingClient: BillingClient? = null
private val _billingReady = MutableStateFlow(false)
val billingReady: StateFlow<Boolean> = _billingReady.asStateFlow()
```

3. Add billing methods:
```kotlin
/**
 * Initialize Google Play Billing connection.
 * Call this from MainActivity.onCreate().
 */
fun initBilling(activity: Activity) {
    billingClient = BillingClient.newBuilder(context)
        .setListener { billingResult, purchases ->
            if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
                for (purchase in purchases) {
                    handlePurchase(purchase)
                }
            }
        }
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .build()

    billingClient?.startConnection(object : BillingClientStateListener {
        override fun onBillingSetupFinished(billingResult: BillingResult) {
            _billingReady.value = billingResult.responseCode == BillingClient.BillingResponseCode.OK
        }
        override fun onBillingServiceDisconnected() {
            _billingReady.value = false
        }
    })
}

/**
 * Launch purchase flow for a subscription product.
 * @param productId One of: predict_pro_monthly, predict_pro_annual, predict_premium_monthly, predict_premium_annual
 */
fun launchPurchase(activity: Activity, productId: String) {
    val client = billingClient ?: return

    val productList = listOf(
        QueryProductDetailsParams.Product.newBuilder()
            .setProductId(productId)
            .setProductType(BillingClient.ProductType.SUBS)
            .build()
    )

    val params = QueryProductDetailsParams.newBuilder()
        .setProductList(productList)
        .build()

    client.queryProductDetailsAsync(params) { billingResult, productDetailsList ->
        if (billingResult.responseCode == BillingClient.BillingResponseCode.OK && productDetailsList.isNotEmpty()) {
            val productDetails = productDetailsList[0]
            val offerToken = productDetails.subscriptionOfferDetails?.firstOrNull()?.offerToken ?: return@queryProductDetailsAsync

            val flowParams = BillingFlowParams.newBuilder()
                .setProductDetailsParamsList(
                    listOf(
                        BillingFlowParams.ProductDetailsParams.newBuilder()
                            .setProductDetails(productDetails)
                            .setOfferToken(offerToken)
                            .build()
                    )
                )
                .build()

            client.launchBillingFlow(activity, flowParams)
        }
    }
}

/**
 * Handle completed purchase - verify with server and upgrade tier.
 */
private fun handlePurchase(purchase: Purchase) {
    if (purchase.purchaseState != Purchase.PurchaseState.PURCHASED) return

    scope.launch {
        try {
            val api = PredictRetrofitClient.getInstance(context).apiService
            val response = api.verifyPurchase(
                mapOf(
                    "purchase_token" to purchase.purchaseToken,
                    "product_id" to (purchase.products.firstOrNull() ?: ""),
                    "order_id" to (purchase.orderId ?: ""),
                )
            )

            if (response.isSuccessful && response.body()?.get("success") == true) {
                val newTier = response.body()?.get("tier") as? String ?: return@launch
                _currentTier.value = newTier
                saveCachedState()

                // Acknowledge purchase
                if (!purchase.isAcknowledged) {
                    val ackParams = AcknowledgePurchaseParams.newBuilder()
                        .setPurchaseToken(purchase.purchaseToken)
                        .build()
                    billingClient?.acknowledgePurchase(ackParams) { /* result */ }
                }

                // Refresh permissions from server
                refreshPermissions()
            }
        } catch (e: Exception) {
            // Log error, will retry on next app launch
        }
    }
}
```

### STEP 20: Add verifyPurchase Endpoint to PredictApiService

**File**: `network/PredictApiService.kt`

Add:
```kotlin
@POST("/api/billing/verify-purchase")
suspend fun verifyPurchase(@Body request: Map<String, String>): Response<Map<String, Any>>
```

### STEP 21: Update Subscription/Paywall Screens

**File**: `ui/screens/subscription/SubscriptionScreen.kt`

READ this file first. Remove all Fatora references. Update purchase buttons to call:
```kotlin
SubscriptionManager.getInstance(context).launchPurchase(activity, "predict_pro_monthly")
```

Use these product IDs:
- `predict_pro_monthly`
- `predict_pro_annual`
- `predict_premium_monthly`
- `predict_premium_annual`

**File**: `ui/screens/subscription/PaywallScreen.kt`

Same changes — remove Fatora, use `SubscriptionManager.launchPurchase()`.

### STEP 22: Update Guardian Mode Access in Navigation

**File**: `navigation/MainNavigationApp.kt`

READ this file first. Find where guardian mode access is checked. The current code likely checks for a guardian token. Change it to check `UserPermissions.hasGuardianAccess` which is tied to the Premium tier.

If the user tries to switch to Guardian mode without Premium, navigate to the PaywallScreen instead.

### STEP 23: Remove Guardian Login/Register from Welcome Screens

**File**: `ui/screens/guardian/GuardianWelcomeScreen.kt`
**File**: `ui/screens/guardianv2/GuardianWelcomeScreen.kt`

READ these files. Remove any "Guardian Login" or "Guardian Register" buttons/forms. The guardian welcome should just show the dashboard directly (since auth is via the main API key).

---

## PART 3: GAUGE SMOOTHER ENGINE

### STEP 24: Add Low-Pass Filter Engine to SmoothGaugeValue

**File**: `ui/components/guardian/SmoothGaugeValue.kt`

This file already has `rememberSmoothGaugeValue()` (spring-based), `GaugeSprings`, and `gaugeSpring()`. Keep ALL existing code. ADD the following new components at the END of the file (before the usage examples):

```kotlin
// =============================================================================
// LOW-PASS FILTER GAUGE SMOOTHER ENGINE
// =============================================================================

/**
 * Response modes for gauge smoothing.
 * Controls how responsive the gauge feels.
 */
enum class GaugeResponseMode(val baseAlpha: Float, val displayName: String) {
    SPORT(0.6f, "Sport"),      // Most responsive, less smoothing
    NORMAL(0.3f, "Normal"),    // Balanced
    ECO(0.15f, "Eco")          // Smoothest, most damped
}

/**
 * Pre-configured low-pass filter settings per metric type.
 */
object GaugeSmootherConfig {
    data class Config(
        val mode: GaugeResponseMode,
        val maxDelta: Float,
        val accelerationFactor: Float = 0.001f
    )

    /** RPM: Fast response for quick rev changes */
    val RPM = Config(mode = GaugeResponseMode.SPORT, maxDelta = 500f, accelerationFactor = 0.0005f)
    /** Speed: Balanced response */
    val SPEED = Config(mode = GaugeResponseMode.NORMAL, maxDelta = 30f)
    /** Temperature: Slow, smooth (temp changes gradually) */
    val TEMPERATURE = Config(mode = GaugeResponseMode.ECO, maxDelta = 5f)
    /** Fuel: Very smooth, liquid-like */
    val FUEL = Config(mode = GaugeResponseMode.ECO, maxDelta = 2f)
    /** Voltage: Precise, moderate smoothing */
    val VOLTAGE = Config(mode = GaugeResponseMode.NORMAL, maxDelta = 1f)
    /** Boost pressure: Fast for turbo response */
    val BOOST = Config(mode = GaugeResponseMode.SPORT, maxDelta = 10f)
    /** Throttle position: Very fast response */
    val THROTTLE = Config(mode = GaugeResponseMode.SPORT, maxDelta = 50f, accelerationFactor = 0.0008f)
    /** Engine load: Moderate response */
    val ENGINE_LOAD = Config(mode = GaugeResponseMode.NORMAL, maxDelta = 20f)
    /** MAF rate: Moderate response */
    val MAF = Config(mode = GaugeResponseMode.NORMAL, maxDelta = 50f)
    /** Intake temp: Slow like coolant temp */
    val INTAKE_TEMP = Config(mode = GaugeResponseMode.ECO, maxDelta = 3f)

    /**
     * Auto-detect config based on metric label.
     */
    fun forMetric(label: String): Config = when {
        label.contains("RPM", ignoreCase = true) || label.contains("Rev", ignoreCase = true) -> RPM
        label.contains("Speed", ignoreCase = true) || label.contains("km/h", ignoreCase = true) -> SPEED
        label.contains("Temp", ignoreCase = true) || label.contains("°C", ignoreCase = true) -> TEMPERATURE
        label.contains("Fuel", ignoreCase = true) -> FUEL
        label.contains("Volt", ignoreCase = true) || label.contains("Battery", ignoreCase = true) -> VOLTAGE
        label.contains("Boost", ignoreCase = true) || label.contains("Turbo", ignoreCase = true) -> BOOST
        label.contains("Throttle", ignoreCase = true) || label.contains("TPS", ignoreCase = true) -> THROTTLE
        label.contains("Load", ignoreCase = true) -> ENGINE_LOAD
        label.contains("MAF", ignoreCase = true) || label.contains("Air Flow", ignoreCase = true) -> MAF
        label.contains("Intake", ignoreCase = true) -> INTAKE_TEMP
        else -> Config(mode = GaugeResponseMode.NORMAL, maxDelta = Float.MAX_VALUE)
    }
}

/**
 * Low-pass filter gauge smoother with acceleration-based dynamic smoothing.
 *
 * Core formula: smoothed += (raw - smoothed) * alpha
 *
 * Alpha adjusts dynamically based on acceleration (rate of change):
 * - Fast changes (sudden RPM spike) → higher alpha → more responsive
 * - Slow changes (temperature drift) → lower alpha → smoother
 *
 * Runs at 60fps via withFrameNanos, decoupled from OBD data update rate.
 *
 * @param targetValue The raw value from OBD
 * @param mode Response mode (SPORT/NORMAL/ECO)
 * @param maxDelta Maximum change per frame (clamps extreme jumps)
 * @param accelerationFactor How much acceleration affects alpha
 * @param initialValue Starting value
 */
@Composable
fun rememberLowPassGaugeValue(
    targetValue: Float,
    mode: GaugeResponseMode = GaugeResponseMode.NORMAL,
    maxDelta: Float = Float.MAX_VALUE,
    accelerationFactor: Float = 0.001f,
    initialValue: Float = targetValue
): State<Float> {
    val smoothedValue = remember { mutableFloatStateOf(initialValue) }
    val previousTarget = remember { mutableFloatStateOf(initialValue) }

    LaunchedEffect(Unit) {
        // 60fps render loop — runs continuously, independent of data updates
        while (true) {
            withFrameNanos { _ ->
                val raw = targetValue
                val current = smoothedValue.floatValue

                // Clamp delta to prevent extreme jumps
                val rawDelta = raw - current
                val clampedTarget = current + rawDelta.coerceIn(-maxDelta, maxDelta)

                // Calculate acceleration (how fast the target is changing)
                val acceleration = kotlin.math.abs(raw - previousTarget.floatValue)

                // Dynamic alpha: base + acceleration boost, clamped to [0.05, 0.9]
                val dynamicAlpha = (mode.baseAlpha + acceleration * accelerationFactor)
                    .coerceIn(0.05f, 0.9f)

                // Apply low-pass filter
                smoothedValue.floatValue += (clampedTarget - current) * dynamicAlpha

                // Track previous for acceleration calculation
                previousTarget.floatValue = raw
            }
        }
    }

    return smoothedValue
}

/**
 * Convenience overload using GaugeSmootherConfig.
 */
@Composable
fun rememberLowPassGaugeValue(
    targetValue: Float,
    config: GaugeSmootherConfig.Config,
    initialValue: Float = targetValue
): State<Float> = rememberLowPassGaugeValue(
    targetValue = targetValue,
    mode = config.mode,
    maxDelta = config.maxDelta,
    accelerationFactor = config.accelerationFactor,
    initialValue = initialValue
)

/**
 * Convenience overload for Double values.
 */
@Composable
fun rememberLowPassGaugeValue(
    targetValue: Double,
    config: GaugeSmootherConfig.Config,
    initialValue: Double = targetValue
): State<Float> = rememberLowPassGaugeValue(
    targetValue = targetValue.toFloat(),
    mode = config.mode,
    maxDelta = config.maxDelta,
    accelerationFactor = config.accelerationFactor,
    initialValue = initialValue.toFloat()
)
```

Make sure to add the required import at the top of the file:
```kotlin
import androidx.compose.runtime.withFrameNanos
```

### STEP 25: Apply GaugeSmoother to EnhancedMotecGauge

**File**: `ui/screens/EnhancedMotecGauge.kt`

1. Add imports at the top:
```kotlin
import com.predict.app.ui.components.guardian.rememberLowPassGaugeValue
import com.predict.app.ui.components.guardian.GaugeSmootherConfig
```

2. Find the current animation code (around line 79-85):
```kotlin
// Animated value
val animatedValue = remember { Animatable(0f) }
LaunchedEffect(rawValue) {
    animatedValue.animateTo(
        targetValue = rawValue.toFloat(),
        animationSpec = tween(durationMillis = 150, easing = LinearOutSlowInEasing)
    )
}
```

Replace with:
```kotlin
// Smooth animated value using low-pass filter engine
val smoothConfig = GaugeSmootherConfig.forMetric(metric.label)
val animatedValue = rememberLowPassGaugeValue(
    targetValue = rawValue.toFloat(),
    config = smoothConfig
)
```

3. Update all `animatedValue.value` references — `rememberLowPassGaugeValue` returns `State<Float>`, so `animatedValue.value` still works. But if code was using `animatedValue.targetValue` or `animatedValue.isRunning`, those need to be removed since the return type changed from `Animatable` to `State<Float>`.

### STEP 26: Apply GaugeSmoother to RacingDashboardScreen

**File**: `ui/screens/RacingDashboardScreen.kt`

READ the file. Find all gauge value animations (look for `Animatable`, `animateTo`, `tween`). Replace each one with `rememberLowPassGaugeValue()` using the appropriate config from `GaugeSmootherConfig.forMetric(label)`.

Add the same imports as Step 25.

### STEP 27: Verify MotecDashboardScreen

**File**: `ui/screens/MotecDashboardScreen.kt`

READ this file. It already imports `GaugeSprings` and `rememberSmoothGaugeValue`. Verify it's working correctly. If you find any raw `Animatable` + `tween` patterns, replace with `rememberLowPassGaugeValue()`. If everything already uses `rememberSmoothGaugeValue()`, you can leave it as-is (both systems work).

---

## APPENDIX: COMPLETE ENDPOINT REFERENCE

### Guardian Endpoints in `guardian.py` — Full List

All endpoints are prefixed with `/api/guardian/` (the router is included with that prefix).

#### TO DELETE (8 auth endpoints — Step 5):
| Line | Method | Path | Function |
|------|--------|------|----------|
| 492 | POST | `/auth/register` | `register_guardian` |
| 540 | POST | `/auth/login` | `login_guardian` |
| 605 | GET | `/auth/me` | `get_guardian_me` |
| 642 | POST | `/auth/forgot-password` | `forgot_password` |
| 673 | POST | `/auth/reset-password` | `reset_password` |
| 719 | PUT | `/auth/profile` | `update_profile` |
| 760 | POST | `/auth/change-password` | `change_password` |
| 803 | POST | `/auth/delete-account` | `delete_account` |

#### TO UPDATE — Change `Depends(get_current_guardian)` → `Depends(get_guardian_user)` (48 endpoints — Steps 3-4):

| Line | Method | Path | Function | Uses guardian_id query? |
|------|--------|------|----------|----------------------|
| 850 | POST | `/vehicles/link` | `link_vehicle` | YES — set `user_id` on new VehicleGuardian |
| 910 | POST | `/vehicles/unlink/{profile_id}` | `unlink_vehicle` | YES |
| 950 | GET | `/vehicles` | `list_vehicles` | YES |
| 994 | PUT | `/drivers/{profile_id}/role` | `update_driver_role` | YES |
| 1036 | GET | `/my-role` | `get_my_role` | YES |
| 1072 | GET | `/fleet-members/{profile_id}` | `get_fleet_members` | YES |
| 1128 | GET | `/dashboard` | `get_dashboard` | YES |
| 1191 | GET | `/alerts` | `get_alerts` | YES |
| 1243 | POST | `/alerts/{alert_id}/read` | `mark_alert_read` | YES |
| 1273 | POST | `/alerts/{alert_id}/acknowledge` | `acknowledge_alert` | YES |
| 1309 | POST | `/commands/send-warning` | `send_warning` | YES |
| 1360 | POST | `/commands/request-location` | `request_location` | YES |
| 1424 | POST | `/commands/send` | `send_command` | YES |
| 1473 | GET | `/commands/history` | `get_command_history` | YES |
| 1515 | POST | `/commands/create` | `create_command` | YES |
| 1563 | GET | `/commands/pending/{profile_id}` | `get_pending_commands` | YES |
| 1606 | POST | `/commands/acknowledge` | `acknowledge_command` | YES |
| 1638 | POST | `/commands/complete` | `complete_command` | YES |
| 1675 | GET | `/vehicles/{profile_id}/live` | `get_live_data` | YES |
| 1735 | GET | `/vehicles/{profile_id}/health` | `get_vehicle_health` | YES |
| 1892 | GET | `/vehicles/{profile_id}/daily-stats` | `get_daily_stats` | YES |
| 1950 | GET | `/vehicles/{profile_id}/service-records` | `get_guardian_service_records` | YES |
| 1999 | POST | `/vehicles/{profile_id}/service-records` | `add_guardian_service_record` | YES |
| 2048 | GET | `/trips/{profile_id}` | `get_trips` | YES |
| 2108 | GET | `/trips/{trip_id}/details` | `get_trip_details` | YES |
| 2253 | GET | `/trips/{profile_id}/list` | `list_trips` | YES |
| 2273 | GET | `/predictions/{profile_id}` | `get_predictions` | YES |
| 2309 | GET | `/predictions/{prediction_id}/details` | `get_prediction_details` | YES |
| 2329 | POST | `/predictions/{prediction_id}/acknowledge` | `acknowledge_prediction` | YES |
| 2345 | POST | `/predictions/{prediction_id}/false-alarm` | `mark_false_alarm` | YES |
| 2365 | GET | `/notification-preferences` | `get_notification_preferences` | NO — uses guardian ID as key |
| 2385 | PUT | `/notification-preferences` | `update_notification_preferences` | NO — uses guardian ID as key |
| 2414 | GET | `/action-log` | `get_action_log` | YES |
| 2438 | POST | `/chat/message` | `chat_message` | YES |
| 2592 | GET | `/chat/vehicle-context/{profile_id}` | `get_vehicle_context` | YES |
| 2646 | GET | `/fleet/drivers` | `get_fleet_drivers` | YES |
| 2692 | POST | `/analytics/compare` | `compare_drivers` | YES |
| 2758 | GET | `/geofences/{profile_id}` | `get_geofences` | YES |
| 2810 | POST | `/geofences` | `create_geofence` | YES |
| 2867 | DELETE | `/geofences/{geofence_id}` | `delete_geofence` | YES |
| 3041 | GET | `/telemetry/{profile_id}/latest` | `get_latest_telemetry` | YES |
| 3125 | GET | `/telemetry/{profile_id}/history` | `get_telemetry_history` | YES |
| 3289 | GET | `/events/{profile_id}` | `get_driving_events` | YES |
| 3557 | GET | `/location-requests/remaining` | `get_location_requests_remaining` | NO — uses guardian ID as key |
| 3589 | POST | `/request-location/{profile_id}` | `request_location_guardian` | YES |
| 3670 | GET | `/alerts-recent` | `get_recent_alerts_legacy` | YES |
| 3685 | POST | `/alerts-ack/{alert_id}/acknowledge` | `acknowledge_alert_legacy` | YES |

#### NO AUTH CHANGE NEEDED (driver-side endpoints — no `get_current_guardian`):
| Line | Method | Path | Function | Auth |
|------|--------|------|----------|------|
| 2917 | POST | `/telemetry` | `post_telemetry` | API key (driver sends GPS) |
| 2172 | POST | `/trips/start` | `start_trip` | No auth (or API key) |
| 2205 | POST | `/trips/end` | `end_trip` | No auth (or API key) |
| 3187 | POST | `/events/report` | `report_driving_event` | No explicit auth |
| 3239 | POST | `/events/obd-disconnect` | `report_obd_disconnect` | No explicit auth |
| 3264 | POST | `/events/obd-reconnect` | `report_obd_reconnect` | No explicit auth |
| 3348 | POST | `/events/hard-deceleration` | `report_hard_deceleration` | No explicit auth |
| 3411 | POST | `/driver/consent` | `grant_consent` | No explicit auth |
| 3442 | POST | `/driver/revoke-consent` | `revoke_consent` | No explicit auth |
| 3471 | GET | `/driver/monitoring-status` | `get_monitoring_status` | No explicit auth |
| 3519 | GET | `/driver/guardians` | `get_my_guardians` | No explicit auth |
| 3609 | POST | `/commands/location-response` | `location_response` | No explicit auth |

### Android Endpoints in `PredictApiService.kt` — Guardian Section

These are the Android-side endpoint declarations that correspond to the server guardian endpoints. After Phase C:
- **Delete**: `guardianRegister()`, `guardianLogin()`, `getGuardianProfile()` (guardian auth endpoints)
- **Keep all others** — they will automatically use X-API-Key from `ApiKeyInterceptor`
- **Add**: `verifyPurchase()` for billing

### Billing Endpoints (NEW — replacing Fatora):

| Method | Full Path | Purpose |
|--------|-----------|---------|
| POST | `/api/billing/verify-purchase` | Verify Google Play purchase token, upgrade tier |
| GET | `/api/billing/subscription` | Get current subscription status |
| POST | `/api/billing/cancel` | Cancel subscription |
| GET | `/api/billing/tiers` | List available tiers and pricing |
| GET | `/api/billing/history` | Payment history |

---

## VERIFICATION CHECKLIST

After completing ALL steps, verify:

### Server:
- [ ] `get_guardian_user()` function exists in guardian.py
- [ ] `_verify_vehicle_ownership()` helper exists in guardian.py
- [ ] All 48 guardian endpoints use `Depends(get_guardian_user)` (not `get_current_guardian`)
- [ ] All `current_guardian` references changed to `current_user`
- [ ] All `VehicleGuardian.guardian_id ==` queries changed to `VehicleGuardian.user_id ==`
- [ ] `VehicleGuardian` model has `user_id` column, `guardian_id` is nullable
- [ ] Guardian auth endpoints (register/login/me/forgot/reset/profile/password/delete) DELETED
- [ ] `TIER_DEFAULTS` updated: free has 0 predictions/chat/PDFs, premium has 5x limits
- [ ] `TIER_PERMISSIONS`: Free=[VEHICLE_DATA], Pro=everything except GUARDIAN
- [ ] `billing.py` is fully Google Play (no Fatora code)
- [ ] `Subscription` model exists in `subscription.py`
- [ ] Alembic migrations applied
- [ ] Server starts without errors

### Android:
- [ ] `GuardianAuthInterceptor.kt` deleted
- [ ] `guardianToken` removed from PredictConfig
- [ ] GuardianAuthInterceptor removed from PredictRetrofitClient
- [ ] Guardian auth endpoints removed from PredictApiService
- [ ] Guardian auth methods removed from GuardianRepository
- [ ] Guardian auth public endpoints removed from ApiKeyInterceptor
- [ ] Guardian auth models removed from UnifiedApiModels
- [ ] `billing-ktx:7.0.0` added to build.gradle.kts
- [ ] SubscriptionManager has Google Play Billing methods
- [ ] `verifyPurchase` endpoint added to PredictApiService
- [ ] Subscription/Paywall screens use Google Play (no Fatora)
- [ ] Guardian mode gated by Premium tier (not separate login)
- [ ] `./gradlew clean assembleDebug` succeeds with 0 errors

### Gauges:
- [ ] `GaugeResponseMode` enum exists (SPORT/NORMAL/ECO)
- [ ] `GaugeSmootherConfig` object exists with per-metric configs
- [ ] `rememberLowPassGaugeValue()` composable exists
- [ ] `EnhancedMotecGauge.kt` uses low-pass filter (not Animatable+tween)
- [ ] `RacingDashboardScreen.kt` uses low-pass filter
- [ ] `MotecDashboardScreen.kt` verified (uses SmoothGaugeValue or low-pass)
