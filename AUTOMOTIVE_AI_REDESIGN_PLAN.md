# AUTOMOTIVE-GRADE AI LEARNING SYSTEM - COMPREHENSIVE REDESIGN PLAN

**Date:** 2025-12-16
**Target System:** Predict Desktop AI
**Objective:** Transform from rule-based analyzer to true automotive-grade learning system

---

## 1. LEARNING AUDIT SUMMARY (TASK A)

### Current State Analysis

#### ✅ **Components That TRULY Learn (Update + Persist Parameters)**

1. **enhanced_ai_learning.py**
   - **Location:** `train_global_model()`, `train_brand_model()`, `train_vehicle_model()`
   - **Evidence:** Trains scikit-learn RandomForest/GradientBoosting models, persists to `D:/Predict/ai_model_storage/`
   - **Learning Mechanism:** Exports historical JSONL → CSV → trains supervised models
   - **Persistence:** Uses `pickle` to save/load models
   - **Status:** ✅ REAL LEARNING - Updates parameters based on data

2. **predictive_failure_engine.py**
   - **Location:** `train_models()` (line 613), `train_hybrid_ai()` (line 761)
   - **Evidence:** Trains multiple models (XGBoost, LightGBM, Neural Networks), saves to `CSV DATASETS/MODELS/`
   - **Learning Mechanism:** Imports CSV datasets → feature engineering → trains ensemble → evaluates
   - **Persistence:** `joblib.dump()` for models, JSON for metadata
   - **Status:** ✅ REAL LEARNING - But disconnected from service_history

3. **ai_auto_retraining.py**
   - **Location:** Daily 03:00 scheduler
   - **Evidence:** Calls `enhanced_ai.train_global_model(historical_data)`
   - **Learning Mechanism:** Scheduled retraining with accumulated data
   - **Status:** ✅ REAL LEARNING - Automatic model updates

#### ❌ **Components with PLACEHOLDER / SIMULATED Learning**

1. **unified_ai_module.py**
   - **Location:** `update_from_predictive_engine()` (line 119)
   - **Evidence:** Updates `adaptive_thresholds` dict in memory only
   - **Problem:** Changes NOT persisted, reset on restart
   - **Status:** ⚠️ FAKE LEARNING - Temporary memory updates

2. **unified_ai_module.py - Feedback Loop**
   - **Location:** `feedback_buffer` (line 93), `learning_statistics` (line 84)
   - **Evidence:** Collects feedback but NEVER uses it for training
   - **Problem:** No function consumes `feedback_buffer` to update models
   - **Status:** ❌ DEAD CODE - Data collected but unused

3. **Hard-Coded Accuracy Metrics**
   - **Location:** Multiple files show `'accuracy': 0.85` as hardcoded values
   - **Files:** `unified_ai_module.py:502`, `predictive_failure_engine.py` (implicit in some returns)
   - **Problem:** Not computed from actual predictions vs ground truth
   - **Status:** ❌ FAKE METRIC - Shows fixed 85% regardless of performance

4. **Service History → AI Pipeline**
   - **Location:** `service_history_tab.py` stores repairs in SQLite
   - **Evidence:** Database exists, but NO code reads it for training labels
   - **Problem:** Confirmed repairs never fed back to AI models
   - **Status:** ❌ MISSING INTEGRATION - Data exists but unused

5. **User Feedback → Model Updates**
   - **Location:** Feedback collection exists in UI
   - **Evidence:** No training function accepts user corrections
   - **Problem:** Users can confirm/reject predictions, but models never learn from it
   - **Status:** ❌ BROKEN LOOP - One-way feedback

#### 📊 **Evidence Table**

| Component | True Learning | Persists Data | Uses Feedback | Integration Score |
|-----------|---------------|---------------|---------------|-------------------|
| enhanced_ai_learning | ✅ Yes | ✅ Yes (pickle) | ❌ No | 66% |
| predictive_failure_engine | ✅ Yes | ✅ Yes (joblib) | ❌ No | 66% |
| unified_ai_module | ⚠️ Memory only | ❌ No | ❌ No | 0% |
| service_history integration | ❌ No | ✅ Yes (unused) | ❌ No | 0% |
| user_feedback loop | ❌ No | ❌ No | ❌ No | 0% |
| ai_auto_retraining | ✅ Yes | ✅ Yes | ❌ No | 66% |

**Overall Learning Capability: 33%** (2/6 components truly learn end-to-end)

---

## 2. ARCHITECTURE DIAGRAM (TASK B & C)

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    AUTOMOTIVE-GRADE 3-LAYER LEARNING SYSTEM                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│                         LAYER 1: FLEET MODEL (GLOBAL)                       │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Purpose: Learn universal automotive patterns across ALL vehicles      │ │
│  │ Input: Aggregated time-series from all profiles (anonymized)          │ │
│  │ Features:                                                               │ │
│  │   • Statistical windows (3s, 10s, 30s, 60s rolling means/stds)       │ │
│  │   • Cross-signal correlations (RPM-MAF, Temp-Load, Voltage-Load)     │ │
│  │   • Frequency domain features (FFT on vibration, RPM oscillations)    │ │
│  │   • Trend features (30-day moving avg, acceleration of changes)       │ │
│  │ Models:                                                                 │ │
│  │   • Anomaly Detection: Isolation Forest (unsupervised)                │ │
│  │   • Failure Risk: XGBoost ensemble (7-day, 30-day horizons)          │ │
│  │   • Component Degradation: LSTM for time-series prediction           │ │
│  │ Output: Global baseline probabilities + feature importance rankings   │ │
│  │ Retraining: Weekly with shadow evaluation (Sundays 02:00)            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   LAYER 2: VEHICLE BASELINE MODEL (PERSONALIZED)            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Purpose: Learn THIS vehicle's normal behavior (baseline drift)        │ │
│  │ Input: Single vehicle's time-series (min 7 days, ideal 90 days)      │ │
│  │ Features:                                                               │ │
│  │   • Personalized thresholds (RPM profile, temp zones, driving style)  │ │
│  │   • Deviation from fleet model (z-scores, Mahalanobis distance)      │ │
│  │   • Temporal patterns (morning warmup, highway cruising signature)    │ │
│  │   • Environmental adaptation (ambient temp, altitude, road type)      │ │
│  │ Models:                                                                 │ │
│  │   • Gaussian Mixture Model: Learn multimodal normal states           │ │
│  │   • Online Learning: Incremental PCA for concept drift tracking      │ │
│  │   • Seasonal Decomposition: Separate trend/cycle/residual            │ │
│  │ Output: Personalized score = Fleet_prob × Baseline_deviation_factor  │ │
│  │ Retraining: Daily incremental update (background, non-blocking)      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│               LAYER 3: EVENT/OUTCOME LEARNING (SUPERVISED)                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Purpose: Learn from confirmed outcomes (repairs, DTCs, user feedback) │ │
│  │ Input: Labeled events from service_history + user confirmations       │ │
│  │ Labels:                                                                 │ │
│  │   • Confirmed repairs (part_type, failure_date, symptoms_window)      │ │
│  │   • DTC resolutions (code cleared, root cause confirmed)              │ │
│  │   • User feedback (prediction correct/wrong, actual outcome)          │ │
│  │   • Warranty claims (manufacturer-confirmed failures)                 │ │
│  │ Features:                                                               │ │
│  │   • 7-30 day pre-event windows (sliding lookback)                     │ │
│  │   • Signal progression patterns (gradual vs sudden changes)           │ │
│  │   • Co-occurrence analysis (which sensors correlated with failure)    │ │
│  │ Models:                                                                 │ │
│  │   • Gradient Boosting Classifier (component-specific failures)        │ │
│  │   • Survival Analysis (time-to-failure predictions)                   │ │
│  │   • Causal Inference (what CAUSED the failure, not just correlation)  │ │
│  │ Output: Failure probabilities WITH causal chains for explainability   │ │
│  │ Retraining: Triggered after N new labels (N=20 repairs minimum)      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════════════════╗
║                          EXPLAINABILITY PIPELINE                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│  Prediction Object Structure (NO LLM required)                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ {                                                                       │ │
│  │   "prediction_id": "uuid",                                             │ │
│  │   "vehicle_id": "profile_123",                                         │ │
│  │   "timestamp": "2025-12-16T10:30:45Z",                                │ │
│  │   "model_version": "fleet_v3.2_vehicle_v1.8_event_v2.1",             │ │
│  │                                                                         │ │
│  │   "risk_assessment": {                                                 │ │
│  │     "overall_risk_score": 0.72,  // 0-1 scale                        │ │
│  │     "confidence": 0.83,  // Model certainty                           │ │
│  │     "horizon_days": 7,  // Prediction window                          │ │
│  │     "category": "cooling_system"  // Top risk category                │ │
│  │   },                                                                    │ │
│  │                                                                         │ │
│  │   "layered_explanation": {                                             │ │
│  │     "driver_summary": {  // LAYER 1: Simple language                  │ │
│  │       "headline": "Cooling system shows early warning signs",         │ │
│  │       "risk_level": "MODERATE",  // LOW/MODERATE/HIGH/CRITICAL       │ │
│  │       "urgency": "Check within 3-5 days",                             │ │
│  │       "cost_estimate": "$150-400 if addressed now",                   │ │
│  │       "key_points": [                                                  │ │
│  │         "Coolant temperature running 8°C higher than normal",        │ │
│  │         "Seen in 62% of similar vehicles before radiator issues",    │ │
│  │         "Current data quality: GOOD (47/50 sensors active)"           │ │
│  │       ]                                                                │ │
│  │     },                                                                  │ │
│  │                                                                         │ │
│  │     "technical_breakdown": {  // LAYER 2: For mechanics               │ │
│  │       "signal_chain": [                                                │ │
│  │         {                                                               │ │
│  │           "sensor": "coolant_temp",                                    │ │
│  │           "observation": "Elevated 8°C above baseline",               │ │
│  │           "baseline": 88.2,  // Vehicle-specific normal               │ │
│  │           "current": 96.1,                                             │ │
│  │           "fleet_percentile": 78,  // 78th percentile for this make  │ │
│  │           "trend": "↗ Increasing 0.3°C/day over 14 days"             │ │
│  │         },                                                              │ │
│  │         {                                                               │ │
│  │           "sensor": "rpm_vs_load_correlation",                         │ │
│  │           "observation": "Correlation dropped from 0.92 to 0.78",     │ │
│  │           "interpretation": "Engine working harder for same output",  │ │
│  │           "related_pattern": "Often precedes cooling inefficiency"     │ │
│  │         }                                                               │ │
│  │       ],                                                                │ │
│  │       "suspected_components": [                                         │ │
│  │         {                                                               │ │
│  │           "component": "radiator",                                      │ │
│  │           "probability": 0.68,                                          │ │
│  │           "reasoning": "Temperature rise + load correlation drop",    │ │
│  │           "fleet_confirmation": "62% similar pattern before failure",  │ │
│  │           "last_service": "2024-03-15 (18 months ago)"                │ │
│  │         },                                                              │ │
│  │         {                                                               │ │
│  │           "component": "water_pump",                                    │ │
│  │           "probability": 0.45,                                          │ │
│  │           "reasoning": "No vibration signature detected yet",          │ │
│  │           "note": "Monitor for RPM-correlated vibration"               │ │
│  │         }                                                               │ │
│  │       ]                                                                 │ │
│  │     },                                                                  │ │
│  │                                                                         │ │
│  │     "fleet_statistics": {  // LAYER 3: Data transparency               │ │
│  │       "similar_vehicles": 847,  // Same make/model/year in database  │ │
│  │       "pattern_matches": 524,  // Vehicles with similar signature    │ │
│  │       "confirmed_failures": 327,  // Known outcomes                   │ │
│  │       "false_alarm_rate": 0.18,  // Historical precision              │ │
│  │       "average_time_to_failure": "12-28 days after this signal",     │ │
│  │       "regional_factor": "Hot climate increases risk 1.4×"            │ │
│  │     },                                                                  │ │
│  │                                                                         │ │
│  │     "learning_context": {  // LAYER 4: AI transparency                 │ │
│  │       "fleet_model_version": "3.2",                                    │ │
│  │       "fleet_training_samples": 125000,                                │ │
│  │       "fleet_last_trained": "2025-12-15",                             │ │
│  │       "vehicle_model_version": "1.8",                                  │ │
│  │       "vehicle_training_days": 47,  // Data collected for THIS car   │ │
│  │       "event_model_version": "2.1",                                    │ │
│  │       "event_confirmed_repairs": 1847,  // Labeled training data      │ │
│  │       "data_quality_score": 0.94,  // Completeness metric             │ │
│  │       "missing_sensors": ["oil_pressure", "turbo_boost"]              │ │
│  │     },                                                                  │ │
│  │                                                                         │ │
│  │     "uncertainty_statement": {  // LAYER 5: Honesty                    │ │
│  │       "confidence_level": "MODERATE",                                  │ │
│  │       "known_gaps": [                                                   │ │
│  │         "Oil pressure sensor offline (reduces cooling diagnosis)",    │ │
│  │         "Only 47 days of baseline data (90 days ideal)",              │ │
│  │         "No confirmed repair history for this vehicle yet"            │ │
│  │       ],                                                                │ │
│  │       "recommendation_caveat": "Monitor for 3-5 days. If temperature",│ │
│  │       "continues rising, visit mechanic immediately."                  │ │
│  │     }                                                                   │ │
│  │   },                                                                    │ │
│  │                                                                         │ │
│  │   "causal_chain": {  // For debugging + advanced users                 │ │
│  │     "root_cause_candidates": [                                          │ │
│  │       {                                                                 │ │
│  │         "hypothesis": "Radiator blockage reducing coolant flow",      │ │
│  │         "evidence_strength": 0.72,                                     │ │
│  │         "supporting_signals": ["temp_rise", "load_correlation_drop"], │ │
│  │         "refuting_signals": [],                                        │ │
│  │         "fleet_prevalence": 0.62                                       │ │
│  │       }                                                                 │ │
│  │     ],                                                                  │ │
│  │     "alternative_explanations": [                                       │ │
│  │       "Thermostat stuck partially closed (15% likelihood)",           │ │
│  │       "Coolant level low (12% likelihood - no alerts yet)"            │ │
│  │     ]                                                                   │ │
│  │   }                                                                     │ │
│  │ }                                                                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════════════════╗
║                             CAN FRAME READINESS                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│  Raw CAN Frame Processing (Future-Proof Design)                            │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Input Format:                                                           │ │
│  │   CAN_ID: 0x316 (hex)                                                  │ │
│  │   Payload: [0xA2, 0x5F, 0x..., 0x3C] (8 bytes)                        │ │
│  │   Timestamp: 1734358245.327 (unix epoch + ms)                         │ │
│  │                                                                         │ │
│  │ Feature Extraction (PID-agnostic):                                     │ │
│  │   • Byte-level statistics (mean, std, entropy per byte position)      │ │
│  │   • Message frequency (msgs/sec per CAN ID)                            │ │
│  │   • Payload change rate (how often each byte changes)                 │ │
│  │   • Cross-ID correlations (which IDs change together)                 │ │
│  │   • Anomaly flags (unexpected ID, unusual payload pattern)            │ │
│  │                                                                         │ │
│  │ Learning Approach:                                                      │ │
│  │   1. Unsupervised: Learn normal CAN traffic patterns                  │ │
│  │   2. Detect anomalies without knowing PID meanings                    │ │
│  │   3. Associate anomalies with later failures (outcome learning)       │ │
│  │   4. Gradually build semantic understanding                            │ │
│  │                                                                         │ │
│  │ Storage:                                                                │ │
│  │   • Raw CAN logs: Binary format, compressed (50 MB/hour typical)     │ │
│  │   • Extracted features: Parquet files (10 MB/hour typical)            │ │
│  │   • Models: CAN-ID-specific autoencoders for anomaly detection        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. TRAINING PIPELINE (TASK B)

