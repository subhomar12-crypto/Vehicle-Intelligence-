# PREDICT Platform - Future Enhancements

> Last Updated: January 17, 2026
> Purpose: Track pending enhancements for future implementation

---

## Priority 1: Real-time Features (High Impact)

- [ ] **Push Notifications for Mobile Alerts**
  - FCM (Firebase Cloud Messaging) integration
  - Critical alerts: Battery, Engine, Brakes
  - Priority-based notification routing
  - Files: `alert_notifications.py`, Android apps

- [ ] **WebSocket-based Real-time Data Sync**
  - Live data streaming from server to desktop
  - Instant vehicle status updates
  - Files: `realtime_sync.py` (foundation created), `websocket_manager.py`

- [ ] **Live Connection Quality Monitor**
  - Auto-reconnect on connection loss
  - Visual indicator in status bar
  - Offline queue for pending operations
  - Files: `connection_monitor.py` (to create)

---

## Priority 2: Data Management

- [ ] **Data Export to CSV/JSON from Dashboard**
  - Export vehicle data, predictions, reports
  - Date range selection
  - Format options: CSV, JSON, Excel, PDF
  - Files: `dashboard_widget.py`, `data_export.py` (to create)

- [ ] **Data Retention Policy with Auto-cleanup**
  - Configurable retention periods
  - Automatic cleanup of old telemetry data
  - Archive important predictions/events
  - Files: `database_cleanup.py` (to create)

- [x] **Batch Data Upload with Compression**
  - COMPLETED: Implemented in `data_collection_api.py`
  - Supports gzip + base64 encoding
  - Deduplication using hash

---

## Priority 3: AI/ML Improvements

- [ ] **AI Training Trigger on Data Threshold**
  - Auto-trigger training when X new samples arrive
  - Configurable threshold per model
  - Files: `predictive_failure.py`, `ai_auto_retraining.py`

- [ ] **Auto-retraining Scheduler**
  - Daily/weekly scheduled training
  - Run at low-activity hours (e.g., 3 AM)
  - Files: `ai_auto_retraining.py`

- [ ] **Model Performance Monitoring Dashboard**
  - Accuracy trends over time
  - False positive/negative rates
  - Per-component performance metrics
  - Files: `dashboard_widget.py`, `model_metrics.py` (to create)

---

## Priority 4: User Experience

- [ ] **Tab Consolidation (31 to 12 tabs)**
  - Reduce visible tabs to daily-use only
  - Automate background tasks
  - See main plan for full structure
  - Files: `sidebar_navigation.py`, `main_pyside.py`

- [ ] **Enhanced Dashboard with AI Status Widget**
  - AI model status (last trained, accuracy)
  - Active predictions summary
  - Recent notifications
  - Quick data export
  - Files: `dashboard_widget.py`

- [ ] **Notification Center in Header**
  - Replace Notifications tab with icon
  - Unread count badge
  - Quick actions (dismiss, view, act)
  - Files: `main_pyside.py`, `notification_center.py` (to create)

---

## Priority 5: Server Enhancements

- [ ] **Database Backup Automation**
  - Daily automated backups
  - Cloud storage option (S3, GCS)
  - Retention policy for backups
  - Files: `backup_service.py` (to create)

- [ ] **API Rate Limiting per Tier**
  - Free: 100 requests/hour
  - Premium: 1000 requests/hour
  - Admin: Unlimited
  - Files: `main.py` (server), `rate_limiter.py` (to create)

- [ ] **Cloudflare Tunnel Health Monitoring**
  - Auto-restart on tunnel failure
  - Alert on extended downtime
  - Files: `health_monitor.py`, `server_gui.py`

---

## Priority 6: Owner/Driver Hierarchy (Full Plan)

- [ ] **Owner -> Vehicle -> Driver 3-Level Hierarchy**
  - Database: Add `owners` table
  - UI: Update tree view structure
  - API: Role-based permissions
  - See FIX B in main plan

- [ ] **Role-Based API Key Permissions**
  - Owner: Full access (OBD + Guardian)
  - Driver: Limited access (OBD only)
  - See FIX C in main plan

---

## Priority 7: LLM Enhancements

- [ ] **LLM Full System Awareness**
  - Respond as the AI system ("I detected...")
  - Access to all predictions, notifications
  - Explain why notifications were sent
  - Files: `llm_context_provider.py`, `llm_assistant.py`

- [ ] **7-Day Conversation Memory**
  - Store conversation history per customer
  - Auto-cleanup after 7 days
  - Files: `llm_conversation_history.py` (to create)

- [ ] **Arabic Language Support (Bilingual)**
  - Auto-detect language from input
  - Professional Arabic responses
  - Bilingual notifications
  - Files: `llm_assistant.py`, `alert_notifications.py`

- [ ] **LLM Response Feedback (Thumbs Up/Down)**
  - Collect user feedback on responses
  - Track satisfaction rate
  - Files: `llm_feedback.py` (to create), `chat_tab.py`

---

## Recently Completed (January 2026)

- [x] **Server Control Panel GUI** (`server_gui.py`)
  - Visual status indicators for OBD/LLM servers
  - Start/Stop/Restart controls
  - Live log viewing

- [x] **Health Monitoring System** (`health_monitor.py`)
  - Comprehensive health checks
  - Resource monitoring
  - API endpoints for status

- [x] **Fixed LLM Connection** (`ai_chat_endpoint.py`)
  - Try localhost:12580 first
  - Fallback to tunnel (ai.previlium.com)

- [x] **Fixed Database Path** (`database.py`)
  - Correct path: `C:\D Drive\Predict\PredictData\vehicle_profiles.db`
  - Shared between server and desktop

- [x] **Real-time Sync Service** (`realtime_sync.py`)
  - Database watcher for changes
  - WebSocket client foundation

- [x] **Enhanced Data Collection API** (`data_collection_api.py`)
  - Batch upload endpoint
  - Data validation
  - Incremental sync
  - Collection statistics

---

## Reference: Key File Locations

### Desktop App
```
C:\D Drive\Predict\
├── main_pyside.py          # Main application
├── dashboard_widget.py     # Dashboard UI
├── llm_assistant.py        # LLM integration
├── alert_notifications.py  # Notification system
├── vehicle_module.py       # Vehicle management
├── realtime_sync.py        # NEW: Real-time sync
└── PredictData\
    └── vehicle_profiles.db # Main database
```

### Server
```
C:\OBDserver\Previlium_OBD_Server\
├── main.py                 # FastAPI server
├── server_gui.py           # NEW: Server GUI
├── health_monitor.py       # NEW: Health checks
├── data_collection_api.py  # NEW: Enhanced data API
├── ai_chat_endpoint.py     # LLM proxy
└── database.py             # Database config
```

### Android Apps
```
C:\Predict\PredictOBD\       # OBD App
C:\Predict guradian\         # Guardian App
```

---

## Notes

- Focus on Android app finalization first
- Server infrastructure is ready for testing
- Data collection endpoints are functional
- Real-time features can be added incrementally
