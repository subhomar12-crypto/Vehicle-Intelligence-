"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Remaining Useful Life (RUL) Estimation

Remaining Useful Life (RUL) Estimation Module
==============================================
Predicts when components will fail based on degradation trends.

Features:
- Degradation curve fitting (linear, exponential, polynomial)
- Weibull distribution-based life estimation
- Component-specific life models
- Confidence intervals for predictions
- Mileage and time-based projections
"""

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
import logging
from pathlib import Path
from collections import deque
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class DegradationModel(Enum):
    """Types of degradation models."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    POLYNOMIAL = "polynomial"
    WEIBULL = "weibull"


@dataclass
class ComponentLifeModel:
    """Defines life expectancy model for a component."""
    component_id: str
    name: str
    sensor_parameter: str  # Primary sensor to track
    failure_threshold: float  # Value at which component is considered failed
    warning_threshold: float  # Value at which warning should be issued
    nominal_value: float  # Expected healthy value
    degradation_direction: str  # "increase" or "decrease"
    typical_life_miles: int  # Average life in miles
    typical_life_years: float  # Average life in years
    weibull_shape: float  # Weibull shape parameter (beta)
    weibull_scale: float  # Weibull scale parameter (eta)


@dataclass
class RULPrediction:
    """Result of RUL prediction."""
    component_id: str
    component_name: str
    current_value: float
    current_health_pct: float  # 0-100%
    predicted_rul_miles: Optional[int]
    predicted_rul_days: Optional[int]
    confidence_interval: Tuple[int, int]  # (low, high) in same unit
    confidence_level: float  # 0-1
    degradation_rate: float  # Units per mile or per day
    degradation_model: str
    trend: str  # "stable", "degrading", "rapid_degradation"
    recommendation: str
    timestamp: str