### 3.1 Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION LAYER                               │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
         ┌─────────────────────────┴─────────────────────────┐
         │                                                     │
         ▼                                                     ▼
┌─────────────────────┐                            ┌─────────────────────┐
│   Android/iOS App   │                            │  Desktop USB OBD    │
│   BLE/WiFi Stream   │                            │   Direct Connect    │
│   ~2-3 Hz           │                            │   ~2-3 Hz           │
└──────────┬──────────┘                            └──────────┬──────────┘
           │                                                   │
           │ POST /api/obd                                    │
           ▼                                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Previlium Server (Port 8000) + Desktop App                 │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  mobile_data_bridge.py → unified format converter                 │  │
│  │  main_pyside.py::_on_live_data() → historical_data_manager        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    HISTORICAL DATA MANAGER                                │
│  Storage: D:/Predict/historical_data/{ProfileName}_{ID}/                │
│           obd_data_YYYY_MM.jsonl (append-only, one JSON per line)       │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                      FEATURE ENGINEERING PIPELINE                         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  NEW MODULE: feature_engineering_pipeline.py                       │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Stage 1: Time-Series Windows                                │  │  │
│  │  │    • Rolling mean/std (3s, 10s, 30s, 60s, 5min)             │  │  │
│  │  │    • Min/max within windows                                  │  │  │
│  │  │    • Rate of change (1st derivative approximation)           │  │  │
│  │  │    • Acceleration (2nd derivative approximation)             │  │  │
│  │  │                                                               │  │  │
│  │  │  Stage 2: Cross-Signal Correlations                          │  │  │
│  │  │    • RPM vs MAF (should correlate)                           │  │  │
│  │  │    • RPM vs Speed (transmission efficiency proxy)            │  │  │
│  │  │    • Coolant Temp vs Engine Load                             │  │  │
│  │  │    • Voltage vs Load (alternator health)                     │  │  │
│  │  │    • Sliding window Pearson correlations (60s windows)       │  │  │
│  │  │                                                               │  │  │
│  │  │  Stage 3: Frequency Domain                                   │  │  │
│  │  │    • FFT on RPM (detect misfires, vibration patterns)        │  │  │
│  │  │    • Power spectral density                                  │  │  │
│  │  │    • Dominant frequency detection                            │  │  │
│  │  │                                                               │  │  │
│  │  │  Stage 4: Trend Features                                     │  │  │
│  │  │    • 7-day exponential moving average                        │  │  │
│  │  │    • 30-day moving average                                   │  │  │
│  │  │    • Trend direction (+1/-1/0)                               │  │  │
│  │  │    • Seasonality decomposition (day-of-week, time-of-day)   │  │  │
│  │  │                                                               │  │  │
│  │  │  Stage 5: Missing Data Handling                              │  │  │
│  │  │    • Imputation strategy: forward-fill for transient loss   │  │  │
│  │  │    • Missing indicator features (was_missing_rpm, etc.)      │  │  │
│  │  │    • Sensor availability score (% uptime per 24h)            │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  Output: Feature matrix (N_samples × M_features) as Parquet        │  │
│  │          Stored: D:/Predict/features/{profile_id}_features.parquet  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                     LABEL GENERATION PIPELINE                             │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  NEW MODULE: label_generator.py                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Label Sources:                                              │  │  │
│  │  │                                                               │  │  │
│  │  │  1. Service History Database (service_history_tab.py)        │  │  │
│  │  │     SELECT service_date, component_type, service_km          │  │  │
│  │  │     FROM service_records WHERE profile_name=?                │  │  │
│  │  │     → Creates binary labels: failure_within_7d=1/0          │  │  │
│  │  │     → Lookback window: Use data from [failure_date-30d,     │  │  │
│  │  │       failure_date-1h] as positive examples                  │  │  │
│  │  │                                                               │  │  │
│  │  │  2. DTC Resolution Events                                    │  │  │
│  │  │     - DTC appears → user clears → reappears within 7d       │  │  │
│  │  │       = Label: unresolved issue (component failure)          │  │  │
│  │  │     - DTC cleared + no reappearance for 30d                  │  │  │
│  │  │       = Label: resolved (negative examples)                  │  │  │
│  │  │                                                               │  │  │
│  │  │  3. User Feedback                                            │  │  │
│  │  │     NEW TABLE: user_feedback                                 │  │  │
│  │  │       prediction_id, user_response (correct/wrong/unsure),  │  │  │
│  │  │       actual_outcome, timestamp                              │  │  │
│  │  │     → Use as validation set for model evaluation            │  │  │
│  │  │                                                               │  │  │
│  │  │  4. Extreme Event Detection (Automated)                      │  │  │
│  │  │     - Coolant > 115°C for >5min → overheat_event=1         │  │  │
│  │  │     - Voltage < 11.5V for >30s → battery_failure=1         │  │  │
│  │  │     - RPM >6000 sustained → overrev_event=1                 │  │  │
│  │  │     → Creates "near-failure" labels automatically           │  │  │
│  │  │                                                               │  │  │
│  │  │  Label Format:                                               │  │  │
│  │  │    timestamp, profile_id, failure_type, horizon_days,       │  │  │
│  │  │    confirmed (1=service_record, 0=auto_detected),           │  │  │
│  │  │    component_id, severity (1-5)                              │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  Output: labels.parquet (timestamped failure events)                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    3-LAYER TRAINING ORCHESTRATOR                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  NEW MODULE: training_orchestrator.py                              │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  Layer 1: Fleet Model Training (Weekly)                      │  │  │
│  │  │  ┌────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  • Aggregate features from ALL profiles (anonymized)  │  │  │  │
│  │  │  │  • Sample strategy: Stratified by make/model/year     │  │  │  │
│  │  │  │  • Class balancing: SMOTE for rare failure types      │  │  │  │
│  │  │  │  • Train ensemble:                                     │  │  │  │
│  │  │  │    - XGBoost (primary, 70% weight)                    │  │  │  │
│  │  │  │    - LightGBM (speed, 20% weight)                     │  │  │  │
│  │  │  │    - Isolation Forest (anomaly detection, 10%)        │  │  │  │
│  │  │  │  • Hyperparameter tuning: Bayesian optimization       │  │  │  │
│  │  │  │  • Validation: 5-fold time-series CV                  │  │  │  │
│  │  │  │  • Metrics: ROC-AUC, Precision@k, F2-score            │  │  │  │
│  │  │  │  • Save: fleet_model_vX.Y.pkl + metadata.json         │  │  │  │
│  │  │  └────────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                               │  │  │
│  │  │  Layer 2: Vehicle Baseline Training (Daily per vehicle)      │  │  │
│  │  │  ┌────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  • Load single vehicle's feature matrix               │  │  │  │
│  │  │  │  • Minimum data: 7 days (1008 samples @ 2Hz)          │  │  │  │
│  │  │  │  • Optimal data: 90 days (12960 samples @ 2Hz)        │  │  │  │
│  │  │  │  • Train Gaussian Mixture Model (n_components=3-5)    │  │  │  │
│  │  │  │    - Cluster 1: "idling/warmup"                       │  │  │  │
│  │  │  │    - Cluster 2: "city driving"                        │  │  │  │
│  │  │  │    - Cluster 3: "highway cruising"                    │  │  │  │
│  │  │  │    - Cluster 4-5: "high load" / "extreme conditions"  │  │  │  │
│  │  │  │  • Compute personalized thresholds (95th percentile)  │  │  │  │
│  │  │  │  • Online learning: Incremental update with new data  │  │  │  │
│  │  │  │  • Save: vehicle_{id}_baseline_vX.Y.pkl               │  │  │  │
│  │  │  └────────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                               │  │  │
│  │  │  Layer 3: Event/Outcome Training (Triggered by new labels)   │  │  │
│  │  │  ┌────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  • Triggered when: N_new_labels >= 20 (configurable)  │  │  │  │
│  │  │  │  • Join features + labels on timestamp                │  │  │  │
│  │  │  │  • Create sliding windows: [failure-30d, failure-1h]  │  │  │  │
│  │  │  │  • Negative samples: Random non-failure windows       │  │  │  │
│  │  │  │  • Train component-specific models:                   │  │  │  │
│  │  │  │    - battery_failure_7d                               │  │  │  │
│  │  │  │    - cooling_failure_7d                               │  │  │  │
│  │  │  │    - fuel_system_failure_7d                           │  │  │  │
│  │  │  │    - transmission_failure_30d                         │  │  │  │
│  │  │  │  • Model: Gradient Boosting + SHAP explainability     │  │  │  │
│  │  │  │  • Validation: Temporal split (train on old, test new)│  │  │  │
│  │  │  │  • Save: event_model_vX.Y.pkl + shap_values.npz       │  │  │  │
│  │  │  └────────────────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  Shadow Evaluation Before Promotion:                                │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  • New model runs in parallel with current production model  │  │  │
│  │  │  • Both make predictions on live data                        │  │  │
│  │  │  • Collect outcomes for 7 days                               │  │  │
│  │  │  • Compare metrics:                                           │  │  │
│  │  │    IF new_model_f2_score > prod_model_f2_score + 0.05:       │  │  │
│  │  │      PROMOTE (new becomes production)                        │  │  │
│  │  │    ELSE:                                                       │  │  │
│  │  │      ROLLBACK (keep current production)                      │  │  │
│  │  │  • Log decision to training_history.jsonl                    │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Training Schedule

```
Daily (03:00):  Layer 2 (Vehicle Baselines) - Incremental updates
Weekly (Sun 02:00): Layer 1 (Fleet Model) - Full retrain
Triggered: Layer 3 (Event Learning) - When N_new_labels >= 20
```

---

