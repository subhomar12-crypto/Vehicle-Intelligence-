# KIMI PROMPT: Phase 1 - Server Endpoint Fixes for Android Compatibility

## Your Role
You are implementing server-side API endpoint fixes for the PREDICT Vehicle Intelligence Platform. The Android app calls endpoints that do not exist on the server yet. You must create and modify server files to match what Android expects.

## Project Location
`C:\D Drive\Predict\`

## ARCHITECTURE RULES (MUST FOLLOW - NO EXCEPTIONS)
1. `time.time()` for ALL timestamps (NO `datetime.now()` or `datetime.utcnow()`)
2. `sa.Float()` for DB timestamp columns (NO `sa.DateTime()`)
3. `Mapped[type]` + `mapped_column()` for ORM (NO `Column()`)
4. ALL imports at top of file (NO inline imports)
5. PySide6 only (NO PyQt5/PyQt6) - not applicable for server files
6. `logging.getLogger(__name__)` (NO `print()`)
7. `get_config()` for paths (NO hardcoded `C:\...` paths)
8. `json.loads()` for parsing (NO eval/exec)

## EXISTING PATTERNS TO MATCH

All router files follow this pattern:
```python
"""
Module docstring.
"""

import logging
import time
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.session import get_db_session
from predict.core.security.auth import get_current_user
# ... other imports

