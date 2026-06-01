# PREDICT Production Refactor - ALL PHASES (1 through 12)

## CRITICAL PROTOCOL - READ THIS FIRST

### STOP-AND-REVIEW PROTOCOL
After you finish ALL files in a phase:
1. **Self-review every file** you wrote/modified for architecture violations
2. **List every file** you created or modified with line counts
3. **Print "PHASE X COMPLETE - AWAITING REVIEW"**
4. **STOP. Do NOT proceed to the next phase.**
5. Wait for my review. I will tell you "PROCEED TO PHASE X" when ready.

### ARCHITECTURE RULES (VIOLATIONS = REWRITE)
Every file you write MUST follow these rules. NO EXCEPTIONS:

| Rule | Correct | WRONG (will be rejected) |
|---|---|---|
| Timestamps | `time.time()` (float) | `datetime.now()`, `datetime.utcnow()`, `datetime.datetime` |
| ORM columns | `Mapped[type] = mapped_column(...)` | `Column(...)`, `db.Column(...)` |
| DB operations | `async def` + `await session.execute()` | Sync `session.query()`, raw SQL strings |
| Repository pattern | `class XRepo(BaseRepository[ModelX])` | Direct session usage in routers |
| GUI framework | `from PySide6.QtWidgets import ...` | `from PyQt5`, `from PyQt6` |
| Logging | `logger = logging.getLogger(__name__)` | `print()`, `sys.stdout` |
| Config paths | `from predict.core.config import get_config` | Hardcoded `C:\...`, `"/path/to/..."` |
| Imports | `from predict.core.X import Y` | Relative `from ..X import Y` beyond package |
| Error handling | `logger.error(...)` + raise/return | Bare `except: pass` |
| Float defaults | `default=time.time` (callable) | `default=time.time()` (evaluated once at import) |

### SELF-REVIEW CHECKLIST (RUN AFTER EACH FILE)
Before moving to the next file, verify:
- [ ] No `datetime.now()` or `datetime.utcnow()` anywhere
- [ ] No `print()` statements (only `logger.debug/info/warning/error`)
- [ ] No `Column()` - only `mapped_column()`
- [ ] No hardcoded file paths
- [ ] No `from PyQt5` or `from PyQt6`
- [ ] All DB functions are `async def`
- [ ] All timestamps are `float` (Unix epoch from `time.time()`)
- [ ] Imports use absolute paths: `from predict.core.X import Y`

---

## EXISTING FILE STATUS (DO NOT RECREATE THESE)

### REAL (fully implemented - DO NOT TOUCH unless specified):
```
predict/__main__.py (88 lines)
predict/headless.py (101 lines)
predict/core/config.py (197 lines)
predict/core/version.py
predict/core/db/engine.py (68 lines)
predict/core/db/session.py (61 lines)
predict/core/db/base.py (47 lines)
predict/core/db/models/*.py (ALL models - 10 files)
predict/core/db/repositories/base.py (67 lines)
predict/core/db/repositories/user_repo.py (55 lines)
predict/core/db/repositories/vehicle_repo.py (71 lines)
predict/core/db/repositories/trip_repo.py (198 lines)
predict/core/db/repositories/prediction_repo.py (197 lines)
predict/core/db/repositories/guardian_repo.py (166 lines)
predict/core/db/repositories/subscription_repo.py (178 lines)
predict/core/db/repositories/audit_repo.py (211 lines)
predict/core/db/migrations/env.py
predict/core/db/migrations/versions/001_initial_49_models.py
predict/core/middleware/api_key.py (217 lines)
predict/core/middleware/cors.py (25 lines)
predict/core/middleware/request_tracing.py (30 lines)
predict/core/middleware/validation.py (126 lines)
predict/core/middleware/audit.py (108 lines)
predict/core/middleware/error_handler.py (86 lines)
predict/core/middleware/rate_limiter.py (221 lines)
predict/core/cache/redis_client.py (131 lines)
predict/core/cache/api_key_cache.py (91 lines)
predict/core/cache/pubsub.py (127 lines)
predict/core/security/jwt_handler.py (247 lines)
predict/core/services/auth_service.py (375 lines)
predict/core/services/websocket_service.py (62 lines)
predict/core/services/export_service.py (162 lines)
predict/core/monitoring/health.py (206 lines)
predict/core/monitoring/metrics.py (120 lines)
predict/core/api/app.py
predict/core/api/deps.py
predict/core/api/v1/router.py (86 lines)
predict/core/api/v1/auth.py (397 lines)
predict/core/api/v1/health.py (104 lines)
predict/core/api/v1/profiles.py (480 lines)
predict/core/jobs/queue.py (163 lines)
predict/core/jobs/worker.py (129 lines)
predict/core/ai/uncertainty_estimator.py (198 lines)
predict/core/ai/temporal_consistency.py (210 lines)
predict/core/ai/abstention_manager.py (176 lines)
predict/core/ai/hindsight_collector.py (529 lines)
predict/core/db/models/hindsight.py (208 lines)
predict/core/ai/training/data_fertilizer.py (~1100 lines)
predict/desktop/app.py (108 lines)
```

### STUBS (files that EXIST but need REAL implementation):
```
predict/core/services/email_service.py (134 lines - logs only, no SMTP)
predict/core/services/fcm_service.py (43 lines - logs only, no Firebase)
predict/core/services/billing_service.py (42 lines - returns placeholders)
predict/core/services/guardian_service.py (64 lines - returns None/empty)
predict/core/services/prediction_service.py (48 lines - returns placeholder)
predict/core/services/pdf_service.py (46 lines - not implemented)
predict/core/services/backup_service.py (47 lines - not implemented)
predict/core/services/gdpr_service.py (52 lines - not implemented)
predict/core/services/obd_processor.py (51 lines - not implemented)
predict/core/api/v1/vehicle_data.py (STUB)
predict/core/api/v1/predictions.py (STUB)
predict/core/api/v1/dtc.py (STUB)
predict/core/api/v1/guardian.py (STUB)
predict/core/api/v1/fleet.py (STUB)
predict/core/api/v1/billing.py (STUB)
predict/core/api/v1/reports.py (STUB)
predict/core/api/v1/admin.py (STUB)
predict/core/api/v1/ai_chat.py (STUB)
predict/core/api/v1/legal.py (STUB)
predict/core/api/v1/dashboard.py (STUB)
predict/core/api/v1/driving.py (STUB)
predict/core/api/v1/tiers.py (STUB)
predict/core/api/v1/app_version.py (STUB)
predict/core/api/v1/websockets.py (STUB)
predict/core/jobs/tasks/email_tasks.py (STUB)
predict/core/jobs/tasks/fcm_tasks.py (STUB)
predict/core/jobs/tasks/backup_tasks.py (STUB)
predict/core/jobs/tasks/cleanup_tasks.py (STUB)
predict/core/jobs/tasks/parquet_tasks.py (STUB)
predict/core/jobs/tasks/pdf_tasks.py (STUB)
```

---

