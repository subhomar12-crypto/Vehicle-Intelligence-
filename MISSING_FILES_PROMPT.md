# WORK ORDER: Create 40 Files — START IMMEDIATELY

## ⛔ STOP — READ THIS FIRST

**DO NOT** analyze the project.
**DO NOT** ask which option I want.
**DO NOT** explain what's missing or give a status report.
**DO NOT** ask "do you want me to create these files?" — YES, THAT IS THE ENTIRE POINT.
**DO NOT** give me recommendations, options A/B/C, or a "my recommendation" section.
**DO NOT** respond with anything other than actual Python code files.

**YOUR ONLY JOB**: Read the specs below and **output all 40 complete Python files**. Start with file #1 and don't stop until file #40 is done. Every file must contain full, working, production-grade Python code.

If you respond with analysis, questions, options, or anything that is NOT the actual file contents — you have failed.

---

## YOUR ROLE

You are a **Senior Python Engineer** executing a work order. You write production-grade code. You do NOT cut corners. You do NOT write stubs. You do NOT use `pass`. You do NOT skip methods. Every file must be **fully functional** — real logic, real error handling, real algorithms.

**DO NOT BE LAZY.** If a spec says "5 methods", write all 5 with full implementations. If it says "hardcoded DAG", build the entire graph with all nodes and edges. If it says "rolling stats with windows 5/10/20", implement all three. No shortcuts. No "TODO: implement later". The only acceptable TODO is for external API calls requiring real credentials.

**OUTPUT FORMAT**: For each file, output:
```
### File N: `path/to/file.py`
```python
# full file contents here
```
```

Start with File 1. End with File 40. Nothing else.

---

## PROJECT CONTEXT

- **Project**: PREDICT Vehicle Intelligence Platform
- **Stack**: FastAPI + PySide6 + PostgreSQL + Redis + SQLAlchemy 2.0 (async)
- **Location**: `C:\D Drive\Predict\`
- **Python package**: `predict/`
- **Version**: 3.0.0

The `predict/` package already has a working core — config, database models, base repository, API routes, services, middleware, monitoring. Your job is to create **40 additional files** that complete the architecture. Two files from the original 42 already exist (`model_registry.py` and `rul_estimation.py`), so skip those.

---

## NON-NEGOTIABLE RULES

Break ANY of these and the code is rejected:

| # | Rule |
|---|------|
| 1 | **Timestamps are `float`** (Unix epoch via `time.time()`). NEVER use `datetime` objects for timestamps. |
| 2 | **SQLAlchemy 2.0 syntax**: `Mapped[type]` + `mapped_column()`. |
| 3 | **All DB operations are async**: `AsyncSession`, `async def`, `await`. |
| 4 | **Repositories inherit `BaseRepository[ModelT]`** and call `super().__init__(session, Model)`. |
| 5 | **Desktop uses PySide6** — NOT PyQt5, NOT PyQt6. Import from `PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`. |
| 6 | **Logging**: Every file has `logger = logging.getLogger(__name__)` at module level. |
| 7 | **No hardcoded paths**: Use `from predict.core.config import get_config` then `config = get_config()` for all directories. |
| 8 | **Every file has a module docstring** (triple-quoted string at top). |
| 9 | **ORM models already exist** — import them, do NOT recreate them. |
| 10 | **Each file must be FUNCTIONAL** — real logic, real algorithms, real error handling. `pass` is not acceptable. |

---

## EXISTING CODE YOU MUST MATCH (REAL FILES FROM THE CODEBASE)

### REAL Pattern A: BaseRepository (from `predict/core/db/repositories/base.py`)

```python
"""
Base repository with common async CRUD operations.

All domain repositories inherit from this.
"""

from typing import TypeVar, Generic, Type, Optional, List, Any

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async CRUD repository."""

    def __init__(self, session: AsyncSession, model: Type[ModelT]):
        self.session = session
        self.model = model

    async def get_by_id(self, id_value: int) -> Optional[ModelT]:
        return await self.session.get(self.model, id_value)

    async def get_all(self, limit: int = 100, offset: int = 0) -> List[ModelT]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelT:
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT, **kwargs) -> ModelT:
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def exists(self, **filters) -> bool:
        stmt = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar_one() > 0
```

### REAL Pattern B: Existing Repository (from `predict/core/db/repositories/vehicle_repo.py`)

```python
"""
Vehicle profile and data repository.
"""

from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.vehicle import VehicleProfile, VehicleData, ServiceRecord
from predict.core.db.repositories.base import BaseRepository


class VehicleProfileRepository(BaseRepository[VehicleProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, VehicleProfile)

    async def get_by_plate(self, plate: str) -> Optional[VehicleProfile]:
        stmt = select(VehicleProfile).where(VehicleProfile.license_plate == plate)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_vin(self, vin: str) -> Optional[VehicleProfile]:
        stmt = select(VehicleProfile).where(VehicleProfile.vin == vin)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class VehicleDataRepository(BaseRepository[VehicleData]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, VehicleData)

    async def get_latest(self, profile_id: int, limit: int = 50) -> List[VehicleData]:
        stmt = (
            select(VehicleData)
            .where(VehicleData.profile_id == profile_id)
            .order_by(desc(VehicleData.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_history(
        self, profile_id: int, start_ts: float, end_ts: float
    ) -> List[VehicleData]:
        stmt = (
            select(VehicleData)
            .where(
                VehicleData.profile_id == profile_id,
                VehicleData.timestamp >= start_ts,
                VehicleData.timestamp <= end_ts,
            )
            .order_by(VehicleData.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

### REAL Pattern C: AI Module (from `predict/core/ai/unified_ai_module.py`)

```python
"""
Unified AI module - orchestrates all prediction models.
"""

import logging
from typing import Dict, Any, List, Optional

from predict.core.ai.lstm_predictor import LSTMPredictor
from predict.core.ai.ensemble_voter import EnsembleVoter
from predict.core.ai.explainability import ExplainabilityEngine

logger = logging.getLogger(__name__)


class UnifiedAI:
    """Unified AI interface for vehicle intelligence."""

    def __init__(self):
        self.lstm = LSTMPredictor()
        self.ensemble = EnsembleVoter()
        self.explainer = ExplainabilityEngine()
        self._setup_ensemble()

    def _setup_ensemble(self) -> None:
        self.ensemble.register_model("lstm", self.lstm, weight=1.5)

    async def analyze_vehicle_health(
        self,
        vehicle_id: int,
        obd_data: List[Dict[str, Any]],
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        # ... full implementation with real logic
```

### REAL Pattern D: Desktop Main Window (from `predict/desktop/main_window.py`)

```python
"""
PySide6 Main Window for PREDICT Desktop.
"""

import logging
import sys
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTextEdit,
    QStatusBar, QMessageBox, QProgressBar,
)
from PySide6.QtCore import QTimer, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QFont

from predict.core.version import APP_NAME, APP_VERSION
from predict.desktop.server_thread import get_server_manager

logger = logging.getLogger(__name__)
```

### REAL Pattern E: LLM Assistant (from `predict/core/ai/llm/assistant.py`)

```python
"""
LLM Assistant for vehicle diagnostics and recommendations.
Uses local GGUF models via llama-cpp-python.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from predict.core.ai.model_loader import get_model_loader
from predict.core.config import get_config