## 4. INFERENCE PIPELINE (TASK C)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       REAL-TIME INFERENCE FLOW                            │
└──────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
         Live OBD Data (2-3 Hz from Android or USB)
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Step 1: Feature Extraction (Real-Time)                                  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  • Buffer last 60 seconds of data (in-memory ring buffer)         │  │
│  │  • Compute features on-the-fly:                                    │  │
│  │    - Rolling mean/std (last 10s, 30s, 60s)                        │  │
│  │    - Cross-correlations (RPM-MAF, Temp-Load)                      │  │
│  │    - Rate of change                                                │  │
│  │  • Output: Feature vector (1 × M_features)                        │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Step 2: Layer 1 Inference (Fleet Model)                                 │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  • Load fleet_model_vX.Y.pkl (cached in memory)                   │  │
│  │  • Predict: fleet_prob = model.predict_proba(features)            │  │
│  │  • Extract SHAP values for explainability                         │  │
│  │  • Output: {                                                        │  │
│  │      "battery_failure_7d": 0.23,                                   │  │
│  │      "cooling_failure_7d": 0.68,                                   │  │
│  │      "fuel_failure_7d": 0.12,                                      │  │
│  │      ...                                                            │  │
│  │      "shap_values": {...}                                          │  │
│  │    }                                                                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Step 3: Layer 2 Inference (Vehicle Baseline)                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  • Load vehicle_{id}_baseline_vX.Y.pkl                             │  │
│  │  • Compute deviation from baseline:                                │  │
│  │    baseline_score = gmm.score_samples(features)  # Log-likelihood │  │
│  │    z_score = (current_val - baseline_mean) / baseline_std         │  │
│  │  • Adjust fleet probability:                                       │  │
│  │    adjusted_prob = fleet_prob × (1 + z_score * 0.3)               │  │
│  │    # If z_score=2 (2 stds above normal), increase prob by 60%     │  │
│  │  • Output: {                                                        │  │
│  │      "baseline_deviation": 2.1,  # z-score                         │  │
│  │      "adjusted_cooling_prob": 0.68 × 1.63 = 0.94                  │  │
│  │    }                                                                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Step 4: Layer 3 Inference (Event Model - IF trained)                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  • IF event_model exists (requires >=20 labeled failures):        │  │
│  │    event_prob = event_model.predict_proba(features)               │  │
│  │    Extract causal chains from SHAP force plots                    │  │
│  │    final_prob = 0.5*fleet_prob + 0.3*vehicle_prob +               │  │
│  │                 0.2*event_prob  # Weighted ensemble               │  │
│  │  • ELSE:                                                            │  │
│  │    final_prob = 0.7*fleet_prob + 0.3*vehicle_prob                 │  │
│  │    flag_in_metadata: "event_model_not_trained_yet"                │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Step 5: Explainability Generation                                        │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  NEW MODULE: explanation_builder.py                                │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │  • Driver Summary Generation (Template-Based, NO LLM):      │  │  │
│  │  │    ┌──────────────────────────────────────────────────────┐  │  │  │
│  │  │    │  IF final_prob < 0.3:                                │  │  │  │
│  │  │    │    headline = "All systems operating normally"      │  │  │  │
│  │  │    │    risk_level = "LOW"                                │  │  │  │
│  │  │    │  ELIF 0.3 <= final_prob < 0.6:                       │  │  │  │
│  │  │    │    headline = f"{component} showing early warnings"  │  │  │  │
│  │  │    │    risk_level = "MODERATE"                           │  │  │  │
│  │  │    │  ELIF 0.6 <= final_prob < 0.8:                       │  │  │  │
│  │  │    │    headline = f"{component} requires attention"      │  │  │  │
│  │  │    │    risk_level = "HIGH"                               │  │  │  │
│  │  │    │  ELSE:                                                │  │  │  │
│  │  │    │    headline = f"{component} critical - act now"      │  │  │  │
│  │  │    │    risk_level = "CRITICAL"                           │  │  │  │
│  │  │    └──────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                               │  │  │
│  │  │  • Technical Breakdown (Data-Driven):                        │  │  │
│  │  │    - Extract top 5 SHAP features (highest absolute values)  │  │  │
│  │  │    - For each feature:                                       │  │  │
│  │  │      * Current value                                         │  │  │
│  │  │      * Vehicle baseline                                      │  │  │
│  │  │      * Fleet percentile                                      │  │  │
│  │  │      * Trend (up/down/stable over 7 days)                   │  │  │
│  │  │    - Map features → suspected components using lookup table │  │  │
│  │  │                                                               │  │  │
│  │  │  • Fleet Statistics (Database Query):                        │  │  │
│  │  │    SELECT COUNT(*) FROM historical_data                      │  │  │
│  │  │    WHERE make=? AND model=? AND pattern_similar=1           │  │  │
│  │  │    → "Seen in 62% of 847 similar vehicles"                  │  │  │
│  │  │                                                               │  │  │
│  │  │  • Uncertainty Statement (Rule-Based):                       │  │  │
│  │  │    known_gaps = []                                           │  │  │
│  │  │    IF oil_pressure NOT IN features:                          │  │  │
│  │  │      known_gaps.append("Oil pressure sensor offline")       │  │  │
│  │  │    IF vehicle_baseline_days < 90:                            │  │  │
│  │  │      known_gaps.append(f"Only {days} days baseline")        │  │  │
│  │  │    IF event_model_exists == False:                           │  │  │
│  │  │      known_gaps.append("No repair history yet")             │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                                                                      │  │
│  │  Output: Complete prediction object (as shown in Architecture)      │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Step 6: Persistence & Logging                                            │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  • Save prediction to: predictions.db                              │  │
│  │    CREATE TABLE predictions (                                      │  │
│  │      prediction_id TEXT PRIMARY KEY,                               │  │
│  │      vehicle_id TEXT,                                               │  │
│  │      timestamp TEXT,                                                │  │
│  │      risk_score REAL,                                               │  │
│  │      category TEXT,                                                 │  │
│  │      explanation_json TEXT,  -- Full JSON object                   │  │
│  │      model_versions TEXT,                                           │  │
│  │      shown_to_user INTEGER DEFAULT 1,                              │  │
│  │      user_feedback TEXT  -- To be filled later                     │  │
│  │    )                                                                │  │
│  │                                                                      │  │
│  │  • Log to: D:/Predict/predictions/{vehicle_id}_predictions.jsonl   │  │
│  │    (For offline analysis & model retraining)                       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. FILE-BY-FILE IMPLEMENTATION PLAN (TASK D)

### 5.1 NEW FILES TO CREATE

#### File: `feature_engineering_pipeline.py`
**Purpose:** Extract time-series features from raw OBD data

```python
"""
Feature Engineering Pipeline
Converts raw OBD time-series → ML-ready feature matrix
"""

import numpy as np
import pandas as pd
from scipy import signal, stats
from scipy.fft import fft, fftfreq
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FeatureEngineeringPipeline:
    """
    Automotive-specific feature extraction for time-series OBD data

    Design Principles:
    - NOT PID-specific (works with any numeric sensor)
    - Handles missing data gracefully
    - Computes features in real-time (sliding windows)
    - Ready for raw CAN frames (byte-level statistics)
    """

    def __init__(self, sampling_rate_hz: float = 2.5):
        self.sampling_rate = sampling_rate_hz
        self.window_sizes_sec = [3, 10, 30, 60, 300]  # 3s to 5min

        # Core signal pairs that should correlate
        self.correlation_pairs = [
            ('rpm', 'maf'),  # Engine speed vs airflow
            ('rpm', 'speed'),  # Engine vs wheel speed (transmission)
            ('coolant_temp', 'engine_load'),  # Temp vs load
            ('battery_voltage', 'engine_load'),  # Alternator health
            ('throttle_position', 'maf'),  # Throttle vs airflow
        ]

    def extract_features(self,
                        timeseries_df: pd.DataFrame,
                        realtime_mode: bool = False) -> pd.DataFrame:
        """
        Extract features from OBD time-series data

        Args:
            timeseries_df: DataFrame with columns [timestamp, sensor1, sensor2, ...]
            realtime_mode: If True, only compute features for last row

        Returns:
            DataFrame with extracted features
        """
        if timeseries_df.empty:
            logger.warning("Empty timeseries, returning empty features")
            return pd.DataFrame()

        # Ensure timestamp is datetime
        if 'timestamp' in timeseries_df.columns:
            timeseries_df['timestamp'] = pd.to_datetime(timeseries_df['timestamp'])
            timeseries_df = timeseries_df.sort_values('timestamp')

        # Get numeric columns only
        numeric_cols = timeseries_df.select_dtypes(include=[np.number]).columns.tolist()

        features_list = []

        # Stage 1: Time-Series Windows
        features_list.append(self._extract_window_features(timeseries_df, numeric_cols))

        # Stage 2: Cross-Signal Correlations
        features_list.append(self._extract_correlation_features(timeseries_df))

        # Stage 3: Frequency Domain (if enough data)
        if len(timeseries_df) >= 60:  # Need at least 60 samples for FFT
            features_list.append(self._extract_frequency_features(timeseries_df, numeric_cols))

        # Stage 4: Trend Features (if enough historical data)
        if len(timeseries_df) >= 300:  # ~2 minutes of data
            features_list.append(self._extract_trend_features(timeseries_df, numeric_cols))

        # Stage 5: Missing Data Indicators
        features_list.append(self._extract_missing_data_features(timeseries_df, numeric_cols))

        # Combine all features
        features_df = pd.concat(features_list, axis=1)

        return features_df

    def _extract_window_features(self, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """Compute rolling statistics over multiple window sizes"""
        features = {}

        for col in cols:
            if col not in df.columns:
                continue

            series = df[col]

            for window_sec in self.window_sizes_sec:
                window_samples = int(window_sec * self.sampling_rate)

                if len(series) < window_samples:
                    continue  # Skip if not enough data

                # Rolling mean
                features[f'{col}_mean_{window_sec}s'] = series.rolling(
                    window=window_samples, min_periods=1
                ).mean().iloc[-1]

                # Rolling std (volatility)
                features[f'{col}_std_{window_sec}s'] = series.rolling(
                    window=window_samples, min_periods=1
                ).std().iloc[-1]

                # Rolling min/max
                features[f'{col}_min_{window_sec}s'] = series.rolling(
                    window=window_samples, min_periods=1
                ).min().iloc[-1]

                features[f'{col}_max_{window_sec}s'] = series.rolling(
                    window=window_samples, min_periods=1
                ).max().iloc[-1]

                # Rate of change (1st derivative)
                if len(series) >= 2:
                    rate = (series.iloc[-1] - series.iloc[-window_samples]) / window_sec
                    features[f'{col}_rate_{window_sec}s'] = rate

        return pd.DataFrame([features])

    def _extract_correlation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute correlations between signal pairs"""
        features = {}

        for sig1, sig2 in self.correlation_pairs:
            if sig1 in df.columns and sig2 in df.columns:
                # Use last 60 samples (30 seconds @ 2Hz)
                window = min(60, len(df))
                s1 = df[sig1].iloc[-window:].dropna()
                s2 = df[sig2].iloc[-window:].dropna()

                if len(s1) > 10 and len(s2) > 10:  # Need at least 10 samples
                    # Align series
                    aligned = pd.concat([s1, s2], axis=1).dropna()
                    if len(aligned) > 3:
                        corr = aligned[sig1].corr(aligned[sig2])
                        features[f'corr_{sig1}_{sig2}'] = corr

        return pd.DataFrame([features])

    def _extract_frequency_features(self, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """Extract frequency domain features using FFT"""
        features = {}

        # Focus on RPM for vibration/misfire detection
        if 'rpm' in cols and 'rpm' in df.columns:
            rpm_series = df['rpm'].dropna()

            if len(rpm_series) >= 60:
                # Apply FFT
                fft_vals = fft(rpm_series.values)
                fft_freq = fftfreq(len(rpm_series), 1/self.sampling_rate)

                # Power spectral density
                psd = np.abs(fft_vals) ** 2

                # Dominant frequency
                positive_freq_idx = fft_freq > 0
                dominant_freq = fft_freq[positive_freq_idx][np.argmax(psd[positive_freq_idx])]
                features['rpm_dominant_freq'] = dominant_freq

                # Total power
                features['rpm_spectral_power'] = np.sum(psd)

                # Spectral entropy (measure of signal regularity)
                psd_norm = psd / np.sum(psd)
                psd_norm = psd_norm[psd_norm > 0]
                entropy = -np.sum(psd_norm * np.log2(psd_norm))
                features['rpm_spectral_entropy'] = entropy

        return pd.DataFrame([features])

    def _extract_trend_features(self, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """Extract long-term trend features"""
        features = {}

        for col in cols:
            if col not in df.columns:
                continue

            series = df[col].dropna()

            if len(series) < 100:
                continue

            # Exponential moving average (7-day equivalent at 2Hz = ~1.2M samples)
            # Use smaller window for real-time
            ema_span = min(300, len(series))  # ~2.5 minutes
            ema = series.ewm(span=ema_span).mean().iloc[-1]
            features[f'{col}_ema'] = ema

            # Trend direction: compare recent vs older data
            recent_mean = series.iloc[-30:].mean()  # Last 15 seconds
            older_mean = series.iloc[-60:-30].mean()  # Previous 15 seconds

            if recent_mean > older_mean * 1.05:
                features[f'{col}_trend'] = 1  # Increasing
            elif recent_mean < older_mean * 0.95:
                features[f'{col}_trend'] = -1  # Decreasing
            else:
                features[f'{col}_trend'] = 0  # Stable

        return pd.DataFrame([features])

    def _extract_missing_data_features(self, df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """Compute missing data indicators"""
        features = {}

        for col in cols:
            if col in df.columns:
                # Percentage of missing values in last 60 samples
                window = min(60, len(df))
                missing_pct = df[col].iloc[-window:].isna().sum() / window
                features[f'{col}_missing_pct'] = missing_pct

                # Binary indicator: was missing in last sample?
                features[f'{col}_was_missing'] = int(df[col].iloc[-1] is pd.NA or
                                                     np.isnan(df[col].iloc[-1]))

        # Overall sensor availability score
        total_sensors = len(cols)
        available_sensors = sum(1 for col in cols
                              if col in df.columns and df[col].iloc[-1] is not pd.NA)
        features['sensor_availability_score'] = available_sensors / total_sensors if total_sensors > 0 else 0

        return pd.DataFrame([features])


def process_profile_features(profile_id: int,
                            profile_name: str,
                            historical_data_manager,
                            output_dir: str = "D:/Predict/features") -> str:
    """
    Process historical JSONL data → extract features → save as Parquet

    Returns:
        Path to saved Parquet file
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    # Load historical data
    data_list = historical_data_manager.read_profile_data(
        profile_name, profile_id, limit=None
    )

    if not data_list:
        logger.warning(f"No historical data for {profile_name}")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(data_list)

    # Extract features
    pipeline = FeatureEngineeringPipeline()
    features_df = pipeline.extract_features(df, realtime_mode=False)

    # Save as Parquet (efficient columnar format)
    output_path = os.path.join(output_dir, f"{profile_id}_features.parquet")
    features_df.to_parquet(output_path, compression='snappy')

    logger.info(f"✅ Extracted {len(features_df)} feature rows for {profile_name}")
    logger.info(f"   Saved to: {output_path}")

    return output_path
```

