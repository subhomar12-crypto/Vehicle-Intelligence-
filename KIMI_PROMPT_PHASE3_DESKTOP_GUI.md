# KIMI PROMPT: Phase 3 - Desktop GUI (6 Tabs, Fully Wired)

## Your Role
You are implementing the PREDICT Desktop GUI. This replaces the current placeholder 3-tab window with a fully-wired 6-tab admin interface. Every button, table, and chart makes real HTTP calls to the embedded FastAPI server (localhost:8000). Phase 1 (server endpoint fixes) and Phase 2 (server enhancements) are already complete.

## Project Location
`C:\D Drive\Predict\`

## ARCHITECTURE RULES (MUST FOLLOW - NO EXCEPTIONS)
1. `time.time()` for ALL timestamps (NO `datetime.now()` or `datetime.utcnow()`)
2. ALL imports at top of file (NO inline imports inside functions)
3. **PySide6 ONLY** (NO PyQt5, NO PyQt6) - import from `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`
4. `logging.getLogger(__name__)` (NO `print()`)
5. `get_config()` for paths (NO hardcoded `C:\...` paths)
6. `json.loads()` for parsing
7. `requests` library for HTTP (NOT httpx, NOT aiohttp)
8. `QThread` + `Signal` for background work (NO asyncio in GUI thread)
9. Use `PredictTheme` colors from `predict/desktop/theme.py` (do NOT hardcode color values)

## EXISTING CODE YOU MUST USE

### Theme (`predict/desktop/theme.py`)
```python
from predict.desktop.theme import PredictTheme, get_table_stylesheet, get_card_stylesheet

# Colors available:
PredictTheme.BG_PRIMARY     # "#0D1117" - main background
PredictTheme.BG_SECONDARY   # "#21262D" - secondary bg
PredictTheme.CARD_BG        # "#1E2329" - card background
PredictTheme.CARD_BG_HOVER  # "#2D333B"
PredictTheme.TEXT_PRIMARY    # "#F0F6FC" - white text
PredictTheme.TEXT_SECONDARY  # "#8B949E" - gray text
PredictTheme.TEXT_MUTED      # "#5F6368"
PredictTheme.BORDER          # "#30363D"
PredictTheme.PRIMARY         # "#C40000" - PREDICT red
PredictTheme.SUCCESS         # "#198754" - green
PredictTheme.WARNING         # "#F59E0B" - amber
PredictTheme.DANGER          # "#DC3545" - red
PredictTheme.INFO            # "#0D6EFD" - blue
```

### ServerManager (`predict/desktop/server_thread.py`)
```python
from predict.desktop.server_thread import get_server_manager

server_manager = get_server_manager()
server_manager.server.base_url  # "http://127.0.0.1:8000"
server_manager.is_running       # bool
server_manager.start_server(host, port)
server_manager.stop_server()
```

### Config (`predict/core/config.py`)
```python
from predict.core.config import get_config
config = get_config()
config.LOGS_DIR   # Path to logs directory
config.DATA_DIR   # Path to data directory
config.ADMIN_API_KEY  # Admin API key (if it exists on config)
```

---

## FILES TO CREATE (11 total: 9 new + 2 modified)

---

## FILE 1: CREATE `predict/desktop/api_client.py`

Centralized HTTP client. All tabs use this instead of making direct `requests` calls.

```python
"""
Centralized HTTP API client for PREDICT Desktop.

All tabs use this client to communicate with the embedded FastAPI server.
Runs synchronous requests (called from QThread workers, never from GUI thread).
"""

import json
import logging
import time
from typing import Optional, Dict, Any, List

import requests

from predict.core.config import get_config

logger = logging.getLogger(__name__)