logger = logging.getLogger(__name__)


class LLMAssistant:
    def __init__(self, model_filename: Optional[str] = None):
        self.config = get_config()
        self.model_path: Optional[Path] = None
        self.llm = None
        self._load_model(model_filename or self._get_default_model())
```

---

## CONFIG PATHS AVAILABLE (from `PredictConfig`)

When you call `config = get_config()`, these paths are available:

| Property | Resolves To |
|----------|-------------|
| `config.ROOT_DIR` | `C:\D Drive\Predict\` |
| `config.DATA_DIR` | `ROOT_DIR / "data"` |
| `config.LOGS_DIR` | `DATA_DIR / "logs"` |
| `config.BACKUPS_DIR` | `DATA_DIR / "backups"` |
| `config.EXPORTS_DIR` | `DATA_DIR / "exports"` |
| `config.PARQUET_DIR` | `DATA_DIR / "parquet"` |
| `config.CACHE_DIR` | `DATA_DIR / "cache"` |
| `config.MODELS_DIR` | `ROOT_DIR / "models"` |
| `config.GGUF_DIR` | `MODELS_DIR / "gguf"` |
| `config.LSTM_MODELS_DIR` | `MODELS_DIR / "lstm"` |
| `config.CONFIG_DIR` | `ROOT_DIR / "config"` |
| `config.PREDICT_DATA_DIR` | `ROOT_DIR / "PredictData"` |
| `config.REPORTS_DIR` | `PREDICT_DATA_DIR / "reports"` |
| `config.AI_DIR` | `PREDICT_DATA_DIR / "ai"` |
| `config.AI_MODELS_DIR` | `AI_DIR / "models"` |
| `config.AI_RAW_DIR` | `AI_DIR / "raw"` |
| `config.AI_TRAINING_SETS_DIR` | `AI_DIR / "cleaned" / "training_sets"` |
| `config.CUSTOMERS_DIR` | `PREDICT_DATA_DIR / "customers"` |
| `config.SECRET_KEY` | From `Secrets` / env var |
| `config.DATABASE_URL` | PostgreSQL async connection string |
| `config.REDIS_URL` | Redis connection |

---

## ORM MODELS (ALREADY EXIST — IMPORT ONLY, DO NOT RECREATE)

Located in `predict/core/db/models/`:

- **user.py**: `User`, `ApiKey`, `Entitlement`, `RateLimit`, `UsageCounter`, `TierPreset`, `DriverAssignment`, `UserFeatureOverride`, `PricingConfig`
- **vehicle.py**: `VehicleProfile`, `VehicleData`, `OBDRecord`, `TelemetryRecord`, `SensorConfig`
- **dtc.py**: `DTCCode`, `DTCHistory`
- **guardian.py**: `Guardian`, `VehicleGuardian`, `Alert`, `GuardianCommand`, `LocationRequest`, `ConsentRecord`, `GuardianTelemetry`, `DrivingEvent`
- **trip.py**: `Trip`, `TripEvent`, `Driver`, `VehicleDriver`, `DriverSession`, `DriverInviteCode`, `DriverBehaviorSummary`, `GuardianTrip`
- **prediction.py**: `Prediction`, `MLTrainingLabel`, `MLAggregatedFeature`, `FleetBaseline`, `OBDSensorConfig`
- **subscription.py**: `FleetInvite`, `Geofence`, `GeofenceEvent`, `TierUpgradeRequest`, `SubscriptionAuditLog`
- **audit.py**: `AuditLog`, `VerificationCode`, `VerificationSession`, `IdempotencyCache`, `FailedOperation`, `DataExportConfig`, `ExportHistory`

## EXISTING MODULES (ALREADY EXIST — DO NOT RECREATE)

- `predict/core/ai/model_registry.py` — `ModelRegistry` class (ALREADY EXISTS, SKIP)
- `predict/core/ai/rul_estimation.py` — `RULEstimator` class (ALREADY EXISTS, SKIP)
- `predict/core/ai/ensemble_voter.py` — `EnsembleVoter` class
- `predict/core/ai/explainability.py` — `ExplainabilityEngine` class
- `predict/core/ai/lstm_predictor.py` — `LSTMPredictor` class
- `predict/core/ai/model_loader.py` — `get_model_loader()` function
- `predict/core/ai/unified_ai_module.py` — `UnifiedAI` class
- `predict/core/ai/llm/assistant.py` — `LLMAssistant` class
- `predict/core/services/websocket_service.py` — `ConnectionManager` class with `ws_manager` singleton
- `predict/core/db/repositories/base.py` — `BaseRepository[ModelT]` generic class
- `predict/core/db/repositories/user_repo.py` — User repository
- `predict/core/db/repositories/vehicle_repo.py` — Vehicle repository
- `predict/core/security/secrets_loader.py` — `Secrets` (pydantic-settings)

---

## FILES TO CREATE (40 total)

All paths relative to `C:\D Drive\Predict\`. Create each file at that exact path.

---

### GROUP 1: AI MODULES (17 files)

All under `predict/core/ai/`

---

#### 1. `predict/core/ai/cnn_lstm_model.py`
**Purpose**: CNN-LSTM hybrid for temporal pattern recognition in OBD data
**Class**: `CNNLSTM`
**Constructor**: `__init__(input_dim=12, hidden_dim=64, num_layers=2, output_dim=1)`
**Methods**:
- `build_model()` — construct Conv1D + LSTM + Dense layers (numpy-based if torch unavailable)
- `predict(sequence_data: np.ndarray) -> float` — failure probability 0-1
- `train(X_train: np.ndarray, y_train: np.ndarray, epochs=50, batch_size=32)` — train with validation split
- `save_model(path: Path)` / `load_model(path: Path)` — persistence
**Dependencies**: `numpy` required; `try: import torch` with numpy-only fallback (implement a simple numpy neural net for forward pass if torch unavailable)

---

#### 2. `predict/core/ai/attention_lstm.py`
**Purpose**: LSTM with self-attention for long-range OBD dependencies
**Class**: `AttentionLSTM`
**Constructor**: `__init__(input_dim=12, hidden_dim=64, num_heads=4, output_dim=1)`
**Methods**:
- `predict(sequence_data: np.ndarray) -> Dict[str, Any]` — returns `{"failure_probability": float, "attention_weights": np.ndarray}`
- `get_attention_map() -> np.ndarray` — last computed attention weights
- `train(X_train, y_train, epochs, batch_size)`
- `_compute_attention(query, key, value) -> np.ndarray` — scaled dot-product attention
**Dependencies**: Same as cnn_lstm — torch optional, numpy fallback

---

#### 3. `predict/core/ai/autoencoder.py`
**Purpose**: LSTM autoencoder for anomaly detection via reconstruction error
**Class**: `LSTMAutoencoder`
**Constructor**: `__init__(input_dim=12, encoding_dim=6, sequence_length=20)`
**Methods**:
- `train(normal_data: np.ndarray, epochs=100)` — train on normal OBD patterns, store threshold
- `predict(data: np.ndarray) -> float` — reconstruction error (higher = more anomalous)
- `get_anomaly_score(data: np.ndarray) -> float` — normalized 0-1 score
- `get_reconstruction(data: np.ndarray) -> np.ndarray` — reconstructed input for visual comparison
- `_encode(data) -> np.ndarray` / `_decode(encoded) -> np.ndarray`
**Logic**: Compute MSE between input and reconstruction. Threshold = mean + 2*std of training errors.

---

#### 4. `predict/core/ai/failure_engine.py`
**Purpose**: Predictive failure using RandomForest + XGBoost + LightGBM ensemble
**Class**: `PredictiveFailureEngine`
**Constructor**: `__init__()`
**Methods**:
- `train(features_df, labels)` — train all available models
- `predict(features: dict) -> dict` — returns `{"random_forest": float, "xgboost": float, "lightgbm": float, "ensemble": float, "confidence": float}`
- `get_feature_importance() -> Dict[str, float]` — averaged importance across models
- `get_model_status() -> Dict[str, bool]` — which models are loaded
- `save_models(directory: Path)` / `load_models(directory: Path)`
**Dependencies**: `from sklearn.ensemble import RandomForestClassifier` (required), `try: import xgboost`, `try: import lightgbm` — use whatever is available, sklearn is the minimum

---

#### 5. `predict/core/ai/feature_engineering.py`
**Purpose**: Advanced feature derivation from raw OBD sensor data
**Class**: `AdvancedFeatureEngineering`
**Methods**:
- `extract_features(obd_records: list) -> Dict[str, float]` — master method, returns 30+ features
- `_compute_rolling_stats(values: list, window: int) -> Dict[str, float]` — mean, std, trend for given window
- `_compute_rate_of_change(values: list) -> Dict[str, float]` — first/second derivatives
- `_compute_cross_sensor_features(data: dict) -> Dict[str, float]` — RPM/speed ratio, load/temp correlation, battery/engine_load ratio, fuel_trim imbalance
- `_compute_degradation_indicators(history: list) -> Dict[str, float]` — wear metrics based on sensor drift over time
**Features to compute** (implement ALL of these):
  - Rolling mean/std for windows [5, 10, 20] for RPM, speed, coolant_temp, battery_voltage
  - Rate of change (derivative) for RPM, coolant_temp, battery_voltage
  - Min/max delta within window for each sensor
  - Cross-sensor: RPM_speed_ratio, coolant_load_ratio, battery_engine_load_ratio
  - Fuel trim imbalance: abs(LTFT_bank1 - LTFT_bank2)
  - Degradation: linear trend slope over full history for each sensor

---

#### 6. `predict/core/ai/vehicle_baseline.py`
**Purpose**: Per-vehicle baseline learning — what is "normal" for THIS specific car
**Class**: `VehicleBaselineLearning`
**Constructor**: `__init__()`
**Methods**:
- `learn_baseline(profile_id: int, obd_history: list) -> dict` — compute normal ranges, save to file
- `get_baseline(profile_id: int) -> Optional[dict]` — load from file, returns `{sensor: {mean, std, min, max, p5, p95}}`
- `is_anomalous(profile_id: int, current_values: dict) -> Dict[str, bool]` — per-sensor anomaly check
- `_compute_z_score(value: float, mean: float, std: float) -> float`
- `_compute_percentiles(values: list) -> Dict[str, float]` — p5, p25, p50, p75, p95
**Storage**: JSON files at `config.DATA_DIR / "baselines" / f"{profile_id}.json"`

---

#### 7. `predict/core/ai/ai_bridge.py`
**Purpose**: THE KEY FILE — connects UnifiedAI predictions with LLM explanations
**Class**: `AIBridge`
**Constructor**: `__init__()`
**Methods**:
- `get_ai_enriched_context(obd_data: dict, profile: dict, history: list, dtcs: list) -> str` — formatted AI analysis string for LLM
- `chat_with_ai_context(user_message: str, obd_data: dict, profile: dict, history: list, dtcs: list) -> str` — full LLM response
- `format_predictions_for_llm(intelligence: dict) -> str` — structured text block
**Logic flow**:
1. Import `from predict.core.ai.unified_ai_module import UnifiedAI`
2. Import `from predict.core.ai.llm.assistant import LLMAssistant`
3. Call `UnifiedAI().analyze_vehicle_health()` to get predictions
4. Format subsystem scores, failure predictions, correlations into structured text
5. Build system prompt + AI analysis context + user question
6. Call `LLMAssistant().chat()` for natural language response

---

#### 8. `predict/core/ai/causal_graph.py`
**Purpose**: Root cause analysis via DAG of vehicle system relationships
**Class**: `CausalGraph`
**Data**: Build the COMPLETE hardcoded DAG (not a placeholder — all these edges):
```
alternator_failing -> [low_battery_voltage, engine_load_increase]
thermostat_stuck -> [high_coolant_temp]
low_coolant -> [high_coolant_temp, engine_overheating]
vacuum_leak -> [lean_fuel_trim, rough_idle, misfire]
worn_spark_plugs -> [misfire, reduced_power, fuel_efficiency_drop]
clogged_fuel_filter -> [low_fuel_pressure, engine_hesitation]
failing_water_pump -> [high_coolant_temp, coolant_leak]
worn_timing_belt -> [engine_noise, reduced_power, timing_drift]
bad_oxygen_sensor -> [rich_fuel_trim, poor_fuel_economy, high_emissions]
failing_catalytic_converter -> [reduced_power, rotten_egg_smell, high_emissions, P0420_code]
worn_brake_pads -> [brake_noise, increased_stopping_distance, brake_vibration]
low_transmission_fluid -> [harsh_shifting, transmission_slippage, overheating_transmission]
```
**Methods**:
- `find_root_cause(symptoms: list) -> List[Dict[str, Any]]` — returns ranked root causes with probability scores (based on how many symptoms match each cause's output set)
- `get_related_symptoms(root_cause: str) -> List[str]` — all expected symptoms
- `explain_chain(root_cause: str) -> str` — human-readable cause-effect chain: "alternator_failing -> low_battery_voltage -> engine_load_increase"
- `get_all_causes() -> List[str]` — list all known root causes

---

#### 9. `predict/core/ai/survival_analysis.py`
**Purpose**: Weibull time-to-failure with confidence bands
**Class**: `SurvivalAnalyzer`
**Methods**:
- `fit_weibull(degradation_data: list) -> Dict[str, float]` — returns `{shape, scale, r_squared}`
- `predict_failure_distribution(component: str, current_data: list) -> Dict[str, float]` — returns `{p50_days, p80_days, p95_days, median_days}`
- `get_optimal_maintenance_window(failure_dist: dict) -> Tuple[int, int]` — (earliest_day, latest_day) = (p50, p80)
- `_weibull_cdf(t, shape, scale) -> float` — cumulative distribution function
- `_weibull_pdf(t, shape, scale) -> float` — probability density function
**Dependencies**: `try: from lifelines import WeibullFitter` — if unavailable, implement Weibull fitting with numpy (maximum likelihood estimation via scipy.optimize or manual Newton-Raphson)

---

#### 10. `predict/core/ai/anomaly_detector.py`
**Purpose**: Multi-method anomaly detection with context-awareness
**Class**: `AnomalyDetector`
**Constructor**: `__init__()`
**Methods**:
- `detect_anomalies(obd_data: dict, profile_id: int) -> Dict[str, Dict[str, Any]]` — per-sensor anomaly report with score, is_anomalous, method_used
- `_isolation_forest_score(data: np.ndarray) -> float` — multivariate anomaly score
- `_zscore_detection(value: float, baseline_mean: float, baseline_std: float) -> bool` — threshold at |z| > 3
- `_context_aware_thresholds(vehicle_state: str) -> Dict[str, Dict[str, float]]` — returns {sensor: {min, max}} adjusted for state
**Vehicle states and their adjusted thresholds** (implement ALL):
  - `idle`: RPM 600-900, speed 0, coolant 80-100, battery 13.5-14.5
  - `city`: RPM 800-3000, speed 10-60, coolant 85-105, battery 13.5-14.7
  - `highway`: RPM 1500-3500, speed 60-140, coolant 90-110, battery 14.0-14.8
  - `cold_start`: RPM 900-1500, speed 0, coolant 10-60, battery 12.0-14.5
  - `hot_weather`: RPM same as normal, coolant thresholds +10C, battery -0.3V lower bounds
**Dependencies**: `try: from sklearn.ensemble import IsolationForest` with z-score-only fallback

---

#### 11. `predict/core/ai/failure_correlation.py`
**Purpose**: Detect multi-sensor failure patterns
**Class**: `FailureCorrelationEngine`
**Hardcoded correlation patterns** (implement ALL as structured rules):
1. High RPM (>4000) + Low oil pressure (<20 PSI) = bearing_wear_risk (severity: critical)
2. High coolant temp (>105C) + Low RPM (<1000) = thermostat_stuck_closed (severity: high)
3. Rich fuel trim both banks (LTFT > +15%) + misfire DTC = injector_failure (severity: high)
4. Battery voltage declining (trend < -0.1V/week) + engine load rising (trend > +5%/week) = alternator_failing (severity: critical)
5. Speed/RPM ratio anomaly (deviation > 15% from baseline) = transmission_slippage (severity: critical)
6. High exhaust temp + reduced power DTC = catalytic_converter_failing (severity: medium)
7. Low fuel pressure + engine hesitation DTC = fuel_pump_weak (severity: high)
8. Coolant temp oscillation (std > 10C in 5min) = thermostat_intermittent (severity: medium)
**Methods**:
- `find_correlations(obd_data: dict, dtcs: list) -> List[Dict[str, Any]]` — evaluate ALL patterns, return matched ones with severity
- `get_risk_assessment(correlations: list) -> List[Dict[str, Any]]` — sort by severity, add recommended actions

---

#### 12. `predict/core/ai/fleet_learning.py`
**Purpose**: Cross-vehicle comparison — this car vs. fleet of same make/model/year
**Class**: `FleetLearningAggregator`
**Constructor**: `__init__()`
**Methods**:
- `async get_fleet_comparison(profile_id: int, component: str, value: float) -> Dict[str, Any]` — percentile rank among similar vehicles (uses DB)
- `async aggregate_fleet_stats(make: str, model: str, year: int) -> Dict[str, Dict[str, float]]` — fleet averages per sensor
- `async get_fleet_failure_rates(make: str, model: str, year: int) -> Dict[str, float]` — component failure rates
**DB access**: Uses `from predict.core.db.session import get_db_session` to query `VehicleProfile`, `Prediction`, `FleetBaseline` tables

---

#### 13. `predict/core/ai/recall_monitor.py`
**Purpose**: NHTSA recall API integration
**Class**: `RecallMonitor`
**Constructor**: `__init__()` — init cache dict, cache TTL = 86400 (24 hours)
**Methods**:
- `async check_recalls(make: str, model: str, year: int) -> List[Dict[str, Any]]` — fetch from NHTSA API
- `async check_tsbs(make: str, model: str, year: int) -> List[Dict[str, Any]]` — technical service bulletins
- `async _fetch_nhtsa(url: str) -> Optional[dict]` — HTTP GET with timeout, retry, caching
- `_is_cache_valid(key: str) -> bool` — check if cached result is still fresh
**API URLs**:
  - Recalls: `https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}`
  - Complaints: `https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}`
**Dependencies**: `try: import httpx` -> `try: import aiohttp` -> fallback to `urllib.request` (sync wrapped in executor)

---

#### 14. `predict/core/ai/llm/model_config.py`
**Purpose**: LLM model configurations
**Content**:
```python
from dataclasses import dataclass
from predict.core.config import get_config