logger = logging.getLogger(__name__)
router = APIRouter()  # NO prefix here - prefix is set in router.py
```

Authentication dependency:
```python
from predict.core.security.auth import get_current_user
# Usage: current_user = Depends(get_current_user)
# Returns dict with: user_id, api_key_id, tier, permissions, etc.
```

Database session dependency:
```python
from predict.core.db.session import get_db_session
# Usage: session: AsyncSession = Depends(get_db_session)
```

Admin check:
```python
from predict.core.api.deps import require_admin
# Usage in endpoint: current_user: dict = Depends(require_admin)
```

---

## FILE 1: CREATE `predict/core/api/v1/usage.py`

This file handles usage tracking, quota checking, and permissions for the Android app.

### Endpoints to implement:

**1. GET /key/permissions**
- Auth: `get_current_user`
- Returns the full permissions, entitlements, rate limits, and usage for the current API key
- Android expects this exact response shape:
```json
{
    "success": true,
    "permissions": {
        "has_driver_access": true,
        "has_guardian_access": false,
        "max_vehicles": 1,
        "subscription_tier": "pro",
        "role": "owner",
        "features": ["obd_reading", "dtc_reading", "ai_chat"]
    },
    "entitlements": {
        "obd_reading": true,
        "dtc_reading": true,
        "ai_chat": true,
        "guardian_mode": false,
        "pdf_reports": true,
        "fleet_management": false
    },
    "rate_limits": {
        "daily_obd_requests": {"max": 2000, "period": "day"},
        "predictions_per_day": {"max": 2, "period": "day"},
        "llm_chat_per_day": {"max": 15, "period": "day"},
        "pdfs_per_week": {"max": 1, "period": "week"}
    },
    "usage": {
        "daily_obd_requests": {"used": 45, "limit": 2000, "remaining": 1955, "unlimited": false, "has_access": true, "period": "day"},
        "predictions_per_day": {"used": 1, "limit": 2, "remaining": 1, "unlimited": false, "has_access": true, "period": "day"},
        "llm_chat_per_day": {"used": 3, "limit": 15, "remaining": 12, "unlimited": false, "has_access": true, "period": "day"}
    },
    "key_info": {
        "key_id": 42,
        "name": "default",
        "profile_id": 1,
        "profile_name": "Toyota Camry"
    }
}
```
- Must check `entitlements` table for per-user overrides, then fall back to tier defaults
- Tier defaults (MUST use these exact values):

| Feature | FREE | PRO | PREMIUM | ADMIN |
|---------|------|-----|---------|-------|
| daily_obd_requests | unlimited | unlimited | unlimited | unlimited |
| stored_vehicles | 1 | 1 | 4 | unlimited |
| dtc_checks_total | 2 | unlimited | unlimited | unlimited |
| predictions_per_day | 0 | 2 | 5 per vehicle | unlimited |
| llm_chat_per_day | 0 | 15 | 25 per vehicle | unlimited |
| pdfs_per_week | 0 | 1 | 2 per vehicle | unlimited |
| guardian_mode | false | false | true | true |
| fleet_management | false | false | false | true |
| ai_chat | false | true | true | true |
| prediction_history_days | 7 | 90 | 365 | unlimited |

NOTE: For PREMIUM, "per vehicle" means multiply by the number of vehicles the user has (max 4). So 4 vehicles = 20 predictions/day, 100 chat messages/day, 8 PDFs/week.

**2. POST /usage/track**
- Auth: `get_current_user`
- Body: `{"feature": "llm_chat", "count": 1}`
- Increments usage counter for the feature
- Store in Redis with TTL (daily features: expire at midnight, weekly: expire Sunday midnight)
- If Redis unavailable, store in database `usage_tracking` field on user or in a simple cache table
- Response:
```json
{
    "success": true,
    "feature": "llm_chat",
    "usage": {"used": 4, "limit": 15, "remaining": 11},
    "tier": "pro"
}
```
- If over limit: `{"success": false, "error": "limit_exceeded", "upgrade_required": true, "message": "You have reached your daily chat limit"}`

**3. GET /usage/check/{feature}**
- Auth: `get_current_user`
- Returns whether the user can use the feature right now
- Response:
```json
{
    "success": true,
    "allowed": true,
    "reason": null,
    "usage": {"used": 3, "limit": 15, "remaining": 12},
    "feature": "llm_chat",
    "tier": "pro",
    "upgrade_required": false,
    "message": null
}
```
- If not allowed: `{"allowed": false, "reason": "limit_exceeded", "upgrade_required": true, "message": "Upgrade to Pro for AI chat access"}`

**4. GET /usage/all**
- Auth: `get_current_user`
- Returns all usage stats for the current user
- Response:
```json
{
    "success": true,
    "tier": "pro",
    "usage": {
        "daily_obd_requests": {"used": 45, "limit": -1, "remaining": -1, "unlimited": true},
        "predictions_per_day": {"used": 1, "limit": 2, "remaining": 1, "unlimited": false},
        "llm_chat_per_day": {"used": 3, "limit": 15, "remaining": 12, "unlimited": false},
        "pdfs_per_week": {"used": 0, "limit": 1, "remaining": 1, "unlimited": false},
        "dtc_checks": {"used": 0, "limit": -1, "remaining": -1, "unlimited": true}
    },
    "resets_at": {
        "daily": 1707523200.0,
        "weekly": 1707955200.0
    }
}
```

### Implementation Notes:
- Use Redis keys like `usage:{user_id}:llm_chat:daily:{date_str}` with TTL
- Fall back to in-memory dict if Redis unavailable
- Import `get_config` for any config values
- Check entitlements table first: `SELECT * FROM entitlements WHERE user_id = ? AND feature = ?`
- If entitlement exists and not expired, use its value instead of tier default

---

## FILE 2: CREATE `predict/core/api/v1/fcm.py`

FCM token registration endpoint.

### Endpoint:

**POST /fcm/register**
- Auth: Optional (can use API key OR be anonymous with just device_id)
- Body:
```json
{
    "fcm_token": "firebase-cloud-messaging-token-string",
    "device_id": "unique-device-identifier",
    "platform": "android",
    "app_name": "PredictOBD"
}
```
- Save/update FCM token in the `users` table (`fcm_token` field) if authenticated
- If not authenticated, store in a separate `fcm_tokens` table or just log it
- Response: `{"success": true, "message": "FCM token registered"}`

### Implementation:
```python
from predict.core.db.models.user import User
# Update user.fcm_token = request.fcm_token
# Also update user.language if provided
```

---

## FILE 3: MODIFY `predict/core/api/v1/ai_chat.py`

### CRITICAL BUG FIX:
The current file has `router = APIRouter(prefix="/ai-chat", tags=["AI Chat"])` but router.py includes it with `prefix="/ai"`. This means the actual path is `/ai/ai-chat/chat` which is WRONG.

**FIX**: Change line 17 to `router = APIRouter()` (remove the prefix, it's set in router.py).

After fix, paths become: `/ai/chat`, `/ai/explain-dtc/{code}`, `/ai/status`

### Add these new endpoints:

**1. POST /smart-chat** (alias for /chat that Android expects)
- Same logic as `/chat` but accepts JSON body instead of query params:
```json
{
    "message": "Is my battery healthy?",
    "profile_id": 42,
    "vehicle_context": {
        "rpm": 850,
        "speed": 0,
        "coolant_temp": 92,
        "oil_temp": 95,
        "dtc_codes": ["P0171"],
        "dtc_count": 1
    },
    "conversation_id": "optional-uuid",
    "stream": false
}
```
- Response:
```json
{
    "response": "Based on your vehicle data...",
    "sources": [],
    "confidence": 0.85,
    "alerts": [],
    "is_final": true,
    "conversation_id": "uuid"
}
```

**2. GET /chat/remaining**
- Auth: `get_current_user`
- Returns remaining chat messages for user's tier
- Response:
```json
{
    "remaining": 12,
    "limit": 15,
    "used": 3,
    "tier": "pro",
    "unlimited": false,
    "resets_at": 1707523200.0
}
```
- For FREE tier: `{"remaining": 0, "limit": 0, "tier": "free", "unlimited": false}`
- For ADMIN: `{"remaining": -1, "limit": -1, "tier": "admin", "unlimited": true}`

**3. GET /models**
- Auth: `get_current_user`
- Returns available AI models
- Response:
```json
{
    "models": [
        {
            "id": "qwen2.5-7b",
            "name": "Qwen 2.5 7B Instruct",
            "description": "Primary diagnostic assistant",
            "quantization": "Q5_K_M",
            "size_gb": 5.2,
            "loaded": true
        }
    ],
    "current_model": "qwen2.5-7b",
    "status": "ready"
}
```

**4. POST /models/switch**
- Auth: `get_current_user` (admin only)
- Body: `{"model_id": "qwen2.5-7b"}`
- Response: `{"success": true, "message": "Model switched", "model": "qwen2.5-7b"}`
- Since we only use Qwen 2.5 now, this is mostly a no-op but must exist for Android compatibility

### Also fix the inline imports in the existing `/chat` endpoint:
Lines 43-44 and 59 have inline imports (`from predict.core.db.models.vehicle import VehicleProfile` etc.). Move ALL imports to the top of the file.

---

## FILE 4: MODIFY `predict/core/api/v1/predictions.py`

### Add these new endpoints:

**1. GET /pending/{profile_id}**
- Auth: `get_current_user`
- Returns unacknowledged predictions for a vehicle
- Response:
```json
{
    "success": true,
    "profile_id": 42,
    "pending_predictions": [
        {
            "prediction_id": "uuid",
            "component": "battery",
            "failure_probability": 0.78,
            "confidence": 0.85,
            "estimated_days": 15,
            "severity": "high",
            "created_at": 1707523200.0
        }
    ],
    "count": 1
}
```
- Query: `SELECT * FROM predictions WHERE profile_id = ? AND status = 'active' ORDER BY created_at DESC`

**2. POST /analyze/{vehicle_id}** (already exists as POST /{vehicle_id}/analyze, verify it works)

**3. Legacy feedback alias: POST /feedback** (root level)
- Android calls `POST /api/v1/feedback` with body `{"profile_id": 42, "prediction_id": "uuid", "was_correct": true, ...}`
- This needs to be a legacy route that maps to the existing feedback logic
- Add to the legacy_router or create one in this file

**4. LSTM endpoints (add to predictions router or create sub-router):**

**POST /lstm/predict**
- Auth: `get_current_user`
- Body:
```json
{
    "profile_id": 42,
    "sequence_data": [
        {"rpm": 850, "speed": 0, "coolant_temp": 92, "battery_voltage": 14.2, "timestamp": 1707523200.0}
    ]
}
```
- Response:
```json
{
    "success": true,
    "prediction": {
        "failure_probability": 0.78,
        "failure_type": "battery_degradation",
        "days_to_failure": 15,
        "confidence": 0.85,
        "prediction_id": "uuid",
        "components_at_risk": ["battery", "alternator"]
    },
    "model_version": "1.0.0",
    "timestamp": 1707523200.0
}
```
- Call `UnifiedAI.get_complete_vehicle_intelligence()` and extract LSTM results

**GET /lstm/status**
- Auth: `get_current_user`
- Response:
```json
{
    "available": true,
    "status": {
        "model_loaded": true,
        "model_version": "1.0.0",
        "is_trained": true,
        "accuracy": 0.87
    }
}
```

---

## FILE 5: MODIFY `predict/core/api/v1/tiers.py`

### Add alias endpoint:

**GET /list** (alias for GET /)
- Same logic as the existing `list_tiers()` function
- Android calls `GET /tiers/list` but server only has `GET /tiers/`
- Simply add:
```python
@router.get("/list", response_model=List[TierResponse])
async def list_tiers_alias(db: AsyncSession = Depends(get_db)):
    """Alias for list_tiers - Android compatibility."""
    return await list_tiers(db=db)