**Integration Points:**
- Called by `training_orchestrator.py` during training
- Called by `unified_ai_module.py` for real-time inference

---

#### File: `label_generator.py`
**Purpose:** Extract training labels from service history + user feedback

```python
"""
Label Generation Pipeline
Converts service history + user feedback → ML training labels
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class LabelGenerator:
    """
    Generates training labels from multiple sources:
    1. Service history database (confirmed repairs)
    2. DTC resolution events (cleared codes)
    3. User feedback (prediction confirmations)
    4. Extreme events (auto-detected near-failures)
    """

    def __init__(self,
                 service_db_path: str = './data/service_history.db',
                 predictions_db_path: str = './data/predictions.db'):
        self.service_db_path = service_db_path
        self.predictions_db_path = predictions_db_path

        self._init_predictions_db()

    def _init_predictions_db(self):
        """Initialize predictions & feedback database"""
        conn = sqlite3.connect(self.predictions_db_path)
        c = conn.cursor()

        # Predictions table
        c.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                prediction_id TEXT PRIMARY KEY,
                vehicle_id TEXT NOT NULL,
                profile_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                risk_score REAL,
                risk_category TEXT,
                horizon_days INTEGER,
                explanation_json TEXT,
                model_versions TEXT,
                shown_to_user INTEGER DEFAULT 1,
                user_feedback TEXT,
                user_feedback_timestamp TEXT,
                actual_outcome TEXT,
                outcome_date TEXT,
                FOREIGN KEY (vehicle_id) REFERENCES vehicle_profiles(profile_id)
            )
        ''')

        # User feedback table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_feedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT NOT NULL,
                vehicle_id TEXT NOT NULL,
                feedback_type TEXT NOT NULL,  -- 'correct', 'incorrect', 'unsure'
                actual_outcome TEXT,  -- What really happened
                outcome_date TEXT,
                repair_cost REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Predictions database initialized")

    def generate_labels(self,
                       profile_id: int,
                       profile_name: str,
                       horizon_days: int = 7) -> pd.DataFrame:
        """
        Generate training labels for a vehicle profile

        Args:
            profile_id: Vehicle profile ID
            profile_name: Vehicle profile name
            horizon_days: Prediction horizon (7 or 30 days)

        Returns:
            DataFrame with columns:
            [timestamp, failure_type, failure_within_Xd, component_id,
             severity, confirmed, failure_date]
        """
        labels_list = []

        # Source 1: Service History
        service_labels = self._extract_service_history_labels(
            profile_name, horizon_days
        )
        labels_list.extend(service_labels)

        # Source 2: DTC Resolutions
        dtc_labels = self._extract_dtc_labels(
            profile_id, horizon_days
        )
        labels_list.extend(dtc_labels)

        # Source 3: User Feedback
        feedback_labels = self._extract_user_feedback_labels(
            profile_id, horizon_days
        )
        labels_list.extend(feedback_labels)

        # Source 4: Extreme Events (Auto-detected)
        extreme_labels = self._extract_extreme_event_labels(
            profile_id, profile_name, horizon_days
        )
        labels_list.extend(extreme_labels)

        if not labels_list:
            logger.warning(f"No labels generated for {profile_name}")
            return pd.DataFrame()

        # Convert to DataFrame
        labels_df = pd.DataFrame(labels_list)

        # Deduplicate (same event might appear in multiple sources)
        labels_df = labels_df.drop_duplicates(
            subset=['timestamp', 'failure_type', 'component_id']
        )

        labels_df = labels_df.sort_values('timestamp')

        logger.info(f"Generated {len(labels_df)} labels for {profile_name}")

        return labels_df

    def _extract_service_history_labels(self,
                                       profile_name: str,
                                       horizon_days: int) -> List[Dict]:
        """Extract labels from service_records table"""
        conn = sqlite3.connect(self.service_db_path)

        query = """
            SELECT
                service_date,
                component_type,
                service_km,
                service_type,
                condition_at_replacement,
                created_at
            FROM service_records
            WHERE profile_name = ?
            ORDER BY service_date DESC
        """

        df = pd.read_sql_query(query, conn, params=(profile_name,))
        conn.close()

        labels = []

        for _, row in df.iterrows():
            failure_date = pd.to_datetime(row['service_date'])

            # Create lookback window: [failure_date - horizon_days, failure_date - 1hour]
            # This is the "pre-failure" period we want to label as positive
            lookback_start = failure_date - timedelta(days=horizon_days)
            lookback_end = failure_date - timedelta(hours=1)

            # Map component_type to failure category
            component_map = {
                'Battery': 'battery_failure',
                'Alternator': 'battery_failure',
                'Radiator': 'cooling_failure',
                'Thermostat': 'cooling_failure',
                'Water Pump': 'cooling_failure',
                'Fuel Pump': 'fuel_failure',
                'Fuel Filter': 'fuel_failure',
                'Fuel Injector': 'fuel_failure',
                'Transmission Fluid': 'transmission_failure',
                'Transmission': 'transmission_failure',
            }

            failure_type = component_map.get(row['component_type'], 'other_failure')

            # Severity based on condition_at_replacement
            condition = row['condition_at_replacement'] or ''
            if 'critical' in condition.lower() or 'failed' in condition.lower():
                severity = 5
            elif 'poor' in condition.lower() or 'worn' in condition.lower():
                severity = 4
            else:
                severity = 3

            label = {
                'timestamp': lookback_start,  # Start of lookback window
                'failure_type': failure_type,
                f'failure_within_{horizon_days}d': 1,  # Positive label
                'component_id': row['component_type'],
                'severity': severity,
                'confirmed': 1,  # Confirmed by service record
                'failure_date': failure_date,
                'source': 'service_history'
            }

            labels.append(label)

        return labels

    def _extract_dtc_labels(self,
                           profile_id: int,
                           horizon_days: int) -> List[Dict]:
        """Extract labels from DTC clear/reappear patterns"""
        # TODO: Implement DTC tracking
        # For now, return empty
        return []

    def _extract_user_feedback_labels(self,
                                      profile_id: int,
                                      horizon_days: int) -> List[Dict]:
        """Extract labels from user_feedback table"""
        conn = sqlite3.connect(self.predictions_db_path)

        query = """
            SELECT
                uf.prediction_id,
                uf.feedback_type,
                uf.actual_outcome,
                uf.outcome_date,
                p.timestamp,
                p.risk_category,
                p.vehicle_id
            FROM user_feedback uf
            JOIN predictions p ON uf.prediction_id = p.prediction_id
            WHERE p.vehicle_id = ?
            AND uf.feedback_type IN ('correct', 'incorrect')
        """

        df = pd.read_sql_query(query, conn, params=(str(profile_id),))
        conn.close()

        labels = []

        for _, row in df.iterrows():
            if row['feedback_type'] == 'correct':
                # Prediction was correct → use as positive label
                label = {
                    'timestamp': pd.to_datetime(row['timestamp']),
                    'failure_type': row['risk_category'],
                    f'failure_within_{horizon_days}d': 1,
                    'component_id': row['risk_category'],
                    'severity': 3,
                    'confirmed': 1,
                    'failure_date': pd.to_datetime(row['outcome_date']) if row['outcome_date'] else None,
                    'source': 'user_feedback_correct'
                }
                labels.append(label)

            elif row['feedback_type'] == 'incorrect':
                # Prediction was wrong → use as negative label
                label = {
                    'timestamp': pd.to_datetime(row['timestamp']),
                    'failure_type': row['risk_category'],
                    f'failure_within_{horizon_days}d': 0,  # Negative
                    'component_id': row['risk_category'],
                    'severity': 0,
                    'confirmed': 1,
                    'failure_date': None,
                    'source': 'user_feedback_incorrect'
                }
                labels.append(label)

        return labels

    def _extract_extreme_event_labels(self,
                                      profile_id: int,
                                      profile_name: str,
                                      horizon_days: int) -> List[Dict]:
        """Auto-detect extreme events from historical data"""
        # TODO: Scan historical_data for extreme events
        # - Coolant > 115°C sustained
        # - Voltage < 11.5V sustained
        # - RPM > 6000 sustained
        # - etc.
        return []
```

**Integration Points:**
- Called by `training_orchestrator.py` before training
- Used by `service_history_tab.py` when new service logged

---

#### File: `training_orchestrator.py`
**Purpose:** Coordinate 3-layer training with shadow evaluation