@dataclass
class LLMModelConfig:
    name: str
    file_path: str  # relative to config.GGUF_DIR
    context_length: int
    gpu_layers: int
    temperature: float
    system_prompt: str

AVAILABLE_MODELS = {
    "qwen2.5-7b": LLMModelConfig(
        name="qwen2.5-7b",
        file_path="qwen2.5-7b-instruct-q4_k_m.gguf",
        context_length=8192,
        gpu_layers=35,
        temperature=0.3,
        system_prompt="You are PREDICT AI, an expert automotive diagnostic assistant..."
    ),
    "phi-3-mini": LLMModelConfig(
        name="phi-3-mini",
        file_path="phi-3-mini-4k-instruct-q4_k_m.gguf",
        context_length=4096,
        gpu_layers=32,
        temperature=0.3,
        system_prompt="You are PREDICT AI, an expert automotive diagnostic assistant..."
    ),
}

def get_default_model() -> str:
    return "qwen2.5-7b"

def get_model_config(name: str) -> LLMModelConfig:
    return AVAILABLE_MODELS[name]

def get_model_path(name: str) -> "Path":
    config = get_config()
    model_config = AVAILABLE_MODELS[name]
    return config.GGUF_DIR / model_config.file_path
```

---

#### 15. `predict/core/ai/training/data_pipeline.py`
**Purpose**: Async data pipeline reads training data from PostgreSQL
**Class**: `TrainingDataPipeline`
**Methods**:
- `async fetch_training_data(profile_id: int, days_back: int = 30) -> List[dict]` — query OBDRecord table
- `async fetch_labeled_data() -> Tuple[np.ndarray, np.ndarray]` — features + labels from MLTrainingLabel
- `prepare_sequences(records: list, window_size: int = 20) -> Tuple[np.ndarray, np.ndarray]` — sliding window for LSTM input
- `_normalize_features(data: np.ndarray) -> np.ndarray` — min-max normalization
**Imports**: `from predict.core.db.session import get_db_session`, models from `predict.core.db.models.vehicle` and `predict.core.db.models.prediction`

---

#### 16. `predict/core/ai/training/parquet_writer.py`
**Purpose**: Buffered Parquet file writes for training data lake
**Class**: `ParquetWriter`
**Constructor**: `__init__(buffer_size=1000, flush_interval_seconds=3600)`
**Methods**:
- `add_record(record: dict)` — append to buffer, auto-flush if buffer full
- `flush()` — write buffer to timestamped Parquet file
- `_write_parquet(records: list, path: Path)` — actual write
- `_write_csv_fallback(records: list, path: Path)` — CSV if pyarrow unavailable
- `get_stats() -> dict` — buffer size, total written, last flush time
**Storage**: `config.PARQUET_DIR / f"training_{int(time.time())}.parquet"`
**Dependencies**: `try: import pyarrow.parquet as pq` with CSV fallback

---

#### 17. `predict/core/ai/training/auto_retrain.py`
**Purpose**: Automatic model retraining trigger logic
**Class**: `AutoRetrainer`
**Constructor**: `__init__(accuracy_threshold=0.85, min_new_records=500)`
**Methods**:
- `async check_retrain_needed(model_name: str) -> bool` — check accuracy drift below threshold OR new data > min_records since last train
- `async trigger_retrain(model_name: str) -> Dict[str, Any]` — execute retrain pipeline, return metrics
- `get_retrain_status() -> Dict[str, Dict[str, Any]]` — per-model status with last_trained, accuracy, needs_retrain
- `_check_accuracy_drift(model_name: str) -> float` — compare recent prediction accuracy vs training accuracy
**Uses**: `ModelRegistry` (existing) for model metadata, `TrainingDataPipeline` for data

---

### GROUP 2: REPOSITORIES (5 files)

All under `predict/core/db/repositories/`. Each inherits `BaseRepository[ModelT]`. Follow the EXACT pattern from `vehicle_repo.py` shown above.

---

#### 18. `predict/core/db/repositories/guardian_repo.py`
**Models**: Import `Guardian`, `VehicleGuardian`, `Alert`, `GuardianCommand` from `predict.core.db.models.guardian`
**Classes**:
- `GuardianRepository(BaseRepository[Guardian])`:
  - `get_by_guardian_id(guardian_id: str) -> Optional[Guardian]`
  - `get_vehicles_for_guardian(guardian_id: str) -> List[VehicleGuardian]`
  - `get_guardians_for_vehicle(profile_id: int) -> List[VehicleGuardian]`
- `AlertRepository(BaseRepository[Alert])`:
  - `get_recent_alerts(guardian_id: str, limit: int = 20) -> List[Alert]`
  - `get_unread_alerts(guardian_id: str) -> List[Alert]`
  - `mark_as_read(alert_id: int) -> None`
- `GuardianCommandRepository(BaseRepository[GuardianCommand])`:
  - `get_pending_commands(profile_id: int) -> List[GuardianCommand]`
  - `mark_executed(command_id: int) -> None`

---

#### 19. `predict/core/db/repositories/trip_repo.py`
**Models**: Import `Trip`, `TripEvent`, `DriverBehaviorSummary` from `predict.core.db.models.trip`
**Classes**:
- `TripRepository(BaseRepository[Trip])`:
  - `get_trips_for_profile(profile_id: int, limit: int = 50) -> List[Trip]`
  - `get_active_trip(profile_id: int) -> Optional[Trip]` — where `end_time IS NULL`
  - `get_trips_in_range(profile_id: int, start_ts: float, end_ts: float) -> List[Trip]`
- `TripEventRepository(BaseRepository[TripEvent])`:
  - `get_events_for_trip(trip_id: int) -> List[TripEvent]`
- `DriverBehaviorRepository(BaseRepository[DriverBehaviorSummary])`:
  - `get_driver_summary(driver_id: int) -> Optional[DriverBehaviorSummary]`
  - `get_summaries_for_profile(profile_id: int) -> List[DriverBehaviorSummary]`

---

#### 20. `predict/core/db/repositories/prediction_repo.py`
**Models**: Import `Prediction`, `MLTrainingLabel`, `MLAggregatedFeature` from `predict.core.db.models.prediction`
**Classes**:
- `PredictionRepository(BaseRepository[Prediction])`:
  - `get_active_predictions(profile_id: int) -> List[Prediction]` — where `is_active == True`
  - `get_prediction_history(profile_id: int, limit: int = 100) -> List[Prediction]`
  - `get_by_component(profile_id: int, component: str) -> List[Prediction]`
- `MLTrainingLabelRepository(BaseRepository[MLTrainingLabel])`:
  - `create_training_label(prediction_id: int, actual_outcome: str) -> MLTrainingLabel`
  - `get_unlabeled(limit: int = 100) -> List[MLTrainingLabel]`

---

#### 21. `predict/core/db/repositories/subscription_repo.py`
**Models**: Import `FleetInvite`, `Geofence`, `TierUpgradeRequest` from `predict.core.db.models.subscription`
**Classes**:
- `GeofenceRepository(BaseRepository[Geofence])`:
  - `get_active_geofences(profile_id: int) -> List[Geofence]`
  - `get_geofence_by_name(profile_id: int, name: str) -> Optional[Geofence]`
- `FleetInviteRepository(BaseRepository[FleetInvite])`:
  - `get_invite_by_code(code: str) -> Optional[FleetInvite]`
  - `get_pending_invites(user_id: int) -> List[FleetInvite]`
- `TierUpgradeRepository(BaseRepository[TierUpgradeRequest])`:
  - `get_pending_upgrades() -> List[TierUpgradeRequest]`
  - `approve_upgrade(request_id: int) -> TierUpgradeRequest`

---

#### 22. `predict/core/db/repositories/audit_repo.py`
**Models**: Import `AuditLog`, `FailedOperation` from `predict.core.db.models.audit`
**Classes**:
- `AuditLogRepository(BaseRepository[AuditLog])`:
  - `log_action(action: str, user_id: int, details: str, ip: str, request_id: str) -> AuditLog`
  - `get_audit_trail(user_id: int, limit: int = 100) -> List[AuditLog]`
  - `get_by_action(action: str, limit: int = 50) -> List[AuditLog]`
- `FailedOperationRepository(BaseRepository[FailedOperation])`:
  - `get_failed_operations(status: str, limit: int = 50) -> List[FailedOperation]`
  - `mark_operation_completed(op_id: int) -> FailedOperation`
  - `get_retry_candidates() -> List[FailedOperation]` — where status == "pending" and retry_count < max_retries

---

### GROUP 3: API ROUTER (1 file)

#### 23. `predict/core/api/v1/websockets.py`
**Purpose**: WebSocket endpoints for real-time data streaming
**NOTE**: The `ConnectionManager` class already exists at `predict/core/services/websocket_service.py`. Import `ws_manager` from there.
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from predict.core.services.websocket_service import ws_manager

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await ws_manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            await ws_manager.send_to_user(user_id, {"type": "echo", "data": data})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, user_id)
```
Add additional endpoints: `/ws/vehicle/{profile_id}/live` for live OBD streaming, `/ws/alerts/{user_id}` for real-time alerts.

