"""Survival analysis engine — time-to-failure estimation using survival analysis.

Uses lifelines library for Cox PH and Kaplan-Meier estimators.
Outputs survival curves for Android charting and mean remaining life estimates.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Canonical component IDs matching unified_scoring_pipeline.py
COMPONENT_IDS = [
    "engine_oil",
    "coolant_system", 
    "battery",
    "brakes",
    "transmission_fluid",
    "spark_plugs",
    "catalytic_converter",
    "o2_sensors",
    "air_filter",
    "fuel_system",
]

# Feature columns from telemetry (5 stats × 15 sensors = 75 features)
SENSOR_COLUMNS = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "maf_rate", "intake_temp", "short_term_fuel_trim",
    "long_term_fuel_trim", "timing_advance", "injector_ms",
    "fuel_trim_b2", "accel_pedal", "ambient_temp",
]


class SurvivalEngine:
    """Survival analysis for time-to-failure estimation."""
    
    def __init__(self):
        """Initialize survival engine."""
        self.models: Dict[str, Any] = {}  # Component -> fitted model
        self.km_estimators: Dict[str, Any] = {}  # Component -> KaplanMeierFitter
        self.is_trained = False
        
    def _extract_features(self, telemetry_window: List[Dict[str, Any]]) -> np.ndarray:
        """Extract 75 statistical features from telemetry window.
        
        Features: mean, std, min, max, delta for each of 15 sensors
        
        Args:
            telemetry_window: List of telemetry readings
            
        Returns:
            Feature vector (75,)
        """
        if not telemetry_window or len(telemetry_window) < 2:
            return np.zeros(75)
        
        features = []
        
        for sensor in SENSOR_COLUMNS:
            values = []
            for reading in telemetry_window:
                val = reading.get(sensor)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (TypeError, ValueError):
                        values.append(0.0)
                else:
                    values.append(0.0)
            
            values = np.array(values)
            
            # Compute 5 statistics
            features.append(np.mean(values))      # mean
            features.append(np.std(values))       # std
            features.append(np.min(values))       # min
            features.append(np.max(values))       # max
            features.append(values[-1] - values[0])  # delta
        
        return np.array(features)
    
    async def train_from_db(
        self,
        session: AsyncSession,
        min_failures: int = 10,
    ) -> Dict[str, Any]:
        """Train survival models from database failure records.
        
        Args:
            session: Database session
            min_failures: Minimum failure records per component
            
        Returns:
            Training metrics
        """
        from predict.core.db.models.prediction_feedback import PredictionFeedback
        
        metrics = {
            "components_trained": [],
            "components_skipped": [],
            "samples_per_component": {},
        }
        
        try:
            from lifelines import CoxPHFitter, KaplanMeierFitter
        except ImportError:
            logger.error("lifelines library not installed. Install with: pip install lifelines")
            return metrics
        
        for component in COMPONENT_IDS:
            # Query failure records
            result = await session.execute(
                select(PredictionFeedback).where(
                    PredictionFeedback.component == component,
                    PredictionFeedback.was_correct == True,
                )
            )
            failure_records = result.scalars().all()
            
            if len(failure_records) < min_failures:
                logger.warning(
                    f"Insufficient failures for {component}: "
                    f"got {len(failure_records)}, need {min_failures}"
                )
                metrics["components_skipped"].append(component)
                continue
            
            # Build survival dataset
            # Each record: features, duration (days), event (1=failed, 0=censored)
            data_rows = []
            
            for record in failure_records:
                # Calculate duration from prediction timestamp to reported_at
                if record.predicted_at and record.reported_at:
                    duration_days = (record.reported_at - record.predicted_at).days
                    if duration_days > 0:
                        data_rows.append({
                            "duration": duration_days,
                            "event": 1,  # Failed
                            "component": component,
                        })
            
            if len(data_rows) < min_failures:
                logger.warning(f"Insufficient data for {component} after processing")
                metrics["components_skipped"].append(component)
                continue
            
            # Fit Kaplan-Meier estimator
            kmf = KaplanMeierFitter()
            durations = [r["duration"] for r in data_rows]
            events = [r["event"] for r in data_rows]
            
            kmf.fit(durations, event_observed=events)
            self.km_estimators[component] = kmf
            
            # Fit Cox PH model if we have covariates
            # For now, just use KM as primary model
            self.models[component] = kmf
            
            metrics["components_trained"].append(component)
            metrics["samples_per_component"][component] = len(data_rows)
            
            logger.info(f"Trained {component} survival model on {len(data_rows)} records")
        
        self.is_trained = len(self.models) > 0
        return metrics
    
    def train_from_synthetic(
        self,
        n_samples: int = 500,
    ) -> Dict[str, Any]:
        """Train on synthetic survival data for development.
        
        Args:
            n_samples: Samples per component
            
        Returns:
            Training metrics
        """
        metrics = {
            "components_trained": [],
            "components_skipped": [],
        }
        
        try:
            from lifelines import KaplanMeierFitter
        except ImportError:
            logger.warning("lifelines not installed, using scipy for survival")
            from scipy import stats
            
            # Fallback: use exponential distribution parameters
            for component in COMPONENT_IDS:
                # Generate synthetic survival times
                scale = np.random.uniform(100, 500)  # Mean survival time
                self.models[component] = {"scale": scale, "dist": "exponential"}
                metrics["components_trained"].append(component)
            
            self.is_trained = True
            return metrics
        
        np.random.seed(42)
        
        for component in COMPONENT_IDS:
            # Generate synthetic survival times based on component type
            if component == "engine_oil":
                # Oil changes every ~180 days
                base_time = 180
                scale = 30
            elif component == "battery":
                # Batteries last ~1095 days (3 years)
                base_time = 1095
                scale = 200
            elif component == "brakes":
                # Brake pads ~730 days (2 years)
                base_time = 730
                scale = 150
            else:
                base_time = 365
                scale = 100
            
            # Generate survival times (Weibull distribution)
            durations = np.random.weibull(2, n_samples) * base_time + np.random.normal(0, scale, n_samples)
            durations = np.clip(durations, 1, None)  # Ensure positive
            
            # Some censored data (event=0) - hasn't failed yet
            events = np.random.choice([0, 1], n_samples, p=[0.2, 0.8])
            
            # Fit Kaplan-Meier
            kmf = KaplanMeierFitter()
            kmf.fit(durations, event_observed=events)
            
            self.km_estimators[component] = kmf
            self.models[component] = kmf
            
            metrics["components_trained"].append(component)
            logger.info(f"Trained {component} survival model on {n_samples} synthetic samples")
        
        self.is_trained = True
        return metrics
    
    def predict_survival_curve(
        self,
        component: str,
        days_ahead: int = 365,
    ) -> Optional[Dict[str, Any]]:
        """Predict survival curve for a component.
        
        Args:
            component: Component ID
            days_ahead: Days to predict ahead
            
        Returns:
            Survival curve data or None
        """
        if component not in self.models:
            return None
        
        model = self.models[component]
        
        # Generate timeline
        timeline = np.linspace(0, days_ahead, 50)
        
        if hasattr(model, 'predict_survival_function'):
            # lifelines KaplanMeierFitter
            sf = model.predict_survival_function(timeline)
            probabilities = sf.values.flatten().tolist()
        elif hasattr(model, 'survival_function_'):
            # lifelines fitted model
            sf = model.survival_function_
            # Interpolate to timeline
            probabilities = []
            for t in timeline:
                # Find closest time point
                idx = np.argmin(np.abs(sf.index - t))
                probabilities.append(float(sf.iloc[idx]))
        elif isinstance(model, dict) and model.get("dist") == "exponential":
            # Synthetic exponential model
            from scipy import stats
            scale = model["scale"]
            probabilities = [stats.expon.sf(t, scale=scale) for t in timeline]
        else:
            return None
        
        return {
            "component": component,
            "timeline_days": timeline.tolist(),
            "survival_probability": probabilities,
            "days_ahead": days_ahead,
        }
    
    def predict_mean_remaining_life(
        self,
        component: str,
        current_age_days: int = 0,
    ) -> Optional[int]:
        """Predict mean remaining life for a component.
        
        Args:
            component: Component ID
            current_age_days: Current age of component in days
            
        Returns:
            Mean remaining life in days, or None
        """
        if component not in self.models:
            return None
        
        model = self.models[component]
        
        if hasattr(model, 'predict_median'):
            # lifelines model
            median_life = model.predict_median([current_age_days])
            if isinstance(median_life, (list, np.ndarray)):
                median_life = median_life[0]
            remaining = max(0, int(median_life) - current_age_days)
            return remaining
        elif isinstance(model, dict) and model.get("dist") == "exponential":
            # Exponential model: memoryless property
            scale = model["scale"]
            return int(scale)
        
        # Default: estimate from survival curve
        curve = self.predict_survival_curve(component, days_ahead=2000)
        if curve:
            # Find time where survival probability drops below 0.5
            for t, p in zip(curve["timeline_days"], curve["survival_probability"]):
                if p < 0.5:
                    return max(0, int(t) - current_age_days)
        
        return None
    
    def predict_all_components(
        self,
        current_ages: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Predict survival for all components.
        
        Args:
            current_ages: Dict mapping component -> current age in days
            
        Returns:
            Dict mapping component -> prediction results
        """
        if not self.is_trained:
            logger.warning("Models not trained")
            return {}
        
        if current_ages is None:
            current_ages = {comp: 0 for comp in COMPONENT_IDS}
        
        results = {}
        
        for component in COMPONENT_IDS:
            current_age = current_ages.get(component, 0)
            
            survival_curve = self.predict_survival_curve(component)
            remaining_life = self.predict_mean_remaining_life(component, current_age)
            
            results[component] = {
                "mean_remaining_life_days": remaining_life,
                "survival_curve": survival_curve,
                "current_age_days": current_age,
            }
        
        return results
    
    def serialize(self, output_dir: str) -> Dict[str, str]:
        """Serialize survival models.
        
        Args:
            output_dir: Directory to save models
            
        Returns:
            Dict mapping component -> file path
        """
        if not self.is_trained:
            raise ValueError("Models not trained")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        paths = {}
        
        for component, model in self.models.items():
            model_path = output_dir / f"{component}_survival.json"
            
            # Extract survival function data
            if hasattr(model, 'survival_function_'):
                sf = model.survival_function_
                data = {
                    "timeline": sf.index.tolist(),
                    "survival_prob": sf.values.flatten().tolist(),
                    "median_survival": float(model.median_survival_time_) if hasattr(model, 'median_survival_time_') else None,
                }
            elif isinstance(model, dict):
                data = model
            else:
                continue
            
            with open(model_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            paths[component] = str(model_path)
        
        # Save metadata
        metadata = {
            "components": COMPONENT_IDS,
            "sensor_columns": SENSOR_COLUMNS,
            "n_components": len(self.models),
        }
        
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        paths["metadata"] = str(metadata_path)
        
        return paths
    
    def load(self, model_dir: str) -> None:
        """Load survival models from directory.
        
        Args:
            model_dir: Directory containing model files
        """
        model_dir = Path(model_dir)
        
        # Load metadata
        metadata_path = model_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            logger.info(f"Loaded metadata: {metadata}")
        
        # Load models
        for component in COMPONENT_IDS:
            model_path = model_dir / f"{component}_survival.json"
            if model_path.exists():
                with open(model_path, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct simple model
                self.models[component] = data
                logger.info(f"Loaded {component} survival model")
        
        self.is_trained = len(self.models) > 0
        logger.info(f"Loaded {len(self.models)} survival models")
    
    def get_survival_probability_at_time(
        self,
        component: str,
        days: int,
    ) -> Optional[float]:
        """Get survival probability at specific time.
        
        Args:
            component: Component ID
            days: Time in days
            
        Returns:
            Survival probability (0-1) or None
        """
        curve = self.predict_survival_curve(component, days_ahead=days)
        if not curve:
            return None
        
        # Find closest time point
        timeline = curve["timeline_days"]
        probabilities = curve["survival_probability"]
        
        idx = np.argmin(np.abs(np.array(timeline) - days))
        return probabilities[idx]