```python
"""
Training Orchestrator
Coordinates fleet, vehicle, and event model training with shadow evaluation
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
import joblib
import json
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score, f1_score, fbeta_score
)
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import IsolationForest, VotingClassifier
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from feature_engineering_pipeline import FeatureEngineeringPipeline, process_profile_features
from label_generator import LabelGenerator

logger = logging.getLogger(__name__)


class TrainingOrchestrator:
    """
    Coordinates 3-layer training:
    1. Fleet Model (weekly)
    2. Vehicle Baselines (daily per vehicle)
    3. Event Models (triggered by new labels)

    Implements shadow evaluation before model promotion
    """

    def __init__(self,
                 models_dir: str = "D:/Predict/ai_models",
                 features_dir: str = "D:/Predict/features"):
        self.models_dir = models_dir
        self.features_dir = features_dir

        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(features_dir, exist_ok=True)
        os.makedirs(os.path.join(models_dir, 'fleet'), exist_ok=True)
        os.makedirs(os.path.join(models_dir, 'vehicle'), exist_ok=True)
        os.makedirs(os.path.join(models_dir, 'event'), exist_ok=True)
        os.makedirs(os.path.join(models_dir, 'shadow'), exist_ok=True)

        self.feature_pipeline = FeatureEngineeringPipeline()
        self.label_generator = LabelGenerator()

        # Training history
        self.training_log_path = os.path.join(models_dir, 'training_history.jsonl')

    def train_fleet_model(self,
                         historical_data_manager,
                         vehicle_profiles: List[Dict],
                         horizon_days: int = 7) -> Dict:
        """
        Layer 1: Train fleet model on ALL vehicles

        Returns:
            {
                'success': bool,
                'model_version': str,
                'metrics': dict,
                'feature_importance': dict
            }
        """
        logger.info("=" * 70)
        logger.info("Starting Fleet Model Training (Layer 1)")
        logger.info("=" * 70)

        try:
            # Step 1: Extract features for all profiles
            all_features_list = []
            all_labels_list = []

            for profile in vehicle_profiles:
                profile_id = profile['profile_id']
                profile_name = profile['name']

                logger.info(f"Processing {profile_name}...")

                # Extract features
                features_path = process_profile_features(
                    profile_id, profile_name, historical_data_manager, self.features_dir
                )

                if not features_path:
                    continue

                # Load features
                features_df = pd.read_parquet(features_path)

                # Generate labels
                labels_df = self.label_generator.generate_labels(
                    profile_id, profile_name, horizon_days
                )

                if labels_df.empty:
                    logger.warning(f"No labels for {profile_name}, skipping")
                    continue

                # Merge features + labels on timestamp
                merged = features_df.merge(
                    labels_df,
                    left_on='timestamp',
                    right_on='timestamp',
                    how='inner'
                )

                if len(merged) > 0:
                    all_features_list.append(merged)

            if not all_features_list:
                return {
                    'success': False,
                    'error': 'No training data available'
                }

            # Combine all profiles
            combined_df = pd.concat(all_features_list, ignore_index=True)

            logger.info(f"Total training samples: {len(combined_df)}")

            # Step 2: Prepare X, y
            target_col = f'failure_within_{horizon_days}d'

            if target_col not in combined_df.columns:
                return {
                    'success': False,
                    'error': f'Target column {target_col} not found'
                }

            feature_cols = [col for col in combined_df.columns
                          if col not in ['timestamp', 'failure_type', target_col,
                                       'component_id', 'severity', 'confirmed',
                                       'failure_date', 'source']]

            X = combined_df[feature_cols]
            y = combined_df[target_col]

            # Handle missing values
            X = X.fillna(X.mean())

            # Check class balance
            n_positive = y.sum()
            n_negative = len(y) - n_positive
            logger.info(f"Class balance: {n_positive} positive, {n_negative} negative")

            if n_positive < 20:
                return {
                    'success': False,
                    'error': f'Insufficient positive samples: {n_positive} < 20'
                }

            # Step 3: Split data (temporal split)
            # Use last 20% as validation (most recent data)
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
            y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

            # Step 4: Train ensemble
            logger.info("Training XGBoost (primary model)...")

            # Handle class imbalance with scale_pos_weight
            scale_pos_weight = n_negative / n_positive if n_positive > 0 else 1

            xgb_model = xgb.XGBClassifier(
                n_estimators=200,
                max_depth=8,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                n_jobs=-1,
                eval_metric='aucpr'  # Better for imbalanced data
            )

            xgb_model.fit(X_train, y_train)

            # Step 5: Evaluate
            y_pred_proba = xgb_model.predict_proba(X_val)[:, 1]
            y_pred = (y_pred_proba >= 0.5).astype(int)

            metrics = {
                'roc_auc': float(roc_auc_score(y_val, y_pred_proba)),
                'precision': float(precision_score(y_val, y_pred, zero_division=0)),
                'recall': float(recall_score(y_val, y_pred, zero_division=0)),
                'f1': float(f1_score(y_val, y_pred, zero_division=0)),
                'f2': float(fbeta_score(y_val, y_pred, beta=2, zero_division=0)),  # Favor recall
                'n_train_samples': int(len(X_train)),
                'n_val_samples': int(len(X_val)),
                'n_features': int(len(feature_cols))
            }

            logger.info(f"Validation Metrics:")
            logger.info(f"  ROC-AUC: {metrics['roc_auc']:.3f}")
            logger.info(f"  F2-Score: {metrics['f2']:.3f}")
            logger.info(f"  Precision: {metrics['precision']:.3f}")
            logger.info(f"  Recall: {metrics['recall']:.3f}")

            # Step 6: Extract feature importance
            feature_importance = dict(zip(
                feature_cols,
                xgb_model.feature_importances_
            ))

            top_features = sorted(
                feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )[:20]

            logger.info("Top 10 Important Features:")
            for feat, importance in top_features[:10]:
                logger.info(f"  {feat}: {importance:.4f}")

            # Step 7: Save model
            model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = os.path.join(
                self.models_dir, 'fleet', f'fleet_model_{model_version}.pkl'
            )

            joblib.dump(xgb_model, model_path)

            # Save metadata
            metadata = {
                'model_version': model_version,
                'trained_at': datetime.now().isoformat(),
                'horizon_days': horizon_days,
                'metrics': metrics,
                'top_features': dict(top_features),
                'n_profiles': len(vehicle_profiles),
                'feature_columns': feature_cols
            }

            metadata_path = os.path.join(
                self.models_dir, 'fleet', f'fleet_metadata_{model_version}.json'
            )

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Log training event
            self._log_training_event({
                'layer': 'fleet',
                'model_version': model_version,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            })

            logger.info(f"✅ Fleet model saved: {model_path}")

            return {
                'success': True,
                'model_version': model_version,
                'model_path': model_path,
                'metrics': metrics,
                'feature_importance': dict(top_features)
            }

        except Exception as e:
            logger.error(f"Fleet training failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def train_vehicle_baseline(self,
                              profile_id: int,
                              profile_name: str,
                              historical_data_manager) -> Dict:
        """
        Layer 2: Train personalized baseline for one vehicle

        Returns:
            {
                'success': bool,
                'model_version': str,
                'baseline_clusters': int,
                'personalized_thresholds': dict
            }
        """
        logger.info(f"Training vehicle baseline for {profile_name}...")

        try:
            # Extract features
            features_path = process_profile_features(
                profile_id, profile_name, historical_data_manager, self.features_dir
            )

            if not features_path:
                return {
                    'success': False,
                    'error': 'No historical data'
                }

            # Load features
            features_df = pd.read_parquet(features_path)

            # Need at least 7 days of data (~1000 samples @ 2Hz)
            if len(features_df) < 1000:
                return {
                    'success': False,
                    'error': f'Insufficient data: {len(features_df)} samples < 1000'
                }

            # Drop non-numeric columns
            numeric_df = features_df.select_dtypes(include=[np.number])

            # Fill missing values
            numeric_df = numeric_df.fillna(numeric_df.mean())

            # Normalize
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(numeric_df)

            # Train Gaussian Mixture Model
            # Auto-select number of components (3-5)
            best_bic = np.inf
            best_gmm = None
            best_n_components = 3

            for n_components in [3, 4, 5]:
                gmm = GaussianMixture(
                    n_components=n_components,
                    covariance_type='full',
                    random_state=42
                )
                gmm.fit(X_scaled)
                bic = gmm.bic(X_scaled)

                if bic < best_bic:
                    best_bic = bic
                    best_gmm = gmm
                    best_n_components = n_components

            logger.info(f"Selected {best_n_components} baseline clusters")

            # Compute personalized thresholds (95th percentile)
            personalized_thresholds = {}
            for col in numeric_df.columns:
                p95 = numeric_df[col].quantile(0.95)
                p5 = numeric_df[col].quantile(0.05)
                mean = numeric_df[col].mean()
                std = numeric_df[col].std()

                personalized_thresholds[col] = {
                    'mean': float(mean),
                    'std': float(std),
                    'p95': float(p95),
                    'p5': float(p5)
                }

            # Save model
            model_version = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            model_path = os.path.join(
                self.models_dir, 'vehicle', f'vehicle_{profile_id}_baseline_{model_version}.pkl'
            )

            model_data = {
                'gmm': best_gmm,
                'scaler': scaler,
                'feature_columns': list(numeric_df.columns),
                'personalized_thresholds': personalized_thresholds,
                'n_clusters': best_n_components,
                'n_training_samples': len(numeric_df)
            }

            joblib.dump(model_data, model_path)

            logger.info(f"✅ Vehicle baseline saved: {model_path}")

            return {
                'success': True,
                'model_version': model_version,
                'model_path': model_path,
                'baseline_clusters': best_n_components,
                'personalized_thresholds': personalized_thresholds,
                'training_samples': len(numeric_df)
            }

        except Exception as e:
            logger.error(f"Vehicle baseline training failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _log_training_event(self, event: Dict):
        """Log training event to JSONL file"""
        with open(self.training_log_path, 'a') as f:
            json.dump(event, f)
            f.write('\n')
```

**Integration Points:**
- Called by `ai_auto_retraining.py` scheduler
- Called by `ai_training_tab.py` manual training UI

---

---

#### File: `explanation_builder.py`
**Purpose:** Generate structured explanations WITHOUT LLMs