class PredictAPIClient:
    """HTTP client for the embedded PREDICT server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self):
        """Set admin API key header."""
        config = get_config()
        api_key = getattr(config, "ADMIN_API_KEY", None)
        if api_key:
            self.session.headers["X-API-Key"] = api_key
        else:
            logger.warning("No ADMIN_API_KEY configured - API calls may fail")

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request and return parsed JSON."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", 30)
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {"success": True}
        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass
            logger.error(f"HTTP {e.response.status_code} on {method} {path}: {error_data}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection failed: {url}")
            raise
        except Exception as e:
            logger.error(f"Request failed: {method} {path}: {e}")
            raise

    def get(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> Dict[str, Any]:
        return self._request("DELETE", path, **kwargs)

    def get_raw(self, path: str, **kwargs) -> requests.Response:
        """Return raw response (for file downloads)."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", 60)
        return self.session.get(url, **kwargs)

    # =========================================================================
    # ADMIN USERS
    # =========================================================================

    def search_users(self, query: str = "", limit: int = 50, offset: int = 0) -> Dict:
        params = {"limit": limit, "offset": offset}
        if query:
            params["search"] = query
        return self.get("/admin/users", params=params)

    def get_user(self, user_id: int) -> Dict:
        return self.get(f"/admin/users/{user_id}")

    def change_user_tier(self, user_id: int, tier: str) -> Dict:
        return self.put(f"/admin/users/{user_id}/tier", json={"tier": tier})

    def update_user(self, user_id: int, **fields) -> Dict:
        return self.patch(f"/admin/users/{user_id}", json=fields)

    def delete_user(self, user_id: int) -> Dict:
        return self.delete(f"/admin/users/{user_id}")

    def get_system_stats(self) -> Dict:
        return self.get("/admin/stats")

    def get_audit_log(self, limit: int = 100) -> Dict:
        return self.get("/admin/audit-log", params={"limit": limit})

    def update_entitlements(self, user_id: int, entitlements: List[Dict]) -> Dict:
        return self.put(f"/admin/users/{user_id}/entitlements",
                        json={"entitlements": entitlements})

    # =========================================================================
    # VEHICLES
    # =========================================================================

    def get_user_vehicles(self, user_id: int) -> Dict:
        return self.get(f"/profile/vehicles", params={"user_id": user_id})

    def get_vehicle(self, vehicle_id: int) -> Dict:
        return self.get(f"/profile/vehicles/{vehicle_id}")

    def create_vehicle(self, **fields) -> Dict:
        return self.post("/profile/vehicles", json=fields)

    def update_vehicle(self, vehicle_id: int, **fields) -> Dict:
        return self.put(f"/profile/vehicles/{vehicle_id}", json=fields)

    def delete_vehicle(self, vehicle_id: int) -> Dict:
        return self.delete(f"/profile/vehicles/{vehicle_id}")

    # =========================================================================
    # SERVICE RECORDS
    # =========================================================================

    def get_service_records(self, vehicle_id: int) -> Dict:
        return self.get(f"/profile/vehicles/{vehicle_id}/service-records")

    # =========================================================================
    # OBD DATA
    # =========================================================================

    def get_latest_vehicle_data(self, vehicle_id: int) -> Dict:
        return self.get(f"/obd/vehicle/{vehicle_id}/data/latest")

    def get_vehicle_data_history(self, vehicle_id: int, limit: int = 100) -> Dict:
        return self.get(f"/obd/vehicle/{vehicle_id}/data/history",
                        params={"limit": limit})

    def get_vehicle_stats(self, vehicle_id: int) -> Dict:
        return self.get(f"/obd/vehicle/{vehicle_id}/stats")

    # =========================================================================
    # DTC
    # =========================================================================

    def get_dtc_history(self, vehicle_id: int) -> Dict:
        return self.get(f"/dtc/{vehicle_id}")

    def get_active_dtcs(self, vehicle_id: int) -> Dict:
        return self.get(f"/dtc/{vehicle_id}/active")

    def lookup_dtc(self, code: str) -> Dict:
        return self.get(f"/dtc/lookup/{code}")

    def clear_dtc(self, vehicle_id: int, dtc_id: int) -> Dict:
        return self.delete(f"/dtc/{vehicle_id}/{dtc_id}")

    def get_dtc_summary(self, vehicle_id: int) -> Dict:
        return self.get(f"/dtc/{vehicle_id}/summary")

    # =========================================================================
    # PREDICTIONS
    # =========================================================================

    def get_predictions(self, vehicle_id: int) -> Dict:
        return self.get(f"/predictions/{vehicle_id}")

    def get_prediction_history(self, vehicle_id: int, limit: int = 50) -> Dict:
        return self.get(f"/predictions/{vehicle_id}/history",
                        params={"limit": limit})

    # =========================================================================
    # AI CHAT
    # =========================================================================

    def chat_with_ai(self, message: str, profile_id: int = 0,
                     context: str = "") -> Dict:
        payload = {"message": message}
        if profile_id:
            payload["profile_id"] = profile_id
        if context:
            payload["context"] = context
        return self.post("/ai/chat", json=payload)

    def explain_dtc(self, code: str) -> Dict:
        return self.post(f"/ai/explain-dtc/{code}")

    def get_ai_status(self) -> Dict:
        return self.get("/ai/status")

    # =========================================================================
    # REPORTS
    # =========================================================================

    def generate_report(self, vehicle_id: int, report_type: str,
                        include_llm: bool = False) -> Dict:
        return self.post("/report/generate", json={
            "vehicle_id": vehicle_id,
            "report_type": report_type,
            "include_llm_explanations": include_llm,
        })

    def get_report_status(self, report_id: int) -> Dict:
        return self.get(f"/report/status/{report_id}")

    def download_report(self, report_id: int) -> requests.Response:
        return self.get_raw(f"/report/download/{report_id}")

    def get_report_history(self, limit: int = 50) -> Dict:
        return self.get("/report/history", params={"limit": limit})

    def delete_report(self, report_id: int) -> Dict:
        return self.delete(f"/report/{report_id}")

    # =========================================================================
    # HEALTH
    # =========================================================================

    def health_check(self) -> Dict:
        return self.get("/health")

    def detailed_health(self) -> Dict:
        return self.get("/health/detailed")

    def readiness(self) -> Dict:
        return self.get("/health/ready")

    # =========================================================================
    # ADMIN OPS
    # =========================================================================

    def clear_cache(self) -> Dict:
        return self.post("/admin/maintenance/clear-cache")

    def trigger_backup(self) -> Dict:
        return self.post("/admin/backup")

    def get_job_status(self) -> Dict:
        return self.get("/admin/jobs/status")

    # =========================================================================
    # TIERS
    # =========================================================================

    def list_tiers(self) -> Dict:
        return self.get("/tiers/")

    def get_tier_features(self) -> Dict:
        return self.get("/tiers/features")

    # =========================================================================
    # DRIVING
    # =========================================================================

    def get_driving_score(self, vehicle_id: int) -> Dict:
        return self.get(f"/driver/score/{vehicle_id}")
