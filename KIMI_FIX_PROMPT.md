# STOP. READ THIS ENTIRE PROMPT BEFORE WRITING ANY CODE.

You are a **Senior Python Engineer** working on the PREDICT Vehicle Intelligence Platform.

Your job has TWO parts:
1. **FIX** all architecture violations found in your previous code
2. **ADD** 5 new modules/features that are critical for production safety

DO NOT analyze. DO NOT ask questions. DO NOT give options.
WRITE THE FIXED CODE. Every file listed below must be output as a complete, working Python file.

---

# PART 1: MANDATORY FIXES

## FIX #1: datetime VIOLATIONS (CRITICAL — 60+ occurrences)

The architecture rule is: **ALL timestamps must use `time.time()` (float seconds since epoch). NEVER use `datetime.now()`, `datetime.utcnow()`, or `datetime.now(timezone.utc)`.**

For display-only formatting (like chat message timestamps in the GUI), use:
```python
import time
timestamp_display = time.strftime("%H:%M", time.localtime())
```

For ISO string output in API responses, use:
```python
import time
timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
```

For timing/elapsed measurements, use:
```python
import time
start = time.perf_counter()
# ... do work ...
elapsed_ms = (time.perf_counter() - start) * 1000
```

### Files that MUST be fixed (every datetime.now/utcnow replaced):

**predict/core/monitoring/health.py** — WORST OFFENDER (20+ uses)
- Lines 50, 103, 124, 142, 146, 157, 166, 174, 184, 191, 201, 211, 217, 227, 237, 248, 256, 277, 300, 308, 317
- Replace ALL `datetime.utcnow()` with `time.time()` for timestamps
- Replace ALL timing measurements with `time.perf_counter()`
- Replace ALL `.isoformat()` with `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())`

**predict/core/ai/unified_ai_module.py** — Lines 76, 154, 239
- Replace `datetime.utcnow().isoformat()` with `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())`

**predict/core/ai/ensemble_voter.py** — Lines 112, 245
- Same fix

**predict/core/ai/lstm_predictor.py** — Lines 171, 186
- Same fix

**predict/core/ai/llm/assistant.py** — Line 123
- Same fix

**predict/core/middleware/audit.py** — Line 94
- Replace `datetime.now(timezone.utc).isoformat()` with `time.strftime(...)`

**predict/core/middleware/error_handler.py** — Line 110
- Same fix

**predict/core/middleware/rate_limiter.py** — Lines 118, 143
- Replace `datetime.utcnow()` with `time.time()` for the rate limiter window tracking

**predict/core/api/v1/dtc.py** — Lines 233, 305
- Replace `datetime.now(timezone.utc)` with `time.time()`

**predict/core/api/v1/ai_chat.py** — Lines 118, 119
- Same fix

**predict/core/api/v1/dashboard.py** — Line 30
- Same fix

**predict/core/api/v1/health.py** — Lines 23, 49
- Same fix

**predict/core/api/v1/legal.py** — Line 59
- Same fix

**predict/core/api/v1/vehicle_data.py** — Lines 103, 173
- Same fix

**predict/core/api/v1/predictions.py** — Lines 152, 227
- Same fix

**predict/core/services/export_service.py** — Lines 44, 82, 109, 145, 153, 255
- Replace all `datetime.utcnow()` with `time.time()` or `time.strftime(...)` as appropriate

**predict/core/monitoring/metrics.py** — Line 181
- Same fix

**predict/core/jobs/tasks/cleanup_tasks.py** — Lines 62, 78, 96, 124, 166
- Replace all datetime usage with time.time()

**predict/core/jobs/tasks/backup_tasks.py** — Lines 28, 67, 135
- Same fix

**predict/core/jobs/tasks/pdf_tasks.py** — Lines 58, 94
- Same fix

**predict/core/db/base.py** — Lines 22, 27, 28
- Replace `datetime.utcnow().timestamp()` with just `time.time()`
- This is the BASE MODEL — every table inherits from it. This MUST be:
```python
import time
# In the base model:
created_at: Mapped[float] = mapped_column(Float, default=time.time)
updated_at: Mapped[float] = mapped_column(Float, default=time.time, onupdate=time.time)
```

