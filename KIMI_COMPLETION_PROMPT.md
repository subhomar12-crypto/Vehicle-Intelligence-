# KIMI COMPLETION PROMPT — Port Real Logic + AI Enhancements

## Context
All 12 structural phases are COMPLETE and reviewed. You built 156 files (~34K lines).
Claude reviewed every phase and fixed 21 bugs (4 critical: eval() RCE, async/await mismatch, FileHandler crash, missing method).

**The structure is solid. Now we need the REAL business logic inside it.**

The new routers/services have the correct structure but many contain simplified or partial logic. The REAL production logic lives in the OLD codebase files listed below. Your job is to PORT that logic into the new structure while keeping all architecture rules.

---

## ARCHITECTURE RULES (STILL ENFORCED — ZERO EXCEPTIONS)

| Rule | Correct | Wrong |
|------|---------|-------|
| Timestamps | `time.time()` returns float | `datetime.now()`, `datetime.utcnow()` |
| DB columns | `sa.Float()` for timestamps | `sa.DateTime()` |
| ORM style | `Mapped[type]` + `mapped_column()` | `Column()` |
| Imports | ALL at top of file | `import X` inside functions |
| GUI | `PySide6` | `PyQt5`, `PyQt6` |
| Logging | `logger = logging.getLogger(__name__)` | `print()` in production code |
| Paths | `get_config().DATA_DIR` | Hardcoded `C:\...` paths |
| Security | `json.loads()` for parsing | `eval()`, `exec()` |

---

## SELF-REVIEW CHECKLIST (Run after EVERY file)

Before marking any file complete, verify:
- [ ] Zero `datetime.now()` or `datetime.utcnow()` — use `time.time()`
- [ ] Zero `import X` inside function bodies — all imports at top
- [ ] Zero `print()` in production code (OK in scripts/)
- [ ] Zero `eval()` or `exec()`
- [ ] Zero hardcoded paths
- [ ] All async functions properly `await`ed
- [ ] No unused imports

---

## STOP-AND-REVIEW PROTOCOL

**STOP after each phase below. Do NOT proceed to the next phase until told "PROCEED TO PHASE X".**

After each phase:
1. List every file you modified/created
2. Show line count per file
3. State what you ported from which old file
4. Confirm self-review checklist passed

---

## OLD CODEBASE REFERENCE FILES

These contain the REAL business logic to port:

### Server (C:\OBDserver\)
| Old File | Size | Contains |
|----------|------|----------|
| `main.py` | 460KB, ~12,000 lines | ALL 162+ API endpoints with full business logic |
| `database.py` | 341KB | All DB operations, queries, table definitions |
| `guardian_api.py` | 88KB | 40+ guardian endpoints |
| `fatora_billing.py` | ~15KB | Fatora payment integration |
| `fcm_service.py` | ~8KB | Firebase push notifications |
| `email_service.py` | ~10KB | SMTP email with templates |
| `websocket_manager.py` | ~8KB | WebSocket connection management |
| `health_monitor.py` | ~12KB | Health checks, circuit breaker |
| `error_responses.py` | ~5KB | ErrorCode enum, API error helpers |
| `validation_middleware.py` | ~8KB | OBD_RANGES, VIN validation |
| `api_key_middleware.py` | ~10KB | API key validation, permissions, tiers |
| `backup_utility.py` | ~5KB | Database backup logic |
| `pdf_report.py` | ~15KB | PDF generation with ReportLab |
| `customer_management.py` | ~8KB | User/customer operations |
| `legal_api.py` | ~5KB | Legal/consent endpoints |
| `ai_chat_endpoint.py` | ~8KB | AI chat with web search |