```python
"""
Explanation Builder
Generates layered explanations using templates and data (NO LLM required)
"""

import json
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExplanationBuilder:
    """
    Builds structured, multi-layered explanations from prediction data

    NO LLM REQUIRED - Uses templates + data injection
    """

    def __init__(self):
        # Component mapping for readable names
        self.component_names = {
            'battery_failure': 'Battery/Charging System',
            'cooling_failure': 'Cooling System',
            'fuel_failure': 'Fuel System',
            'transmission_failure': 'Transmission',
            'ignition_failure': 'Ignition System',
            'other_failure': 'Vehicle System'
        }

        # Risk level thresholds
        self.risk_thresholds = {
            'LOW': (0.0, 0.3),
            'MODERATE': (0.3, 0.6),
            'HIGH': (0.6, 0.8),
            'CRITICAL': (0.8, 1.0)
        }

    def build_explanation(self,
                         prediction_result: Dict,
                         vehicle_profile: Dict,
                         fleet_stats: Optional[Dict] = None,
                         model_metadata: Optional[Dict] = None) -> Dict:
        """
        Build complete explanation object

        Args:
            prediction_result: {
                'risk_score': float,
                'category': str,
                'confidence': float,
                'horizon_days': int,
                'shap_values': dict,
                'baseline_deviation': float,
                'feature_values': dict
            }
            vehicle_profile: Vehicle information
            fleet_stats: Optional fleet statistics
            model_metadata: Optional model version info

        Returns:
            Complete explanation object
        """
        risk_score = prediction_result['risk_score']
        category = prediction_result['category']

        # Determine risk level
        risk_level = self._get_risk_level(risk_score)

        explanation = {
            'prediction_id': prediction_result.get('prediction_id'),
            'vehicle_id': vehicle_profile.get('profile_id'),
            'timestamp': datetime.now().isoformat(),
            'model_version': model_metadata.get('version') if model_metadata else 'unknown',

            'risk_assessment': {
                'overall_risk_score': round(risk_score, 2),
                'confidence': round(prediction_result.get('confidence', 0.8), 2),
                'horizon_days': prediction_result.get('horizon_days', 7),
                'category': category
            },

            'layered_explanation': {
                'driver_summary': self._build_driver_summary(
                    risk_score, risk_level, category, prediction_result
                ),
                'technical_breakdown': self._build_technical_breakdown(
                    prediction_result, vehicle_profile
                ),
                'fleet_statistics': self._build_fleet_statistics(
                    category, fleet_stats
                ),
                'learning_context': self._build_learning_context(
                    model_metadata, vehicle_profile
                ),
                'uncertainty_statement': self._build_uncertainty_statement(
                    prediction_result, vehicle_profile
                )
            },

            'causal_chain': self._build_causal_chain(
                prediction_result
            )
        }

        return explanation

    def _get_risk_level(self, risk_score: float) -> str:
        """Determine risk level from score"""
        for level, (low, high) in self.risk_thresholds.items():
            if low <= risk_score < high:
                return level
        return 'CRITICAL'

    def _build_driver_summary(self, risk_score: float, risk_level: str,
                             category: str, prediction_result: Dict) -> Dict:
        """LAYER 1: Simple language for drivers"""
        component = self.component_names.get(category, 'Vehicle System')

        # Template-based headline generation
        if risk_level == 'LOW':
            headline = "All systems operating normally"
            urgency = "Continue regular maintenance"
            cost_estimate = "N/A"
        elif risk_level == 'MODERATE':
            headline = f"{component} showing early warning signs"
            urgency = "Check within 3-5 days"
            cost_estimate = "$150-400 if addressed now"
        elif risk_level == 'HIGH':
            headline = f"{component} requires attention"
            urgency = "Schedule service within 24-48 hours"
            cost_estimate = "$300-800 (may increase if delayed)"
        else:  # CRITICAL
            headline = f"{component} critical - immediate action needed"
            urgency = "Visit mechanic today"
            cost_estimate = "$500-1500+ (prevent breakdown)"

        # Extract key observations
        key_points = []

        # Add top SHAP feature if available
        shap_values = prediction_result.get('shap_values', {})
        if shap_values:
            top_feature = max(shap_values.items(), key=lambda x: abs(x[1]))
            feature_name = top_feature[0].replace('_', ' ').title()
            key_points.append(f"{feature_name} shows unusual pattern")

        # Add baseline deviation if available
        baseline_dev = prediction_result.get('baseline_deviation')
        if baseline_dev and baseline_dev > 1.5:
            key_points.append(f"Behavior deviates {baseline_dev:.1f}× from your vehicle's normal")

        # Add confidence statement
        confidence = prediction_result.get('confidence', 0.8)
        if confidence >= 0.8:
            key_points.append(f"Prediction confidence: HIGH ({confidence*100:.0f}%)")
        elif confidence >= 0.6:
            key_points.append(f"Prediction confidence: MODERATE ({confidence*100:.0f}%)")
        else:
            key_points.append(f"Prediction confidence: LOW ({confidence*100:.0f}%) - monitor closely")

        return {
            'headline': headline,
            'risk_level': risk_level,
            'urgency': urgency,
            'cost_estimate': cost_estimate,
            'key_points': key_points
        }

    def _build_technical_breakdown(self, prediction_result: Dict,
                                   vehicle_profile: Dict) -> Dict:
        """LAYER 2: Technical details for mechanics"""
        signal_chain = []

        # Extract top SHAP features
        shap_values = prediction_result.get('shap_values', {})
        feature_values = prediction_result.get('feature_values', {})
        baseline_values = prediction_result.get('baseline_values', {})

        # Sort by absolute SHAP value
        sorted_features = sorted(
            shap_values.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]  # Top 5 contributors

        for feature_name, shap_val in sorted_features:
            current_val = feature_values.get(feature_name)
            baseline_val = baseline_values.get(feature_name)

            if current_val is not None:
                signal_entry = {
                    'sensor': feature_name,
                    'observation': self._describe_observation(
                        feature_name, current_val, baseline_val
                    ),
                    'current': round(current_val, 2),
                    'shap_contribution': round(shap_val, 4)
                }

                if baseline_val is not None:
                    signal_entry['baseline'] = round(baseline_val, 2)
                    deviation = ((current_val - baseline_val) / baseline_val * 100) if baseline_val != 0 else 0
                    signal_entry['deviation_pct'] = round(deviation, 1)

                signal_chain.append(signal_entry)

        # Suspected components
        suspected_components = self._map_features_to_components(
            sorted_features,
            prediction_result.get('category')
        )

        return {
            'signal_chain': signal_chain,
            'suspected_components': suspected_components
        }

    def _describe_observation(self, feature: str, current: float,
                             baseline: Optional[float]) -> str:
        """Generate human-readable observation"""
        if baseline is None:
            return f"Current value: {current:.2f}"

        diff = current - baseline
        pct_diff = (diff / baseline * 100) if baseline != 0 else 0

        if abs(pct_diff) < 5:
            return f"Normal (within ±5% of baseline)"
        elif diff > 0:
            return f"Elevated {abs(pct_diff):.1f}% above baseline"
        else:
            return f"Decreased {abs(pct_diff):.1f}% below baseline"

    def _map_features_to_components(self, features: List[Tuple],
                                    category: str) -> List[Dict]:
        """Map SHAP features to suspected components"""
        # Simplified mapping (could be expanded with domain knowledge)
        component_mapping = {
            'cooling_failure': [
                {'component': 'radiator', 'probability': 0.65},
                {'component': 'water_pump', 'probability': 0.45},
                {'component': 'thermostat', 'probability': 0.35}
            ],
            'battery_failure': [
                {'component': 'battery', 'probability': 0.70},
                {'component': 'alternator', 'probability': 0.50}
            ],
            'fuel_failure': [
                {'component': 'fuel_pump', 'probability': 0.60},
                {'component': 'fuel_filter', 'probability': 0.40}
            ]
        }

        return component_mapping.get(category, [])

    def _build_fleet_statistics(self, category: str,
                                fleet_stats: Optional[Dict]) -> Dict:
        """LAYER 3: Fleet-level transparency"""
        if not fleet_stats:
            return {
                'similar_vehicles': 0,
                'pattern_matches': 0,
                'note': 'Fleet statistics not yet available'
            }

        return {
            'similar_vehicles': fleet_stats.get('total_vehicles', 0),
            'pattern_matches': fleet_stats.get('pattern_matches', 0),
            'confirmed_failures': fleet_stats.get('confirmed_failures', 0),
            'false_alarm_rate': round(fleet_stats.get('false_alarm_rate', 0.2), 2),
            'average_time_to_failure': fleet_stats.get('avg_ttf', 'Unknown')
        }

    def _build_learning_context(self, model_metadata: Optional[Dict],
                                vehicle_profile: Dict) -> Dict:
        """LAYER 4: AI transparency"""
        if not model_metadata:
            return {
                'note': 'Model metadata not available'
            }

        return {
            'fleet_model_version': model_metadata.get('fleet_version', 'unknown'),
            'fleet_training_samples': model_metadata.get('fleet_samples', 0),
            'fleet_last_trained': model_metadata.get('fleet_trained_date', 'unknown'),
            'vehicle_model_version': model_metadata.get('vehicle_version', 'unknown'),
            'vehicle_training_days': model_metadata.get('vehicle_days', 0),
            'event_model_trained': model_metadata.get('event_model_exists', False),
            'data_quality_score': round(model_metadata.get('data_quality', 0.8), 2)
        }

    def _build_uncertainty_statement(self, prediction_result: Dict,
                                    vehicle_profile: Dict) -> Dict:
        """LAYER 5: Honest limitations"""
        known_gaps = []

        # Check for missing sensors
        feature_values = prediction_result.get('feature_values', {})
        critical_sensors = ['rpm', 'coolant_temp', 'battery_voltage', 'maf']

        for sensor in critical_sensors:
            if sensor not in feature_values or feature_values[sensor] is None:
                known_gaps.append(f"{sensor.replace('_', ' ').title()} sensor offline")

        # Check baseline data sufficiency
        vehicle_days = prediction_result.get('vehicle_training_days', 0)
        if vehicle_days < 30:
            known_gaps.append(f"Only {vehicle_days} days of baseline data (30+ recommended)")

        # Check event model availability
        if not prediction_result.get('event_model_exists', False):
            known_gaps.append("No confirmed repair history for this vehicle yet")

        confidence = prediction_result.get('confidence', 0.8)
        if confidence >= 0.75:
            confidence_level = 'HIGH'
        elif confidence >= 0.5:
            confidence_level = 'MODERATE'
        else:
            confidence_level = 'LOW'

        return {
            'confidence_level': confidence_level,
            'known_gaps': known_gaps,
            'recommendation_caveat': 'This is a predictive warning based on statistical patterns. Always consult a qualified mechanic for diagnosis.'
        }

    def _build_causal_chain(self, prediction_result: Dict) -> Dict:
        """Causal reasoning (for debugging)"""
        shap_values = prediction_result.get('shap_values', {})

        if not shap_values:
            return {'note': 'Causal analysis not available'}

        # Sort by positive SHAP values (contributors to failure)
        positive_contributors = {
            k: v for k, v in shap_values.items() if v > 0
        }

        sorted_contributors = sorted(
            positive_contributors.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        return {
            'root_cause_candidates': [
                {
                    'feature': feat,
                    'evidence_strength': round(val, 3),
                    'interpretation': f"{feat.replace('_', ' ').title()} contributed +{val:.3f} to failure probability"
                }
                for feat, val in sorted_contributors
            ]
        }
```

**Integration Points:**
- Called by `unified_ai_module.py` during inference
- Called by `reports_tab.py` for report generation
- Replaces `phi_explainer.py` (NO LLM dependency)

---

#### File: `inference_engine.py`
**Purpose:** Real-time inference coordinator

```python
"""
Inference Engine
Coordinates real-time predictions using 3-layer models + explanation generation
"""

import os
import logging
from typing import Dict, Optional
import pandas as pd
import numpy as np
import joblib
from collections import deque

from feature_engineering_pipeline import FeatureEngineeringPipeline
from explanation_builder import ExplanationBuilder

logger = logging.getLogger(__name__)


class InferenceEngine:
    """
    Real-time inference using 3-layer model architecture
    """

    def __init__(self, models_dir: str = "D:/Predict/ai_models"):
        self.models_dir = models_dir
        self.feature_pipeline = FeatureEngineeringPipeline()
        self.explanation_builder = ExplanationBuilder()

        # In-memory ring buffers for real-time feature extraction
        self.data_buffers = {}  # profile_id -> deque of recent samples
        self.buffer_size = 300  # 5 minutes @ 2Hz

        # Cached models (loaded once, reused)
        self.fleet_model = None
        self.vehicle_baselines = {}  # profile_id -> baseline model
        self.event_model = None

        self._load_models()

    def _load_models(self):
        """Load latest models from disk"""
        try:
            # Load fleet model
            fleet_dir = os.path.join(self.models_dir, 'fleet')
            if os.path.exists(fleet_dir):
                fleet_files = [f for f in os.listdir(fleet_dir) if f.startswith('fleet_model_')]
                if fleet_files:
                    latest_fleet = sorted(fleet_files)[-1]
                    self.fleet_model = joblib.load(os.path.join(fleet_dir, latest_fleet))
                    logger.info(f"Loaded fleet model: {latest_fleet}")
        except Exception as e:
            logger.error(f"Failed to load fleet model: {e}")

    def load_vehicle_baseline(self, profile_id: int):
        """Load vehicle-specific baseline"""
        try:
            vehicle_dir = os.path.join(self.models_dir, 'vehicle')
            if os.path.exists(vehicle_dir):
                pattern = f'vehicle_{profile_id}_baseline_'
                baseline_files = [f for f in os.listdir(vehicle_dir) if f.startswith(pattern)]
                if baseline_files:
                    latest_baseline = sorted(baseline_files)[-1]
                    self.vehicle_baselines[profile_id] = joblib.load(
                        os.path.join(vehicle_dir, latest_baseline)
                    )
                    logger.info(f"Loaded vehicle baseline for profile {profile_id}")
        except Exception as e:
            logger.error(f"Failed to load baseline for profile {profile_id}: {e}")

    def predict(self,
                obd_data: Dict,
                profile_id: int,
                profile_name: str,
                vehicle_profile: Dict) -> Optional[Dict]:
        """
        Make real-time prediction

        Args:
            obd_data: Current OBD reading
            profile_id: Vehicle profile ID
            profile_name: Vehicle name
            vehicle_profile: Full vehicle profile dict

        Returns:
            Complete prediction + explanation object
        """
        try:
            # Step 1: Update ring buffer
            if profile_id not in self.data_buffers:
                self.data_buffers[profile_id] = deque(maxlen=self.buffer_size)

            self.data_buffers[profile_id].append(obd_data)

            # Need at least 60 seconds of data
            if len(self.data_buffers[profile_id]) < 120:
                return None

            # Step 2: Extract features
            buffer_df = pd.DataFrame(list(self.data_buffers[profile_id]))
            features_df = self.feature_pipeline.extract_features(buffer_df, realtime_mode=True)

            if features_df.empty:
                return None

            # Step 3: Fleet model inference
            if self.fleet_model is None:
                logger.warning("Fleet model not loaded")
                return None

            # Prepare feature vector
            X = features_df.iloc[-1:].values

            fleet_prob = self.fleet_model.predict_proba(X)[0][1]  # Probability of failure

            # Extract SHAP values (if model supports)
            shap_values = {}
            if hasattr(self.fleet_model, 'feature_importances_'):
                for i, col in enumerate(features_df.columns):
                    shap_values[col] = float(self.fleet_model.feature_importances_[i] * X[0][i])

            # Step 4: Vehicle baseline adjustment
            baseline_deviation = 1.0
            if profile_id in self.vehicle_baselines:
                baseline_model = self.vehicle_baselines[profile_id]
                gmm = baseline_model['gmm']
                scaler = baseline_model['scaler']

                # Compute deviation
                X_scaled = scaler.transform(X)
                log_likelihood = gmm.score_samples(X_scaled)[0]

                # Convert to z-score-like deviation
                baseline_deviation = max(0.1, abs(log_likelihood) / 10)

            # Adjust probability based on baseline
            adjusted_prob = min(1.0, fleet_prob * (1 + baseline_deviation * 0.3))

            # Step 5: Determine risk category
            # For now, use highest contributing feature group
            risk_category = 'other_failure'
            if 'coolant' in str(shap_values):
                risk_category = 'cooling_failure'
            elif 'battery' in str(shap_values) or 'voltage' in str(shap_values):
                risk_category = 'battery_failure'
            elif 'fuel' in str(shap_values) or 'maf' in str(shap_values):
                risk_category = 'fuel_failure'

            # Step 6: Build explanation
            prediction_result = {
                'prediction_id': f"pred_{profile_id}_{int(pd.Timestamp.now().timestamp())}",
                'risk_score': adjusted_prob,
                'category': risk_category,
                'confidence': 0.8,  # TODO: Compute from model uncertainty
                'horizon_days': 7,
                'shap_values': shap_values,
                'baseline_deviation': baseline_deviation,
                'feature_values': features_df.iloc[-1].to_dict(),
                'baseline_values': {}  # TODO: Load from baseline model
            }

            explanation = self.explanation_builder.build_explanation(
                prediction_result,
                vehicle_profile,
                fleet_stats=None,  # TODO: Load from database
                model_metadata={'version': 'v1.0'}  # TODO: Load actual metadata
            )

            return explanation

        except Exception as e:
            logger.error(f"Prediction failed: {e}", exc_info=True)
            return None
```

**Integration Points:**
- Called by `unified_ai_module.py` for real-time predictions
- Replaces hardcoded thresholds with ML predictions

---

### 5.2 MODIFICATIONS TO EXISTING FILES

#### File: `unified_ai_module.py`
**Location:** Main AI coordinator
**Changes Required:**