**predict/desktop/tabs/chat.py** — Lines 217, 239
- Replace `datetime.now().strftime(...)` with `time.strftime("%H:%M", time.localtime())`

**predict/desktop/tabs/ai_training.py** — Line 343
- Same pattern

**predict/desktop/tabs/reports.py** — Line 51
- Same pattern

---

# PART 2: NEW MODULES TO CREATE

You must create these 5 new files. They are critical for production safety.

## NEW FILE 1: `predict/core/ai/uncertainty_estimator.py`

Purpose: Estimate prediction uncertainty from ensemble model disagreement.

Requirements:
- Class `UncertaintyEstimator`
- Method `estimate(predictions: List[Dict]) -> Dict` that takes predictions from multiple models and returns:
  - `mean_risk`: float — average risk score across models
  - `epistemic_uncertainty`: float — variance across model predictions (model disagreement)
  - `confidence`: float — 1.0 / (1.0 + epistemic_uncertainty), clamped to [0, 1]
  - `confidence_level`: str — "high" (>0.8), "medium" (0.5-0.8), "low" (<0.5)
  - `models_agree`: bool — True if all models within 0.2 of each other
  - `should_suppress_alert`: bool — True if confidence < 0.5
  - `should_abstain`: bool — True if confidence < 0.3 OR models disagree by > 0.5
- Method `calibrate(predictions: np.ndarray, true_labels: np.ndarray)` for Platt scaling calibration
- Uses `import time` for timestamps, `import logging` for logs
- Uses `from predict.core.config import get_config`
- NO datetime imports

Integration points:
- Called by `ensemble_voter.py` after collecting all model votes
- Called by `unified_ai_module.py` when generating final assessment
- Results included in every prediction output dict

```python
# Example usage:
estimator = UncertaintyEstimator()
result = estimator.estimate([
    {"model": "lstm", "risk": 0.82, "component": "battery"},
    {"model": "cnn_lstm", "risk": 0.78, "component": "battery"},
    {"model": "xgboost", "risk": 0.35, "component": "battery"},  # disagrees!
])
# result = {
#     "mean_risk": 0.65,
#     "epistemic_uncertainty": 0.062,
#     "confidence": 0.94,  # Wait, models disagree...
#     "confidence_level": "low",  # because std is high
#     "models_agree": False,
#     "should_suppress_alert": True,
#     "should_abstain": False,
# }
```

## NEW FILE 2: `predict/core/ai/temporal_consistency.py`

Purpose: Smooth risk scores over time to prevent erratic jumps.

Requirements:
- Class `TemporalConsistencyFilter`
- Maintains per-vehicle, per-component risk history (in-memory dict)
- Method `smooth(vehicle_id: int, component: str, raw_risk: float, anomaly_surge: bool = False, multi_sensor_agreement: bool = False) -> float`
  - Normal mode: EMA with alpha=0.1 (heavy smoothing)
  - Anomaly surge + multi-sensor agreement: alpha=0.7 (fast response)
  - Anomaly surge alone: alpha=0.3 (moderate response)
- Method `get_trend(vehicle_id: int, component: str) -> Dict` returns:
  - `current_smoothed`: float
  - `direction`: "increasing" | "decreasing" | "stable"
  - `rate_of_change`: float (per-step delta)
  - `readings_count`: int
- Method `reset(vehicle_id: int)` clears history for a vehicle
- CRITICAL OVERRIDES: If any of these are true, skip smoothing entirely (alpha=1.0):
  - `coolant_temp > 115`
  - `oil_pressure < 10` (if you have oil pressure)
  - `battery_voltage < 11.0`
  These are catastrophic conditions where delay = damage.
- Uses `time.time()` for timestamps
- NO datetime imports

## NEW FILE 3: `predict/core/ai/abstention_manager.py`

Purpose: Decide when the AI should say "I don't know" instead of guessing.