### Desktop (C:\D Drive\Predict\)
| Old File | Size | Contains |
|----------|------|----------|
| `main_pyside.py` | 463KB, ~12,000 lines | Full GUI: MainWindow, all tabs, all widgets |
| `unified_ai_module.py` | 1,147 lines | Central AI orchestrator (REAL version) |
| `enhanced_prediction_engine.py` | ~800 lines | Full prediction pipeline |
| `predictive_failure_engine.py` | ~600 lines | RandomForest/XGBoost/LightGBM |
| `lstm_predictor.py` | ~500 lines | LSTM model architecture |
| `cnn_lstm_model.py` | ~400 lines | CNN-LSTM model |
| `attention_lstm_model.py` | ~400 lines | Attention-LSTM model |
| `lstm_autoencoder.py` | ~450 lines | Autoencoder anomaly detection |
| `llm_assistant.py` | ~300 lines | In-process llama.cpp |
| `advanced_feature_engineering.py` | ~400 lines | Feature pipeline |
| `failure_correlation_engine.py` | ~300 lines | Failure patterns |
| `rul_estimation.py` | ~200 lines | Remaining useful life |
| `vehicle_baseline_learning.py` | ~250 lines | Per-vehicle baselines |
| `fleet_learning_aggregator.py` | ~300 lines | Cross-vehicle learning |
| `recall_monitor.py` | ~200 lines | NHTSA recall API |
| `web_search.py` | ~150 lines | DuckDuckGo search |
| `vehicle_research_engine.py` | ~200 lines | Vehicle research |

---

## PHASE A: AUDIT + CREATE predict_run.bat (DO FIRST)

### Task 1: Create predict_run.bat
Create a batch file at the project root so the developer can quickly launch and test.

**File: `C:\D Drive\Predict\predict_run.bat`**
```bat
@echo off
title PREDICT Vehicle Intelligence Platform
echo ============================================================
echo  PREDICT v3.0.0 - Vehicle Intelligence Platform
echo ============================================================
echo.

REM Check Python
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install dependencies if needed
if not exist "venv\Lib\site-packages\fastapi" (
    echo Installing dependencies...
    pip install -e ".[dev]"
)

REM Create data directories
if not exist "data\logs" mkdir data\logs
if not exist "data\backups" mkdir data\backups
if not exist "data\parquet" mkdir data\parquet
if not exist "data\exports" mkdir data\exports

echo.
echo Choose mode:
echo   1. Desktop (GUI + Server)
echo   2. Headless (Server only)
echo   3. Run tests
echo   4. Run migrations (alembic upgrade head)
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo Starting Desktop mode...
    python -m predict --desktop
) else if "%choice%"=="2" (
    echo Starting Headless mode...
    python -m predict --headless --host 0.0.0.0 --port 8000
) else if "%choice%"=="3" (
    echo Running tests...
    pytest tests/ -v --tb=short
) else if "%choice%"=="4" (
    echo Running migrations...
    alembic upgrade head
) else (
    echo Invalid choice
)

pause
```

### Task 2: Audit all files

Read every file in `predict/core/` and identify which have REAL logic vs simplified stubs.

For each file, categorize as:
- **REAL**: Has complete business logic (no work needed)
- **PARTIAL**: Has structure but simplified/missing logic (needs porting)
- **STUB**: Has class/function signatures but minimal implementation (needs full porting)

Focus on these directories:
1. `predict/core/api/v1/` — Are all 162+ endpoints ported with full logic?
2. `predict/core/services/` — Do services have complete business logic?
3. `predict/core/ai/` — Do AI modules have real model code or just structure?
4. `predict/desktop/tabs/` — Do tabs have real PySide6 widget code?

**Output**: A table showing every file, its status (REAL/PARTIAL/STUB), and what old file to port from.

**STOP HERE. Wait for "PROCEED TO PHASE B".**

---

## PHASE B: PORT API ENDPOINT LOGIC

**Goal**: Port ALL real business logic from `C:\OBDserver\main.py` into the new router files.

**Method**: For each router file in `predict/core/api/v1/`:
1. Read the corresponding section of old `main.py`
2. Read the current new router file
3. Port the FULL business logic (not simplified versions)
4. Preserve EXACT API contracts (paths, request/response formats, status codes)

**Priority order** (most critical first):
1. `auth.py` — Registration, login, verify email, password reset, token refresh
2. `vehicle_data.py` — OBD upload, telemetry, sensor data
3. `profiles.py` — User + vehicle profile CRUD
4. `predictions.py` — AI predictions endpoints
5. `dtc.py` — DTC lookup, history
6. `guardian.py` — Port from `guardian_api.py` (40+ endpoints)
7. `billing.py` — Port from `fatora_billing.py`
8. `admin.py` — Admin dashboard, user management, system controls
9. `reports.py` — PDF generation, export
10. `ai_chat.py` — Port from `ai_chat_endpoint.py`
11. `websockets.py` — Port from `websocket_manager.py`
12. `driving.py` — Driver behavior, trip tracking
13. `fleet.py` — Fleet management
14. `legal.py` — Port from `legal_api.py`
15. `tiers.py` — Subscription tiers
16. `app_version.py` — Force update check
17. `health.py` — Enhanced health checks
18. `dashboard.py` — Desktop monitoring API