```

This is the COMPLETE file. Create it exactly as shown.

---

## FILE 2: CREATE `predict/desktop/workers.py`

Background workers for non-blocking API calls + WebSocket listener.

```python
"""
Background workers for PREDICT Desktop.

Provides QThread-based workers for non-blocking API calls
and WebSocket real-time event listening.
"""

import json
import logging
import time
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class APIWorker(QThread):
    """One-shot background worker for API calls."""

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            result = self._func(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"APIWorker error: {e}")
            self.error.emit(str(e))


class PollingWorker(QThread):
    """Repeating poll worker for periodic API calls."""

    data_received = Signal(object)
    error = Signal(str)

    def __init__(self, func: Callable, interval_ms: int = 5000):
        super().__init__()
        self._func = func
        self._interval_ms = interval_ms
        self._running = True

    def run(self):
        while self._running:
            try:
                result = self._func()
                self.data_received.emit(result)
            except Exception as e:
                self.error.emit(str(e))

            # Interruptible sleep
            for _ in range(self._interval_ms // 100):
                if not self._running:
                    break
                self.msleep(100)

    def stop(self):
        self._running = False


class WebSocketListener(QThread):
    """Listens to server WebSocket for real-time events."""

    vehicle_update = Signal(dict)
    user_change = Signal(dict)
    alert = Signal(dict)
    connected = Signal()
    disconnected = Signal()

    def __init__(self, ws_url: str):
        super().__init__()
        self._ws_url = ws_url
        self._running = True

    def run(self):
        try:
            import websocket
        except ImportError:
            logger.warning(
                "websocket-client not installed - real-time updates disabled"
            )
            return

        while self._running:
            try:
                ws = websocket.WebSocket()
                ws.settimeout(5)
                ws.connect(self._ws_url)
                self.connected.emit()
                logger.info(f"WebSocket connected to {self._ws_url}")

                while self._running:
                    try:
                        raw = ws.recv()
                        if not raw:
                            continue
                        data = json.loads(raw)
                        msg_type = data.get("type", "")

                        if msg_type == "VEHICLE_UPDATE":
                            self.vehicle_update.emit(data)
                        elif msg_type == "USER_CHANGE":
                            self.user_change.emit(data)
                        elif msg_type == "ALERT":
                            self.alert.emit(data)
                        else:
                            logger.debug(f"Unknown WS message type: {msg_type}")

                    except websocket.WebSocketTimeoutException:
                        continue
                    except websocket.WebSocketConnectionClosedException:
                        logger.info("WebSocket connection closed")
                        break
                    except Exception as e:
                        logger.error(f"WebSocket receive error: {e}")
                        break

                ws.close()

            except Exception as e:
                logger.debug(f"WebSocket connect error: {e}")

            self.disconnected.emit()

            # Reconnect delay (interruptible)
            for _ in range(50):  # 5 seconds
                if not self._running:
                    return
                self.msleep(100)

    def stop(self):
        self._running = False
```

NOTE: The `import websocket` inside `run()` is an intentional exception to the "no inline imports" rule because `websocket-client` is an optional dependency. If the user doesn't have it installed, the rest of the app still works.

---

## FILE 3: CREATE `predict/desktop/tabs/profile_tab.py`

Tab 1: Profile Management - user search, list, double-click opens detail.

### Layout:
- **Top**: QHBoxLayout with QLineEdit (placeholder "Search by name, email, or plate...") + QPushButton "Search" + QPushButton "Refresh"
- **Middle**: QTableWidget with columns: Name, Email, Plate, Tier, Status, Last Seen
- **Bottom**: QHBoxLayout with QLabel "Showing X users" + stretch + QPushButton "Prev" + QPushButton "Next"

### Behavior:
- Constructor: `__init__(self, api_client, ws_listener=None)`
- On first show: load all users via `APIWorker(self.api.search_users, "")`
- Search button clicked / Enter pressed: `APIWorker(self.api.search_users, query_text)`
- Refresh button: reload current query
- Double-click row: get user_id from `item.data(Qt.UserRole)`, open `UserDetailDialog(user_id, self.api)`
- Tier column: set item background color based on tier:
  - "free" -> `PredictTheme.TEXT_MUTED`
  - "pro" -> `PredictTheme.SUCCESS`
  - "premium" -> `PredictTheme.WARNING`
  - "admin" -> `PredictTheme.DANGER`
- "Last Seen" column: show relative time using `time.time() - timestamp`
  - < 60s: "Just now"
  - < 3600: "X min ago"
  - < 86400: "X hours ago"
  - else: "X days ago"
- Pagination: `self._offset` and `self._limit = 50`, Prev/Next enable/disable

### WebSocket integration:
- If `ws_listener` provided: connect `ws_listener.user_change` signal to refresh method

### Table setup:
```python
table = QTableWidget()
table.setColumnCount(6)
table.setHorizontalHeaderLabels(["Name", "Email", "Plate", "Tier", "Status", "Last Seen"])
table.setSelectionBehavior(QTableWidget.SelectRows)
table.setSelectionMode(QTableWidget.SingleSelection)
table.setEditTriggers(QTableWidget.NoEditTriggers)
table.setAlternatingRowColors(True)
table.horizontalHeader().setStretchLastSection(True)
table.setStyleSheet(get_table_stylesheet())
table.cellDoubleClicked.connect(self._on_row_double_clicked)
```

### How to store user_id per row:
```python
item = QTableWidgetItem(user["name"])
item.setData(Qt.UserRole, user["id"])  # Store user_id
table.setItem(row, 0, item)
```

---

## FILE 4: CREATE `predict/desktop/tabs/user_detail_dialog.py`

QDialog (900x700) opened when double-clicking a user in ProfileTab.

Constructor: `__init__(self, user_id: int, api_client: PredictAPIClient, parent=None)`

### Contains QTabWidget with 6 sub-tabs:

**Sub-tab 1: User Info**
- QFormLayout with QLabel pairs (field name: value)
- Fields: Name, Email, Phone, Role, Status, Registered, Last Login
- Vehicle info section: Make, Model, Year, Plate
- "Edit" QPushButton toggles labels to QLineEdit for editable fields
- "Save" QPushButton calls `APIWorker(self.api.update_user, user_id, **changed_fields)`
- Load data: `APIWorker(self.api.get_user, user_id)` on dialog open

**Sub-tab 2: Vehicles & Drivers**
- Top: Vehicles QTableWidget (Make/Model, Year, Plate, Last Seen) + "Add Vehicle" button
  - Delete button per row via QPushButton in table cell
- Bottom: Drivers QTableWidget (Name, Email, Role) - read-only placeholder
- Load: `APIWorker(self.api.get_user_vehicles, user_id)`

**Sub-tab 3: Tier Management**
- Current tier: large QLabel with colored background
- QComboBox with: free, pro, premium, admin
- Features table: QTableWidget (Feature | Current Limit | After Change)
  - Rows: Vehicles, DTC Checks, Predictions/day, LLM Chat/day, PDFs/week, Guardian, Fleet, History
  - "After Change" column updates when combo selection changes
- "Apply Tier Change" QPushButton -> `APIWorker(self.api.change_user_tier, user_id, tier)`
- Per-user overrides section:
  - QTableWidget: Feature | Tier Default | Custom Override | Actions
  - "Set Override" QPushButton per row -> input dialog for custom value
  - "Reset" QPushButton per row -> remove override
  - Uses `api.update_entitlements(user_id, entitlements_list)`

Tier limits reference (for populating the features table):
```python
TIER_LIMITS = {
    "free": {"vehicles": 1, "dtc_checks": 2, "predictions_day": 0,
             "llm_chat_day": 0, "pdfs_week": 0, "guardian": False,
             "fleet": False, "history_days": 7},
    "pro": {"vehicles": 1, "dtc_checks": -1, "predictions_day": 2,
            "llm_chat_day": 15, "pdfs_week": 1, "guardian": False,
            "fleet": False, "history_days": 90},
    "premium": {"vehicles": 4, "dtc_checks": -1, "predictions_day": 20,
                "llm_chat_day": 100, "pdfs_week": 8, "guardian": True,
                "fleet": False, "history_days": 365},
    "admin": {"vehicles": -1, "dtc_checks": -1, "predictions_day": -1,
              "llm_chat_day": -1, "pdfs_week": -1, "guardian": True,
              "fleet": True, "history_days": -1},
}
# -1 means unlimited
```

**Sub-tab 4: Service History**
- Vehicle selector: QComboBox (populated from user's vehicles)
- Stats cards: QHBoxLayout with 3 QGroupBox cards (Total Services, Last Service, Total Cost)
- Service records: QTableWidget (Date, Type, Component, Cost, Mileage)
- OBD snapshot: QGroupBox with QGridLayout showing key-value pairs
  - RPM, Speed, Coolant Temp, Battery Voltage, Engine Load, Throttle
- Load on vehicle change: `api.get_service_records(vid)`, `api.get_latest_vehicle_data(vid)`

**Sub-tab 5: Billing** (read-only)
- QTableWidget for payment history
- If API returns 404: show QLabel "No billing data available"
- Wrap API call in try/except

**Sub-tab 6: Fleet Info** (read-only)
- Fleet role QLabel + fleet vehicles QTableWidget
- If API returns 404: show QLabel "User is not part of a fleet"

### ALL data loading uses APIWorker. Show "Loading..." label while waiting.

---

## FILE 5: CREATE `predict/desktop/tabs/server_ops_tab.py`

Tab 2: Server & Operations.

Constructor: `__init__(self, api_client: PredictAPIClient)`

### Layout: QScrollArea wrapping QVBoxLayout with 4 sections:

**Section 1: Server Controls** (QGroupBox titled "Server Controls")
- QHBoxLayout: Start button + Stop button + Restart button + Spacer + Status indicator
- Status indicator: QLabel with colored text ("Running" green / "Stopped" red)
- Uptime: QLabel showing "Uptime: Xh Xm"
- Uses `get_server_manager()` directly
- Start/Stop buttons: call server_manager methods
- Status updates via QTimer every 2 seconds

**Section 2: Health Metrics** (QGroupBox titled "Health Metrics")
- QHBoxLayout with 4 metric cards (each is QGroupBox):
  - Card layout: large number QLabel (24pt) + description QLabel (10pt)
  - CPU: from health response
  - Memory: from health response
  - Requests: from health response
  - Connections: from health response
- PollingWorker(api.detailed_health, interval_ms=5000)
- Color the number label: green if < 70%, `PredictTheme.WARNING` if 70-90%, `PredictTheme.DANGER` if > 90%

**Section 3: Services Status** (QGroupBox titled "Services")
- QTableWidget: Service | Status | Details
- 5 rows: PostgreSQL, Redis, LLM Engine, ARQ Workers, Cloudflare
- Status column: text with color (green "Connected", red "Disconnected", yellow "Degraded")
- Refresh via same PollingWorker as health (parse different fields from same response)
- LLM status: from `api.get_ai_status()` (separate call)

**Section 4: Server Logs** (QGroupBox titled "Logs")
- Filter: QComboBox ("ALL", "ERROR", "WARNING", "INFO", "DEBUG") + "Clear" button
- QPlainTextEdit: read-only, monospace font ("Consolas" or "Courier New"), max 1000 lines
- Dark background (`PredictTheme.PANEL_BG`), light text
- Auto-tail: QTimer every 2 seconds reads new lines from log file
- Implementation:
  ```python
  self._log_file = get_config().LOGS_DIR / "desktop.log"
  self._last_pos = 0

  def _read_new_logs(self):
      if not self._log_file.exists():
          return
      with open(self._log_file, "r", encoding="utf-8", errors="replace") as f:
          f.seek(self._last_pos)
          new_lines = f.readlines()
          self._last_pos = f.tell()
      for line in new_lines:
          # Apply filter
          if self._log_filter != "ALL" and self._log_filter not in line:
              continue
          self._log_display.appendPlainText(line.rstrip())
      # Trim if too many lines
      if self._log_display.blockCount() > 1000:
          # Remove oldest lines
          cursor = self._log_display.textCursor()
          cursor.movePosition(cursor.MoveOperation.Start)
          for _ in range(self._log_display.blockCount() - 1000):
              cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
          cursor.removeSelectedText()
  ```

---

## FILE 6: CREATE `predict/desktop/tabs/ai_llm_tab.py`

Tab 3: AI & LLM Panel.

Constructor: `__init__(self, api_client: PredictAPIClient)`

### QTabWidget with 2 sub-tabs:

**Sub-tab 1: LLM Chat**

Layout (QVBoxLayout):
- Status bar: QHBoxLayout with QLabel "Qwen 2.5-7B" + status dot QLabel (colored circle via CSS)
- Chat display: QTextEdit (read-only, accepts rich text)
  - User messages: right-aligned div with red background (#C40000)
  - AI responses: left-aligned div with card background
  - HTML template per message:
    ```python
    user_html = f'<div style="text-align:right;margin:8px 0;">'
                f'<span style="background:{PredictTheme.PRIMARY};color:white;'
                f'padding:8px 12px;border-radius:12px;display:inline-block;'
                f'max-width:70%;">{message}</span></div>'

    ai_html = f'<div style="text-align:left;margin:8px 0;">'
              f'<span style="background:{PredictTheme.CARD_BG};color:{PredictTheme.TEXT_PRIMARY};'
              f'padding:8px 12px;border-radius:12px;display:inline-block;'
              f'max-width:70%;">{response}</span></div>'
    ```
- Input: QHBoxLayout with QLineEdit + QPushButton "Send"
- Connect QLineEdit.returnPressed to send

Chat flow:
1. User types message, clicks Send
2. Disable input, show "Thinking..." in chat
3. Parse message for data lookups (in APIWorker):
   - Plate regex: `r"[A-Z]{1,3}\s?\d{1,4}"` -> search user
   - DTC regex: `r"[PBCU]\d{4}"` -> explain DTC
   - Keywords "predict", "health", "battery" -> get predictions
4. Build context string from API results
5. Send to `api.chat_with_ai(message, profile_id, context)` via APIWorker
6. Display response, re-enable input

**Sub-tab 2: AI Training Control**

Layout (QVBoxLayout):
- Schedule (QGroupBox "Training Schedule"):
  - QFormLayout: "Start Time" QTimeEdit + "End Time" QTimeEdit
  - "Auto-train enabled" QCheckBox
  - "Save Schedule" QPushButton
  - Reads from / writes to: `get_config().DATA_DIR / "ai_schedule.json"`
- Status (QGroupBox "Training Status"):
  - State: QLabel (large, colored: green "Idle", yellow "Training", red "Error")
  - Progress: QProgressBar
  - Metrics: QGridLayout with Loss, Accuracy, Epoch, ETA labels
  - Updated from `api.get_ai_status()` via PollingWorker (every 5s)
- Controls: QHBoxLayout with "Start Training Now" + "Stop Training" buttons
- History: QTableWidget (Date, Duration, Accuracy, Loss)

---

## FILE 7: CREATE `predict/desktop/tabs/pdf_tab.py`

Tab 4: PDF Creating/Monitoring.

Constructor: `__init__(self, api_client: PredictAPIClient)`

### Top Section: Generate New Report (QGroupBox "Generate Report")
- Owner search: QHBoxLayout with QLineEdit + "Search" QPushButton
  - Results populate QComboBox below (shows "Name (email)")
  - Search via `APIWorker(api.search_users, query)`
- Vehicle list: QListWidget with checkable items
  - Populated when owner selected from combo
  - Load via `APIWorker(api.get_user_vehicles, user_id)`
- Report type: QComboBox ("Full Diagnostic", "Maintenance", "Trip Summary", "Invoice")
- Options: QHBoxLayout with QRadioButton "Combined" + QRadioButton "Separate" + QCheckBox "Include LLM"
- Generate: QPushButton (objectName="primary" for red styling) + QProgressBar (hidden initially)

### Generate flow:
1. Click Generate
2. Validate: owner selected, at least 1 vehicle checked
3. For each checked vehicle: `APIWorker(api.generate_report, vid, type, llm_flag)`
4. Start QTimer polling every 2s: `api.get_report_status(report_id)`
5. Update progress bar
6. On complete: add to reports table, show success message

### Bottom Section: Recent Reports (QGroupBox "Recent Reports")
- QTableWidget: Date, Owner, Vehicle, Type, Status, Actions
- Status: colored text ("Ready" green, "Generating" yellow, "Failed" red)
- Actions column: "Download" + "Delete" buttons
- Download: save dialog -> write bytes from `api.download_report(id)` -> open file
- Load on tab show: `APIWorker(api.get_report_history)`

---

## FILE 8: CREATE `predict/desktop/tabs/dtc_tab.py`

Tab 5: DTC Management.

Constructor: `__init__(self, api_client: PredictAPIClient)`

### Top: Search & Filter (QHBoxLayout)
- User search: QLineEdit (placeholder "Search user or plate...") + "Search" QPushButton
- Vehicle: QComboBox (populated after user found)
- Severity: QComboBox ("All", "Critical", "Major", "Minor", "Info")
- "Active Only" QCheckBox (default True)
- "Refresh" QPushButton

### Middle: DTC Table (QTableWidget)
- Columns: Code, Description, Severity, Vehicle, Status, First Seen, Count
- Severity colors:
  - Critical -> `PredictTheme.DANGER` (red)
  - Major -> `PredictTheme.WARNING` (amber)
  - Minor -> `PredictTheme.INFO` (blue)
  - Info -> `PredictTheme.TEXT_SECONDARY` (gray)
- Click row: show detail panel below
- Load: search user -> get vehicles -> get DTCs for selected vehicle

### Bottom: Detail Panel (QGroupBox, initially hidden with `setVisible(False)`)
- Left column: Code (large font), Description, Category, Severity badge, Dates, Count
- Right column: Freeze frame data in QGridLayout (key-value pairs)
- AI Explanation: QTextEdit (read-only), initially "Click 'Get AI Explanation'"
- Buttons: "Get AI Explanation" + "Clear DTC" + "Mark Resolved"
  - AI Explanation: `APIWorker(api.explain_dtc, code)` -> display result
  - Clear DTC: `APIWorker(api.clear_dtc, vehicle_id, dtc_id)` -> refresh table

---

## FILE 9: CREATE `predict/desktop/tabs/analytics_tab.py`

Tab 6: Analytics.

Constructor: `__init__(self, api_client: PredictAPIClient)`

**CRITICAL**: pyqtgraph is optional. Use this pattern:
```python
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False
```

If `HAS_PYQTGRAPH` is False, show QLabel "Charts require pyqtgraph. Install: pip install pyqtgraph" instead of charts.

### QTabWidget with 2 sub-tabs:

**Sub-tab 1: System Overview**
- Stats row: QHBoxLayout with 4 QGroupBox cards (Total Users, Vehicles, Predictions, DTCs)
  - Large number QLabel + description
  - Load from `APIWorker(api.get_system_stats)`
- Chart area (if pyqtgraph available):
  - Tier distribution: pg.BarGraphItem (horizontal bars for free/pro/premium/admin)
  - API traffic: pg.PlotWidget with time series line
- Auto-refresh: PollingWorker(api.get_system_stats, interval_ms=30000)

**Sub-tab 2: Per-User Analytics**
- Search: QLineEdit + "Search" button
- Vehicle selector: QComboBox
- Charts grid (QGridLayout 2x2 of pg.PlotWidget):
  1. Coolant temp over time + red threshold line at 100
  2. Battery voltage over time + red threshold line at 12.4
  3. Engine load % over time
  4. RPM over time
- Load data: `APIWorker(api.get_vehicle_data_history, vid, limit=500)`
- pyqtgraph styling:
  ```python
  plot = pg.PlotWidget()
  plot.setBackground(PredictTheme.BG_PRIMARY)
  plot.getAxis("bottom").setPen(pg.mkPen(PredictTheme.TEXT_SECONDARY))
  plot.getAxis("left").setPen(pg.mkPen(PredictTheme.TEXT_SECONDARY))
  plot.showGrid(x=True, y=True, alpha=0.3)
  # Data line
  plot.plot(timestamps, values, pen=pg.mkPen(PredictTheme.PRIMARY, width=2))
  # Threshold line
  plot.addLine(y=100, pen=pg.mkPen(PredictTheme.DANGER, width=1, style=Qt.DashLine))
  ```

---

## FILE 10: MODIFY `predict/desktop/main_window.py`

Replace the ENTIRE file. New version creates 6 tabs with real data.

Key changes from current version:
- Import all 6 tab classes + PredictAPIClient + WebSocketListener
- Create `PredictAPIClient` in constructor
- Create `WebSocketListener` and start it
- 6 tabs instead of 3 placeholder tabs
- Pass `api_client` to every tab constructor
- Connect WS signals to profile tab
- Keep StatusPoller for status bar
- Clean shutdown of all workers

Structure:
```python
# In __init__:
server = get_server_manager().server
self._api_client = PredictAPIClient(base_url=server.base_url)
self._ws_listener = WebSocketListener(f"ws://{server.host}:{server.port}/ws")

# Create tabs
self._profile_tab = ProfileTab(self._api_client, self._ws_listener)
self._server_ops_tab = ServerOpsTab(self._api_client)
self._ai_llm_tab = AILLMTab(self._api_client)
self._pdf_tab = PDFTab(self._api_client)
self._dtc_tab = DTCTab(self._api_client)
self._analytics_tab = AnalyticsTab(self._api_client)

# Add to tab widget
self._tabs.addTab(self._profile_tab, "Profiles")
self._tabs.addTab(self._server_ops_tab, "Server & Ops")
self._tabs.addTab(self._ai_llm_tab, "AI & LLM")
self._tabs.addTab(self._pdf_tab, "PDF Reports")
self._tabs.addTab(self._dtc_tab, "DTC Manager")
self._tabs.addTab(self._analytics_tab, "Analytics")

# Start WebSocket
self._ws_listener.start()

# In closeEvent:
if self._ws_listener:
    self._ws_listener.stop()
    self._ws_listener.wait(2000)
```

---

## FILE 11: MODIFY `predict/desktop/app.py`

Add dark theme application before creating window:
```python
from predict.desktop.theme import PredictTheme

# After creating QApplication:
PredictTheme.apply_dark_theme(app)
```

Keep everything else the same.

---

## OLD TABS TO DELETE

After all new files are created and working, delete these mock tab files:
- `predict/desktop/tabs/connection.py`
- `predict/desktop/tabs/subscription.py`
- `predict/desktop/tabs/dashboard_monitor.py`
- `predict/desktop/tabs/cloud_sync.py`
- `predict/desktop/tabs/chat.py`
- `predict/desktop/tabs/ai_training.py`
- `predict/desktop/tabs/reports.py`
- `predict/desktop/tabs/dtc.py`
- `predict/desktop/tabs/maintenance.py`
- `predict/desktop/tabs/live_data.py`

Keep `predict/desktop/tabs/__init__.py` (do NOT delete it).

---

## SUMMARY

| # | File | Action | Purpose |
|---|------|--------|---------|
| 1 | `predict/desktop/api_client.py` | CREATE | HTTP client for all tabs |
| 2 | `predict/desktop/workers.py` | CREATE | QThread workers + WebSocket |
| 3 | `predict/desktop/tabs/profile_tab.py` | CREATE | Tab 1: User management |
| 4 | `predict/desktop/tabs/user_detail_dialog.py` | CREATE | User detail popup (6 sub-tabs) |
| 5 | `predict/desktop/tabs/server_ops_tab.py` | CREATE | Tab 2: Server monitoring |
| 6 | `predict/desktop/tabs/ai_llm_tab.py` | CREATE | Tab 3: LLM chat + training |
| 7 | `predict/desktop/tabs/pdf_tab.py` | CREATE | Tab 4: PDF generation |
| 8 | `predict/desktop/tabs/dtc_tab.py` | CREATE | Tab 5: DTC management |
| 9 | `predict/desktop/tabs/analytics_tab.py` | CREATE | Tab 6: Analytics charts |
| 10 | `predict/desktop/main_window.py` | REPLACE | New 6-tab window |
| 11 | `predict/desktop/app.py` | MODIFY | Add dark theme |

---

## VERIFICATION

After implementing all files:

1. Run `python -c "from predict.desktop.main_window import PredictMainWindow"` - no import errors
2. Launch `python -m predict` - GUI with 6 tabs, dark theme, no crashes
3. Profile tab loads users from database
4. Server ops shows live health metrics
5. AI chat sends and receives messages
6. No GUI freezing (all API calls on background threads)

---

## IMPORTANT REMINDERS
- **PySide6 ONLY** - every import must be `from PySide6...` NOT PyQt5/PyQt6
- **NO inline imports** - all at file top (except optional deps like pyqtgraph/websocket)
- **NO print()** - use logger
- **NO datetime** - use `time.time()`
- **NO hardcoded paths** - use `get_config()`
- **ALL API calls via APIWorker on QThread** - NEVER from GUI thread
- **Handle errors** - try/except, user-friendly messages, no crashes
- **Use PredictTheme** - import colors from theme.py
- After completing this phase, STOP and wait for review

## STOP AFTER THIS PHASE
Do NOT make any further changes. Present all files for review. The reviewer will check imports, test GUI launch, verify tab wiring, and confirm no regressions before signing off.
