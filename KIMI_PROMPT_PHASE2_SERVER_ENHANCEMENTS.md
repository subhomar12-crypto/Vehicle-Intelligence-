# KIMI PROMPT: Phase 2 - Server Enhancements (Real-Time + Notifications)

## Your Role
You are adding real-time WebSocket broadcasts and FCM push notifications to existing server endpoints. These changes make the desktop GUI update instantly when Android users send data, and mobile users get push notifications when the admin takes actions on the desktop.

## Project Location
`C:\D Drive\Predict\`

## ARCHITECTURE RULES (MUST FOLLOW - NO EXCEPTIONS)
1. `time.time()` for ALL timestamps (NO `datetime.now()` or `datetime.utcnow()`)
2. `sa.Float()` for DB timestamp columns (NO `sa.DateTime()`)
3. `Mapped[type]` + `mapped_column()` for ORM (NO `Column()`)
4. ALL imports at top of file (NO inline imports inside functions)
5. `logging.getLogger(__name__)` (NO `print()`)
6. `get_config()` for paths (NO hardcoded paths)
7. `json.loads()` for parsing

## IMPORTANT: Phase 1 must be completed first
This phase assumes Phase 1 files already exist: `usage.py`, `fcm.py`, updated `ai_chat.py`, updated `predictions.py`, updated `tiers.py`, updated `router.py`, `training_tasks.py`.

---

## EXISTING CODE REFERENCE

### WebSocket Service (`predict/core/services/websocket_service.py`)
```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket, user_id) -> None: ...
    async def disconnect(self, websocket, user_id) -> None: ...
    async def send_to_user(self, user_id, data) -> None: ...
    async def broadcast(self, data) -> None: ...

ws_manager = ConnectionManager()
```
- `broadcast()` sends to ALL connected WebSocket clients
- `send_to_user()` sends to a specific user's connections
- Import: `from predict.core.services.websocket_service import ws_manager`

### FCM Service (`predict/core/services/fcm_service.py`)
```python
class FCMService:
    async def send_push(self, token, title, body, data=None, channel_id=None) -> bool: ...
    async def send_to_user(self, user_id, title, body, data=None) -> bool: ...
    async def send_to_multiple(self, tokens, title, body, data=None) -> Dict: ...
```
- `send_to_user()` is NOT fully implemented yet - needs to look up `fcm_token` from User table
- Import: `from predict.core.services.fcm_service import FCMService`

### Entitlement Model (`predict/core/db/models/user.py`)
```python
class Entitlement(Base):
    __tablename__ = "entitlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    granted_at: Mapped[float] = mapped_column(Float, nullable=False)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer)
    user: Mapped["User"] = relationship(back_populates="entitlements")
```

### RateLimit Model (for numeric overrides)
```python
class RateLimit(Base):
    __tablename__ = "rate_limits"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    max_requests: Mapped[Optional[int]] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
```

### User Model has `fcm_token` field
```python
class User(Base):
    __tablename__ = "users"
    # ... other fields ...
    fcm_token: Mapped[Optional[str]] = mapped_column(String(255))  # if exists
```
NOTE: Check if `fcm_token` field exists on User model. If not, it needs to be added as:
```python
fcm_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

---

## FILE 1: MODIFY `predict/core/api/v1/admin.py`

### Change 1: Add entitlements management endpoint

Add these Pydantic models near the top (after existing models):

```python
class EntitlementRequest(BaseModel):
    feature: str
    enabled: bool = True
    custom_limit: Optional[int] = None
    period: Optional[str] = None  # day, week, month


class EntitlementBulkRequest(BaseModel):
    entitlements: List[EntitlementRequest]
```

Add this new endpoint (after the existing `change_user_tier` endpoint):

**PUT /admin/users/{user_id}/entitlements**
- Auth: admin only
- Body: `EntitlementBulkRequest`
- For each entitlement in the request:
  - Upsert into `entitlements` table (set `enabled`, `granted_at=time.time()`, `granted_by=admin_user_id`)
  - If `custom_limit` is provided, also upsert into `rate_limits` table (set `max_requests`, `period`)
- Response:
```json
{
    "status": "success",
    "user_id": 42,
    "updated_entitlements": [
        {"feature": "predictions_per_day", "enabled": true, "custom_limit": 200}
    ],
    "timestamp": 1707523200.0
}
```
- Log to audit: `event_type="entitlements_updated"`

### Change 2: Add WebSocket broadcast + FCM notification after tier change

In the existing `change_user_tier` endpoint (currently at line ~168), after the audit log is written and before the return statement, add:

```python
    # Broadcast tier change via WebSocket
    try:
        await ws_manager.broadcast({
            "type": "USER_CHANGE",
            "event": "tier_changed",
            "user_id": user_id,
            "old_tier": old_tier,
            "new_tier": request.tier,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")

    # Send FCM push notification to the user
    try:
        fcm = FCMService()
        tier_display = request.tier.capitalize()
        await fcm.send_to_user(
            user_id=user_id,
            title="Subscription Updated",
            body=f"Your plan has been changed to {tier_display}",
            data={
                "type": "tier_change",
                "new_tier": request.tier,
                "old_tier": old_tier,
            },
        )
    except Exception as e:
        logger.debug(f"FCM notification failed (non-critical): {e}")
```

### Change 3: Add required imports at top of file

Add these to the existing imports (do NOT duplicate already-imported modules):
```python
from predict.core.services.websocket_service import ws_manager
from predict.core.services.fcm_service import FCMService
from predict.core.db.models.user import User, ApiKey, Entitlement, RateLimit
```

Also add `List` to the typing import if not there:
```python
from typing import Optional, List
```

And add `BaseModel` list support:
```python
from pydantic import BaseModel
```

---

## FILE 2: MODIFY `predict/core/api/v1/auth.py`

### Change: Add WebSocket broadcast after registration

In the `register` endpoint (the main one, not the legacy), after `await db.commit()` (around line 413) and before the return statement, add:

```python
    # Broadcast new user registration via WebSocket
    try:
        await ws_manager.broadcast({
            "type": "USER_CHANGE",
            "event": "user_registered",
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "tier": "free",
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")
```

### Required import at top of file:
```python
from predict.core.services.websocket_service import ws_manager
```

---

## FILE 3: MODIFY `predict/core/api/v1/reports.py`

### Change 1: Fix inline imports

The current file has inline imports inside functions (lines 52, 82-83, 115, 146, 175, 218, 253, 289). Move ALL of these to the top of the file:

```python
from predict.core.db.models.vehicle import VehicleProfile, ServiceRecord
from predict.core.db.models.prediction import Prediction
from predict.core.db.models.trip import Trip
from predict.core.db.models.audit import Report
from predict.core.services.fcm_service import FCMService
from predict.core.services.websocket_service import ws_manager
```

Remove ALL `from predict.core.db.models...` lines that are inside the endpoint functions.

### Change 2: Add FCM notification after report generation

In the `generate_report` endpoint, after the report is saved to DB and before the return statement (around line 196), add:

```python
    # Send FCM notification that report is ready
    try:
        fcm = FCMService()
        await fcm.send_to_user(
            user_id=user_id,
            title="Report Ready",
            body=f"Your {request.report_type} report is ready for download",
            data={
                "type": "report_ready",
                "report_id": str(report.id),
                "report_type": request.report_type,
                "vehicle_id": str(request.vehicle_id),
            },
        )
    except Exception as e:
        logger.debug(f"FCM notification failed (non-critical): {e}")

    # Broadcast report ready via WebSocket
    try:
        await ws_manager.broadcast({
            "type": "ALERT",
            "event": "report_ready",
            "user_id": user_id,
            "report_id": report.id,
            "report_type": request.report_type,
            "vehicle_id": request.vehicle_id,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.debug(f"WebSocket broadcast failed (non-critical): {e}")
```

---

## FILE 4: MODIFY `predict/core/services/fcm_service.py`

### Change: Implement `send_to_user` method

The current `send_to_user` method at line 212 is a stub that logs a warning and returns False. Replace it with a working implementation:

```python
    async def send_to_user(
        self,
        user_id: int,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification to a user by looking up their FCM token.

        Args:
            user_id: User ID to send to
            title: Notification title
            body: Notification body
            data: Optional data payload

        Returns:
            True if sent successfully
        """
        try:
            from predict.core.db.session import get_async_session
            from predict.core.db.models.user import User
            from sqlalchemy import select

            async with get_async_session() as session:
                stmt = select(User.fcm_token).where(
                    User.id == user_id,
                    User.is_active == True,
                )
                result = await session.execute(stmt)
                fcm_token = result.scalar_one_or_none()

            if not fcm_token:
                logger.info(f"No FCM token for user {user_id} - notification skipped")
                return False

            return await self.send_push(
                token=fcm_token,
                title=title,
                body=body,
                data=data,
            )
        except Exception as e:
            logger.error(f"FCM send_to_user failed for user {user_id}: {e}")
            return False
```

**IMPORTANT**: Check if `get_async_session` exists in `predict/core/db/session.py`. It should be a context manager that creates and yields an AsyncSession. If it doesn't exist, you need to create it:

```python
# In predict/core/db/session.py, if get_async_session doesn't exist:
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_async_session():
    """Context manager for getting a database session outside of FastAPI."""
    session = async_session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

NOTE: The `from predict.core.db.session import get_async_session` is an inline import because this is a SERVICE file, not an API route. The service might be called outside the FastAPI dependency injection context, so it needs to create its own session. This is an acceptable exception to the "no inline imports" rule since circular imports would occur if we imported at the top of this file.

---

## FILE 5: MODIFY `predict/core/db/models/user.py`

### Change: Add `fcm_token` field to User model (if not already present)

Check if `fcm_token` already exists on the User model. If not, add it:

```python
class User(Base):
    # ... existing fields ...
    fcm_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
