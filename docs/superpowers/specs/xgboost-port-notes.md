# XGBoost Port Notes

Extracted from `predict/core/ai/failure_engine.py` before deletion.
These patterns should be reimplemented cleanly in the v3 training pipeline.

---

## Model Config (Tuned Hyperparameters)

```python
XGBOOST_CONFIG = {
    'n_estimators': 200,
    'max_depth': 8,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'random_state': 42,
    'n_jobs': -1,
}

LIGHTGBM_CONFIG = {
    'n_estimators': 200,
    'max_depth': 8,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'random_state': 42,
    'n_jobs': -1,
    'verbose': -1,
}

RANDOM_FOREST_CONFIG = {
    'n_estimators': 200,
    'max_depth': 15,
    'min_samples_split': 5,
    'min_samples_leaf': 2,
    'random_state': 42,
    'n_jobs': -1,
}
```

## Feature Engineering Patterns

### Rolling Window Features
```python
rolling_windows = [3, 5, 10]
numeric_cols = ['rpm', 'speed', 'coolant_temp', 'battery_voltage', 'engine_load']

for col in numeric_cols:
    for window in rolling_windows:
        df[f'{col}_rolling_mean_{window}'] = df[col].rolling(window=window, min_periods=1).mean()
        df[f'{col}_rolling_std_{window}']  = df[col].rolling(window=window, min_periods=1).std()
```

### Ratio / Interaction Features
```python
# RPM-to-speed ratio (gear proxy)
df['rpm_speed_ratio'] = df['rpm'] / (df['speed'] + 1)

# Temperature-load interaction (thermal stress proxy)
df['temp_load_interaction'] = df['coolant_temp'] * df['engine_load'] / 1000
```

### Time-Based Features
```python
df['hour'] = df['timestamp'].dt.hour
df['day_of_week'] = df['timestamp'].dt.dayofweek
df['month'] = df['timestamp'].dt.month
df['is_weekend'] = (df['timestamp'].dt.dayofweek >= 5).astype(int)

# Cyclical encoding for hour (preserves proximity of 23:00 and 01:00)
df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
```

### Historical Context Features
```python
# Recent averages from trailing window
for col in ['rpm', 'speed', 'coolant_temp', 'battery_voltage', 'engine_load']:
    recent = hist_df[col].tail(5)
    df[f'{col}_recent_avg'] = recent.mean()
    df[f'{col}_recent_std'] = recent.std()
```

## Feature Selection

Two methods were used:
1. **Univariate** (SelectKBest with f_classif) -- fast, used by default
2. **RFE** (Recursive Feature Elimination with RandomForest) -- better but slower

```python
# Univariate
selector = SelectKBest(score_func=f_classif, k=min(30, X.shape[1]))
selector.fit(X, y)
selected = X.columns[selector.get_support()].tolist()

# RFE
rf = RandomForestClassifier(n_estimators=50, random_state=42)
selector = RFE(estimator=rf, n_features_to_select=min(k, X.shape[1]))
selector.fit(X, y)
selected = X.columns[selector.get_support()].tolist()
```

## Ensemble Architecture

Soft-voting ensemble combining RF + XGBoost + LightGBM:

```python
estimators = [('rf', rf_model)]
if xgboost_available:
    estimators.append(('xgb', xgb_model))
if lightgbm_available:
    estimators.append(('lgb', lgb_model))

ensemble = VotingClassifier(estimators=estimators, voting='soft')
```

## Ensemble Feature Importance

Averaged across all tree-based models:

```python
for model_name in ['random_forest', 'xgboost', 'lightgbm']:
    model = models.get(model_name)
    if model and hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        for i, feat in enumerate(selected_features):
            feature_importance.setdefault(feat, []).append(importances[i])

averaged = {feat: float(np.mean(vals)) for feat, vals in feature_importance.items()}
```

## Confidence Estimation

Model agreement as confidence proxy:

```python
std = np.std(probabilities)
confidence = 1 - (std / 0.5)  # Higher agreement = higher confidence
confidence = max(0.5, min(1.0, confidence))
```

## Hybrid AI Engine (Isolation Forest + Random Forest)

Unsupervised anomaly detection combined with supervised failure prediction:

```python
# Anomaly score from Isolation Forest
anomaly_score = -1 * iso_model.decision_function(vector_scaled)[0]
anomaly_risk = 1.0 if anomaly_score > 0 else 0.0

# Supervised failure probability
failure_prob = rf_model.predict_proba(vector_scaled)[0][1]

# Combined risk
total_risk = max(failure_prob, anomaly_risk * 0.8)
```

## Rule-Based Fallback Thresholds

Used when ML models are not trained:

```python
thresholds = {
    'battery_voltage': {'critical_max': 16.0, 'critical_min': 11.8, 'warning_min': 12.2, 'normal_min': 12.6},
    'coolant_temp':    {'critical_max': 110,  'warning_max': 100,   'normal_max': 95},
    'engine_load':     {'critical_min': 90,   'warning_min': 80,    'normal_max': 75},
    'rpm':             {'critical_min': 5000, 'warning_min': 4000,  'normal_max': 3500},
}
```

## SHAP Explainability

Used TreeExplainer for per-model SHAP values:

```python
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)
```

## Hyperparameter Tuning (GridSearchCV)

```python
param_grid = {
    'n_estimators': [100, 200],
    'max_depth': [10, 15, None],
    'min_samples_split': [2, 5],
    'min_samples_leaf': [1, 2],
}
grid_search = GridSearchCV(rf, param_grid, cv=3, scoring='roc_auc', n_jobs=-1)
```

## Model Persistence

Dual format: joblib (primary, fast) with standard library fallback. Metadata saved as both binary and JSON.

## Notes for v3 Reimplementation

- The rolling window features (mean + std at windows 3, 5, 10) were the most useful
- rpm_speed_ratio and temp_load_interaction were effective interaction features
- Cyclical hour encoding is important for time-of-day patterns
- SelectKBest with k=30 was a good default for initial feature pruning
- The hybrid anomaly + supervised approach is worth keeping
- SHAP integration was good but optional (heavy dependency)
- LightGBM verbose=-1 is needed to suppress training output