class RULEstimator:
    """
    Estimates Remaining Useful Life for vehicle components.
    Uses physics-informed models combined with observed degradation.
    """

    def __init__(self, config=None):
        """Initialize RUL estimator."""
        self.config = config

        # Component life models
        self.component_models = self._define_component_models()

        # Historical data for degradation tracking
        self.degradation_history: Dict[str, Dict[str, deque]] = {}  # vehicle_id -> component -> readings

        # Storage path
        self.storage_path = CONFIG.AI_DIR / "rul_data"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Cached RUL predictions
        self.cached_predictions: Dict[str, Dict[str, RULPrediction]] = {}

        # Load saved history
        self._load_history()

        logger.info(f"RUL Estimator initialized with {len(self.component_models)} component models")

    def _define_component_models(self) -> Dict[str, ComponentLifeModel]:
        """Define life models for trackable components."""
        models = {}

        # Battery
        models['battery'] = ComponentLifeModel(
            component_id='battery',
            name='Battery',
            sensor_parameter='battery_voltage',
            failure_threshold=11.5,
            warning_threshold=12.0,
            nominal_value=12.6,
            degradation_direction='decrease',
            typical_life_miles=50000,
            typical_life_years=4.0,
            weibull_shape=2.5,
            weibull_scale=4.5
        )

        # Alternator
        models['alternator'] = ComponentLifeModel(
            component_id='alternator',
            name='Alternator',
            sensor_parameter='charging_voltage',  # Voltage while running
            failure_threshold=13.0,
            warning_threshold=13.5,
            nominal_value=14.2,
            degradation_direction='decrease',
            typical_life_miles=100000,
            typical_life_years=7.0,
            weibull_shape=3.0,
            weibull_scale=7.5
        )

        # Thermostat
        models['thermostat'] = ComponentLifeModel(
            component_id='thermostat',
            name='Thermostat',
            sensor_parameter='warmup_time',  # Time to reach operating temp
            failure_threshold=20,  # Minutes
            warning_threshold=15,
            nominal_value=8,
            degradation_direction='increase',
            typical_life_miles=75000,
            typical_life_years=5.0,
            weibull_shape=2.0,
            weibull_scale=5.5
        )

        # Fuel Pump
        models['fuel_pump'] = ComponentLifeModel(
            component_id='fuel_pump',
            name='Fuel Pump',
            sensor_parameter='fuel_trim_at_load',  # STFT under high load
            failure_threshold=25,
            warning_threshold=15,
            nominal_value=0,
            degradation_direction='increase',
            typical_life_miles=100000,
            typical_life_years=8.0,
            weibull_shape=2.8,
            weibull_scale=8.0
        )

        # Spark Plugs
        models['spark_plugs'] = ComponentLifeModel(
            component_id='spark_plugs',
            name='Spark Plugs',
            sensor_parameter='misfire_rate',  # Derived from misfire counts
            failure_threshold=5.0,  # Misfires per 1000 revolutions
            warning_threshold=2.0,
            nominal_value=0,
            degradation_direction='increase',
            typical_life_miles=60000,  # Iridium plugs
            typical_life_years=5.0,
            weibull_shape=3.5,
            weibull_scale=5.0
        )

        # Oxygen Sensors
        models['o2_sensor'] = ComponentLifeModel(
            component_id='o2_sensor',
            name='Oxygen Sensor',
            sensor_parameter='o2_response_time',  # Response time degradation
            failure_threshold=500,  # ms
            warning_threshold=300,
            nominal_value=100,
            degradation_direction='increase',
            typical_life_miles=80000,
            typical_life_years=6.0,
            weibull_shape=2.5,
            weibull_scale=6.0
        )

        # Catalytic Converter
        models['catalytic_converter'] = ComponentLifeModel(
            component_id='catalytic_converter',
            name='Catalytic Converter',
            sensor_parameter='cat_efficiency',  # Derived from O2 sensors
            failure_threshold=70,  # Efficiency %
            warning_threshold=85,
            nominal_value=98,
            degradation_direction='decrease',
            typical_life_miles=150000,
            typical_life_years=10.0,
            weibull_shape=3.0,
            weibull_scale=10.0
        )

        # MAF Sensor
        models['maf_sensor'] = ComponentLifeModel(
            component_id='maf_sensor',
            name='MAF Sensor',
            sensor_parameter='fuel_trim_drift',  # Long-term fuel trim drift
            failure_threshold=20,
            warning_threshold=12,
            nominal_value=0,
            degradation_direction='increase',
            typical_life_miles=120000,
            typical_life_years=8.0,
            weibull_shape=2.5,
            weibull_scale=8.0
        )

        # Coolant (fluid degradation)
        models['coolant'] = ComponentLifeModel(
            component_id='coolant',
            name='Engine Coolant',
            sensor_parameter='temp_variance',  # Temperature stability
            failure_threshold=10,  # Degrees variance
            warning_threshold=5,
            nominal_value=2,
            degradation_direction='increase',
            typical_life_miles=30000,  # Or 2 years
            typical_life_years=2.0,
            weibull_shape=4.0,
            weibull_scale=2.5
        )

        # Transmission (if ATF)
        models['transmission_fluid'] = ComponentLifeModel(
            component_id='transmission_fluid',
            name='Transmission Fluid',
            sensor_parameter='shift_quality',  # Derived from RPM/speed changes
            failure_threshold=50,  # Quality score
            warning_threshold=70,
            nominal_value=95,
            degradation_direction='decrease',
            typical_life_miles=60000,
            typical_life_years=4.0,
            weibull_shape=3.0,
            weibull_scale=4.5
        )

        return models

    def _load_history(self):
        """Load saved degradation history."""
        history_file = self.storage_path / "degradation_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    for vehicle_id, components in data.items():
                        self.degradation_history[vehicle_id] = {}
                        for comp_id, readings in components.items():
                            self.degradation_history[vehicle_id][comp_id] = deque(readings, maxlen=1000)
                logger.info(f"Loaded degradation history for {len(self.degradation_history)} vehicles")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

    def _save_history(self):
        """Save degradation history to disk."""
        history_file = self.storage_path / "degradation_history.json"
        try:
            data = {}
            for vehicle_id, components in self.degradation_history.items():
                data[vehicle_id] = {
                    comp_id: list(readings)
                    for comp_id, readings in components.items()
                }
            with open(history_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")

    def add_reading(self, vehicle_id: str, component_id: str, value: float,
                    mileage: Optional[int] = None, timestamp: datetime = None):
        """
        Add a component health reading.

        Args:
            vehicle_id: Vehicle identifier
            component_id: Component being tracked
            value: Current measured value
            mileage: Current vehicle mileage (optional)
            timestamp: Reading timestamp (defaults to now)
        """
        if vehicle_id not in self.degradation_history:
            self.degradation_history[vehicle_id] = {}

        if component_id not in self.degradation_history[vehicle_id]:
            self.degradation_history[vehicle_id][component_id] = deque(maxlen=1000)

        reading = {
            'value': value,
            'mileage': mileage,
            'timestamp': (timestamp or datetime.now()).isoformat()
        }

        self.degradation_history[vehicle_id][component_id].append(reading)

    def estimate_rul(self, vehicle_id: str, component_id: str,
                     current_value: float = None,
                     current_mileage: int = None) -> Optional[RULPrediction]:
        """
        Estimate remaining useful life for a component.

        Args:
            vehicle_id: Vehicle identifier
            component_id: Component to estimate
            current_value: Current measured value (optional, uses latest if not provided)
            current_mileage: Current vehicle mileage (optional)

        Returns:
            RULPrediction object or None if insufficient data
        """
        model = self.component_models.get(component_id)
        if not model:
            logger.warning(f"No model for component: {component_id}")
            return None

        # Get historical readings
        history = self.degradation_history.get(vehicle_id, {}).get(component_id, [])

        # Use provided current value or get from history
        if current_value is None:
            if not history:
                return None
            current_value = history[-1]['value']

        # Calculate current health percentage
        health_pct = self._calculate_health_percentage(current_value, model)

        # Determine degradation rate and trend
        degradation_rate, trend, deg_model = self._fit_degradation_curve(
            history, model, current_value, current_mileage
        )

        # Estimate RUL
        rul_miles, rul_days, confidence = self._project_remaining_life(
            current_value, degradation_rate, model, current_mileage, trend
        )

        # Calculate confidence interval
        ci_low, ci_high = self._calculate_confidence_interval(
            rul_miles or rul_days, confidence, model
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            component_id, health_pct, rul_miles, rul_days, trend, model
        )

        prediction = RULPrediction(
            component_id=component_id,
            component_name=model.name,
            current_value=round(current_value, 2),
            current_health_pct=round(health_pct, 1),
            predicted_rul_miles=rul_miles,
            predicted_rul_days=rul_days,
            confidence_interval=(ci_low, ci_high),
            confidence_level=round(confidence, 2),
            degradation_rate=round(degradation_rate, 6),
            degradation_model=deg_model,
            trend=trend,
            recommendation=recommendation,
            timestamp=datetime.now().isoformat()
        )

        # Cache the prediction
        if vehicle_id not in self.cached_predictions:
            self.cached_predictions[vehicle_id] = {}
        self.cached_predictions[vehicle_id][component_id] = prediction

        return prediction

    def _calculate_health_percentage(self, current_value: float,
                                      model: ComponentLifeModel) -> float:
        """Calculate current health as percentage (0-100)."""
        if model.degradation_direction == 'decrease':
            # Health decreases as value decreases (e.g., battery voltage)
            if current_value >= model.nominal_value:
                return 100.0
            elif current_value <= model.failure_threshold:
                return 0.0
            else:
                range_size = model.nominal_value - model.failure_threshold
                health = ((current_value - model.failure_threshold) / range_size) * 100
                return max(0, min(100, health))
        else:
            # Health decreases as value increases (e.g., fuel trim drift)
            if current_value <= model.nominal_value:
                return 100.0
            elif current_value >= model.failure_threshold:
                return 0.0
            else:
                range_size = model.failure_threshold - model.nominal_value
                health = ((model.failure_threshold - current_value) / range_size) * 100
                return max(0, min(100, health))

    def _fit_degradation_curve(self, history: List[Dict], model: ComponentLifeModel,
                               current_value: float, current_mileage: int = None
                               ) -> Tuple[float, str, str]:
        """
        Fit degradation curve to historical data.

        Returns:
            Tuple of (degradation_rate, trend, model_type)
        """
        if len(history) < 3:
            # Insufficient data - use default degradation rate
            default_rate = self._get_default_degradation_rate(model)
            return default_rate, 'unknown', 'default'

        # Extract values and time/mileage
        values = [r['value'] for r in history]
        timestamps = [datetime.fromisoformat(r['timestamp']) for r in history]
        mileages = [r.get('mileage') for r in history]

        # Use mileage if available, otherwise time
        if all(m is not None for m in mileages):
            x_data = np.array(mileages)
            x_unit = 'miles'
        else:
            # Convert to days from first reading
            first_time = timestamps[0]
            x_data = np.array([(t - first_time).total_seconds() / 86400 for t in timestamps])
            x_unit = 'days'

        y_data = np.array(values)

        # Try linear fit
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_data, y_data)
            r_squared = r_value ** 2

            # Determine trend
            if abs(slope) < std_err:
                trend = 'stable'
            elif model.degradation_direction == 'decrease':
                trend = 'degrading' if slope < 0 else 'improving'
            else:
                trend = 'degrading' if slope > 0 else 'improving'

            # Check for rapid degradation
            if trend == 'degrading':
                expected_rate = self._get_default_degradation_rate(model)
                if abs(slope) > abs(expected_rate) * 2:
                    trend = 'rapid_degradation'

            return abs(slope), trend, 'linear'

        except Exception as e:
            logger.warning(f"Failed to fit degradation curve: {e}")
            return self._get_default_degradation_rate(model), 'unknown', 'default'

    def _get_default_degradation_rate(self, model: ComponentLifeModel) -> float:
        """Get default degradation rate based on component life model."""
        # Calculate expected degradation over typical life
        value_range = abs(model.nominal_value - model.failure_threshold)
        rate_per_mile = value_range / model.typical_life_miles

        return rate_per_mile

    def _project_remaining_life(self, current_value: float, degradation_rate: float,
                                model: ComponentLifeModel, current_mileage: int = None,
                                trend: str = 'degrading') -> Tuple[Optional[int], Optional[int], float]:
        """
        Project remaining life based on current state and degradation rate.

        Returns:
            Tuple of (rul_miles, rul_days, confidence)
        """
        if trend == 'stable' or trend == 'improving':
            # Component is stable or improving - high RUL
            return model.typical_life_miles, int(model.typical_life_years * 365), 0.6

        if degradation_rate == 0:
            return None, None, 0.3

        # Calculate remaining value until failure
        if model.degradation_direction == 'decrease':
            remaining_value = current_value - model.failure_threshold
        else:
            remaining_value = model.failure_threshold - current_value

        if remaining_value <= 0:
            return 0, 0, 0.9  # Already at or past failure

        # Project time/mileage to failure
        projected_units = remaining_value / degradation_rate

        # Determine confidence based on data quality and trend
        confidence = 0.7
        if trend == 'rapid_degradation':
            confidence = 0.8  # More confident in rapid degradation
        elif trend == 'unknown':
            confidence = 0.4

        # Apply Weibull correction if we have mileage data
        if current_mileage is not None:
            # Use Weibull distribution to adjust prediction
            weibull_factor = self._weibull_survival_factor(
                current_mileage, model.weibull_shape, model.weibull_scale
            )
            projected_units *= weibull_factor
            confidence *= 1.1  # Slightly higher confidence with mileage data

        rul_miles = int(projected_units) if projected_units > 0 else 0

        # Convert to days using typical driving (12,000 miles/year = ~33 miles/day)
        daily_miles = 33
        rul_days = int(rul_miles / daily_miles) if rul_miles else 0

        return rul_miles, rul_days, min(1.0, confidence)

    def _weibull_survival_factor(self, current_mileage: int,
                                  shape: float, scale: float) -> float:
        """
        Calculate Weibull survival factor to adjust RUL prediction.
        Uses conditional reliability given current mileage.
        """
        # Convert scale from years to miles (assuming 12,000 miles/year)
        scale_miles = scale * 12000

        # Current survival probability
        current_survival = np.exp(-(current_mileage / scale_miles) ** shape)

        if current_survival < 0.01:
            return 0.5  # Component has exceeded expected life

        # Factor to adjust remaining life
        return min(2.0, max(0.5, current_survival))

    def _calculate_confidence_interval(self, rul_estimate: int,
                                        confidence: float,
                                        model: ComponentLifeModel) -> Tuple[int, int]:
        """Calculate confidence interval for RUL estimate."""
        if rul_estimate is None or rul_estimate <= 0:
            return (0, 0)

        # Width of interval based on confidence
        uncertainty = 1 - confidence
        margin = rul_estimate * (0.2 + uncertainty * 0.3)  # 20-50% margin

        low = max(0, int(rul_estimate - margin))
        high = int(rul_estimate + margin)

        return (low, high)

    def _generate_recommendation(self, component_id: str, health_pct: float,
                                  rul_miles: int, rul_days: int, trend: str,
                                  model: ComponentLifeModel) -> str:
        """Generate maintenance recommendation based on RUL prediction."""
        if health_pct >= 90:
            return f"{model.name} is in excellent condition. No action needed."

        if health_pct >= 70:
            if trend == 'stable':
                return f"{model.name} is healthy. Continue normal monitoring."
            else:
                return f"{model.name} showing early degradation. Monitor closely."

        if health_pct >= 50:
            if rul_miles and rul_miles < 10000:
                return f"Schedule {model.name.lower()} inspection/replacement within {rul_miles:,} miles."
            elif rul_days and rul_days < 180:
                return f"Schedule {model.name.lower()} inspection within {rul_days} days."
            else:
                return f"{model.name} degradation detected. Plan replacement at next service."

        if health_pct >= 25:
            if trend == 'rapid_degradation':
                return f"URGENT: {model.name} degrading rapidly. Replace as soon as possible."
            else:
                return f"{model.name} needs replacement soon. Schedule service promptly."

        # Health < 25%
        return f"CRITICAL: {model.name} near failure. Replace immediately to avoid breakdown."

    def estimate_all_components(self, vehicle_id: str,
                                 current_data: Dict[str, Any] = None,
                                 current_mileage: int = None) -> List[RULPrediction]:
        """
        Estimate RUL for all trackable components.

        Args:
            vehicle_id: Vehicle identifier
            current_data: Current sensor data (optional)
            current_mileage: Current vehicle mileage (optional)

        Returns:
            List of RUL predictions for all components with sufficient data
        """
        predictions = []

        # Map current data to component parameters
        param_mapping = {
            'battery': ['battery_voltage', 'control_module_voltage'],
            'alternator': ['battery_voltage', 'control_module_voltage'],  # While running
            'maf_sensor': ['long_term_fuel_trim_1', 'fuel_trim_long']
        }

        for comp_id, model in self.component_models.items():
            current_value = None

            # Try to get current value from data
            if current_data:
                for param in param_mapping.get(comp_id, [model.sensor_parameter]):
                    if param in current_data and current_data[param] is not None:
                        try:
                            current_value = float(current_data[param])
                            break
                        except (ValueError, TypeError):
                            pass

            # Estimate RUL
            prediction = self.estimate_rul(
                vehicle_id, comp_id,
                current_value=current_value,
                current_mileage=current_mileage
            )

            if prediction:
                predictions.append(prediction)

        return predictions

    def get_maintenance_schedule(self, vehicle_id: str,
                                  current_mileage: int = None) -> List[Dict[str, Any]]:
        """
        Generate a maintenance schedule based on RUL predictions.

        Returns:
            List of maintenance items sorted by urgency
        """
        predictions = self.estimate_all_components(
            vehicle_id, current_mileage=current_mileage
        )

        schedule = []
        for pred in predictions:
            if pred.current_health_pct < 90:  # Only include items needing attention
                urgency_score = (100 - pred.current_health_pct)
                if pred.trend == 'rapid_degradation':
                    urgency_score *= 1.5

                schedule.append({
                    'component': pred.component_name,
                    'health_pct': pred.current_health_pct,
                    'rul_miles': pred.predicted_rul_miles,
                    'rul_days': pred.predicted_rul_days,
                    'urgency_score': round(urgency_score, 1),
                    'trend': pred.trend,
                    'recommendation': pred.recommendation,
                    'confidence': pred.confidence_level
                })

        # Sort by urgency (highest first)
        schedule.sort(key=lambda x: x['urgency_score'], reverse=True)

        return schedule

    def save_data(self):
        """Save all RUL data to disk."""
        self._save_history()
        logger.info("RUL data saved")