Requirements:
- Class `AbstentionManager`
- Method `should_abstain(context: Dict) -> Tuple[bool, str]` checks:
  - `model_disagreement`: ensemble std > 0.3 → abstain, reason="Models disagree significantly"
  - `high_uncertainty`: confidence < 0.3 → abstain, reason="Insufficient confidence"
  - `insufficient_data`: sequence_length < 30 readings → abstain, reason="Need more sensor data"
  - `sensor_dropout`: active_sensors < 8 out of 14 → abstain, reason="Too many sensors offline"
  - `novel_pattern`: if autoencoder reconstruction error is in top 5% → abstain, reason="Unusual pattern, monitoring"
  - Returns (False, "") if no abstention triggers fire
- Method `get_abstention_message(reason: str) -> str` returns user-friendly messages:
  - NOT "I don't know" — instead: "Analyzing driving patterns... Collecting more data for accurate assessment."
  - Different messages for each reason
- Method `get_abstention_stats() -> Dict` returns counts of abstentions by reason (for monitoring)
- Uses `time.time()` for timestamps
- NO datetime imports

## NEW FILE 4: `predict/core/ai/hindsight_collector.py`

Purpose: Silent data collector that records everything needed for future hindsight learning. Runs in "hold" mode — collects but does NOT train. When released, provides months of real failure data for retrospective label propagation.

Requirements:
- Class `HindsightCollector`
- Constructor takes `hold_mode: bool = True` (when True, only collects — never triggers training)
- Method `on_dtc_detected(vehicle_id: int, dtc_code: str, sensor_snapshot: Dict, mileage: float, session)`:
  - Checks if AI predicted this DTC in advance (queries recent predictions)
  - If AI MISSED it (false negative): this is a hindsight observation
  - Extracts preceding sensor data window (configurable, default 200 data points before DTC)
  - Stores to `hindsight_observations` DB table with fields:
    - `id`, `vehicle_id`, `dtc_code`, `detected_at` (float, time.time())
    - `was_predicted`: bool (did AI catch it?)
    - `sensor_window_before`: JSON (the sensor data before the DTC)
    - `prediction_at_time`: JSON (what the AI was predicting when DTC hit)
    - `mileage_at_detection`: float
    - `status`: "collected" | "validated" | "used_for_training" | "rejected"
    - `credibility_score`: float (based on DTC type — P0300 misfire = 0.95, P0455 EVAP = 0.40)
    - `repair_data`: JSON (filled in later when repair is recorded)
    - `post_repair_window`: JSON (filled in after repair to capture "healthy" state)
    - `created_at`: float (time.time())
- Method `on_repair_recorded(vehicle_id: int, dtc_code: str, repair_description: str, mileage: float, session)`:
  - Finds the matching hindsight_observation
  - Updates `repair_data` field
  - Starts collecting post-repair sensor window
- Method `on_post_repair_data(vehicle_id: int, sensor_data: Dict, session)`:
  - Fills in `post_repair_window` — what "healthy" looks like after the fix
  - Checks if same DTC recurs within 30 days — if so, mark as "bad_repair" and exclude from training
- Method `get_collection_stats(session) -> Dict`:
  - Total observations, by status, by DTC code
  - Missed prediction rate
  - Average credibility score
  - How many have complete before→repair→after cycles
- Method `release_hold(min_credibility: float = 0.7, min_observations: int = 50, session) -> Dict`:
  - Only processes observations with status="collected" AND credibility >= min_credibility
  - Returns the validated observations ready for training
  - Updates status to "validated"
  - DOES NOT auto-train — just returns the data for manual review