---

### GROUP 4: SECURITY (2 files)

#### 24. `predict/core/security/hashing.py`
**Purpose**: Centralized password/API key hashing
**Functions** (module-level, not a class):
- `hash_password(password: str) -> str` — bcrypt, rounds=12
- `verify_password(password: str, hashed: str) -> bool`
- `hash_api_key(key: str) -> str` — bcrypt, rounds=10
- `verify_api_key(key: str, hashed: str) -> bool`
- `hash_sha256(value: str) -> str` — SHA-256 hex digest (for non-security checksums)
**Dependencies**: `try: import bcrypt` with `hashlib.pbkdf2_hmac` fallback (NOT plaintext)

#### 25. `predict/core/security/jwt_handler.py`
**Purpose**: JWT creation/verification for Guardian mobile auth
**Functions**:
- `create_token(guardian_id: str, expires_hours: int = 24) -> str`
- `verify_token(token: str) -> Optional[dict]` — returns decoded payload or None
- `decode_token(token: str) -> dict` — raises `ValueError` on invalid/expired
**Secret**: `from predict.core.security.secrets_loader import get_secrets` then `secrets.SECRET_KEY`
**Dependencies**: `try: import jwt` (PyJWT) with HMAC-SHA256 + base64 manual fallback

---

### GROUP 5: MONITORING (1 file)