**CRITICAL**: For each endpoint verify:
- Same HTTP method (GET/POST/PUT/DELETE)
- Same URL path
- Same request body schema
- Same response body schema
- Same HTTP status codes
- Same error codes (ErrorCode enum)

The Android app must work WITHOUT any changes.

**STOP HERE. Wait for "PROCEED TO PHASE C".**

---

## PHASE C: PORT SERVICE LOGIC

**Goal**: Ensure all services in `predict/core/services/` have COMPLETE business logic.

For each service:
1. `auth_service.py` — bcrypt + SHA-256 fallback (30-day transition), JWT
2. `email_service.py` — Port email templates from old `email_service.py`
3. `fcm_service.py` — Port FCM logic from old `fcm_service.py`, add circuit breaker
4. `billing_service.py` — Port Fatora API from old `fatora_billing.py`, add circuit breaker
5. `guardian_service.py` — Port guardian business logic
6. `websocket_service.py` — Port from old `websocket_manager.py`, add Redis pub/sub
7. `prediction_service.py` — Connect to UnifiedAI properly
8. `pdf_service.py` — Port from old `pdf_report.py` + Desktop `pdf_exporter.py`
9. `backup_service.py` — Port from old `backup_utility.py`, convert to pg_dump
10. `gdpr_service.py` — Data retention enforcement
11. `obd_processor.py` — OBD data validation and processing

**STOP HERE. Wait for "PROCEED TO PHASE D".**

---

## PHASE D: PORT AI MODULE LOGIC

**Goal**: Ensure ALL AI modules have the REAL model code from the Desktop codebase.

For each AI module, compare the new file with the old Desktop file and port any missing logic:

1. `unified_ai_module.py` — Compare with old `C:\D Drive\Predict\unified_ai_module.py` (1,147 lines). The old one is the REAL version with complete `get_complete_vehicle_intelligence()`, subsystem scoring, trend analysis, etc. Port ALL missing methods.

2. `lstm_predictor.py` — Compare with old `lstm_predictor.py`. Ensure full LSTM architecture, training, inference.

3. `cnn_lstm_model.py` — Compare with old. Full CNN-LSTM with training.

4. `attention_lstm.py` — Compare with old `attention_lstm_model.py`. Full attention mechanism.

5. `autoencoder.py` — Compare with old `lstm_autoencoder.py`. Full autoencoder + reconstruction error anomaly scoring.

6. `failure_engine.py` — Compare with old `predictive_failure_engine.py`. Full RandomForest/XGBoost/LightGBM ensemble.

7. `feature_engineering.py` — Compare with old `advanced_feature_engineering.py`. Full feature pipeline.

8. `failure_correlation.py` — Compare with old `failure_correlation_engine.py`.

9. `rul_estimation.py` — Compare with old.

10. `vehicle_baseline.py` — Compare with old `vehicle_baseline_learning.py`.

11. `fleet_learning.py` — Compare with old `fleet_learning_aggregator.py`.

12. `recall_monitor.py` — Compare with old.

13. `llm/assistant.py` — Compare with old `llm_assistant.py`. Ensure in-process llama.cpp works.

**STOP HERE. Wait for "PROCEED TO PHASE E".**

---

## PHASE E: AI BRIDGE — Connect Predictions to LLM (Phase 6B from plan)

**Goal**: Make UnifiedAI predictions feed INTO the LLM as context so ALL text output is intelligent and data-driven.

**Current problem**: UnifiedAI generates health scores and failure predictions, but the LLM chat only gets raw sensor values. They're completely isolated.

**The fix**: `predict/core/ai/ai_bridge.py` already exists (Claude fixed async issues). Verify it:
1. Actually calls `unified_ai.analyze_vehicle_health()` with real data
2. Formats ALL prediction data (health scores, subsystem scores, LSTM forecasts, correlations, fleet comparisons) as structured text
3. Passes formatted context to LLM prompt
4. LLM generates human-readable explanations using the prediction data