## REFERENCE: Original Server Code Location
The original server code with ALL endpoint logic is at: `C:\OBDserver\`
- `C:\OBDserver\main.py` — 460KB, 12000+ lines, ALL 162+ endpoints
- `C:\OBDserver\guardian_api.py` — 88KB, guardian endpoints
- `C:\OBDserver\fatora_billing.py` — Fatora payment endpoints
- `C:\OBDserver\fcm_service.py` — Firebase Cloud Messaging
- `C:\OBDserver\email_service.py` — Email with SMTP
- `C:\OBDserver\health_monitor.py` — Health monitoring
- `C:\OBDserver\database.py` — 341KB, all table definitions + DB logic
- `C:\OBDserver\backup_utility.py` — Backup logic
- `C:\OBDserver\pdf_report.py` — PDF generation
- `C:\OBDserver\websocket_manager.py` — WebSocket management
- `C:\OBDserver\legal_api.py` — Legal endpoints
- `C:\OBDserver\ai_chat_endpoint.py` — AI chat endpoints

The original desktop code is at: `C:\D Drive\Predict\` (root level .py files)
- `unified_ai_module.py` — 1147 lines, central AI hub
- `enhanced_prediction_engine.py` — Enhanced predictions
- `lstm_predictor.py`, `cnn_lstm_model.py`, `attention_lstm_model.py` — ML models
- `llm_assistant.py` — LLM integration
- `main_pyside.py` — 463KB desktop GUI
- `predictive_failure_engine.py` — RandomForest/XGBoost/LightGBM
- `failure_correlation_engine.py` — Failure pattern detection
- `advanced_feature_engineering.py` — Feature engineering
- `fleet_learning_aggregator.py` — Fleet learning
- `vehicle_baseline_learning.py` — Per-vehicle baselines
- `recall_monitor.py` — NHTSA recalls
- `web_search.py` — DuckDuckGo integration
- `vehicle_research_engine.py` — Vehicle-specific research

**IMPORTANT**: Extract logic from these original files. Do NOT invent new endpoint paths or response formats. The Android app depends on the EXACT same API contracts.

---

# PHASE 1: Database Layer Verification

**Status**: Mostly done. Verify everything works together.

## Tasks:
1. **Read and verify** `predict/core/db/engine.py` — Ensure it creates an AsyncEngine with proper pool settings (pool_size=5, max_overflow=15, pool_pre_ping=True). Ensure it reads DATABASE_URL from config/environment.
2. **Read and verify** `predict/core/db/session.py` — Ensure `async_session_maker` and `get_db` async generator work correctly.
3. **Read and verify** `predict/core/db/base.py` — Ensure `TimestampMixin` uses `Float` with `default=time.time` (NOT datetime).
4. **Read and verify** ALL models in `predict/core/db/models/` — Check for any remaining `datetime` usage, `Column()` instead of `mapped_column()`, or missing fields compared to the original `C:\OBDserver\database.py`.
5. **Read and verify** `predict/core/db/repositories/base.py` — Ensure `BaseRepository[ModelT]` has: `get_by_id()`, `get_all()`, `create()`, `update()`, `delete()`, `count()`.
6. **Read and verify** ALL repositories — Ensure they extend `BaseRepository[ModelT]` correctly.
7. **Read and verify** `alembic.ini` and `predict/core/db/migrations/env.py` — Ensure Alembic is configured for async SQLAlchemy.
8. **Read and verify** `predict/core/db/migrations/versions/001_initial_49_models.py` — Ensure it creates ALL tables.

## Fix any issues found. Do NOT skip verification steps.

## Expected output:
```
PHASE 1 COMPLETE - AWAITING REVIEW
Files verified: [list]
Files modified: [list with changes]
Issues found and fixed: [list]
```

---

# PHASE 2: Core Services (Fill the Stubs)

**Goal**: Replace all stub services with real implementations. Reference the original server code at `C:\OBDserver\` for the actual logic.

## File 1: `predict/core/services/email_service.py`
Reference: `C:\OBDserver\email_service.py`

Implement:
- `async def send_email(to, subject, body, html_body=None)` — Real SMTP via `aiosmtplib`
- `async def send_verification_email(email, code)` — HTML template with 6-digit code
- `async def send_password_reset(email, code)` — Reset email
- `async def send_welcome_email(email, name)` — Welcome after registration
- `async def send_alert_email(email, alert_data)` — Guardian alerts

Config from environment:
```python
SMTP_HOST = config.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = config.get("SMTP_PORT", 587)
SMTP_USER = config.get("SMTP_USER")
SMTP_PASSWORD = config.get("SMTP_PASSWORD")
```

Pattern:
```python
import logging
import time
from typing import Optional
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from predict.core.config import get_config

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.config = get_config()
        # Read SMTP settings from config/environment

    async def send_email(self, to: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.config.smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=self.config.smtp_host,
                port=self.config.smtp_port,
                username=self.config.smtp_user,
                password=self.config.smtp_password,
                use_tls=True,
            )
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False
```

## File 2: `predict/core/services/fcm_service.py`
Reference: `C:\OBDserver\fcm_service.py`

Implement:
- `async def send_push(token, title, body, data=None, channel_id=None)` — Send via Firebase HTTP v1 API
- `async def send_to_multiple(tokens, title, body, data=None)` — Batch send
- `async def send_guardian_alert(guardian_token, alert_type, alert_data)` — Guardian-specific notifications
- `async def remove_invalid_token(token)` — Clean up expired tokens
- Circuit breaker integration: if 5 consecutive failures, open circuit for 60 seconds

Pattern:
```python
import logging
import time
import httpx
from predict.core.config import get_config
from predict.core.monitoring.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

class FCMService:
    def __init__(self):
        self.config = get_config()
        self.circuit_breaker = CircuitBreaker(
            name="fcm",
            failure_threshold=5,
            recovery_timeout=60.0,
        )

    async def send_push(self, token: str, title: str, body: str, data: dict = None, channel_id: str = None) -> bool:
        if not self.circuit_breaker.allow_request():
            logger.warning("FCM circuit breaker OPEN - skipping push")
            return False
        try:
            # Use httpx for async HTTP to FCM
            async with httpx.AsyncClient() as client:
                payload = {
                    "message": {
                        "token": token,
                        "notification": {"title": title, "body": body},
                    }
                }
                if data:
                    payload["message"]["data"] = {k: str(v) for k, v in data.items()}
                if channel_id:
                    payload["message"]["android"] = {
                        "notification": {"channel_id": channel_id}
                    }
                response = await client.post(
                    f"https://fcm.googleapis.com/v1/projects/{self.config.firebase_project_id}/messages:send",
                    json=payload,
                    headers={"Authorization": f"Bearer {await self._get_access_token()}"},
                )
                if response.status_code == 200:
                    self.circuit_breaker.record_success()
                    return True
                else:
                    self.circuit_breaker.record_failure()
                    logger.error(f"FCM error {response.status_code}: {response.text}")
                    return False
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"FCM send failed: {e}")
            return False