#### 26. `predict/core/monitoring/sentry.py`
**Purpose**: Sentry error tracking (graceful no-op if not installed)
**Functions**:
- `init_sentry(dsn: Optional[str] = None)` — call `sentry_sdk.init()` if available
- `capture_exception(error: Exception, context: dict = None)` — report error
- `set_user_context(user_id: int, email: str = "")` — set user scope
- `add_breadcrumb(message: str, category: str = "general", level: str = "info")`
**Pattern**: Every function wraps in `try: ... except ImportError: pass` so the app never crashes if Sentry SDK isn't installed

---

### GROUP 6: JOBS (1 file)

#### 27. `predict/core/jobs/tasks/parquet_tasks.py`
**Purpose**: ARQ background task for Parquet writes
**Functions**:
- `async def flush_parquet_buffer(ctx: dict)` — instantiate `ParquetWriter`, call `flush()`
- `async def compact_parquet_files(ctx: dict)` — read small Parquet files from `config.PARQUET_DIR`, merge into larger ones, delete originals
**Import**: `from predict.core.ai.training.parquet_writer import ParquetWriter`

---

### GROUP 7: DESKTOP GUI (13 files)

All use PySide6. Each tab is `QWidget` subclass with `_setup_ui()`.

**IMPORTANT — EXISTING DESKTOP UI STYLING TO MATCH**:

The existing `main_pyside.py` uses a dark professional theme. ALL new tabs MUST match this style:

```python
# Color scheme from existing ProfessionalTheme:
BACKGROUND_PRIMARY = "#0D1117"     # Main background
BACKGROUND_SECONDARY = "#21262D"   # Card/panel backgrounds
CARD_BG = "#1E2329"                # Grouped card backgrounds
CARD_BG_HOVER = "#2D333B"         # Hover state
TEXT_PRIMARY = "#F0F6FC"           # Main text
TEXT_SECONDARY = "#8B949E"         # Muted text
BORDER = "#30363D"                 # Borders
PRIMARY = "#C40000"                # PREDICT red accent
SUCCESS = "#198754"                # Green
WARNING = "#F59E0B"                # Amber
DANGER = "#DC3545"                 # Red
INFO = "#0D6EFD"                   # Blue

# Table styling pattern (from existing code):
table.setStyleSheet("""
    QTableWidget {
        background-color: #0D1117;
        color: #F0F6FC;
        border: 1px solid #30363D;
        border-radius: 6px;
        gridline-color: #21262D;
    }
    QTableWidget::item {
        padding: 8px;
        border-bottom: 1px solid #21262D;
    }
    QTableWidget::item:selected {
        background-color: #C40000;
        color: #FFFFFF;
    }
    QTableWidget::item:alternate {
        background-color: #161B22;
    }
    QHeaderView::section {
        background-color: #21262D;
        color: #8B949E;
        font-weight: bold;
        padding: 10px;
        border: none;
        border-bottom: 2px solid #C40000;
    }
""")

# Card/GroupBox pattern (from existing code):
card = QGroupBox(title)
card.setStyleSheet(f"""
    QGroupBox {{
        font-weight: bold;
        font-size: 13px;
        color: {color};
        border: 2px solid {color};
        border-radius: 8px;
        margin-top: 12px;
        padding: 15px;
        background-color: #1E2329;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 15px;
        padding: 0 8px;
        background-color: #1E2329;
    }}
""")

# Stat card pattern (from existing subscription management):
stat_card = QFrame()
stat_card.setFixedHeight(80)
stat_card.setStyleSheet(f"""
    QFrame {{
        background-color: #1E2329;
        border: 2px solid {color};
        border-radius: 8px;
        padding: 8px;
    }}
""")
# Title: QFont("Segoe UI", 9), color #8B949E
# Value: QFont("Segoe UI", 20, Bold), color matches border

# Button styling pattern:
button.setStyleSheet("""
    QPushButton {
        background-color: #21262D;
        color: #F0F6FC;
        border: 1px solid #30363D;
        border-radius: 6px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background-color: #30363D;
    }
""")
```

Use "Segoe UI" as the font family throughout. Headers at 18pt bold, subheaders at 13pt bold, body at 12px.

**IMPORTANT — PROFILE MANAGEMENT TREE STYLE**: The existing `main_pyside.py` uses a 3-level `QTreeWidget` hierarchy for profiles: **Owner -> Vehicle -> Driver**. Any profile management in the new desktop tabs MUST follow this same tree pattern:

```python
# From existing main_pyside.py — this is the tree style to match:
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

self.tree = QTreeWidget()
self.tree.setColumnCount(8)
self.tree.setHeaderLabels(["#", "Name", "Make", "Model", "Year", "VIN", "★", "ℹ️"])
self.tree.setSelectionMode(QTreeWidget.SingleSelection)
self.tree.setIndentation(20)
self.tree.setRootIsDecorated(True)   # Show expand/collapse arrows
self.tree.setAnimated(True)          # Smooth expand/collapse
self.tree.itemSelectionChanged.connect(self._on_selection_changed)
self.tree.setContextMenuPolicy(Qt.CustomContextMenu)

# 3-level hierarchy:
# Level 0: Owner (bold, colored by source — green=Android, blue=Desktop)
# Level 1: Vehicle (indented under owner, shows make/model/year)
# Level 2: Driver (indented under vehicle, shows role badge)

# Owner item:
owner_item = QTreeWidgetItem([str(row_num), owner_display, "", "", "", "", "", "ℹ️"])
owner_item.setData(0, Qt.UserRole, {'type': 'owner', 'data': owner})
owner_font = owner_item.font(1)
owner_font.setBold(True)
owner_item.setFont(1, owner_font)
self.tree.addTopLevelItem(owner_item)

# Vehicle item (child of owner):
vehicle_item = QTreeWidgetItem(["", f"  {veh_display}", make, model, year, vin, "★", "ℹ️"])
vehicle_item.setData(0, Qt.UserRole, {'type': 'profile', 'data': vehicle, 'owner_id': owner_id})
owner_item.addChild(vehicle_item)

# Driver item (child of vehicle):
driver_item = QTreeWidgetItem(["", f"    {role_icon}{driver_name}", "", "", "", "", "", ""])
driver_item.setData(0, Qt.UserRole, {'type': 'driver', 'data': driver})
vehicle_item.addChild(driver_item)
```