```python
# BEFORE (Lines ~100-120)
def update_from_predictive_engine(self, prediction):
    """Updates adaptive thresholds based on predictions"""
    # ❌ PROBLEM: Only updates memory, not persisted
    if 'sensor' in prediction and 'threshold' in prediction:
        self.adaptive_thresholds[prediction['sensor']] = prediction['threshold']

    # ❌ PROBLEM: feedback_buffer never consumed
    self.feedback_buffer.append(prediction)


# AFTER (Replace with)
def __init__(self):
    # ... existing init code ...

    # ✅ ADD: Import new inference engine
    from inference_engine import InferenceEngine
    self.inference_engine = InferenceEngine()

    # Remove dead code
    # DELETE: self.feedback_buffer = []  # Never used
    # DELETE: self.adaptive_thresholds = {}  # Not persisted


def get_health_assessment(self, data_dict, profile_id, profile_name, vehicle_profile):
    """
    Generate health assessment using ML predictions
    """
    # ✅ NEW: Use inference engine for real-time predictions
    ml_prediction = self.inference_engine.predict(
        obd_data=data_dict,
        profile_id=profile_id,
        profile_name=profile_name,
        vehicle_profile=vehicle_profile
    )

    if ml_prediction:
        # Return ML-based assessment
        return {
            'health_score': int((1 - ml_prediction['risk_assessment']['overall_risk_score']) * 100),
            'risk_level': ml_prediction['layered_explanation']['driver_summary']['risk_level'],
            'predictions': ml_prediction,
            'source': 'ml_inference'
        }

    # Fallback to rule-based if ML not ready
    return self._rule_based_assessment(data_dict)


# ✅ DELETE: Remove hardcoded accuracy
# REMOVE lines ~500-510 with 'accuracy': 0.85
```

**Key Changes:**
1. ✅ Integrate `InferenceEngine` for real-time ML predictions
2. ❌ Delete `feedback_buffer` (dead code)
3. ❌ Delete `adaptive_thresholds` (not persisted)
4. ✅ Replace rule-based with ML-based health scores
5. ✅ Compute real accuracy from prediction history

---

#### File: `service_history_tab.py`
**Location:** Service logging UI
**Changes Required:**

```python
# AFTER existing service logging code (Line ~250)

def log_service(self, ...):
    # ... existing service logging code ...

    # ✅ ADD: Trigger label generation for AI training
    from label_generator import LabelGenerator

    label_gen = LabelGenerator()

    # Generate training labels from this service event
    labels = label_gen._extract_service_history_labels(
        profile_name=self.current_profile_name,
        horizon_days=7
    )

    logger.info(f"Generated {len(labels)} training labels from service event")

    # ✅ ADD: Check if we have enough labels to retrain event model
    total_labels = self._count_total_labels()
    if total_labels >= 20:  # Minimum for event model training
        logger.info(f"✅ Sufficient labels ({total_labels}) for event model training")
        self.signals.training_trigger.emit('event_model', total_labels)

    # ... rest of existing code ...


# ✅ ADD: New signal for training trigger
class ServiceHistorySignals(QObject):
    service_logged = pyqtSignal(dict)
    training_trigger = pyqtSignal(str, int)  # ✅ NEW: (model_type, n_labels)
```

**Key Changes:**
1. ✅ Emit training trigger when service logged
2. ✅ Generate labels immediately after service entry
3. ✅ Track total label count for event model training threshold

---

#### File: `ai_training_tab.py`
**Location:** Training UI tab
**Changes Required:**

```python
# ✅ ADD: Import new training orchestrator
from training_orchestrator import TrainingOrchestrator

class AITrainingTab(QWidget):
    def __init__(self, ...):
        super().__init__()

        # ✅ ADD: Training orchestrator
        self.training_orchestrator = TrainingOrchestrator()

        # ✅ ADD: New UI elements
        self._setup_3layer_training_ui()

    def _setup_3layer_training_ui(self):
        """Setup UI for 3-layer training control"""
        layout = QVBoxLayout()

        # Fleet Model Section
        fleet_group = QGroupBox("Layer 1: Fleet Model (Global)")
        fleet_layout = QVBoxLayout()

        self.fleet_status_label = QLabel("Status: Not trained")
        self.fleet_train_btn = QPushButton("Train Fleet Model (Weekly)")
        self.fleet_train_btn.clicked.connect(self.train_fleet_model)

        fleet_layout.addWidget(self.fleet_status_label)
        fleet_layout.addWidget(self.fleet_train_btn)
        fleet_group.setLayout(fleet_layout)
        layout.addWidget(fleet_group)

        # Vehicle Baseline Section
        vehicle_group = QGroupBox("Layer 2: Vehicle Baselines")
        vehicle_layout = QVBoxLayout()

        self.vehicle_status_label = QLabel("Status: No vehicles trained")
        self.vehicle_train_btn = QPushButton("Train Current Vehicle Baseline")
        self.vehicle_train_btn.clicked.connect(self.train_vehicle_baseline)

        vehicle_layout.addWidget(self.vehicle_status_label)
        vehicle_layout.addWidget(self.vehicle_train_btn)
        vehicle_group.setLayout(vehicle_layout)
        layout.addWidget(vehicle_group)

        # Event Model Section
        event_group = QGroupBox("Layer 3: Event/Outcome Learning")
        event_layout = QVBoxLayout()

        self.event_status_label = QLabel("Status: Waiting for 20+ labeled repairs")
        self.event_train_btn = QPushButton("Train Event Model")
        self.event_train_btn.setEnabled(False)  # Enable when enough labels
        self.event_train_btn.clicked.connect(self.train_event_model)

        event_layout.addWidget(self.event_status_label)
        event_layout.addWidget(self.event_train_btn)
        event_group.setLayout(event_layout)
        layout.addWidget(event_group)

        # Shadow Evaluation Section
        shadow_group = QGroupBox("Shadow Evaluation")
        shadow_layout = QVBoxLayout()

        self.shadow_status_label = QLabel("No shadow models running")
        self.shadow_results_text = QTextEdit()
        self.shadow_results_text.setReadOnly(True)
        self.shadow_results_text.setMaximumHeight(150)

        shadow_layout.addWidget(self.shadow_status_label)
        shadow_layout.addWidget(self.shadow_results_text)
        shadow_group.setLayout(shadow_layout)
        layout.addWidget(shadow_group)

        self.setLayout(layout)

    def train_fleet_model(self):
        """Train fleet model (Layer 1)"""
        self.fleet_train_btn.setEnabled(False)
        self.fleet_status_label.setText("Status: Training... (this may take 10-30 min)")

        # Run in background thread
        from PyQt6.QtCore import QThread

        class TrainingThread(QThread):
            def __init__(self, orchestrator, profiles, hdm):
                super().__init__()
                self.orchestrator = orchestrator
                self.profiles = profiles
                self.hdm = hdm
                self.result = None

            def run(self):
                self.result = self.orchestrator.train_fleet_model(
                    self.hdm,
                    self.profiles,
                    horizon_days=7
                )

        self.training_thread = TrainingThread(
            self.training_orchestrator,
            self.vehicle_profiles,
            self.historical_data_manager
        )
        self.training_thread.finished.connect(self.on_fleet_training_complete)
        self.training_thread.start()

    def on_fleet_training_complete(self):
        """Handle fleet training completion"""
        result = self.training_thread.result

        if result['success']:
            metrics = result['metrics']
            self.fleet_status_label.setText(
                f"✅ Trained: {result['model_version']} | "
                f"F2={metrics['f2']:.3f} | ROC-AUC={metrics['roc_auc']:.3f}"
            )
        else:
            self.fleet_status_label.setText(f"❌ Training failed: {result.get('error', 'Unknown')}")

        self.fleet_train_btn.setEnabled(True)

    # Similar methods for vehicle baseline and event model training...
```

**Key Changes:**
1. ✅ Add 3-layer training UI (Fleet, Vehicle, Event)
2. ✅ Add shadow evaluation status display
3. ✅ Background threading for non-blocking training
4. ✅ Real-time progress/metrics display

---

#### File: `reports_tab.py`
**Location:** Report generation UI
**Changes Required:**

```python
# ✅ MODIFY: Report generation to use new explanation format

def generate_report(self, profile_id, profile_name):
    """Generate report with ML explanations"""

    # ... existing report setup code ...

    # ✅ ADD: Fetch recent predictions from database
    predictions = self._load_recent_predictions(profile_id, days=30)

    report_content = {
        'vehicle_info': vehicle_profile,
        'health_score': current_health_score,
        'recent_predictions': predictions,  # ✅ NEW: ML predictions
        'service_history': service_records,
        'dtc_codes': dtc_codes
    }

    # Generate PDF with new explanation format
    pdf_path = self.pdf_generator.generate_report(report_content)

    return pdf_path


def _load_recent_predictions(self, profile_id, days=30):
    """Load predictions from predictions.db"""
    import sqlite3
    from datetime import datetime, timedelta

    conn = sqlite3.connect('./data/predictions.db')

    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

    query = """
        SELECT prediction_id, timestamp, risk_score, risk_category,
               explanation_json, user_feedback
        FROM predictions
        WHERE vehicle_id = ?
        AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 10
    """

    cursor = conn.execute(query, (str(profile_id), cutoff_date))
    predictions = []

    for row in cursor.fetchall():
        predictions.append({
            'prediction_id': row[0],
            'timestamp': row[1],
            'risk_score': row[2],
            'risk_category': row[3],
            'explanation': json.loads(row[4]) if row[4] else {},
            'user_feedback': row[5]
        })

    conn.close()
    return predictions
```

**Key Changes:**
1. ✅ Load predictions from `predictions.db`
2. ✅ Display ML-based risk assessments in reports
3. ✅ Show user feedback loop results

---

#### File: `pdf_exporter.py`
**Location:** PDF generation
**Changes Required:**

```python
# ✅ MODIFY: PDF export to include layered explanations

def add_predictions_section(self, pdf, predictions):
    """Add ML predictions section to PDF"""

    pdf.add_heading("AI Predictive Analysis", level=2)

    for pred in predictions:
        explanation = pred.get('explanation', {})
        layered = explanation.get('layered_explanation', {})
        driver_summary = layered.get('driver_summary', {})

        # Risk headline
        pdf.add_paragraph(
            f"• {driver_summary.get('headline', 'No predictions available')}",
            style='bold'
        )

        # Risk level badge
        risk_level = driver_summary.get('risk_level', 'UNKNOWN')
        color = self._get_risk_color(risk_level)
        pdf.add_colored_badge(risk_level, color)

        # Key points
        for point in driver_summary.get('key_points', []):
            pdf.add_paragraph(f"  - {point}", indent=20)

        # Technical breakdown (collapsed)
        pdf.add_collapsible_section(
            "Technical Details",
            self._format_technical_breakdown(layered.get('technical_breakdown', {}))
        )

        pdf.add_spacing(10)
```

**Key Changes:**
1. ✅ Display layered explanations in PDFs
2. ✅ Include risk levels, key points, technical breakdowns
3. ✅ Add fleet statistics section

---

#### File: `ai_auto_retraining.py`
**Location:** Scheduled retraining
**Changes Required:**

```python
# ✅ MODIFY: Auto-retraining to use new 3-layer orchestrator

from training_orchestrator import TrainingOrchestrator

class AIAutoRetraining:
    def __init__(self, ...):
        # ... existing code ...

        # ✅ ADD: Training orchestrator
        self.training_orchestrator = TrainingOrchestrator()

    def daily_retrain_schedule(self):
        """Daily retraining (03:00) - Vehicle Baselines"""
        schedule.every().day.at("03:00").do(self.retrain_vehicle_baselines)

        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def weekly_retrain_schedule(self):
        """Weekly retraining (Sunday 02:00) - Fleet Model"""
        schedule.every().sunday.at("02:00").do(self.retrain_fleet_model)

        while self.running:
            schedule.run_pending()
            time.sleep(3600)  # Check hourly

    def retrain_vehicle_baselines(self):
        """Retrain all vehicle baselines (Layer 2)"""
        logger.info("Starting daily vehicle baseline retraining...")

        profiles = self.database.get_all_profiles()

        for profile in profiles:
            result = self.training_orchestrator.train_vehicle_baseline(
                profile_id=profile['profile_id'],
                profile_name=profile['name'],
                historical_data_manager=self.historical_data_manager
            )

            if result['success']:
                logger.info(f"✅ Baseline updated: {profile['name']}")
            else:
                logger.warning(f"⚠️ Baseline failed: {profile['name']} - {result.get('error')}")

    def retrain_fleet_model(self):
        """Retrain fleet model (Layer 1)"""
        logger.info("Starting weekly fleet model retraining...")

        profiles = self.database.get_all_profiles()

        # Train new model in shadow mode
        result = self.training_orchestrator.train_fleet_model(
            historical_data_manager=self.historical_data_manager,
            vehicle_profiles=profiles,
            horizon_days=7
        )

        if result['success']:
            # Start shadow evaluation
            self._start_shadow_evaluation(result['model_version'], result['metrics'])
        else:
            logger.error(f"❌ Fleet training failed: {result.get('error')}")

    def _start_shadow_evaluation(self, new_model_version, new_metrics):
        """Run shadow evaluation for 7 days before promoting"""
        logger.info(f"Starting shadow evaluation for {new_model_version}")

        # Mark model as "shadow" in database
        shadow_record = {
            'model_version': new_model_version,
            'start_date': datetime.now().isoformat(),
            'end_date': (datetime.now() + timedelta(days=7)).isoformat(),
            'status': 'evaluating',
            'training_metrics': new_metrics
        }

        # Save to shadow evaluation table
        # TODO: Implement shadow_evaluation tracking table
```

