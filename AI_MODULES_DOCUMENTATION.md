# PREDICT Vehicle Intelligence Platform - AI Modules Documentation

> **Last Updated**: January 2026
> **Total AI/ML Modules**: 27+
> **Architecture**: Hub-and-Spoke with Central Orchestration

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Deep Learning Models](#core-deep-learning-models)
3. [Feature Engineering](#feature-engineering)
4. [Physics & Rule-Based Engines](#physics--rule-based-engines)
5. [RUL & Degradation Analysis](#rul--degradation-analysis)
6. [Confidence & Validation](#confidence--validation)
7. [Unified & Integrated Systems](#unified--integrated-systems)
8. [Fleet Intelligence](#fleet-intelligence)
9. [Server-Side AI Agents](#server-side-ai-agents)
10. [Training Systems](#training-systems)
11. [Module Status & Degradation](#module-status--degradation)
12. [Recommendations: New Agents Needed?](#recommendations-new-agents-needed)

---

## Architecture Overview

```
                    ┌─────────────────────────────────────┐
                    │     enhanced_prediction_engine.py   │
                    │        (Central Orchestrator)       │
                    └───────────────┬─────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   LSTM Stack  │          │ Feature Eng.  │          │  Validation   │
│               │          │               │          │               │
│ • lstm_pred   │          │ • adv_feature │          │ • confidence  │
│ • cnn_lstm    │          │ • baseline    │          │ • physics     │
│ • attention   │          │ • research    │          │ • integrity   │
│ • autoencoder │          │               │          │               │
└───────────────┘          └───────────────┘          └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │      unified_ai_module.py     │
                    │     (Output & Integration)    │
                    └───────────────────────────────┘
```

---

## Core Deep Learning Models

### 1. LSTM Predictor (`lstm_predictor.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `LSTMPredictor` |
| **Singleton** | `get_lstm_predictor()` |
| **Prediction Horizon** | 30-60 days |
| **Status** | CORE - Critical |

**What It Does:**
- Time-series sequence learning for vehicle failure prediction
- Bidirectional LSTM with attention mechanisms
- Multi-head output: failure probability, type classification, time-to-failure

**What It Helps With:**
- Predicting component failures weeks in advance
- Identifying which component will fail
- Estimating days until failure

**Key Features:**
- Transfer learning support
- Model versioning
- Confidence calibration

---

### 2. CNN-LSTM Hybrid (`cnn_lstm_model.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `CNNLSTMModel` |
| **Singleton** | `get_cnn_lstm_model()` |
| **Architecture** | CNN + LSTM |
| **Status** | Advanced |

**What It Does:**
- Combines CNN for spatial feature extraction with LSTM for temporal patterns
- Physics-informed constraints integration

**What It Helps With:**
- Detecting complex multi-sensor patterns
- Better feature extraction from raw sensor data

---

### 3. Attention LSTM (`attention_lstm_model.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `AttentionLSTMModel` |
| **Singleton** | `get_attention_lstm_model()` |
| **Attention Types** | Multi-head, Hierarchical, Self |
| **Status** | Advanced |

**What It Does:**
- LSTM with multiple attention mechanisms
- Feature-level attention (what matters)
- Temporal attention (when matters)

**What It Helps With:**
- Interpretable predictions (explains what caused prediction)
- Better accuracy on complex patterns

---

### 4. LSTM Autoencoder (`lstm_autoencoder.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `LSTMAutoencoder` |
| **Singleton** | `get_lstm_autoencoder()` |
| **Type** | Unsupervised Anomaly Detection |
| **Status** | CORE - Critical |

**What It Does:**
- Learns normal vehicle behavior patterns
- Detects deviations indicating potential failures
- Sequence-to-sequence architecture

**What It Helps With:**
- Catching anomalies no rule can define
- Learning each vehicle's "normal"
- Multi-scale anomaly detection (point, contextual, collective)

---

## Feature Engineering

### 5. Advanced Feature Engineering (`advanced_feature_engineering.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `AdvancedFeatureEngineering` |
| **Input** | Raw OBD-II data |
| **Output** | 50+ derived features |

**What It Does:**
- Rate of change calculations (dT/dt)
- Rolling statistics (mean, std, min, max)
- Cross-sensor correlations
- Physics-based derived features

**What It Helps With:**
- Extracting hidden patterns from raw data
- Creating features that improve model accuracy

---

### 6. Vehicle Baseline Learning (`vehicle_baseline_learning.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `VehicleBaselineLearning` |
| **Learning Type** | Per-vehicle personalization |
| **States Tracked** | Idle, Cruising, Acceleration |

**What It Does:**
- Learns what's "normal" for each specific vehicle
- Operating state-aware baselines
- Seasonal/temperature adjustments

**What It Helps With:**
- Detecting anomalies specific to THIS vehicle
- Reducing false positives
- Fleet-wide comparison

---

### 7. Research Feature Extractor (`research_feature_extractor.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `ResearchFeatureExtractor` |
| **Data Source** | LLM web research |
| **Output** | Numerical AI features |

**What It Does:**
- Converts LLM research to numerical features
- Bounds validation to prevent hallucination impact
- Component-specific risk boosts

**What It Helps With:**
- Known issue multipliers from real-world data
- Cost estimates from research
- Recall/TSB information

---

## Physics & Rule-Based Engines

### 8. Physics Constraints Validator (`physics_constraints.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `PhysicsValidator` |
| **Singleton** | `get_physics_validator()` |
| **Domains** | Battery, Cooling, Fuel, Transmission, Engine |

**What It Does:**
- Validates sensor data against physical laws
- Kirchhoff's laws, Peukert's law, thermodynamics
- Detects impossible sensor readings

**What It Helps With:**
- Catching sensor failures
- Filtering bad data before AI processing
- Adding physics-based confidence

---

### 9. Failure Correlation Engine (`failure_correlation_engine.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `FailureCorrelationEngine` |
| **Method** | Multi-sensor rule-based correlation |
| **Rules** | 30+ correlation rules |

**What It Does:**
- Combines multiple sensors to detect failures
- Root cause analysis
- Failure chain detection

**What It Helps With:**
- Detecting failures no single sensor shows
- Understanding WHY something failed
- Cascading failure prevention

---

## RUL & Degradation Analysis

### 10. RUL Estimator (`rul_estimation.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `RULEstimator` |
| **Models** | Linear, Exponential, Polynomial, Weibull |
| **Output** | Days/miles until failure |

**What It Does:**
- Remaining Useful Life estimation
- Degradation curve fitting
- Component-specific life models

**What It Helps With:**
- Predicting when components will fail
- Maintenance scheduling
- Mileage/time projections

---

### 11. Component Prediction Models (`component_prediction_models.py`)

| Property | Value |
|----------|-------|
| **Classes** | `BrakePredictionModel`, `OilLifePredictionModel`, `BatteryHealthModel` |
| **Method** | Physics + ML hybrid |

**What It Does:**
- Specialized models for brakes, oil, battery
- Physics-based calculations + ML refinement

**What It Helps With:**
- Accurate brake wear prediction
- Oil change timing
- Battery replacement scheduling

---

## Confidence & Validation

### 12. Prediction Confidence Scorer (`prediction_confidence.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `PredictionConfidenceScorer` |
| **Output** | Confidence score 0.0-1.0 |
| **Factors** | Data quality, history, corroboration, recency |

**What It Does:**
- Calculates trustworthiness of predictions
- Tracks historical accuracy
- Combines multiple confidence factors

**What It Helps With:**
- Knowing when to trust predictions
- Identifying uncertain predictions
- Calibrating over time

---

### 13. AI Prediction Integrity (`ai_prediction_integrity.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `AIPredictionManager` |
| **Features** | Versioning, audit trail, feedback loop |

**What It Does:**
- Model versioning and rollback
- Complete audit trail
- Suppresses low-confidence predictions

**What It Helps With:**
- Trustworthy AI predictions
- Debugging failed predictions
- Continuous improvement

---

### 14. Model Validation Framework (`model_validation_framework.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `ModelValidationFramework` |
| **Validation** | Safety-critical thresholds |

**What It Does:**
- Validates models before deployment
- Safety metric thresholds
- Robustness testing

**What It Helps With:**
- Ensuring models are safe to deploy
- Catching model degradation
- Meeting safety requirements

---

## Unified & Integrated Systems

### 15. Enhanced Prediction Engine (`enhanced_prediction_engine.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `EnhancedPredictionEngine` |
| **Role** | Central Orchestrator |
| **Status** | CORE - Critical |

**What It Does:**
- Integrates ALL other AI modules
- Coordinates data flow between modules
- Combines predictions from multiple sources
- Module degradation tracking

**What It Helps With:**
- Single point of prediction
- Unified health scoring
- Graceful degradation when modules fail

---

### 16. Unified AI Module (`unified_ai_module.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `UnifiedAIModule` |
| **Role** | Output generation |

**What It Does:**
- Generates unique insights per vehicle
- Real-time data analysis
- DTC integration

**What It Helps With:**
- User-facing insights
- Per-vehicle unique analysis
- Health score generation

---

### 17. Model Factory (`advanced_model_factory.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `ModelFactory` |
| **Architectures** | LSTM, CNN-LSTM, Attention, Autoencoder |
| **Role** | Model management |

**What It Does:**
- Factory pattern for model creation
- Automatic model selection
- Ensemble methods
- Performance monitoring

**What It Helps With:**
- Unified interface to all models
- Automatic best model selection
- Model rollback

---

## Fleet Intelligence

### 18. Fleet Learning Aggregator (`fleet_learning_aggregator.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `FleetLearningAggregator` |
| **Data Scope** | All vehicles of same make/model/year |

**What It Does:**
- Aggregates data across users with same vehicle
- Fleet health statistics
- Component failure rates across fleet
- Common DTC patterns

**What It Helps With:**
- Learning from ALL Nissan Patrol 2003 owners
- Better predictions for rare vehicles
- Fleet-wide insights

---

## Server-Side AI Agents

### 19. Driving Behavior Agent (`driving_behavior_agent.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `DrivingBehaviorAgent` |
| **Singleton** | `get_driving_behavior_agent()` |
| **Location** | Server (`C:\OBDserver\Previlium_OBD_Server\`) |
| **Status** | NEW - Implemented |

**What It Does:**
- Analyzes driving patterns from trip events
- Calculates safety scores (overall, smoothness, speed compliance, attention)
- Detects risky patterns (night driving, rush hour, weekend)
- Generates personalized coaching recommendations
- Compares driver to fleet percentile

**What It Helps With:**
- Driver safety scoring (0-100)
- Identifying aggressive driving patterns
- Coaching tips to improve driving
- Fleet-wide driver comparison
- Adjusting component wear predictions based on driving style

**Key Data Classes:**
```python
@dataclass
class DrivingBehaviorAnalysis:
    driver_id: str
    vehicle_id: str
    overall_safety_score: int  # 0-100
    smoothness_score: int
    speed_compliance_score: int
    attention_score: int
    harsh_braking_count: int
    speeding_events_count: int
    coaching_tips: List[str]
    percentile_vs_fleet: int
```

**API Endpoints:**
- `GET /api/v1/driver/{driver_id}/behavior` - Full behavior analysis
- `GET /api/v1/driver/{driver_id}/coaching` - Just coaching tips

---

### 20. Trip Analysis Agent (`trip_analysis_agent.py`)

| Property | Value |
|----------|-------|
| **Main Class** | `TripAnalysisAgent` |
| **Singleton** | `get_trip_analysis_agent()` |
| **Location** | Server (`C:\OBDserver\Previlium_OBD_Server\`) |
| **Status** | NEW - Implemented |

**What It Does:**
- Analyzes individual completed trips
- Calculates fuel efficiency with baseline comparison
- Classifies trips (city, highway, commute, mixed)
- Detects anomalies (high fuel consumption, long duration)
- Generates efficiency tips
- Summarizes trip patterns over time

**What It Helps With:**
- Per-trip fuel efficiency analysis
- Identifying fuel-wasting habits
- Trip pattern insights (peak hours, common routes)
- Anomaly detection (unusual trips)
- Adjusting wear predictions for heavy usage

**Key Data Classes:**
```python
@dataclass
class TripAnalysis:
    trip_id: str
    distance_km: float
    duration_minutes: float
    fuel_efficiency_km_per_l: float
    efficiency_rating: str  # "excellent", "good", "average", "poor"
    efficiency_vs_baseline: float  # +15% or -10%
    trip_type: str  # "city", "highway", "commute", "mixed"
    anomalies: List[str]
    efficiency_tips: List[str]

@dataclass
class TripPatternSummary:
    total_trips: int
    total_distance_km: float
    avg_trips_per_day: float
    most_common_trip_type: str
    peak_driving_hours: List[int]
    fuel_efficiency_trend: str  # "improving", "declining", "stable"
```

**API Endpoints:**
- `GET /api/v1/trip/{trip_id}/analysis` - Single trip analysis
- `GET /api/v1/vehicle/{vehicle_id}/trip-patterns` - Pattern summary

---

### Integration with Prediction Engine

Both agents are integrated into `enhanced_prediction_engine.py`:

```python
# Driving behavior affects component wear predictions
if driver_safety_score < 50:
    driving_risk_factor = 1.15  # 15% increased wear

# Trip patterns affect usage intensity
if avg_trips_per_day > 5:
    usage_intensity = 1.15  # Heavy usage

# Combined factor adjusts RUL and failure probabilities
for rul in rul_predictions:
    rul.estimated_days = int(rul.estimated_days / combined_factor)
```

**Wear-affected components:**
- Brake pads
- Tires
- Transmission
- Clutch
- Suspension
- CV joints
- Wheel bearings

---

## Training Systems

### 21. LSTM Bootstrap Trainer (`lstm_bootstrap_trainer.py`)

**What It Does:** Initial LSTM training using synthetic data

### 20. AI Auto Retraining (`ai_auto_retraining.py`)

**What It Does:** Automatic daily retraining of all models

### 21. Enhanced AI Learning (`enhanced_ai_learning.py`)

**What It Does:** Combines global, brand-specific, and vehicle-specific learning

---

## Module Status & Degradation

The system tracks which modules are available and applies **confidence penalties** when modules are missing:

| Module | Penalty if Missing |
|--------|-------------------|
| LSTM Predictor | 10% |
| Autoencoder | 8% |
| Physics Validator | 5% |
| Research Extractor | 4% |
| Fleet Aggregator | 3% |
| Recall Monitor | 2% |
| Feedback Collector | 2% |
| ESP32 Bridge | 1% |

**Maximum penalty:** 30%

---

## Recommendations: New Agents Needed?

### Currently Well-Covered:
- Failure prediction (LSTM stack)
- Anomaly detection (Autoencoder)
- Physics validation
- Component-specific models
- Fleet learning
- Confidence scoring
- **Driving behavior analysis** (NEW)
- **Trip analysis & patterns** (NEW)

### Implemented Agents:

#### 1. **Driving Behavior Agent** (IMPLEMENTED)
**Purpose:** Analyze driver behavior patterns for safety scoring
**Location:** `C:\OBDserver\Previlium_OBD_Server\driving_behavior_agent.py`
**Helps With:**
- Driver safety scoring (0-100)
- Coaching recommendations
- Fleet comparison
- Wear prediction adjustments

**Status:** IMPLEMENTED - Integrated with prediction engine

---

#### 2. **Trip Analysis Agent** (IMPLEMENTED)
**Purpose:** Per-trip fuel efficiency and behavior analysis
**Location:** `C:\OBDserver\Previlium_OBD_Server\trip_analysis_agent.py`
**Helps With:**
- Fuel economy optimization
- Trip-level insights
- Pattern analysis
- Usage intensity tracking

**Status:** IMPLEMENTED - Integrated with prediction engine

---

### Potential Future Agents:

#### 3. **Sensor Fusion Agent** (OPTIONAL)
**Purpose:** Combine OBD with external sensors (ESP32, GPS, accelerometer)
**Would Help With:**
- Road condition detection
- Driving pattern analysis
- More accurate predictions

**Estimated Value:** MEDIUM

---

#### 4. **Natural Language Explanation Agent** (OPTIONAL)
**Purpose:** Generate human-readable explanations of predictions
**Would Help With:**
- User-facing insights
- PDF report generation
- LLM-powered explanations

**Estimated Value:** MEDIUM

---

#### 5. **Recall Alert Agent** (EXISTS - `recall_monitor.py`)
**Purpose:** Monitor for new recalls and TSBs
**Status:** Already implemented

---

### Implementation Status:

| Agent | Status | Location |
|-------|--------|----------|
| Driving Behavior Agent | DONE | Server |
| Trip Analysis Agent | DONE | Server |
| Recall Alert Agent | DONE | Desktop |
| Sensor Fusion Agent | PENDING | - |
| NL Explanation Agent | PENDING | - |

---

## Quick Reference: Module Names

| Short Name | Full Path | Purpose |
|------------|-----------|---------|
| `lstm_predictor` | lstm_predictor.py | 30-60 day failure prediction |
| `cnn_lstm` | cnn_lstm_model.py | Hybrid CNN-LSTM architecture |
| `attention_lstm` | attention_lstm_model.py | Interpretable predictions |
| `autoencoder` | lstm_autoencoder.py | Anomaly detection |
| `feature_eng` | advanced_feature_engineering.py | Feature extraction |
| `baseline` | vehicle_baseline_learning.py | Per-vehicle learning |
| `physics` | physics_constraints.py | Physics validation |
| `correlation` | failure_correlation_engine.py | Multi-sensor rules |
| `rul` | rul_estimation.py | Remaining useful life |
| `confidence` | prediction_confidence.py | Trust scoring |
| `integrity` | ai_prediction_integrity.py | Audit & versioning |
| `validation` | model_validation_framework.py | Safety validation |
| `engine` | enhanced_prediction_engine.py | Central orchestrator |
| `unified` | unified_ai_module.py | Output generation |
| `factory` | advanced_model_factory.py | Model management |
| `fleet` | fleet_learning_aggregator.py | Cross-vehicle learning |
| `research` | research_feature_extractor.py | LLM feature extraction |
| `behavior` | driving_behavior_agent.py | Driver safety scoring (SERVER) |
| `trip` | trip_analysis_agent.py | Trip efficiency analysis (SERVER) |

---

## Summary

The PREDICT platform has a **comprehensive AI stack** with:
- 4 deep learning models
- 2 feature engineering modules
- 2 physics/rule engines
- 4 confidence/validation systems
- 3 integrated orchestrators
- 1 fleet learning system
- **2 server-side AI agents** (NEW)

**Current Status:** FUNCTIONAL AND ENHANCED
- Critical issues fixed (division-by-zero, confidence inflation)
- Module degradation tracking added
- LLM bounds validation implemented
- Neutral health baselines established
- **Driving Behavior Agent implemented** (NEW)
- **Trip Analysis Agent implemented** (NEW)

**Server-Side Agents (NEW):**
- Run on server at `C:\OBDserver\Previlium_OBD_Server\`
- Exposed via REST API endpoints
- Integrated with `enhanced_prediction_engine.py`
- Adjust wear predictions based on driving behavior
- Adjust degradation for heavy usage patterns

**API Endpoints Added:**
- `GET /api/v1/driver/{driver_id}/behavior` - Driving behavior analysis
- `GET /api/v1/driver/{driver_id}/coaching` - Coaching tips
- `GET /api/v1/trip/{trip_id}/analysis` - Trip analysis
- `GET /api/v1/vehicle/{vehicle_id}/trip-patterns` - Trip patterns
- `GET /api/v1/ai-agents/status` - Agent availability status

**Recommended Next Steps:**
1. Test agents with real trip data
2. Monitor prediction accuracy improvements
3. Expand fleet learning data
4. Consider Sensor Fusion Agent for future