- DTC credibility scores (hardcoded constants):
```python
DTC_CREDIBILITY = {
    "P0300": 0.95,  # Random misfire — real mechanical issue
    "P0301": 0.95, "P0302": 0.95, "P0303": 0.95, "P0304": 0.95,  # Cylinder specific
    "P0171": 0.90,  # System too lean — usually mechanical
    "P0174": 0.90,  # Bank 2 lean
    "P0128": 0.85,  # Coolant thermostat — real failure
    "P0420": 0.70,  # Catalyst — often sensor, sometimes real
    "P0430": 0.70,  # Catalyst bank 2
    "P0562": 0.90,  # System voltage low — real electrical
    "P0455": 0.30,  # EVAP large leak — often loose gas cap (user error)
    "P0456": 0.30,  # EVAP small leak — same
    "P0442": 0.35,  # EVAP small leak
    "P0700": 0.85,  # Transmission — real issue
    "P0730": 0.90,  # Gear ratio — real transmission issue
    "P0217": 0.95,  # Overheating — critical real failure
    "P0087": 0.85,  # Fuel rail pressure — real fuel system
    "P0130": 0.80,  # O2 sensor — usually sensor, sometimes wiring
    "P0135": 0.80,  # O2 heater — real electrical
}
# Default for unknown DTCs
DEFAULT_DTC_CREDIBILITY = 0.60
```
- All DB operations MUST be async (uses session from SQLAlchemy async)
- ALL timestamps use `time.time()`
- NO datetime imports
- Uses `from predict.core.config import get_config`
- Uses `logging.getLogger(__name__)`

## NEW FILE 5: `predict/core/db/models/hindsight.py`

Purpose: SQLAlchemy 2.0 model for the hindsight_observations table.

Requirements:
- Uses `from predict.core.db.base import Base`
- SQLAlchemy 2.0 style: `Mapped[type]` and `mapped_column()`
- ALL timestamp fields are `Mapped[float]` using `time.time` as default
- NO datetime anywhere
- Fields:
  - `id: Mapped[int]` — primary key, autoincrement
  - `vehicle_id: Mapped[int]` — foreign key to vehicle_profiles.id
  - `dtc_code: Mapped[str]` — the DTC that triggered collection
  - `detected_at: Mapped[float]` — time.time() when DTC was detected
  - `was_predicted: Mapped[bool]` — did the AI predict this?
  - `prediction_at_time: Mapped[Optional[str]]` — JSON string of AI prediction at detection time
  - `sensor_window_before: Mapped[Optional[str]]` — JSON string of sensor data before DTC
  - `window_size: Mapped[int]` — number of data points in the window
  - `mileage_at_detection: Mapped[Optional[float]]`
  - `credibility_score: Mapped[float]` — DTC credibility (0.0-1.0)
  - `status: Mapped[str]` — "collected" | "validated" | "used_for_training" | "rejected"
  - `repair_description: Mapped[Optional[str]]`
  - `repair_at: Mapped[Optional[float]]` — when repair happened
  - `post_repair_window: Mapped[Optional[str]]` — JSON sensor data after repair
  - `dtc_recurred: Mapped[bool]` — did the same DTC come back after repair?
  - `notes: Mapped[Optional[str]]`
  - `created_at: Mapped[float]` — default=time.time
  - `updated_at: Mapped[float]` — default=time.time, onupdate=time.time

Also add a `PredictionAuditLog` model in the same file:
  - `id: Mapped[int]` — primary key
  - `vehicle_id: Mapped[int]`
  - `component: Mapped[str]` — which component was predicted
  - `risk_score: Mapped[float]` — the final smoothed risk score
  - `raw_risk_score: Mapped[float]` — before temporal smoothing
  - `confidence: Mapped[float]` — from uncertainty estimator
  - `models_used: Mapped[str]` — JSON list of model names that contributed
  - `model_predictions: Mapped[str]` — JSON dict of each model's individual prediction
  - `abstained: Mapped[bool]` — did the system abstain?
  - `abstention_reason: Mapped[Optional[str]]`
  - `sensor_snapshot: Mapped[Optional[str]]` — JSON of sensor values at prediction time
  - `created_at: Mapped[float]` — default=time.time

---

# PART 3: INTEGRATION POINTS

After creating the new files, update these existing files:

## Update `predict/core/ai/ensemble_voter.py`:
- Import and use `UncertaintyEstimator`
- After collecting all model votes, call `estimator.estimate(predictions)`
- Include uncertainty data in the returned result dict
- Replace any `datetime.utcnow()` with `time.time()`