```

Also add `expires_at` to Entitlement model for time-limited overrides:

```python
class Entitlement(Base):
    __tablename__ = "entitlements"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    feature: Mapped[str] = mapped_column(String(50), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default="true")
    granted_at: Mapped[float] = mapped_column(Float, nullable=False)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer)
    expires_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # ADD THIS

    user: Mapped["User"] = relationship(back_populates="entitlements")

    __table_args__ = (
        UniqueConstraint("user_id", "feature", name="uq_entitlement_user_feature"),
    )
```

---

## FILE 6: MODIFY `predict/core/services/websocket_service.py`

### Change: Add `broadcast_to_channel` method and `channels` property

The existing websockets.py router references `ws_manager.broadcast_to_channel()` and `ws_manager.channels` which don't exist. Add them:

```python
class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.channels: Dict[str, Set[WebSocket]] = {}  # ADD THIS

    async def connect(self, websocket: WebSocket, user_id) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        # Support both int user_id and string channel names
        key = user_id
        if key not in self.active_connections:
            self.active_connections[key] = set()
        self.active_connections[key].add(websocket)

        # Also track by string channel if it's a string
        if isinstance(user_id, str):
            if user_id not in self.channels:
                self.channels[user_id] = set()
            self.channels[user_id].add(websocket)

        logger.info(f"WebSocket connected: {user_id}")

    async def disconnect(self, websocket: WebSocket, user_id) -> None:
        """Remove a WebSocket connection."""
        key = user_id
        if key in self.active_connections:
            self.active_connections[key].discard(websocket)
            if not self.active_connections[key]:
                del self.active_connections[key]

        if isinstance(user_id, str) and user_id in self.channels:
            self.channels[user_id].discard(websocket)
            if not self.channels[user_id]:
                del self.channels[user_id]

        logger.info(f"WebSocket disconnected: {user_id}")

    async def send_to_user(self, user_id, data: Dict[str, Any]) -> None:
        """Send data to all connections for a user."""
        connections = self.active_connections.get(user_id, set())
        for ws in list(connections):
            try:
                await ws.send_json(data)
            except Exception:
                connections.discard(ws)

    async def broadcast(self, data: Dict[str, Any]) -> None:
        """Broadcast data to all connected users."""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, data)

    async def broadcast_to_channel(self, channel: str, data: Dict[str, Any]) -> None:
        """Broadcast data to all connections in a specific channel."""
        connections = self.channels.get(channel, set())
        for ws in list(connections):
            try:
                await ws.send_json(data)
            except Exception:
                connections.discard(ws)

    @property
    def active_count(self) -> int:
        """Number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())
```

---

## SUMMARY OF CHANGES

| File | Action | Changes |
|------|--------|---------|
| `admin.py` | MODIFY | Add entitlements endpoint, WS broadcast + FCM on tier change |
| `auth.py` | MODIFY | Add WS broadcast after registration |
| `reports.py` | MODIFY | Fix inline imports, add FCM + WS on report ready |
| `fcm_service.py` | MODIFY | Implement `send_to_user` with DB token lookup |
| `user.py` (models) | MODIFY | Add `fcm_token` to User, add `expires_at` to Entitlement |
| `websocket_service.py` | MODIFY | Add `channels`, `broadcast_to_channel` |

---

## VERIFICATION

After implementing:

1. Start the server: `python -m predict --headless`
2. Test WebSocket: Connect to `ws://127.0.0.1:8000/ws/1` and verify broadcast messages arrive
3. Test tier change: `PUT /admin/users/{id}/tier` should:
   - Change the tier in DB
   - Broadcast `USER_CHANGE` event via WebSocket (check WS client receives it)
   - Send FCM push (check logs for FCM message)
4. Test entitlements: `PUT /admin/users/{id}/entitlements` with body `{"entitlements": [{"feature": "predictions_per_day", "enabled": true, "custom_limit": 200}]}`
5. Test report notification: `POST /report/generate` should send FCM + WS broadcast when done
6. Verify no import errors on startup
7. Verify all existing endpoints still work (no regressions)

---

## IMPORTANT REMINDERS
- NO inline imports in API route files (services can use inline imports to avoid circular deps)
- NO datetime.now() - use time.time()
- NO print() - use logger
- ALL WebSocket broadcasts and FCM sends MUST be wrapped in try/except - they are non-critical and must NEVER crash the main request
- ALL response timestamps must be float (time.time())
- After completing this phase, STOP and wait for review before proceeding to Phase 3

## STOP AFTER THIS PHASE
Do NOT proceed to Phase 3 (Desktop GUI). After completing all Phase 2 changes, stop and present all modified files for review. The reviewer will trace every change, verify imports, and test before giving the go-ahead for Phase 3.
