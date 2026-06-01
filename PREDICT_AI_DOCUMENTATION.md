# PREDICT AI/ML System Documentation

**Version**: 1.0
**Date**: February 2026
**Author**: PREDICT Development Team

---

## Table of Contents

1. [AI Modules Overview](#1-ai-modules-overview)
2. [Neural Network Architectures](#2-neural-network-architectures)
3. [Training Procedures](#3-training-procedures)
4. [Model Management](#4-model-management)
5. [Data Pipeline](#5-data-pipeline)
6. [Troubleshooting](#6-troubleshooting)
7. [API Integration](#7-api-integration)

---

## 1. AI MODULES OVERVIEW

The PREDICT AI system consists of multiple neural network architectures designed for automotive predictive maintenance. All models are trained on vehicle telemetry data and can predict component failures 30+ days in advance.

### 1.1 Module File Locations

| Module | File Path | Purpose |
|--------|-----------|---------|
| LSTM Baseline | `model_lstm.py` | Primary time-series prediction |
| CNN-LSTM Hybrid | `model_cnn_lstm.py` | Feature extraction + temporal |
| Attention-LSTM | `model_attention_lstm.py` | Physics-informed attention |
| LSTM Autoencoder | `model_lstm_autoencoder.py` | Anomaly detection |
| Model Factory | `model_factory.py` | Ensemble management |
| Training Pipeline | `training_pipeline.py` | Automated training |
| Data Preprocessor | `data_preprocessor.py` | Feature engineering |
| Failure Predictor | `failure_predictor.py` | Main prediction interface |
| Engine Analyzer | `engine_analyzer.py` | Engine-specific analysis |
| DTC Analyzer | `dtc_analyzer.py` | Diagnostic code analysis |

### 1.2 Input/Output Specifications

**Input Data (per sample)**:
```python
{
    "timestamp": float,           # Unix timestamp
    "rpm": float,                 # 0-8000
    "speed": float,               # km/h
    "coolant_temp": float,        # °C
    "battery_voltage": float,     # V
    "engine_load": float,         # 0-100%
    "throttle_position": float,   # 0-100%
    "intake_air_temp": float,     # °C
    "maf_rate": float,            # g/s
    "fuel_pressure": float,       # kPa
    "o2_sensor_voltage": float,   # V
    "catalyst_temp": float,       # °C
    "ambient_temp": float,        # °C
    "dtc_codes": List[str],       # Active DTCs
    "mileage_km": float           # Total mileage
}
```

**Output Prediction**:
```python
{
    "risk_score": float,          # 0.0-1.0 (overall health)
    "risk_level": str,            # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    "predictions": [
        {
            "component": str,     # "Battery", "Engine", "Cooling", etc.
            "probability": float, # 0.0-1.0
            "time_horizon_km": float,  # Predicted km until failure
            "confidence": float,  # Model confidence
            "reason": str         # Human-readable explanation
        }
    ],
    "recommendations": List[str], # Action items
    "anomaly_score": float,       # From autoencoder
    "attention_weights": Dict     # Feature importance
}
```

### 1.3 Data Flow Diagram

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│  OBD Data   │────>│   Preprocess │────>│  Feature Eng.  │
│  (Raw)      │     │   & Clean    │     │  (Normalized)  │
└─────────────┘     └──────────────┘     └───────┬────────┘
                                                  │
        ┌─────────────────────────────────────────┘
        │
        v
┌───────────────────────────────────────────────────────┐
│                    MODEL ENSEMBLE                      │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │ LSTM Base   │  │ CNN-LSTM    │  │ Attention     │  │
│  │ (40%)       │  │ (30%)       │  │ LSTM (30%)    │  │
│  └──────┬──────┘  └──────┬──────┘  └───────┬───────┘  │
│         │                │                  │          │
│         └────────────────┼──────────────────┘          │
│                          │                             │
│                    ┌─────v─────┐                       │
│                    │ Weighted  │                       │
│                    │ Average   │                       │
│                    └─────┬─────┘                       │
└──────────────────────────┼────────────────────────────┘
                           │
                           v
                   ┌───────────────┐
                   │  LSTM Auto-   │
                   │  encoder      │
                   │  (Anomaly)    │
                   └───────┬───────┘
                           │
                           v
                   ┌───────────────┐
                   │  Final        │
                   │  Prediction   │
                   └───────────────┘
```

---

## 2. NEURAL NETWORK ARCHITECTURES

### 2.1 LSTM Baseline Predictor

**Purpose**: Primary time-series forecasting for component failure prediction.

**Architecture**:
```
Input (sequence_length=30, features=15)
    │
    v
LSTM Layer 1 (128 units, return_sequences=True)
    │
    v
Dropout (0.2)
    │
    v
LSTM Layer 2 (64 units, return_sequences=False)
    │
    v
Dropout (0.2)
    │
    v
Dense (32 units, ReLU)
    │
    v
Dense (num_components, Sigmoid)
    │
    v
Output (failure probabilities per component)
```

**Key Parameters**:
- Sequence length: 30 time steps
- Learning rate: 0.001
- Batch size: 32
- Epochs: 100 (early stopping patience=10)

**When to Use**: Default model for all predictions. Best for stable, gradual degradation patterns.

### 2.2 CNN-LSTM Hybrid

**Purpose**: Extracts spatial patterns from sensor data before temporal analysis.

**Architecture**:
```
Input (sequence_length=30, features=15)
    │
    v
Conv1D (64 filters, kernel=3, ReLU)
    │
    v
MaxPooling1D (pool_size=2)
    │
    v
Conv1D (32 filters, kernel=3, ReLU)
    │
    v
LSTM (64 units)
    │
    v
Dense (32, ReLU)
    │
    v
Dense (num_components, Sigmoid)
```

**When to Use**: Best for detecting sudden changes or spikes in sensor patterns. Good for vibration and noise analysis.

### 2.3 Attention-LSTM (Physics-Informed)

**Purpose**: Uses attention mechanism weighted by automotive physics relationships.

**Architecture**:
```
Input (sequence_length=30, features=15)
    │
    v
LSTM Layer (128 units, return_sequences=True)
    │
    v
┌───────────────────────────────────────┐
│        ATTENTION MECHANISM            │
│                                       │
│  Query = Dense(hidden_states)         │
│  Key = Dense(hidden_states)           │
│  Value = hidden_states                │
│                                       │
│  Attention = softmax(Q·K^T / √d)      │
│  Output = Attention · Value           │
│                                       │
│  Physics Weights Applied:             │
│  - Coolant ↔ Engine Load: 1.5x        │
│  - Battery ↔ RPM: 1.3x                │
│  - Throttle ↔ Speed: 1.4x             │
└───────────────────────────────────────┘
    │
    v
Dense (64, ReLU)
    │
    v
Dense (num_components, Sigmoid)
```

**Physics Weight Matrix**:
The attention mechanism is biased by known automotive physics relationships:

| Relationship | Weight | Reason |
|--------------|--------|--------|
| Coolant ↔ Engine Load | 1.5x | High load increases cooling demand |
| Battery ↔ RPM | 1.3x | Alternator charging relationship |
| Throttle ↔ Speed | 1.4x | Direct acceleration relationship |
| O2 Sensor ↔ Fuel | 1.4x | Combustion efficiency indicator |
| MAF ↔ Engine Load | 1.3x | Air intake relationship |

**When to Use**: Best for interpretable predictions. Attention weights show which features drove the prediction.

### 2.4 LSTM Autoencoder (Anomaly Detection)

**Purpose**: Detects unusual patterns that don't match normal vehicle behavior.

**Architecture**:
```
ENCODER:
Input (sequence_length=30, features=15)
    │
    v
LSTM (64 units, return_sequences=True)
    │
    v
LSTM (32 units, return_sequences=False)
    │
    v
Latent Space (16 dimensions)

DECODER:
Latent Space
    │
    v
RepeatVector(30)
    │
    v
LSTM (32 units, return_sequences=True)
    │
    v
LSTM (64 units, return_sequences=True)
    │
    v
TimeDistributed Dense(15)
    │
    v
Reconstructed Input
```

**Anomaly Detection**:
- Reconstruction error = MSE(input, reconstructed)
- Threshold = mean(training_errors) + 3 * std(training_errors)
- If error > threshold → Anomaly detected

**When to Use**: Always runs in parallel. High anomaly score + low component probability → Unknown failure mode.

---

## 3. TRAINING PROCEDURES

### 3.1 Data Requirements

**Minimum Requirements**:
- 50+ telemetry samples per vehicle
- 30+ days of driving history
- At least 5 complete drive cycles
- No more than 20% missing values

**Optimal Training Data**:
- 500+ samples per vehicle
- 90+ days history
- Mix of city/highway driving
- Some known failure events (for supervised learning)

### 3.2 Training Configuration

```python
TRAINING_CONFIG = {
    "sequence_length": 30,        # Time steps per sample
    "batch_size": 32,
    "epochs": 100,
    "learning_rate": 0.001,
    "validation_split": 0.2,
    "early_stopping_patience": 10,
    "reduce_lr_patience": 5,
    "reduce_lr_factor": 0.5,
    "min_lr": 1e-6,

    # Data augmentation
    "noise_factor": 0.05,         # Add 5% Gaussian noise
    "time_shift_range": 3,        # Shift sequences ±3 steps

    # Ensemble weights (sum to 1.0)
    "lstm_weight": 0.4,
    "cnn_lstm_weight": 0.3,
    "attention_weight": 0.3
}
```

### 3.3 Training Pipeline Steps

1. **Data Loading**
   ```python
   # Load from CSV exported by Desktop app
   data = load_telemetry_csv(vehicle_id)
   ```

2. **Preprocessing**
   ```python
   # Clean and normalize
   data = remove_outliers(data, zscore_threshold=3)
   data = interpolate_missing(data, method='linear')
   data = normalize(data, method='minmax')  # 0-1 range
   ```

3. **Sequence Creation**
   ```python
   # Create sliding window sequences
   X, y = create_sequences(data, seq_length=30, target='failure_label')
   ```

4. **Model Training**
   ```python
   # Train each model in ensemble
   lstm_model.fit(X_train, y_train, validation_data=(X_val, y_val))
   cnn_lstm_model.fit(X_train, y_train, validation_data=(X_val, y_val))
   attention_model.fit(X_train, y_train, validation_data=(X_val, y_val))
   autoencoder.fit(X_train, X_train)  # Unsupervised
   ```

5. **Validation**
   ```python
   # Check performance metrics
   for model in [lstm_model, cnn_lstm_model, attention_model]:
       metrics = evaluate(model, X_test, y_test)
       assert metrics['auc'] > 0.75, "Model AUC too low"
       assert metrics['precision'] > 0.70, "Precision too low"
   ```

### 3.4 Validation Metrics to Monitor

| Metric | Target | Description |
|--------|--------|-------------|
| AUC-ROC | > 0.75 | Overall discrimination ability |
| Precision | > 0.70 | True positives / predicted positives |
| Recall | > 0.60 | True positives / actual positives |
| F1 Score | > 0.65 | Harmonic mean of precision/recall |
| Val Loss | Decreasing | Validation loss should trend down |
| Autoencoder MSE | < 0.1 | Reconstruction quality |

### 3.5 How to Know If Training Is Working

**Good Signs**:
- Validation loss decreasing alongside training loss
- AUC-ROC improving over epochs
- No significant gap between training and validation metrics
- Autoencoder reconstruction looks similar to input

**Warning Signs**:
- Validation loss increasing while training loss decreases → Overfitting
- Both losses stuck at high values → Underfitting
- Metrics jumping erratically → Learning rate too high
- Training takes extremely long → Check data size/quality

---

## 4. MODEL MANAGEMENT

### 4.1 Model Factory Pattern

The `ModelFactory` class manages the ensemble:

```python
class ModelFactory:
    def __init__(self):
        self.models = {
            'lstm': LSTMModel(),
            'cnn_lstm': CNNLSTMModel(),
            'attention': AttentionLSTMModel(),
            'autoencoder': LSTMAAutoencoder()
        }
        self.weights = {
            'lstm': 0.4,
            'cnn_lstm': 0.3,
            'attention': 0.3
        }

    def predict(self, data):
        predictions = {}
        for name, model in self.models.items():
            predictions[name] = model.predict(data)

        # Weighted ensemble
        final = sum(
            pred * self.weights[name]
            for name, pred in predictions.items()
            if name in self.weights
        )

        # Add anomaly score from autoencoder
        anomaly_score = self.models['autoencoder'].get_anomaly_score(data)

        return {
            'predictions': final,
            'anomaly_score': anomaly_score,
            'individual': predictions
        }
```

### 4.2 Model Versioning

Models are versioned by vehicle and training date:

```
models/
├── vehicle_ABC123/
│   ├── lstm_v1_2026-01-15.h5
│   ├── lstm_v2_2026-02-01.h5  (current)
│   ├── cnn_lstm_v1_2026-01-15.h5
│   ├── attention_v1_2026-01-15.h5
│   └── autoencoder_v1_2026-01-15.h5
├── vehicle_DEF456/
│   └── ...
└── global/
    ├── lstm_pretrained.h5     (transfer learning base)
    └── component_embeddings.h5
```

### 4.3 Model Updating

Models are automatically retrained when:
- 100+ new telemetry samples accumulated
- Prediction accuracy drops below threshold
- User manually triggers retraining

```python
def should_retrain(vehicle_id):
    new_samples = count_new_samples(vehicle_id)
    current_accuracy = get_recent_accuracy(vehicle_id)

    return (
        new_samples >= 100 or
        current_accuracy < 0.70 or
        days_since_last_training(vehicle_id) > 30
    )
```

---

## 5. DATA PIPELINE

### 5.1 Data Collection (Android → Server)

```
Android App                          Server
┌──────────┐    HTTP POST           ┌──────────┐
│ OBD Data │ ──────────────────────>│ /api/obd │
└──────────┘    Every 5 seconds     │ /data    │
                                    └────┬─────┘
                                         │
                                         v
                                    ┌──────────┐
                                    │ SQLite   │
                                    │ Database │
                                    └────┬─────┘
                                         │
                                         v
                                    ┌──────────┐
                                    │ CSV      │
                                    │ Export   │
                                    └──────────┘
```

### 5.2 Data Export Format

Desktop app exports training data as CSV:

```csv
timestamp,rpm,speed,coolant_temp,battery_voltage,engine_load,throttle_position,...
1706745600,2500,65,85,14.2,45,30,...
1706745605,2600,68,86,14.1,48,35,...
```

### 5.3 Feature Engineering

Raw OBD data is transformed into derived features:

| Feature | Formula | Purpose |
|---------|---------|---------|
| `rpm_change` | rpm[t] - rpm[t-1] | Acceleration indicator |
| `temp_gradient` | d(coolant)/dt | Cooling system health |
| `voltage_stability` | std(voltage, window=10) | Electrical stability |
| `load_efficiency` | speed / (rpm * load) | Engine efficiency |
| `thermal_stress` | max(coolant - ambient, 0) | Heat dissipation stress |

---

## 6. TROUBLESHOOTING

### 6.1 Common Training Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Overfitting | Val loss increases, train loss decreases | Increase dropout, reduce model size, add regularization |
| Underfitting | Both losses high and flat | Increase model capacity, train longer, check data quality |
| Vanishing gradients | Loss stuck, no improvement | Use gradient clipping, reduce learning rate |
| Exploding gradients | Loss becomes NaN | Add gradient clipping, normalize inputs |
| Memory errors | OOM during training | Reduce batch size, sequence length |

### 6.2 Prediction Debugging

```python
def debug_prediction(vehicle_id, data):
    factory = ModelFactory()
    result = factory.predict(data)

    print(f"Overall Risk: {result['predictions'].mean():.2f}")
    print(f"Anomaly Score: {result['anomaly_score']:.2f}")
    print("\nIndividual Model Predictions:")
    for name, pred in result['individual'].items():
        print(f"  {name}: {pred.mean():.2f}")

    if result['anomaly_score'] > 0.5:
        print("\n⚠️  High anomaly score - unusual pattern detected")

    # Check attention weights
    if 'attention_weights' in result:
        top_features = sorted(
            result['attention_weights'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        print("\nTop 5 influential features:")
        for feat, weight in top_features:
            print(f"  {feat}: {weight:.3f}")
```

### 6.3 Fallback Mechanisms

If ML prediction fails:
1. Return rule-based prediction (threshold-based)
2. Use global model if vehicle-specific unavailable
3. Return "Unable to predict" with explanation

```python
def get_prediction_with_fallback(vehicle_id, data):
    try:
        return ml_predict(vehicle_id, data)
    except ModelNotFoundError:
        return global_model_predict(data)
    except PredictionError:
        return rule_based_predict(data)
    except Exception as e:
        return {
            "error": True,
            "message": f"Prediction unavailable: {str(e)}",
            "fallback": "manual_inspection_recommended"
        }
```

---

## 7. API INTEGRATION

### 7.1 Server Prediction Endpoint

**Endpoint**: `POST /api/predict`

**Request**:
```json
{
    "vin": "ABC123456789",
    "mileage_km": 45000,
    "sensors": {
        "rpm": 2500,
        "speed": 65,
        "coolant_temp": 85,
        "battery_voltage": 14.2,
        "engine_load": 45
    }
}
```

**Response**:
```json
{
    "success": true,
    "risk_score": 0.35,
    "risk_level": "LOW",
    "top_risks": [
        {
            "component": "Battery",
            "probability": 0.25,
            "time_horizon_km": 5000,
            "reason": "Voltage instability detected"
        }
    ],
    "recommendations": [
        "Check battery health at next service"
    ],
    "model_version": "v2_2026-02-01",
    "confidence": 0.85
}
```

### 7.2 Desktop Training Trigger

**Endpoint**: `POST /api/ml/train`

**Request**:
```json
{
    "vehicle_id": "ABC123",
    "force": false
}
```

**Response**:
```json
{
    "success": true,
    "message": "Training queued",
    "estimated_time_minutes": 15,
    "samples_available": 523
}
```

---

## Appendix A: Component List

The AI predicts failure probability for these components:

| Component | Sensors Used | Typical Failure Indicators |
|-----------|--------------|----------------------------|
| Battery | Voltage, RPM, Load | Voltage drops, instability |
| Engine | RPM, Load, Coolant, MAF | Rough idle, misfires |
| Cooling System | Coolant temp, Ambient | Overheating, temp spikes |
| Fuel System | Fuel pressure, O2, MAF | Pressure drops, lean/rich |
| Transmission | Speed, RPM, Throttle | Slipping, delayed shifts |
| Exhaust/Catalyst | Catalyst temp, O2 | Efficiency drop |
| Electrical | Voltage, Load | Voltage irregularities |
| Brakes | Speed patterns | Unusual deceleration |

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| **LSTM** | Long Short-Term Memory - neural network for sequences |
| **CNN** | Convolutional Neural Network - pattern detection |
| **Attention** | Mechanism to focus on important features |
| **Autoencoder** | Neural network that compresses and reconstructs data |
| **Anomaly Score** | How unusual the current pattern is vs training data |
| **DTC** | Diagnostic Trouble Code from OBD-II |
| **MAF** | Mass Air Flow sensor |
| **OBD-II** | On-Board Diagnostics version 2 standard |

---

*Document maintained by PREDICT AI Team. Last updated February 2026.*