Use this tree style wherever profile/vehicle lists appear in the new tabs (especially LiveDataTab, ConnectionTab, MaintenanceTab, etc.).

**IMPORTANT — ℹ️ INFO BUTTON & CUSTOMER PROFILE / TIER MANAGEMENT PANEL**:

The existing tree has an ℹ️ column (column 7) on each row. Clicking it opens a slide-in `InfoPanelWidget` from the right side showing full customer/vehicle/driver details. The panel uses a **Premium Automotive Theme** (Mercedes MBUX / BMW iDrive inspired):

```python
# PremiumAutomotiveTheme colors (from existing info_panel_widget.py):
BG_DEEPEST = "#08090A"
BG_PRIMARY = "#0D0F12"
BG_ELEVATED = "#141820"        # Cards
BG_SURFACE = "#1C2028"         # Interactive surfaces
BG_HOVER = "#252A35"
ACCENT_CYAN = "#00D4FF"        # Primary accent (cyan/teal)
ACCENT_AMBER = "#FFB800"       # Warnings
ACCENT_EMERALD = "#00E676"     # Success/healthy
ACCENT_CRIMSON = "#FF3D3D"     # Critical/errors
TEXT_PRIMARY = "#F8F9FA"
TEXT_SECONDARY = "#9AA0A6"
TEXT_MUTED = "#5F6368"
BORDER_SUBTLE = "#1E2430"
GRADIENT_HEADER = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #141820, stop:1 #0D0F12)"
```

The info panel includes these **tier management controls** (from `info_panel_widget.py`):
- **Tier dropdown**: QComboBox to change tier (free/pro/premium/admin)
- **Feature toggle checkboxes** per user (enable/disable specific features)
- **Rate limit spinboxes** (max_requests per feature, period selector)
- **API key regeneration** button
- **Signals**: `tier_changed(user_id, tier)`, `feature_toggled(user_id, feature, enabled)`, `rate_limit_changed(user_id, feature, max_requests, period)`, `api_key_regenerated(user_id)`

The panel sections are styled as `InfoSection(QFrame)` blocks:
```python
section = QFrame()
section.setStyleSheet(f"""
    QFrame {{
        background-color: #141820;
        border-radius: 10px;
        border: 1px solid #1E2430;
    }}
    QFrame:hover {{
        border: 1px solid #00D4FF33;  /* Cyan accent on hover */
    }}
""")
```

Wherever you show customer/profile details in new tabs, **match this panel's style and include the same tier management controls**. The subscription tab (file #37) especially MUST include these tier management controls matching the existing pattern.

---