**Update these to use AIBridge**:
- `predict/core/api/v1/ai_chat.py` — Use `ai_bridge.chat_with_ai_context()`
- `predict/desktop/tabs/chat.py` — Use AIBridge for Desktop chat
- `predict/core/services/pdf_service.py` — LLM generates report narrative sections

**Verify**: Ask "Is my battery healthy?" should use prediction data, not give generic advice.

**STOP HERE. Wait for "PROCEED TO PHASE F".**

---

## PHASE F: AI INTELLIGENCE ENHANCEMENTS (Phase 6C from plan)

**Goal**: Implement the advanced AI features that make predictions genuinely world-class.

### F1: SHAP Explainability
- File: `predict/core/ai/explainability.py`
- Add real SHAP integration for XGBoost/RandomForest/LightGBM predictions
- Every prediction includes top contributing factors with importance scores
- Feed SHAP values to AIBridge so LLM explains WHY

### F2: Ensemble Voting
- File: `predict/core/ai/ensemble_voter.py`
- Weighted voting across all models (LSTM, CNN-LSTM, Attention-LSTM, XGBoost, RandomForest, LightGBM)
- Rolling accuracy-based weights (not static)
- Agreement/disagreement detection
- Replace fake `'ml_confidence': min(95, 70 + len(history))` with real ensemble agreement

### F3: Causal Reasoning Graph
- File: `predict/core/ai/causal_graph.py`
- Directed acyclic graph of vehicle system relationships
- When multiple sensors trigger, trace to ROOT CAUSE
- Example: "Battery low + engine load high" traces to root cause: alternator

### F4: Survival Analysis
- File: `predict/core/ai/survival_analysis.py`
- Library: `lifelines` (Weibull fitter)
- Probability distribution over time (50%/80%/95% failure by day X)
- Confidence bands that narrow with more data

### F5: Context-Aware Anomaly Detection
- File: `predict/core/ai/anomaly_detector.py`
- Isolation Forest for multivariate anomaly detection
- Context windows (different "normal" for idle vs highway vs cold start)
- Per-vehicle baselines from VehicleBaselineLearning

### F6: Replace ALL Fake Values
- `'accuracy': 0.85` must become actual learning_statistics accuracy
- `'ml_confidence': min(95, 70 + len(history))` must become ensemble agreement score
- Cost savings $45/$25/$10 must be calculated from real data
- Service intervals (flat 10K) must be dynamic from degradation curves

### F7: Complete the Feedback Loop
- Fix `add_feedback()` — currently buffers but never processes
- Active learning: ask user "Did this prediction come true?"
- After 100 labeled examples, trigger auto-retrain
- Track REAL accuracy over time

**STOP HERE. Wait for "PROCEED TO PHASE G".**

---

## PHASE G: DESKTOP GUI PORTING

**Goal**: Port real PySide6 widget code from `main_pyside.py` (463KB) into the decomposed tab files.

For each tab in `predict/desktop/tabs/`:
1. Find the corresponding code section in old `main_pyside.py`
2. Port the FULL widget code (layouts, signals, slots, data binding)
3. Connect to shared SQLAlchemy engine (not HTTP calls)
4. Keep ProfessionalTheme styling (#0D1117 bg, #C40000 accent, #F0F6FC text)

Tabs to port:
- `live_data.py` — Real-time gauge display, OBD connection
- `connection.py` — OBD adapter connection management
- `dtc.py` — DTC scanner, code lookup
- `reports.py` — PDF generation, export
- `ai_training.py` — Model training interface
- `chat.py` — AI chat (using AIBridge)
- `subscription.py` — Tier management
- `cloud_sync.py` — Server sync
- `maintenance.py` — Service records
- `dashboard_monitor.py` — System monitoring (CPU, memory, req/s)

Also port:
- `predict/desktop/main_window.py` — MainWindow with tab container, menu bar, status bar
- `predict/desktop/widgets/` — Custom gauges, cards, charts from old code

**STOP HERE. Wait for review.**

---

## FINAL NOTES

1. **Read the OLD file FIRST** before modifying the new file. Understand what the real logic does.
2. **Don't simplify** — port the FULL logic, not a simplified version.
3. **Preserve ALL API contracts** — Android app must work with zero changes.
4. **Architecture rules are NON-NEGOTIABLE** — time.time(), no datetime.now(), imports at top.
5. **Self-review every file** before moving to the next one.
6. **Start with Phase A** (audit + create predict_run.bat). This tells us exactly how much work remains.