```

## File 3: `predict/core/services/billing_service.py`
Reference: `C:\OBDserver\fatora_billing.py`

Implement:
- `async def create_payment(user_id, amount, tier, currency="QAR")` — Create Fatora payment
- `async def verify_payment(payment_id)` — Check Fatora payment status
- `async def handle_webhook(payload, signature)` — Process Fatora webhook callback
- `async def upgrade_tier(user_id, new_tier, payment_id)` — Upgrade user subscription tier
- `async def get_payment_history(user_id)` — List past payments
- Circuit breaker for Fatora API

Extract the EXACT Fatora API integration from `C:\OBDserver\fatora_billing.py`. Keep the same API URLs, headers, and response handling.

## File 4: `predict/core/services/guardian_service.py`
Reference: `C:\OBDserver\guardian_api.py`

Implement:
- `async def create_guardian(parent_user_id, name)` — Create guardian profile
- `async def link_vehicle(guardian_id, vehicle_id, relationship)` — Link guardian to vehicle
- `async def send_command(guardian_id, vehicle_id, command_type, payload)` — Send command to monitored vehicle
- `async def get_alerts(guardian_id, limit=50)` — Get guardian alerts
- `async def get_location(guardian_id, vehicle_id)` — Get last known location
- `async def create_geofence(guardian_id, vehicle_id, lat, lon, radius_m, name)` — Create geofence
- `async def check_geofence_violations(vehicle_id, lat, lon)` — Check if vehicle left geofence

Extract logic from `C:\OBDserver\guardian_api.py`. Use repository pattern (GuardianRepo).

## File 5: `predict/core/services/prediction_service.py`
Reference: `C:\D Drive\Predict\unified_ai_module.py`

Implement:
- `async def get_vehicle_prediction(vehicle_id, session)` — Get AI prediction for vehicle
- `async def get_component_risk(vehicle_id, component, session)` — Get risk for specific component
- `async def check_prediction_quota(user_id, tier, session)` — Check if user has remaining predictions
- `async def log_prediction(vehicle_id, prediction_data, session)` — Log to PredictionAuditLog
- This service is the API-layer bridge to `unified_ai_module.py`

Pattern:
```python
import logging
import time
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from predict.core.ai.unified_ai_module import UnifiedAIModule
from predict.core.db.repositories.prediction_repo import PredictionRepository

logger = logging.getLogger(__name__)

class PredictionService:
    def __init__(self):
        self.ai_module = None  # Lazy init
        self.prediction_repo = PredictionRepository()

    def _ensure_ai(self):
        if self.ai_module is None:
            self.ai_module = UnifiedAIModule()

    async def get_vehicle_prediction(self, vehicle_id: int, session: AsyncSession) -> Dict[str, Any]:
        self._ensure_ai()
        # Fetch recent vehicle data from DB
        from predict.core.db.repositories.vehicle_repo import VehicleDataRepository
        vehicle_repo = VehicleDataRepository()
        recent_data = await vehicle_repo.get_recent(session, vehicle_id, limit=200)

        if not recent_data:
            return {"error": "No vehicle data available", "vehicle_id": vehicle_id}

        # Convert DB records to dict format for AI module
        obd_data = self._records_to_obd_dict(recent_data)

        # Run AI analysis (CPU-bound, use asyncio.to_thread)
        import asyncio
        result = await asyncio.to_thread(
            self.ai_module.get_complete_vehicle_intelligence,
            obd_data, None, [self._record_to_dict(r) for r in recent_data], []
        )

        return result
```

## File 6: `predict/core/services/pdf_service.py`
Reference: `C:\OBDserver\pdf_report.py` + `C:\D Drive\Predict\pdf_exporter.py`

Implement:
- `async def generate_vehicle_report(vehicle_id, session)` — Full PDF health report
- `async def generate_trip_report(vehicle_id, trip_id, session)` — Trip PDF
- Uses ReportLab for PDF generation
- Runs CPU-bound work via `asyncio.to_thread`

## File 7: `predict/core/services/backup_service.py`
Reference: `C:\OBDserver\backup_utility.py`

Implement:
- `async def create_backup(backup_dir=None)` — Run pg_dump
- `async def list_backups()` — List available backups
- `async def restore_backup(backup_path)` — Run pg_restore
- `async def cleanup_old_backups(retention_days=30)` — Delete old backups

Pattern:
```python
import logging
import time
import asyncio
from pathlib import Path
from predict.core.config import get_config

logger = logging.getLogger(__name__)

class BackupService:
    def __init__(self):
        self.config = get_config()

    async def create_backup(self, backup_dir: str = None) -> dict:
        backup_dir = backup_dir or str(self.config.backup_dir)
        Path(backup_dir).mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        filename = f"predict_backup_{timestamp}.sql.gz"
        filepath = Path(backup_dir) / filename

        cmd = (
            f"pg_dump {self.config.database_url} "
            f"| gzip > {filepath}"
        )

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Backup created: {filepath}")
            return {"success": True, "path": str(filepath), "timestamp": timestamp}
        else:
            logger.error(f"Backup failed: {stderr.decode()}")
            return {"success": False, "error": stderr.decode()}