```

### Update DEFAULT_TIERS to match the new tier definitions:
Replace the existing DEFAULT_TIERS with the official limits from the plan. Remove the "basic" tier (not in the new system). Keep: free, pro, premium. Add admin tier.

Update features and limits to match:
- FREE: OBD unlimited, 1 vehicle, 2 DTC checks total, 0 predictions, 0 chat, 0 PDFs, no guardian, 7-day history
- PRO: OBD unlimited, 1 vehicle, unlimited DTC, 2 predictions/day, 15 chat/day, 1 PDF/week, no guardian, 90-day history
- PREMIUM: OBD unlimited, 4 vehicles, unlimited DTC, 5 pred/vehicle/day, 25 chat/vehicle/day, 2 PDF/vehicle/week, guardian (4 vehicles), 365-day history
- ADMIN: Everything unlimited

---

## FILE 6: MODIFY `predict/core/api/v1/router.py`

### Add new routers:

After the existing imports, add:
```python
from predict.core.api.v1 import usage, fcm
```

After the existing router includes, add:
```python
# Usage tracking and permissions
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(usage.key_router, prefix="/key", tags=["permissions"])

# FCM push notifications
api_router.include_router(fcm.router, prefix="/fcm", tags=["fcm"])
```

Note: usage.py should export TWO routers:
- `router` for `/usage/*` endpoints (track, check, all)
- `key_router` for `/key/permissions`

Also add legacy routes for predictions:
```python
api_router.include_router(predictions.legacy_router, tags=["legacy"])
```

---

## FILE 7: CREATE `predict/core/jobs/tasks/training_tasks.py`

AI training auto-scheduler.

```python
"""
AI Training scheduler task.
Runs as ARQ cron job every 15 minutes.
Checks if current time is within the configured training window.
"""

import json
import logging
import time
from pathlib import Path

from predict.core.config import get_config

logger = logging.getLogger(__name__)


async def check_and_start_training(ctx):
    """Check if it's time to start AI training."""
    config = get_config()
    schedule_path = Path(config.DATA_DIR) / "ai_schedule.json"

    if not schedule_path.exists():
        return  # No schedule configured

    with open(schedule_path, "r") as f:
        schedule = json.loads(f.read())

    if not schedule.get("enabled", False):
        return

    # Check if current time is within window
    now = time.localtime()
    current_minutes = now.tm_hour * 60 + now.tm_min
    start_minutes = schedule["start_hour"] * 60 + schedule.get("start_minute", 0)
    end_minutes = schedule["end_hour"] * 60 + schedule.get("end_minute", 0)

    if start_minutes <= current_minutes < end_minutes:
        # Check if training is already in progress
        from predict.core.ai.unified_ai_module import get_unified_ai
        ai = get_unified_ai()
        status = ai.get_system_status()

        if status.get("training_in_progress", False):
            logger.info("Training already in progress, skipping")
            return

        logger.info("Starting scheduled AI training")
        # Start training (this should be non-blocking)
        # The actual training implementation depends on UnifiedAI's API
        # ai.start_training() or similar
    else:
        logger.debug("Outside training window (%02d:%02d - %02d:%02d), current: %02d:%02d",
                     schedule["start_hour"], schedule.get("start_minute", 0),
                     schedule["end_hour"], schedule.get("end_minute", 0),
                     now.tm_hour, now.tm_min)
```

## FILE 8: MODIFY `predict/core/jobs/worker.py`

Add the training cron to the ARQ schedule:

```python
from predict.core.jobs.tasks.training_tasks import check_and_start_training

# In the cron_jobs list, add:
cron_jobs = [
    # ... existing cron jobs ...
    cron(check_and_start_training, minute={0, 15, 30, 45}),  # Every 15 minutes
]
```

---

## FILE 9: CREATE `data/ai_schedule.json`

Default config:
```json
{
    "start_hour": 3,
    "start_minute": 0,
    "end_hour": 5,
    "end_minute": 0,
    "enabled": false
}
```

---

## VERIFICATION

After implementing all files:

1. Start the server: `python -m predict --headless`
2. Test each endpoint with curl/httpie:
   - `GET /key/permissions` with a valid API key -> returns full permissions
   - `POST /usage/track` with `{"feature": "llm_chat", "count": 1}` -> increments usage
   - `GET /usage/check/llm_chat` -> returns allowed/denied
   - `GET /usage/all` -> returns all usage stats
   - `POST /fcm/register` with token -> saves token
   - `POST /ai/smart-chat` with message -> returns AI response
   - `GET /ai/chat/remaining` -> returns remaining messages
   - `GET /ai/models` -> returns model list
   - `GET /predictions/pending/1` -> returns pending predictions
   - `GET /tiers/list` -> returns tier list (same as GET /tiers/)
3. Check that no import errors occur on startup
4. Verify all existing endpoints still work (no regressions)

---

## IMPORTANT REMINDERS
- NO inline imports (move ALL to top of file)
- NO datetime.now() - use time.time()
- NO print() - use logger.info/warning/error
- ALL response timestamps must be float (time.time())
- Match the EXACT response shapes above - Android parses these
- Every endpoint needs proper error handling with HTTPException
- Use Pydantic BaseModel for ALL request/response schemas