## Update `predict/core/ai/unified_ai_module.py`:
- Import `TemporalConsistencyFilter`, `AbstentionManager`, `UncertaintyEstimator`
- After getting ensemble result, apply temporal smoothing
- Check abstention conditions before returning final result
- Include uncertainty and abstention info in output
- If `should_abstain` is True, return a special "monitoring" result instead of a risk score
- Replace all `datetime.utcnow()` with `time.strftime(...)` or `time.time()`

---

# NON-NEGOTIABLE RULES

| Rule | Correct | WRONG |
|---|---|---|
| Timestamps | `time.time()` | `datetime.now()`, `datetime.utcnow()` |
| Display time | `time.strftime("%H:%M", time.localtime())` | `datetime.now().strftime(...)` |
| ISO strings | `time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())` | `datetime.utcnow().isoformat()` |
| Elapsed time | `time.perf_counter()` | `datetime.utcnow() - start_time` |
| DB timestamps | `Mapped[float]` with `default=time.time` | `Mapped[datetime]` |
| ORM style | `Mapped[str] = mapped_column(String)` | `Column(String)` |
| GUI framework | `from PySide6.QtWidgets import ...` | `from PyQt5...` |
| Logging | `logger = logging.getLogger(__name__)` | `print(...)` |
| Config | `from predict.core.config import get_config` | Hardcoded paths |
| DB operations | `async def` + `await session.execute(...)` | Synchronous DB calls |

---

# OUTPUT FORMAT

For EACH file, output:

```python
# FILE: predict/core/ai/uncertainty_estimator.py
<complete file content>
```

Then the next file:

```python
# FILE: predict/core/ai/temporal_consistency.py
<complete file content>
```

And so on for ALL files.

## Files to output (in this order):

### New files (5):
1. `predict/core/ai/uncertainty_estimator.py`
2. `predict/core/ai/temporal_consistency.py`
3. `predict/core/ai/abstention_manager.py`
4. `predict/core/ai/hindsight_collector.py`
5. `predict/core/db/models/hindsight.py`

### Fixed files (ALL datetime violations — complete file rewrites):
6. `predict/core/monitoring/health.py` (FULL REWRITE — 20+ violations)
7. `predict/core/ai/unified_ai_module.py` (fix datetime + add integration)
8. `predict/core/ai/ensemble_voter.py` (fix datetime + add uncertainty)
9. `predict/core/ai/lstm_predictor.py` (fix datetime)
10. `predict/core/ai/llm/assistant.py` (fix datetime)
11. `predict/core/middleware/audit.py` (fix datetime)
12. `predict/core/middleware/error_handler.py` (fix datetime)
13. `predict/core/middleware/rate_limiter.py` (fix datetime)
14. `predict/core/api/v1/dtc.py` (fix datetime)
15. `predict/core/api/v1/ai_chat.py` (fix datetime)
16. `predict/core/api/v1/dashboard.py` (fix datetime)
17. `predict/core/api/v1/health.py` (fix datetime)
18. `predict/core/api/v1/legal.py` (fix datetime)
19. `predict/core/api/v1/vehicle_data.py` (fix datetime)
20. `predict/core/api/v1/predictions.py` (fix datetime)
21. `predict/core/services/export_service.py` (fix datetime)
22. `predict/core/monitoring/metrics.py` (fix datetime)
23. `predict/core/jobs/tasks/cleanup_tasks.py` (fix datetime)
24. `predict/core/jobs/tasks/backup_tasks.py` (fix datetime)
25. `predict/core/jobs/tasks/pdf_tasks.py` (fix datetime)
26. `predict/core/db/base.py` (fix datetime in base model)
27. `predict/desktop/tabs/chat.py` (fix datetime)
28. `predict/desktop/tabs/ai_training.py` (fix datetime)
29. `predict/desktop/tabs/reports.py` (fix datetime)

That is 29 files total. Output ALL of them as complete Python files.

---

# FINAL WARNING

If your response contains analysis, questions, options, or anything other than complete Python code files — you have failed.

START WRITING CODE NOW. File 1: `predict/core/ai/uncertainty_estimator.py`