```

## File 8: `predict/core/services/gdpr_service.py`

Implement:
- `async def export_user_data(user_id, session)` — Export all user data as JSON
- `async def delete_user_data(user_id, session)` — GDPR right to deletion
- `async def cleanup_expired_telemetry(session, retention_days=30)` — Delete old telemetry
- `async def cleanup_expired_verification_codes(session, retention_hours=24)` — Clean verification codes
- `async def get_data_retention_stats(session)` — Show what data exists per retention policy

## File 9: `predict/core/services/obd_processor.py`
Reference: `C:\OBDserver\main.py` (the `/api/obd` endpoint logic)

Implement:
- `async def process_obd_payload(payload, vehicle_id, session)` — Validate + store OBD data
- `async def validate_obd_ranges(data)` — Check sensor values against OBD_RANGES
- `async def detect_anomalies(data, vehicle_id)` — Flag suspicious readings
- `async def update_vehicle_stats(vehicle_id, data, session)` — Update mileage, last seen, etc.

Use the `OBD_RANGES` from `predict/core/middleware/validation.py`.

## Expected output:
```
PHASE 2 COMPLETE - AWAITING REVIEW
Files modified: [list with line counts]
Issues found during self-review: [list]
```

---

# PHASE 3: API Router Migration (Fill All Stubs)

**Goal**: Every API endpoint stub becomes a real endpoint with proper request/response handling. Extract logic from `C:\OBDserver\main.py` and other original files.

**CRITICAL**: Keep EXACT same endpoint paths and response formats. The Android app depends on these.

## For EVERY endpoint file, follow this pattern:

```python
import logging
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.api.deps import get_db, get_current_user
from predict.core.db.repositories.vehicle_repo import VehicleDataRepository

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/endpoint")
async def endpoint_name(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Endpoint description."""
    repo = VehicleDataRepository()
    result = await repo.get_by_id(db, some_id)
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "success", "data": result}
```

## File 1: `predict/core/api/v1/vehicle_data.py`
Reference: `C:\OBDserver\main.py` — search for `/api/obd`, `/api/v1/telemetry`

Endpoints to implement:
- `POST /api/obd` — Receive OBD data from Android (THE most important endpoint)
- `GET /api/vehicle/{vehicle_id}/data` — Get recent vehicle data
- `GET /api/vehicle/{vehicle_id}/data/latest` — Get latest reading
- `GET /api/vehicle/{vehicle_id}/data/history` — Get historical data with pagination
- `POST /api/v1/telemetry` — Receive telemetry snapshot
- `GET /api/vehicle/{vehicle_id}/stats` — Get vehicle statistics
- `GET /api/vehicle/{vehicle_id}/sensors` — Get available sensor list
- `DELETE /api/vehicle/{vehicle_id}/data` — Clear vehicle data (admin only)

Use `OBDProcessorService` for processing and `VehicleDataRepository` for storage.

## File 2: `predict/core/api/v1/predictions.py`
Reference: `C:\OBDserver\main.py` — search for `/api/predictions`

Endpoints:
- `GET /api/predictions/{vehicle_id}` — Get AI predictions for vehicle
- `GET /api/predictions/{vehicle_id}/component/{component}` — Component-specific prediction
- `GET /api/predictions/{vehicle_id}/history` — Prediction history
- `POST /api/predictions/{vehicle_id}/feedback` — User feedback on prediction accuracy
- `GET /api/predictions/quota` — Check remaining predictions for user's tier

Use `PredictionService` for AI predictions and `PredictionRepository` for storage.

## File 3: `predict/core/api/v1/dtc.py`
Reference: `C:\OBDserver\main.py` — search for `/api/dtc`

Endpoints:
- `POST /api/dtc/report` — Report new DTC codes from vehicle
- `GET /api/dtc/{vehicle_id}` — Get DTC history for vehicle
- `GET /api/dtc/{vehicle_id}/active` — Get currently active DTCs
- `GET /api/dtc/lookup/{code}` — Look up DTC code description
- `DELETE /api/dtc/{vehicle_id}/{dtc_id}` — Clear/dismiss a DTC

## File 4: `predict/core/api/v1/guardian.py`
Reference: `C:\OBDserver\guardian_api.py` (88KB — this is the big one)

This file will be the LARGEST router. Extract ALL endpoints from `guardian_api.py`:
- Guardian CRUD (create, read, update, delete)
- Vehicle linking/unlinking
- Location tracking
- Speed/geofence alerts
- Command sending (lock, unlock, horn, lights)
- Trip monitoring
- Driver behavior scoring
- Guardian notifications
- Invite codes
- Report generation

**IMPORTANT**: `guardian_api.py` is already a FastAPI router. Adapt it to use the new repository pattern and async DB operations. Do NOT rewrite from scratch — migrate the existing logic.

## File 5: `predict/core/api/v1/fleet.py`
Reference: `C:\OBDserver\main.py` — search for `/api/fleet`

Endpoints:
- `POST /api/fleet/invite` — Create fleet invite
- `GET /api/fleet/invites` — List pending invites
- `POST /api/fleet/accept/{invite_id}` — Accept fleet invite
- `GET /api/fleet/vehicles` — List fleet vehicles
- `DELETE /api/fleet/vehicle/{vehicle_id}` — Remove vehicle from fleet
- `GET /api/fleet/stats` — Fleet-wide statistics

## File 6: `predict/core/api/v1/billing.py`
Reference: `C:\OBDserver\fatora_billing.py`

Endpoints:
- `POST /api/billing/create-payment` — Create Fatora payment
- `POST /api/billing/webhook` — Fatora callback webhook
- `GET /api/billing/verify/{payment_id}` — Verify payment status
- `GET /api/billing/history` — Payment history
- `GET /api/billing/subscription` — Current subscription info

Adapt from `fatora_billing.py` which is already a FastAPI router.

## File 7: `predict/core/api/v1/reports.py`
Reference: `C:\OBDserver\main.py` — search for `/api/report`

Endpoints:
- `POST /api/report/vehicle/{vehicle_id}` — Generate vehicle health report (PDF)
- `GET /api/report/{report_id}` — Download generated report
- `GET /api/report/list` — List available reports
- `DELETE /api/report/{report_id}` — Delete report

## File 8: `predict/core/api/v1/admin.py`
Reference: `C:\OBDserver\main.py` — search for `@require_admin`, `/api/admin`

Endpoints (ALL require admin authentication):
- `GET /api/admin/users` — List all users
- `GET /api/admin/users/{user_id}` — Get user details
- `PUT /api/admin/users/{user_id}/tier` — Change user tier
- `DELETE /api/admin/users/{user_id}` — Delete user
- `GET /api/admin/stats` — System statistics (users, vehicles, predictions, storage)
- `GET /api/admin/api-keys` — List all API keys
- `POST /api/admin/api-key/generate` — Generate admin API key
- `DELETE /api/admin/api-key/{key_id}` — Revoke API key
- `GET /api/admin/audit-log` — View audit log
- `GET /api/admin/vehicles` — List all vehicles
- `GET /api/admin/jobs/status` — Background job status
- `POST /api/admin/backup` — Trigger manual backup
- `GET /api/admin/backups` — List backups
- `GET /api/admin/health/detailed` — Detailed system health

## File 9: `predict/core/api/v1/ai_chat.py`
Reference: `C:\OBDserver\ai_chat_endpoint.py`

Endpoints:
- `POST /api/ai/chat` — Send message to AI assistant
- `GET /api/ai/chat/history/{vehicle_id}` — Get chat history
- `DELETE /api/ai/chat/history/{vehicle_id}` — Clear chat history
- `GET /api/ai/status` — AI model status

Use the AI Bridge pattern (Phase 6B) — for now, implement the endpoint structure and call the LLM directly. The bridge integration comes later.

## File 10: `predict/core/api/v1/legal.py`
Reference: `C:\OBDserver\legal_api.py`

Endpoints:
- `POST /api/legal/consent` — Record user consent
- `GET /api/legal/consent/{user_id}` — Get consent status
- `GET /api/legal/privacy-policy` — Get current privacy policy
- `GET /api/legal/terms` — Get terms of service
- `POST /api/legal/data-request` — GDPR data export request
- `POST /api/legal/deletion-request` — GDPR deletion request

Adapt from `legal_api.py` which is already a FastAPI router.

## File 11: `predict/core/api/v1/dashboard.py`

NEW endpoint (not in original server):
- `GET /api/dashboard/metrics` — System metrics (CPU, memory, req/s, active users)
- `GET /api/dashboard/ai-status` — AI engine status
- `GET /api/dashboard/circuit-breakers` — Circuit breaker status
- `GET /api/dashboard/recent-errors` — Recent error log
- `WebSocket /api/dashboard/ws` — Real-time dashboard updates

This is used by the Desktop dashboard tab.

## File 12: `predict/core/api/v1/driving.py`
Reference: `C:\OBDserver\main.py` — search for `/api/v1/driver`

Endpoints:
- `POST /api/v1/driver/event` — Record driving event (harsh brake, rapid accel, etc.)
- `GET /api/v1/driver/{vehicle_id}/score` — Get driving behavior score
- `GET /api/v1/driver/{vehicle_id}/events` — List driving events
- `GET /api/v1/driver/{vehicle_id}/trips` — List trips
- `GET /api/v1/driver/{vehicle_id}/trip/{trip_id}` — Get trip details

## File 13: `predict/core/api/v1/tiers.py`
Reference: `C:\OBDserver\main.py` — search for `/api/tiers`

Endpoints:
- `GET /api/tiers` — List available subscription tiers with features
- `GET /api/tiers/current` — Get user's current tier
- `GET /api/tiers/compare` — Compare tier features

## File 14: `predict/core/api/v1/app_version.py`
Reference: `C:\OBDserver\main.py` — search for `/api/app/version`

Endpoints:
- `GET /api/app/version` — Get minimum required app version (for force-update)
- `GET /api/app/changelog` — Get recent changelog

## File 15: `predict/core/api/v1/websockets.py`
Reference: `C:\OBDserver\websocket_manager.py`

Endpoints:
- `WebSocket /ws/vehicle/{vehicle_id}` — Real-time vehicle data stream
- `WebSocket /ws/guardian/{guardian_id}` — Real-time guardian alerts
- `WebSocket /ws/notifications` — User notifications

Use `WebSocketService` for connection management and `RedisPubSub` for scaling.

## Expected output:
```
PHASE 3 COMPLETE - AWAITING REVIEW
Files modified: [list with line counts]
Endpoints implemented: [count]
Issues found during self-review: [list]
```

---

# PHASE 4: Redis + Caching Verification

**Status**: Files exist and appear to be real implementations. Verify they work.

## Tasks:
1. **Read and verify** `predict/core/cache/redis_client.py` — Ensure graceful degradation (works without Redis)
2. **Read and verify** `predict/core/cache/api_key_cache.py` — Ensure 5-min TTL, invalidation on change
3. **Read and verify** `predict/core/cache/pubsub.py` — Ensure proper channel subscription for WebSockets
4. Fix any issues found.

## Expected output:
```
PHASE 4 COMPLETE - AWAITING REVIEW
Files verified: [list]
Files modified: [list with changes]
Issues found and fixed: [list]
```

---

# PHASE 5: Background Jobs (Fill Task Stubs)

**Goal**: Implement all background task functions that are currently stubs.

## File 1: `predict/core/jobs/tasks/email_tasks.py`
```python
import logging
import time
from predict.core.services.email_service import EmailService

logger = logging.getLogger(__name__)

async def send_email_task(ctx, to: str, subject: str, body: str, html_body: str = None):
    """ARQ task: send email with retry."""
    email_service = EmailService()
    success = await email_service.send_email(to, subject, body, html_body)
    if not success:
        raise Exception(f"Failed to send email to {to}")
    return {"sent_to": to, "subject": subject, "timestamp": time.time()}

async def send_verification_email_task(ctx, email: str, code: str):
    """ARQ task: send verification email."""
    email_service = EmailService()
    return await email_service.send_verification_email(email, code)

async def send_alert_email_task(ctx, email: str, alert_data: dict):
    """ARQ task: send guardian alert email."""
    email_service = EmailService()
    return await email_service.send_alert_email(email, alert_data)
```

## File 2: `predict/core/jobs/tasks/fcm_tasks.py`
Same pattern — wrap FCMService calls as ARQ tasks with retry.

## File 3: `predict/core/jobs/tasks/backup_tasks.py`
Implement:
- `async def daily_backup_task(ctx)` — Called by cron at 3 AM
- `async def cleanup_old_backups_task(ctx)` — Delete backups older than 30 days

## File 4: `predict/core/jobs/tasks/cleanup_tasks.py`
Implement:
- `async def gdpr_cleanup_task(ctx)` — Called by cron at 4 AM
  - Delete telemetry > 30 days
  - Delete verification codes > 24 hours
  - Delete expired sessions
  - Log cleanup stats

## File 5: `predict/core/jobs/tasks/pdf_tasks.py`
Implement:
- `async def generate_report_task(ctx, vehicle_id: int, report_type: str, user_id: int)` — Background PDF generation

## File 6: `predict/core/jobs/tasks/parquet_tasks.py`
Implement:
- `async def flush_parquet_buffer_task(ctx)` — Write buffered records to Parquet files
- Uses `predict/core/ai/training/parquet_writer.py`

## Also verify: `predict/core/jobs/worker.py` and `predict/core/jobs/queue.py`
Ensure the worker config includes cron schedules:
```python
cron_jobs = [
    cron(daily_backup_task, hour=3, minute=0),      # 3 AM backup
    cron(gdpr_cleanup_task, hour=4, minute=0),       # 4 AM cleanup
    cron(flush_parquet_buffer_task, hour={0,6,12,18}),  # Every 6 hours
]
```

## Expected output:
```
PHASE 5 COMPLETE - AWAITING REVIEW
Files modified: [list with line counts]
Issues found during self-review: [list]
```

---

# PHASE 6: AI Pipeline

**Goal**: Verify AI modules work together. Fill any stubs. Ensure model loading is singleton.

## Tasks:

### 1. Verify `predict/core/ai/model_loader.py`
Ensure singleton pattern — models load ONCE, shared everywhere:
```python
class ModelLoader:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if ModelLoader._instance is not None:
            raise RuntimeError("Use get_instance()")
        self._models = {}
        self._loaded = False

    def load_all_models(self):
        """Load all AI models once."""
        if self._loaded:
            return
        # Load LSTM, CNN-LSTM, Attention-LSTM, Autoencoder, XGBoost, etc.
        self._loaded = True
```

### 2. Verify `predict/core/ai/model_registry.py`
Ensure it tracks model versions in `models/registry.json`.

### 3. Verify `predict/core/ai/unified_ai_module.py`
This is the CENTRAL AI HUB. Verify:
- It imports and uses all AI sub-modules (LSTM, CNN-LSTM, Attention-LSTM, Autoencoder, FailureEngine, FailureCorrelation, RUL, VehicleBaseline, FeatureEngineering, FleetLearning, RecallMonitor)
- `get_complete_vehicle_intelligence()` aggregates all model outputs
- No fake/hardcoded values (accuracy, confidence, cost savings)

### 4. Verify `predict/core/ai/training/data_pipeline.py`
Ensure it reads training data directly from PostgreSQL via async queries.

### 5. Verify `predict/core/ai/training/parquet_writer.py`
Ensure buffered writes (1000 records or 1 hour, whichever comes first).

### 6. Verify `predict/core/ai/training/auto_retrain.py`
Ensure retraining triggers and logging to `ModelRetrainingEvent` table.

### 7. Verify `predict/core/ai/llm/assistant.py`
Ensure in-process llama.cpp (NOT Flask server). Thread-safe via `asyncio.to_thread`.

### 8. Verify `predict/core/ai/llm/model_config.py`
Ensure Qwen 2.5 and Phi model configurations are correct.

### 9. Verify ALL remaining AI modules:
- `lstm_predictor.py`, `cnn_lstm_model.py`, `attention_lstm.py`, `autoencoder.py`
- `failure_engine.py`, `failure_correlation.py`, `feature_engineering.py`
- `rul_estimation.py`, `vehicle_baseline.py`, `fleet_learning.py`, `recall_monitor.py`

For each: ensure it's a real implementation (not a stub), uses proper logging, no datetime violations.

## Expected output:
```
PHASE 6 COMPLETE - AWAITING REVIEW
Files verified: [list]
Files modified: [list with changes]
Stubs found and filled: [list]
Issues found and fixed: [list]
```

---

# PHASE 6B: AI Bridge (Connect Predictions to LLM)

**Goal**: Make UnifiedAI predictions feed into LLM as context. ALL text output comes from LLM.

## File: `predict/core/ai/ai_bridge.py`

If this file is a stub, implement the full bridge:

```python
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from predict.core.ai.unified_ai_module import UnifiedAIModule
from predict.core.ai.llm.assistant import LLMAssistant
from predict.core.config import get_config

logger = logging.getLogger(__name__)

class AIBridge:
    """
    Connects UnifiedAI predictions with LLM explanations.
    UnifiedAI = the brain (math, predictions, patterns)
    Qwen 2.5 = the voice (explains everything in human words)
    """

    def __init__(self):
        self.config = get_config()
        self.ai_module = UnifiedAIModule()
        self.llm = LLMAssistant()

    async def get_ai_enriched_context(
        self,
        obd_data: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        history: List[Dict[str, Any]],
        dtcs: List[str],
    ) -> str:
        """
        Run full AI analysis and format as LLM context.

        Returns structured text that the LLM can use to give
        specific, data-driven answers.
        """
        # Run AI analysis (CPU-bound)
        intelligence = await asyncio.to_thread(
            self.ai_module.get_complete_vehicle_intelligence,
            obd_data, profile, history, dtcs
        )

        return self._format_for_llm(intelligence)

    async def chat_with_ai_context(
        self,
        user_message: str,
        obd_data: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        history: List[Dict[str, Any]],
        dtcs: List[str],
    ) -> str:
        """
        Answer user question using AI predictions as context.

        1. Run UnifiedAI analysis
        2. Format predictions as LLM context
        3. LLM generates human-readable response
        """
        ai_context = await self.get_ai_enriched_context(
            obd_data, profile, history, dtcs
        )

        system_prompt = (
            "You are PREDICT AI, a vehicle intelligence assistant. "
            "Use the vehicle analysis data provided to give specific, "
            "data-driven answers. Always mention specific numbers, trends, "
            "and timeframes from the analysis. Never give generic answers "
            "when you have specific prediction data."
        )

        full_prompt = f"""VEHICLE AI ANALYSIS (from prediction engine):
{ai_context}

USER QUESTION: {user_message}

INSTRUCTIONS: Use the AI analysis above to give an accurate, specific answer.
Explain WHY using the prediction data. If there are failure risks,
mention them with timeframes. Reference specific sensor values and trends."""

        # Run LLM inference (CPU-bound)
        response = await asyncio.to_thread(
            self.llm.chat, full_prompt, system_prompt
        )

        return response

    def _format_for_llm(self, intelligence: Dict[str, Any]) -> str:
        """Format AI predictions as structured text for LLM context."""
        lines = []

        # Overall health
        health = intelligence.get("overall_health", {})
        lines.append(f"Overall Health Score: {health.get('score', 'N/A')}/100")
        lines.append(f"Health Grade: {health.get('grade', 'N/A')}")
        lines.append(f"Vehicle State: {health.get('state', 'Unknown')}")
        lines.append("")

        # Subsystem scores
        subsystems = intelligence.get("subsystem_scores", {})
        if subsystems:
            lines.append("SUBSYSTEM HEALTH:")
            for name, data in subsystems.items():
                score = data.get("score", 0)
                status = data.get("status", "unknown")
                lines.append(f"  - {name}: {score}% ({status})")
            lines.append("")

        # Failure predictions
        predictions = intelligence.get("failure_predictions", [])
        if predictions:
            lines.append("FAILURE PREDICTIONS:")
            for pred in predictions:
                component = pred.get("component", "unknown")
                probability = pred.get("probability", 0)
                days = pred.get("estimated_days", "unknown")
                lines.append(
                    f"  - {component}: {probability*100:.0f}% probability, "
                    f"~{days} days to failure"
                )
            lines.append("")

        # Active alerts
        alerts = intelligence.get("alerts", [])
        if alerts:
            lines.append("ACTIVE ALERTS:")
            for alert in alerts:
                lines.append(f"  - {alert.get('message', 'Unknown alert')}")
            lines.append("")

        # Correlations
        correlations = intelligence.get("correlations", [])
        if correlations:
            lines.append("SENSOR CORRELATIONS DETECTED:")
            for corr in correlations:
                lines.append(f"  - {corr}")
            lines.append("")

        # Recommendations
        recommendations = intelligence.get("recommendations", [])
        if recommendations:
            lines.append("RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"  {i}. {rec}")

        return "\n".join(lines)
```

## Also update `predict/core/api/v1/ai_chat.py` to use AIBridge
The chat endpoint should call `ai_bridge.chat_with_ai_context()` instead of calling LLM directly.

## Expected output:
```
PHASE 6B COMPLETE - AWAITING REVIEW
Files modified: [list]
```

---

# PHASE 6C: AI Intelligence Enhancements

**Goal**: Wire the 5 new AI modules (explainability, ensemble_voter, causal_graph, survival_analysis, anomaly_detector) into the main prediction pipeline.

## Tasks:

### 1. Verify/implement `predict/core/ai/explainability.py`
- Must use `shap` library
- `explain_prediction(model, features, feature_names)` → top contributing factors
- Works with XGBoost, RandomForest, LightGBM

### 2. Verify/implement `predict/core/ai/ensemble_voter.py`
- Weighted ensemble voting across all models
- Rolling accuracy weights (not static)
- Agreement/disagreement scoring
- Feeds into `uncertainty_estimator.py`

### 3. Verify/implement `predict/core/ai/causal_graph.py`
- Directed acyclic graph of vehicle system relationships
- `find_root_cause(symptoms)` → trace back to root cause
- Pre-defined causal chains:
  - alternator_failing → low_battery + high_load
  - thermostat_stuck → high_coolant
  - vacuum_leak → lean_trim + misfire
  - worn_sparks → misfire + power_loss

### 4. Verify/implement `predict/core/ai/survival_analysis.py`
- Uses `lifelines` library (Weibull fitter)
- `estimate_time_to_failure(degradation_data)` → probability distribution
- Confidence bands at 50%/80%/95%

### 5. Verify/implement `predict/core/ai/anomaly_detector.py`
- Isolation Forest (scikit-learn) for multivariate detection
- Context-aware thresholds (different "normal" per driving state)
- Per-vehicle baselines from `vehicle_baseline.py`

### 6. Wire into `predict/core/ai/unified_ai_module.py`
Add calls to all 5 new modules in `get_complete_vehicle_intelligence()`:
- After ensemble predictions → run explainability
- After risk scoring → run survival analysis
- After sensor analysis → run anomaly detection
- After multi-sensor triggers → run causal graph
- Pass all results to the return dict

### 7. Wire into `predict/core/ai/ai_bridge.py`
Add SHAP values, ensemble agreement, causal findings, and survival estimates to LLM context.

## Expected output:
```
PHASE 6C COMPLETE - AWAITING REVIEW
Files modified: [list]
New integrations added: [list]
```

---

# PHASE 7: Monitoring + Reliability

**Goal**: Complete monitoring infrastructure.

## Tasks:

### 1. Verify/implement `predict/core/monitoring/circuit_breaker.py`
Unified circuit breaker for ALL external services:
```python
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Circuit breaker for external service calls.
    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0

    def allow_request(self) -> bool:
        if self.state == self.CLOSED:
            return True
        elif self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.HALF_OPEN
                logger.info(f"Circuit breaker {self.name}: OPEN → HALF_OPEN")
                return True
            return False
        elif self.state == self.HALF_OPEN:
            return True
        return False

    def record_success(self):
        if self.state == self.HALF_OPEN:
            self.state = self.CLOSED
            self.failure_count = 0
            logger.info(f"Circuit breaker {self.name}: HALF_OPEN → CLOSED")
        self.success_count += 1

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"Circuit breaker {self.name}: CLOSED → OPEN (failures={self.failure_count})")

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }
```

### 2. Verify/implement `predict/core/monitoring/sentry.py`
```python
import logging
from predict.core.config import get_config

logger = logging.getLogger(__name__)

def init_sentry():
    """Initialize Sentry error tracking."""
    config = get_config()
    dsn = getattr(config, 'sentry_dsn', None)
    if not dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
            environment=getattr(config, 'environment', 'production'),
        )
        logger.info("Sentry initialized")
    except ImportError:
        logger.warning("sentry-sdk not installed, error tracking disabled")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry: {e}")
```

### 3. Verify `predict/core/monitoring/health.py`
Ensure it checks: PostgreSQL, Redis, ARQ worker, disk space, AI models loaded.

### 4. Verify `predict/core/monitoring/metrics.py`
Ensure Prometheus-compatible `/metrics` endpoint format.

### 5. Verify `predict/core/security/hashing.py`
Ensure bcrypt primary + SHA-256 fallback for 30-day transition.

### 6. Verify `predict/core/security/secrets_loader.py`
Ensure fail-fast if required secrets are missing.

## Expected output:
```
PHASE 7 COMPLETE - AWAITING REVIEW
Files verified/modified: [list]
```

---

# PHASE 8: Desktop GUI Integration

**Goal**: Verify all desktop files are real implementations using PySide6.

## Tasks:

### 1. Verify `predict/desktop/server_thread.py`
Must run Uvicorn in a QThread:
```python
import logging
from PySide6.QtCore import QThread, Signal
import uvicorn

logger = logging.getLogger(__name__)

class ServerThread(QThread):
    server_started = Signal()
    server_error = Signal(str)

    def __init__(self, host="127.0.0.1", port=8000):
        super().__init__()
        self.host = host
        self.port = port
        self._server = None

    def run(self):
        try:
            config = uvicorn.Config(
                "predict.core.api.app:create_app",
                factory=True,
                host=self.host,
                port=self.port,
                log_level="info",
            )
            self._server = uvicorn.Server(config)
            self.server_started.emit()
            self._server.run()
        except Exception as e:
            logger.error(f"Server error: {e}")
            self.server_error.emit(str(e))

    def stop(self):
        if self._server:
            self._server.should_exit = True
```

### 2. Verify `predict/desktop/main_window.py`
Must be a PySide6 QMainWindow with tab widget containing all tabs.

### 3. Verify `predict/desktop/splash_screen.py`
PySide6 splash screen with loading progress.

### 4. Verify `predict/desktop/theme.py`
Dark theme with colors: #0D1117 background, #C40000 accent, #F0F6FC text.

### 5. Verify `predict/desktop/update_checker.py`
Check for updates (can be basic/placeholder for now).

### 6. Verify ALL tab files in `predict/desktop/tabs/`:
- `live_data.py` — Real-time OBD sensor display
- `connection.py` — OBD adapter connection management
- `dtc.py` — DTC code viewer
- `reports.py` — Report generation
- `ai_training.py` — AI training controls
- `chat.py` — AI chat interface (should use AIBridge eventually)
- `subscription.py` — Subscription management
- `cloud_sync.py` — Cloud sync status
- `maintenance.py` — Maintenance tracking
- `dashboard_monitor.py` — System monitoring (CPU, memory, req/s)

Each tab must:
- Use `from PySide6.QtWidgets import ...`
- NOT use `from PyQt5` or `from PyQt6`
- Have a proper `__init__` that creates the UI
- Use logging, not print()

### 7. Verify `predict/desktop/widgets/__init__.py`
Add any custom widgets (gauges, cards, charts) if needed.

## Expected output:
```
PHASE 8 COMPLETE - AWAITING REVIEW
Files verified/modified: [list]
PySide6 compliance: PASS/FAIL
```

---

# PHASE 9: Data Migration Script

**Goal**: Create the SQLite → PostgreSQL migration script.

## Create: `scripts/migrate_sqlite_to_pg.py`

```python
"""
One-time migration: SQLite → PostgreSQL.

Migrates data from ALL 3 SQLite databases:
1. server_database.db (users, subscriptions, API keys)
2. data/vehicle_data.db (OBD data, 40+ tables)
3. PredictData/vehicle_profiles.db (vehicle profiles)

Usage: python scripts/migrate_sqlite_to_pg.py --sqlite-dir /path/to/sqlite --pg-url postgresql+asyncpg://...
"""
import asyncio
import logging
import time
import sqlite3
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

class SQLiteToPGMigrator:
    def __init__(self, sqlite_dir: str, pg_url: str):
        self.sqlite_dir = Path(sqlite_dir)
        self.pg_url = pg_url
        self.stats = {"tables": 0, "rows": 0, "errors": 0}

    async def migrate_all(self):
        """Migrate all 3 SQLite databases."""
        engine = create_async_engine(self.pg_url)
        async_session = sessionmaker(engine, class_=AsyncSession)

        # Map of SQLite DB → tables to migrate
        databases = {
            "server_database.db": [
                "users", "api_keys", "verification_codes",
                "subscriptions", "audit_log",
            ],
            "vehicle_data.db": [
                "vehicle_data", "obd_records", "telemetry_records",
                "dtc_history", "trips", "trip_events",
                "predictions", "service_records",
            ],
            "vehicle_profiles.db": [
                "vehicle_profiles",
            ],
        }

        for db_name, tables in databases.items():
            db_path = self.sqlite_dir / db_name
            if not db_path.exists():
                logger.warning(f"SQLite DB not found: {db_path}")
                continue

            logger.info(f"Migrating {db_name}...")
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            for table in tables:
                await self._migrate_table(conn, table, async_session)

            conn.close()

        await engine.dispose()
        return self.stats

    async def _migrate_table(self, sqlite_conn, table_name, async_session):
        """Migrate a single table."""
        try:
            cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()

            if not rows:
                logger.info(f"  {table_name}: 0 rows (skipped)")
                return

            # Bulk insert via async session
            async with async_session() as session:
                # Build INSERT statements based on column names
                columns = [desc[0] for desc in cursor.description]
                for row in rows:
                    # Convert Row to dict, handle type conversions
                    data = dict(row)
                    # Insert into PG table
                    # ... (table-specific mapping)

                await session.commit()

            count = len(rows)
            self.stats["rows"] += count
            self.stats["tables"] += 1
            logger.info(f"  {table_name}: {count} rows migrated")

        except Exception as e:
            self.stats["errors"] += 1
            logger.error(f"  {table_name}: FAILED - {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-dir", required=True)
    parser.add_argument("--pg-url", required=True)
    args = parser.parse_args()

    asyncio.run(SQLiteToPGMigrator(args.sqlite_dir, args.pg_url).migrate_all())
```

Implement the full migration with:
- Table-specific column mapping (old names → new names)
- Type conversions (string dates → float timestamps where needed)
- Duplicate detection (skip if already exists)
- Progress reporting
- Row count verification

## Also create: `scripts/generate_api_key.py`
Admin utility to generate API keys:
```python
"""Generate an admin API key."""
import asyncio
import secrets
from predict.core.security.hashing import hash_api_key
# ... generate key, hash it, insert into database
```

## Expected output:
```
PHASE 9 COMPLETE - AWAITING REVIEW
Files created: [list]
```

---

# PHASE 10: Headless Mode + Windows Service

**Goal**: Verify headless mode works. Create Windows service installer.

## Tasks:

### 1. Verify `predict/headless.py`
Ensure it starts: Uvicorn + ARQ worker + health monitor + Cloudflare tunnel (optional).

### 2. Verify `predict/__main__.py`
Ensure `--headless` and `--desktop` flags work correctly.

### 3. Create: `scripts/install_service.py`
```python
"""
Install PREDICT as a Windows service using NSSM.

Usage:
    python scripts/install_service.py install
    python scripts/install_service.py remove
    python scripts/install_service.py start
    python scripts/install_service.py stop
"""
import subprocess
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

NSSM_PATH = "nssm.exe"  # Must be in PATH
SERVICE_NAME = "PredictServer"

def install_service():
    python_exe = sys.executable
    script = str(Path(__file__).parent.parent / "predict" / "__main__.py")

    subprocess.run([
        NSSM_PATH, "install", SERVICE_NAME,
        python_exe, f"-m predict --headless"
    ], check=True)

    # Set service properties
    subprocess.run([NSSM_PATH, "set", SERVICE_NAME, "DisplayName", "PREDICT Vehicle Intelligence Server"], check=True)
    subprocess.run([NSSM_PATH, "set", SERVICE_NAME, "Description", "PREDICT AI-powered vehicle diagnostics server"], check=True)
    subprocess.run([NSSM_PATH, "set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"], check=True)
    subprocess.run([NSSM_PATH, "set", SERVICE_NAME, "AppStdout", str(Path("data/logs/service_stdout.log"))], check=True)
    subprocess.run([NSSM_PATH, "set", SERVICE_NAME, "AppStderr", str(Path("data/logs/service_stderr.log"))], check=True)

    logger.info(f"Service {SERVICE_NAME} installed successfully")

def remove_service():
    subprocess.run([NSSM_PATH, "remove", SERVICE_NAME, "confirm"], check=True)
    logger.info(f"Service {SERVICE_NAME} removed")

def start_service():
    subprocess.run([NSSM_PATH, "start", SERVICE_NAME], check=True)

def stop_service():
    subprocess.run([NSSM_PATH, "stop", SERVICE_NAME], check=True)

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    {"install": install_service, "remove": remove_service, "start": start_service, "stop": stop_service}[action]()
```

## Expected output:
```
PHASE 10 COMPLETE - AWAITING REVIEW
Files verified/created: [list]
```

---

# PHASE 11: CI/CD + Docker

**Goal**: Create GitHub Actions workflows and Docker configuration.

## Create: `.github/workflows/ci.yml`
```yaml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install ruff
      - run: ruff check predict/

  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: predict_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v --tb=short
        env:
          DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/predict_test
          REDIS_URL: redis://localhost:6379
```

## Create: `.github/workflows/security.yml`
```yaml
name: Security
on:
  schedule:
    - cron: "0 0 * * 1"  # Weekly Monday
  push:
    branches: [main]

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install pip-audit
      - run: pip-audit -r requirements.txt
```

## Create: `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY predict/ predict/
COPY alembic.ini .
COPY .env.example .env

# Run migrations and start server
CMD ["python", "-m", "predict", "--headless"]
```

## Create: `docker-compose.yml`
```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://predict:predict@postgres:5432/predict
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: predict
      POSTGRES_USER: predict
      POSTGRES_PASSWORD: predict
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U predict"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

## Create: `tests/conftest.py`
```python
"""Shared test fixtures."""
import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from predict.core.db.base import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def db_session(engine):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
```

## Expected output:
```
PHASE 11 COMPLETE - AWAITING REVIEW
Files created: [list]
```

---

# PHASE 12: Hardening + Final Verification

**Goal**: Security hardening, configuration validation, and documentation.

## Tasks:

### 1. Verify CORS configuration
`predict/core/middleware/cors.py` must lock to specific origins:
```python
ALLOWED_ORIGINS = [
    "https://predict.previlium.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
```

### 2. Verify rate limiting is strict
Registration: 5/hour per IP. API calls: Based on tier. Admin: 100/minute.

### 3. Verify SQL injection protection
ALL database queries MUST use SQLAlchemy ORM (parameterized). NO raw SQL strings. Search all files for raw SQL and fix.

### 4. Verify XSS headers
Add security headers middleware:
```python
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response
```

### 5. Verify all secrets are in .env
Check that NO secrets are hardcoded anywhere. ALL must come from environment variables or .env file.

### 6. Update `.env.example` with ALL required variables
```
# Database
DATABASE_URL=postgresql+asyncpg://predict:password@localhost:5432/predict

# Redis
REDIS_URL=redis://localhost:6379

# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# Fatora
FATORA_API_KEY=your-fatora-key
FATORA_WEBHOOK_SECRET=your-webhook-secret

# Security
JWT_SECRET_KEY=generate-a-random-secret
API_KEY_SALT=generate-a-random-salt

# Sentry (optional)
SENTRY_DSN=https://your-sentry-dsn

# LLM
LLM_MODEL_PATH=models/gguf/qwen2.5-3b-instruct-q4_k_m.gguf

# Cloudflare Tunnel (optional)
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token
```

### 7. Verify `pyproject.toml` has ALL dependencies
Check that every import used in the codebase has a corresponding dependency in pyproject.toml.

### 8. Verify `requirements.txt` matches pyproject.toml
Pin all versions.

### 9. Create basic test files
Create at least:
- `tests/test_api/test_health.py` — Test health endpoints
- `tests/test_api/test_auth.py` — Test auth flow
- `tests/test_services/test_auth_service.py` — Test auth service
- `tests/test_db/test_repositories.py` — Test base repository CRUD

### 10. Final architecture scan
Search ALL files for:
- `datetime.now()` or `datetime.utcnow()` → MUST be zero
- `print(` → MUST be zero (except in scripts/)
- `Column(` → MUST be zero (only `mapped_column()`)
- `from PyQt` → MUST be zero
- Hardcoded paths `C:\` or `/home/` → MUST be zero
- `TODO` or `FIXME` → List all remaining stubs

## Expected output:
```
PHASE 12 COMPLETE - ALL PHASES FINISHED
Files created/modified: [list]
Architecture violations found: [count]
Architecture violations fixed: [count]
Remaining TODOs: [list]
Total files in project: [count]
```

---

# REMINDER: STOP AFTER EACH PHASE

After completing each phase:
1. Self-review EVERY file for architecture violations
2. List ALL files created/modified with line counts
3. Print **"PHASE X COMPLETE - AWAITING REVIEW"**
4. **STOP AND WAIT** for review approval before proceeding

DO NOT skip phases. DO NOT combine phases. DO NOT proceed without explicit "PROCEED TO PHASE X" instruction.