**Key Changes:**
1. ✅ Daily: Retrain vehicle baselines (Layer 2)
2. ✅ Weekly: Retrain fleet model (Layer 1) with shadow evaluation
3. ✅ Triggered: Retrain event model when 20+ new labels
4. ✅ Non-blocking background execution

---

## 6. RISKS & MITIGATIONS (TASK E)

### 6.1 Cold Start Problem

**Risk:** New vehicles have no baseline data (0-7 days)
**Impact:** Predictions may be inaccurate or unavailable
**Mitigation:**
- ✅ Require minimum 7 days data before showing predictions
- ✅ Use fleet model only (Layer 1) until baseline trained
- ✅ Display prominent "Building Baseline" badge in UI
- ✅ Show data collection progress (e.g., "3/7 days collected")

**Code Implementation:**
```python
if vehicle_training_days < 7:
    return {
        'status': 'building_baseline',
        'days_collected': vehicle_training_days,
        'days_required': 7,
        'message': 'Collecting baseline data... Predictions available after 7 days'
    }
```

---

### 6.2 Catastrophic Forgetting

**Risk:** Model forgets old patterns when trained on new data
**Impact:** Previously learned failure modes no longer detected
**Mitigation:**
- ✅ Use incremental learning for vehicle baselines (append, don't replace)
- ✅ Maintain "memory buffer" of rare failure cases
- ✅ Periodically validate on historical test set
- ✅ Shadow evaluation catches degradation before promotion

**Code Implementation:**
```python
# Online learning for vehicle baseline
gmm.fit(X_new)  # Don't retrain from scratch
gmm.partial_fit(X_new)  # Incremental update

# Maintain rare failure buffer
if failure_type in RARE_FAILURES:
    rare_failure_buffer.append(sample)
    # Always include in training
```

---

### 6.3 False Positives (Alarm Fatigue)

**Risk:** Too many false alarms reduce user trust
**Impact:** Users ignore real warnings
**Mitigation:**
- ✅ Set conservative thresholds (0.6+ for warnings, 0.8+ for critical)
- ✅ Track false positive rate per user
- ✅ Adjust thresholds based on user feedback
- ✅ Display confidence levels ("Prediction confidence: 72%")

**Acceptable False Positive Rate:** 15-20% (industry standard for preventive maintenance)

**Code Implementation:**
```python
# Adjust threshold based on user feedback history
false_positive_rate = self._compute_fpr(profile_id)

if false_positive_rate > 0.25:  # Too high
    threshold = 0.7  # Make more conservative
else:
    threshold = 0.5  # Standard
```

---

### 6.4 False Negatives (Missed Failures)

**Risk:** Miss critical failures, leading to breakdowns
**Impact:** User safety compromised, brand reputation damaged
**Mitigation:**
- ✅ Use F2-score (favors recall over precision)
- ✅ Never suppress warnings for known critical systems (battery, cooling)
- ✅ Always show DTC codes even if ML predicts low risk
- ✅ Redundant detection: Rule-based + ML

**Acceptable False Negative Rate:** <5% for critical systems

---

### 6.5 Data Quality Issues

**Risk:** Missing sensors, sporadic connectivity, corrupt data
**Impact:** Model trained on garbage → garbage predictions
**Mitigation:**
- ✅ Compute data quality score (% sensors available, % missing values)
- ✅ Require 80%+ data quality for predictions
- ✅ Forward-fill missing values (max 30 seconds)
- ✅ Flag predictions with "Low data quality" warnings

**Code Implementation:**
```python
data_quality_score = (n_available_sensors / n_total_sensors) * (1 - missing_pct)

if data_quality_score < 0.8:
    return {
        'warning': 'Low data quality',
        'quality_score': data_quality_score,
        'suppress_predictions': True
    }
```

---

### 6.6 Shadow Training Failures

**Risk:** New model performs worse than production
**Impact:** Degraded predictions if auto-promoted
**Mitigation:**
- ✅ Shadow evaluation for 7 days before promotion
- ✅ Require 5%+ improvement in F2-score
- ✅ Auto-rollback if performance drops
- ✅ Manual approval option for critical changes

**Code Implementation:**
```python
# After 7 days of shadow evaluation
if new_model_f2 > prod_model_f2 + 0.05:
    promote_model(new_model)
    logger.info(f"✅ Model promoted: F2 {new_model_f2:.3f} > {prod_model_f2:.3f}")
else:
    rollback_model(new_model)
    logger.warning(f"⚠️ Model rejected: F2 {new_model_f2:.3f} <= {prod_model_f2:.3f}")
```

---

### 6.7 User Trust & Transparency

**Risk:** Users don't trust "black box" AI predictions
**Impact:** Users ignore warnings, don't provide feedback
**Mitigation:**
- ✅ Layered explanations (5 levels of detail)
- ✅ Show confidence levels, known gaps, data sources
- ✅ Display fleet statistics ("62% of similar vehicles...")
- ✅ Always allow user to dismiss with feedback
- ✅ Track prediction accuracy per user, show improvement over time

**Trust-Building Features:**
```python
explanation['uncertainty_statement'] = {
    'confidence_level': 'MODERATE',
    'known_gaps': [
        'Oil pressure sensor offline',
        'Only 47 days of baseline data (90 recommended)'
    ],
    'recommendation_caveat': 'This is a predictive warning. Always consult a mechanic.'
}
```

---

### 6.8 Regional/Climate Variations

**Risk:** Qatar hot climate patterns differ from global fleet
**Impact:** Fleet model trained on diverse regions may not fit local conditions
**Mitigation:**
- ✅ Add regional metadata to training data
- ✅ Train region-specific sub-models if enough data
- ✅ Vehicle baseline (Layer 2) adapts to local conditions
- ✅ Include ambient temperature as feature

**Code Implementation:**
```python
features['regional_ambient_temp_avg'] = 45  # Qatar summer
features['climate_zone'] = 'hot_arid'

# Weight vehicle baseline higher in extreme climates
if climate_zone == 'hot_arid':
    final_prob = 0.4*fleet_prob + 0.6*vehicle_prob  # Trust personalized more
```

---

## 7. FINAL CLARIFYING QUESTIONS

### 7.1 Prediction Behavior

**Q1:** What is the acceptable false positive rate for predictions?
- Option A: 10-15% (more conservative, fewer alarms)
- Option B: 20-25% (more sensitive, catch more failures)
- **Recommendation:** Start at 15%, adjust per user based on feedback

**Q2:** Should predictions be shown immediately, or only after N days of data?
- Option A: Show from day 1 (using fleet model only)
- Option B: Wait until 7 days baseline collected
- **Recommendation:** Option B (show "Building Baseline" message for first 7 days)

**Q3:** How should the system handle very low confidence predictions (<50%)?
- Option A: Show all predictions with confidence badges
- Option B: Suppress predictions below threshold
- **Recommendation:** Option A (transparency > hiding information)

---

### 7.2 Training Automation

**Q4:** Should shadow training be fully automatic, or require manual approval?
- Option A: Fully automatic (promote if metrics improve)
- Option B: Automatic shadow evaluation, manual promotion
- **Recommendation:** Option A for minor updates, Option B for major version changes

**Q5:** Minimum labeled repairs before training event model (Layer 3)?
- Option A: 10 repairs (faster bootstrap)
- Option B: 20 repairs (more stable model)
- Option C: 50 repairs (high confidence)
- **Recommendation:** Option B (20 repairs), show "Collecting data..." badge until then

**Q6:** Should training run during active usage, or only when idle?
- Option A: Background training anytime (may slow UI)
- Option B: Only during off-hours (03:00)
- **Recommendation:** Option B for fleet model, anytime for vehicle baselines (lightweight)

---

### 7.3 CAN Frame Integration

**Q7:** Timeline for ESP32 raw CAN frame integration?
- **Question:** When do you expect ESP32 OBD adapter to send CAN frames?
- **Impact:** Determines priority of CAN-agnostic feature engineering

**Q8:** CAN frame format expectations?
- **Question:** Will CAN frames include parsed PIDs, or raw 8-byte payloads?
- **Impact:** Determines parsing logic requirements

---

### 7.4 Fleet Learning

**Q9:** Should fleet model learn across ALL makes/models, or train separate models?
- Option A: Single universal model (learns cross-brand patterns)
- Option B: One model per make/model (e.g., Nissan-specific, Toyota-specific)
- **Recommendation:** Option A initially, Option B when 100+ vehicles per brand

**Q10:** Minimum fleet size before fleet model is useful?
- Option A: 10 vehicles (early testing)
- Option B: 50 vehicles (reasonable statistics)
- Option C: 100+ vehicles (production-grade)
- **Recommendation:** Option A for testing, show "Fleet learning: 10/50 vehicles" progress

---

### 7.5 User Feedback Loop

**Q11:** How should users provide feedback on predictions?
- Option A: Simple buttons ("Correct" / "Wrong")
- Option B: Detailed form (what actually happened, when, cost)
- **Recommendation:** Option A for quick feedback, Option B optional for detailed reports

**Q12:** Should wrong predictions trigger immediate model updates?
- Option A: Yes, online learning after every feedback
- Option B: No, accumulate and retrain weekly
- **Recommendation:** Option B (avoid overfitting to single cases)

---

## 8. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Weeks 1-2)
- ✅ Create `feature_engineering_pipeline.py`
- ✅ Create `label_generator.py`
- ✅ Create `training_orchestrator.py` (Layers 1 & 2)
- ✅ Create `explanation_builder.py`
- ✅ Create `inference_engine.py`
- ✅ Create `predictions.db` schema

### Phase 2: Integration (Weeks 3-4)
- ✅ Modify `unified_ai_module.py` (use inference engine)
- ✅ Modify `service_history_tab.py` (emit training triggers)
- ✅ Modify `ai_training_tab.py` (3-layer UI)
- ✅ Modify `ai_auto_retraining.py` (scheduled training)
- ✅ Test end-to-end: Android data → features → training → predictions

### Phase 3: Testing & Tuning (Weeks 5-6)
- ✅ Train fleet model on existing historical data
- ✅ Train vehicle baselines for all profiles
- ✅ Validate predictions on recent service events
- ✅ Tune thresholds based on false positive/negative rates
- ✅ Shadow evaluation testing

### Phase 4: Production Deployment (Week 7)
- ✅ Deploy to desktop application
- ✅ Monitor prediction accuracy
- ✅ Collect user feedback
- ✅ Iterate on explanations based on user understanding

---

## 9. SUCCESS METRICS

### Technical Metrics
- ✅ F2-Score ≥ 0.65 (favor recall for safety)
- ✅ ROC-AUC ≥ 0.75
- ✅ False Positive Rate ≤ 20%
- ✅ False Negative Rate ≤ 5% (critical systems)
- ✅ Inference latency <100ms per prediction

### User Metrics
- ✅ User feedback rate ≥ 30% (users provide feedback)
- ✅ Prediction accuracy (user-confirmed) ≥ 70%
- ✅ User trust score (survey) ≥ 4/5
- ✅ Time-to-failure prediction error <5 days (for 7-day horizon)

### System Metrics
- ✅ Training completion rate 100% (no crashes)
- ✅ Shadow evaluation pass rate ≥ 80%
- ✅ Data quality score ≥ 85% across fleet
- ✅ Model storage <500 MB (fleet + vehicles + event)

---

## 10. CONCLUSION

This redesign transforms the Predict AI system from rule-based heuristics to a true automotive-grade learning system with:

✅ **3-Layer Learning:** Fleet (global) → Vehicle (personalized) → Event (outcome-driven)
✅ **LLM-Free Explanations:** Template-based, data-driven, transparent
✅ **Production-Ready:** Shadow training, rollback, conservative predictions
✅ **Future-Proof:** CAN frame ready, PID-agnostic features
✅ **Trust-Focused:** 5-layer explanations, confidence levels, known gaps

The implementation maintains backward compatibility while enabling powerful new capabilities. Android integration remains unchanged, with all enhancements on the desktop backend.

**Status:** Ready for implementation. All architecture, code templates, and integration points defined.

---

**Document Version:** 1.0
**Last Updated:** 2025-12-16
**Author:** Claude (Anthropic) + Omar (System Architect)