#### 28. `predict/desktop/splash_screen.py`
**Class**: `SplashScreen(QWidget)` — frameless loading screen
- App name "PREDICT" in large font, version number, animated progress bar
- `update_status(message: str, progress: int)` — update label + progress bar value
- `finish()` — fade out and close
- Dark background (#1e1e2e), accent purple (#7c3aed)

#### 29. `predict/desktop/theme.py`
**Purpose**: Centralized theme for the new `predict/desktop/` tabs — MUST be consistent with both existing themes
**Classes and Functions**:
- `class PredictTheme`: Consolidates both `ProfessionalTheme` (from main_pyside.py tables/general UI) and `PremiumAutomotiveTheme` (from info_panel_widget.py info panels) color constants
  - General UI: `BG_PRIMARY = "#0D1117"`, `BG_SECONDARY = "#21262D"`, `CARD_BG = "#1E2329"`, `TEXT_PRIMARY = "#F0F6FC"`, `TEXT_SECONDARY = "#8B949E"`, `BORDER = "#30363D"`, `PRIMARY = "#C40000"`, `SUCCESS = "#198754"`, `WARNING = "#F59E0B"`, `DANGER = "#DC3545"`, `INFO = "#0D6EFD"`
  - Premium panels: `PANEL_BG = "#0D0F12"`, `PANEL_ELEVATED = "#141820"`, `ACCENT_CYAN = "#00D4FF"`, `ACCENT_EMERALD = "#00E676"`, `ACCENT_AMBER = "#FFB800"`, `ACCENT_CRIMSON = "#FF3D3D"`
- `apply_dark_theme(app: QApplication)` — set QPalette + call `app.setStyleSheet(get_stylesheet())`
- `get_stylesheet() -> str` — comprehensive QSS for ALL widget types (QWidget, QPushButton, QTableWidget, QTabWidget, QGroupBox, QLineEdit, QComboBox, QScrollBar, QProgressBar, QLabel, QHeaderView, QTreeWidget)
- `get_table_stylesheet() -> str` — reusable table QSS matching the existing pattern
- `get_card_stylesheet(color: str) -> str` — reusable card/groupbox QSS

#### 30. `predict/desktop/update_checker.py`
**Class**: `UpdateChecker(QThread)` — runs in background thread
- Signal: `update_available = Signal(dict)` — emits `{version, download_url, changelog}`
- `run()` — compare `APP_VERSION` against a remote version endpoint
- `check_for_updates() -> Optional[dict]` — synchronous version
- Uses `from predict.core.version import APP_VERSION`

---

#### Desktop Tabs (10 files under `predict/desktop/tabs/`)

---

#### 31. `predict/desktop/tabs/live_data.py`
**Class**: `LiveDataTab(QWidget)` — Real-time OBD sensor display
- `_setup_ui()`: Grid of sensor gauge widgets (RPM, Speed, Coolant Temp, Battery Voltage, Engine Load, Intake Temp, MAF, Throttle Position)
- Each gauge: QLabel with large font value, colored by threshold (green/yellow/red)
- QTimer at 1000ms interval to refresh data
- `_update_data()` — fetch latest OBD data, update all gauge labels
- `_get_value_color(sensor, value) -> str` — returns hex color based on normal/warning/critical ranges

#### 32. `predict/desktop/tabs/connection.py`
**Class**: `ConnectionTab(QWidget)` — OBD adapter connection
- COM port dropdown (populated from `serial.tools.list_ports` if available)
- Baud rate selector: 9600, 38400, 115200
- Protocol selector: Auto, SAE J1850 PWM, ISO 9141-2, ISO 14230-4, ISO 15765-4
- Connect/Disconnect buttons
- Status indicator: QLabel showing "Connected" (green) / "Disconnected" (red)
- Refresh ports button
- **Vehicle selection**: Use the Owner->Vehicle->Driver tree style from `main_pyside.py` for selecting which vehicle profile to connect to

#### 33. `predict/desktop/tabs/dtc.py`
**Class**: `DTCTab(QWidget)` — Diagnostic Trouble Code reader
- "Read DTCs" button, "Clear DTCs" button (with confirmation dialog)
- QTableWidget: columns = Code, Description, Severity, System, Status
- Color-coded severity (red=critical, orange=warning, yellow=info)
- DTC detail panel below table showing freeze frame data when a row is selected

#### 34. `predict/desktop/tabs/reports.py`
**Class**: `ReportsTab(QWidget)` — Report generation and viewing
- Report type selector: QComboBox with "Health Report", "Trip Summary", "Diagnostic Report", "Maintenance Schedule"
- "Generate Report" button
- QTableWidget listing past reports: Date, Type, Vehicle, Status, Actions(view/delete)
- Progress bar for report generation

#### 35. `predict/desktop/tabs/ai_training.py`
**Class**: `AITrainingTab(QWidget)` — AI model training management
- Stats group: Total records, date range, labeled count
- Model selector: QComboBox listing registered models
- "Train Model" button with QProgressBar
- Results group: Accuracy, Loss, Training time, Epochs completed
- Training history: QTableWidget with past training runs

#### 36. `predict/desktop/tabs/chat.py`
**Class**: `ChatTab(QWidget)` — AI chat interface
- Chat history: QTextEdit (read-only, HTML-formatted) showing conversation
- Input: QLineEdit + "Send" QPushButton
- "Clear Chat" button
- Status label showing AI model name and status
- Calls `AIBridge.chat_with_ai_context()` for responses (in a QThread to avoid UI freeze)

#### 37. `predict/desktop/tabs/subscription.py`
**Class**: `SubscriptionTab(QWidget)` — Subscription & Tier Management
**CRITICAL**: This tab MUST match the style and layout of the existing `subscription_tab.py` and `subscription_management_tab.py` from the main program. Here is the pattern to follow:

**Layout structure** (from existing `subscription_tab.py`):
- **Header**: Title "Subscription Management" (Segoe UI, 18pt, bold, #F0F6FC) + "New Subscription" button + "Refresh" button
- **Stats row**: Horizontal stat cards: Total (purple #6F42C1), Active (green #198754), Trial (blue #0D6EFD), Expired (red #DC3545), Monthly Revenue (orange #FF9800)
- **Filter bar**: Status filter (All/Active/Expired/Pending/Cancelled) + Plan filter (All/Trial/Basic/Professional/Enterprise)
- **Subscription table**: QTableWidget with columns: Customer, Plan, Status, Expires, Payment — styled with dark theme (#0D1117 bg, #30363D border, #21262D header, accent red #C40000 bottom border on header)
- **Bottom row**: Split panel — Details card (left: Customer ID, Plan, Status, Start/End Date, Days Remaining, Payment Status, License Key) + Actions card (right: upgrade/downgrade/cancel/renew buttons)

**Stat cards** (from existing `subscription_management_tab.py`):
```python
# Each stat card is a QFrame with colored border
card = QFrame()
card.setFixedHeight(80)
card.setStyleSheet(f"""
    QFrame {{
        background-color: #1E2329;
        border: 2px solid {color};
        border-radius: 8px;
        padding: 8px;
    }}
""")
# Title label: Segoe UI 9pt, #8B949E
# Value label: Segoe UI 20pt bold, colored to match border
```

**Tier management features** (from existing `subscription_management_tab.py`):
- Tier filter dropdown: "All Tiers", "free", "pro", "premium", "admin"
- Users table: User ID, Email, Tier, Created, Last Activity, Usage Today, Actions
- Tier change actions with confirmation dialogs
- Table styling: dark bg #0D1117, alternate rows #161B22, selected #21262D, header #21262D with #C40000 bottom border

**The new tab must include BOTH** the customer subscription view AND the admin tier management in separate sub-tabs or sections. Use `QTabWidget` inside the tab if needed to separate "My Subscription" view from "Admin: Manage Tiers" view.

#### 38. `predict/desktop/tabs/cloud_sync.py`
**Class**: `CloudSyncTab(QWidget)` — Server sync status
- Connection indicator: QLabel with green/red dot
- Last sync timestamp display
- "Sync Now" button
- Sync queue: QTableWidget showing pending items (type, count, status)
- Auto-sync toggle (QCheckBox) + interval selector

#### 39. `predict/desktop/tabs/maintenance.py`
**Class**: `MaintenanceTab(QWidget)` — Maintenance schedule
- **Vehicle selection**: Use the Owner->Vehicle->Driver tree style (same hierarchy as main_pyside.py)
- Upcoming maintenance: QTableWidget with Item, Due Date, Mileage, Priority, Status
- "Add Maintenance" button -> dialog with item type, interval, last performed
- Default intervals: Oil Change (5000 mi/6 mo), Tire Rotation (7500 mi), Brake Inspection (15000 mi), Air Filter (20000 mi), Spark Plugs (30000 mi), Transmission Fluid (40000 mi), Coolant Flush (50000 mi)
- Overdue items highlighted in red

#### 40. `predict/desktop/tabs/dashboard_monitor.py`
**Class**: `DashboardMonitorTab(QWidget)` — Server health monitoring
- System metrics: CPU %, Memory %, Disk % (using `psutil` if available)
- Server stats: Requests/sec, Active users, Uptime
- Circuit breaker panel: QTableWidget with service name, state (closed/open/half-open), failure count, last failure
- Database pool: active/idle/max connections
- Redis status: connected/disconnected, memory usage
- QTimer refreshing every 5 seconds
- All metrics use `try: import psutil` with graceful "N/A" fallback

---

## ⛔ FINAL WARNING

**START WRITING CODE NOW.**

Do NOT summarize. Do NOT analyze. Do NOT ask questions. Do NOT give options.

Output format — EXACTLY this, 40 times:

```
### File 1: `predict/core/ai/cnn_lstm_model.py`
```python
"""
CNN-LSTM hybrid model for temporal pattern recognition.
"""
import logging
... (FULL working code, NOT stubs)
```
```

Then File 2, File 3, ... all the way to File 40.

**If your response contains ANYTHING before the first ```python block — you have failed. Start with File 1 immediately.**

## SELF-CHECK BEFORE EACH FILE

Before writing each file, silently verify:
- ✅ Module docstring present
- ✅ `logger = logging.getLogger(__name__)` present
- ✅ All imports reference REAL existing modules (check ORM MODELS and EXISTING MODULES sections)
- ✅ No `datetime` objects — `time.time()` only for timestamps
- ✅ Repos inherit `BaseRepository` with `super().__init__(session, Model)`
- ✅ Async functions use `async def` + `await`
- ✅ PySide6 tabs inherit `QWidget` with `_setup_ui()`
- ✅ No hardcoded paths — `get_config()` for all directories
- ✅ Optional deps use `try: import X` with fallback
- ✅ NO `pass` statements — every method has real implementation
- ✅ Profile trees use 3-level hierarchy (Owner -> Vehicle -> Driver)
- ✅ Desktop styling matches existing ProfessionalTheme colors
