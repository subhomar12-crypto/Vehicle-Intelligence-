"""
Remaining Useful Life (RUL) Estimation for vehicle components.

Fits degradation curves (linear and exponential) to historical sensor data
and predicts when a component will cross a failure threshold.

Features:
- Wiener process degradation modeling
- Exponential degradation curve fitting
- Confidence intervals for RUL predictions
- First principles-based estimation
- Survival analysis integration (Weibull)
- Component-specific life models
"""

import logging
import math
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import deque
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit

from predict.core.config import get_config

logger = logging.getLogger(__name__)


# Mileage estimation chain (Intelligence Engine v2)
def estimate_mileage(vehicle_profile: dict) -> tuple:
    """Returns (mileage_km, source) using priority chain.

    Priority:
      1. OBD odometer (from latest telemetry)
      2. GPS tracker accumulated km
      3. User-entered at registration
      4. Estimated from vehicle age (25,000 km/year Qatar average)
    """
    # Priority 1: OBD odometer (from latest telemetry)
    obd_odo = vehicle_profile.get("obd_odometer")
    if obd_odo and obd_odo > 0:
        return int(obd_odo), "obd_odometer"

    # Priority 2: GPS tracker accumulated
    gps_km = vehicle_profile.get("gps_accumulated_km")
    if gps_km and gps_km > 0:
        return int(gps_km), "gps_tracker"

    # Priority 3: User-entered at registration
    user_km = vehicle_profile.get("mileage_km")
    if user_km and user_km > 0:
        return int(user_km), "user_entered"

    # Priority 4: Estimated from age
    from datetime import datetime as _dt
    year = vehicle_profile.get("year", 2020)
    age_years = max(0, _dt.now().year - year)
    estimated = age_years * 25000  # Qatar average
    return estimated, "estimated"


class DegradationModel(Enum):
    """Types of degradation models."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    POLYNOMIAL = "polynomial"
    WEIBULL = "weibull"
    WIENER = "wiener"


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
    timestamp: float  # epoch seconds


class RULEstimator:
    """
    Estimates Remaining Useful Life for vehicle components based on
    degradation history.

    Supports linear, exponential, and Wiener process degradation models.
    Selects the best-fit model automatically and projects time-to-threshold crossing.
    Includes confidence intervals and survival analysis integration.
    """

    # Default failure thresholds per component (sensor-specific)
    DEFAULT_THRESHOLDS: Dict[str, Dict[str, Any]] = {
        "battery": {"metric": "battery_voltage", "threshold": 11.8, "direction": "below"},
        "coolant_system": {"metric": "coolant_temp_c", "threshold": 110.0, "direction": "above"},
        "engine_oil": {"metric": "oil_temp_c", "threshold": 130.0, "direction": "above"},
        "catalytic_converter": {"metric": "catalyst_temp_c", "threshold": 900.0, "direction": "above"},
        "brake_pads": {"metric": "brake_pad_mm", "threshold": 2.0, "direction": "below"},
        "tires": {"metric": "tire_tread_mm", "threshold": 1.6, "direction": "below"},
        "spark_plugs": {"metric": "misfire_count", "threshold": 50.0, "direction": "above"},
        "fuel_system": {"metric": "fuel_trim_pct", "threshold": 25.0, "direction": "above"},
    }

    def __init__(self) -> None:
        self.config = get_config()
        self._fitted_models: Dict[str, Dict[str, Any]] = {}
        
        # Component life models
        self.component_models = self._define_component_models()
        
        # Historical data for degradation tracking
        self.degradation_history: Dict[str, Dict[str, deque]] = {}  # vehicle_id -> component -> readings
        
        # Storage path
        storage_dir = getattr(self.config, 'AI_DIR', Path("./data/ai"))
        self.storage_path = storage_dir / "rul_data"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Cached RUL predictions
        self.cached_predictions: Dict[str, Dict[str, RULPrediction]] = {}
        
        logger.info("RULEstimator initialized with %d component models", len(self.component_models))

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
            sensor_parameter='charging_voltage',
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
            sensor_parameter='warmup_time',
            failure_threshold=20,
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
            sensor_parameter='fuel_trim_at_load',
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
            sensor_parameter='misfire_rate',
            failure_threshold=5.0,
            warning_threshold=2.0,
            nominal_value=0,
            degradation_direction='increase',
            typical_life_miles=60000,
            typical_life_years=5.0,
            weibull_shape=3.5,
            weibull_scale=5.0
        )

        # Oxygen Sensors
        models['o2_sensor'] = ComponentLifeModel(
            component_id='o2_sensor',
            name='Oxygen Sensor',
            sensor_parameter='o2_response_time',
            failure_threshold=500,
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
            sensor_parameter='cat_efficiency',
            failure_threshold=70,
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
            sensor_parameter='fuel_trim_drift',
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
            sensor_parameter='temp_variance',
            failure_threshold=10,
            warning_threshold=5,
            nominal_value=2,
            degradation_direction='increase',
            typical_life_miles=30000,
            typical_life_years=2.0,
            weibull_shape=4.0,
            weibull_scale=2.5
        )

        # Transmission (if ATF)
        models['transmission_fluid'] = ComponentLifeModel(
            component_id='transmission_fluid',
            name='Transmission Fluid',
            sensor_parameter='shift_quality',
            failure_threshold=50,
            warning_threshold=70,
            nominal_value=95,
            degradation_direction='decrease',
            typical_life_miles=60000,
            typical_life_years=4.0,
            weibull_shape=3.0,
            weibull_scale=4.5
        )

        return models

    def estimate_rul(
        self,
        component: str,
        degradation_history: list,
        current_mileage: Optional[int] = None,
    ) -> dict:
        """
        Estimate remaining useful life for a component.

        Args:
            component: Component name (e.g. "battery", "coolant_system").
            degradation_history: List of dicts, each with keys:
                - timestamp (float): epoch seconds
                - value (float): sensor reading
            current_mileage: Current vehicle mileage (optional, for Weibull correction)

        Returns:
            dict with:
                - estimated_days (float): predicted days until failure
                - confidence (float): 0-1 confidence score
                - degradation_rate (float): rate of change per day
                - model_type (str): "linear", "exponential", or "wiener"
                - current_value (float): most recent reading
                - threshold (float): failure threshold used
                - confidence_interval (tuple): (low, high) days estimate
                - rul_miles (int): predicted miles until failure
        """
        if not degradation_history or len(degradation_history) < 2:
            logger.warning(
                "Insufficient degradation history for %s (%d points)",
                component,
                len(degradation_history) if degradation_history else 0,
            )
            return {
                "estimated_days": -1.0,
                "confidence": 0.0,
                "degradation_rate": 0.0,
                "model_type": "none",
                "current_value": None,
                "threshold": None,
                "confidence_interval": (0, 0),
                "rul_miles": None,
            }

        # Sort by timestamp
        history = sorted(degradation_history, key=lambda p: p["timestamp"])

        # Extract arrays
        timestamps = np.array([p["timestamp"] for p in history], dtype=np.float64)
        values = np.array([p["value"] for p in history], dtype=np.float64)

        # Convert timestamps to days relative to first reading
        t0 = timestamps[0]
        days = (timestamps - t0) / 86400.0

        # Fit models
        curve_params = self.fit_degradation_curve(history)
        linear_params = curve_params.get("linear", {})
        exp_params = curve_params.get("exponential", {})
        wiener_params = curve_params.get("wiener", {})

        # Select best model based on R-squared
        linear_r2 = linear_params.get("r_squared", -1.0)
        exp_r2 = exp_params.get("r_squared", -1.0)
        wiener_r2 = wiener_params.get("r_squared", -1.0)

        best_r2 = max(linear_r2, exp_r2, wiener_r2)
        
        if wiener_r2 == best_r2 and wiener_r2 > 0.0:
            model_type = "wiener"
            best_params = wiener_params
        elif exp_r2 == best_r2 and exp_r2 > 0.0:
            model_type = "exponential"
            best_params = exp_params
        else:
            model_type = "linear"
            best_params = linear_params

        # Store fitted model
        self._fitted_models[component] = {
            "model_type": model_type,
            "params": best_params,
            "last_fit_time": time.time(),
        }

        # Get threshold for component
        comp_info = self.DEFAULT_THRESHOLDS.get(component, {})
        threshold = comp_info.get("threshold")
        direction = comp_info.get("direction", "above")
        
        # Also check component life models
        life_model = self.component_models.get(component)
        if life_model and threshold is None:
            threshold = life_model.failure_threshold
            direction = "below" if life_model.degradation_direction == "decrease" else "above"

        current_value = float(values[-1])
        current_day = float(days[-1])

        if threshold is None:
            # No known threshold -- estimate using trend only
            degradation_rate = best_params.get("slope", 0.0)
            return {
                "estimated_days": -1.0,
                "confidence": max(0.0, best_params.get("r_squared", 0.0)),
                "degradation_rate": degradation_rate,
                "model_type": model_type,
                "current_value": current_value,
                "threshold": None,
                "confidence_interval": (0, 0),
                "rul_miles": None,
            }

        # Calculate days until threshold crossing
        if model_type == "linear":
            slope = best_params.get("slope", 0.0)
            intercept = best_params.get("intercept", current_value)
            estimated_days = self.predict_threshold_crossing(
                current_value,
                slope,
                threshold,
                direction,
            )
            degradation_rate = slope
        elif model_type == "wiener":
            # Wiener process with drift
            drift = best_params.get("drift", 0.0)
            estimated_days = self.predict_threshold_crossing(
                current_value,
                drift,
                threshold,
                direction,
            )
            degradation_rate = drift
        else:
            # Exponential: v(t) = a * exp(b * t)
            a = best_params.get("a", current_value)
            b = best_params.get("b", 0.0)
            if b == 0.0:
                estimated_days = -1.0
            else:
                try:
                    if direction == "above":
                        if current_value >= threshold:
                            estimated_days = 0.0
                        elif b > 0:
                            cross_day = math.log(threshold / max(a, 1e-12)) / b
                            estimated_days = max(0.0, cross_day - current_day)
                        else:
                            estimated_days = -1.0
                    else:
                        if current_value <= threshold:
                            estimated_days = 0.0
                        elif b < 0:
                            cross_day = math.log(threshold / max(a, 1e-12)) / b
                            estimated_days = max(0.0, cross_day - current_day)
                        else:
                            estimated_days = -1.0
                except (ValueError, ZeroDivisionError):
                    estimated_days = -1.0

            # Rate at current time
            degradation_rate = a * b * math.exp(b * current_day) if b != 0.0 else 0.0

        # Apply Weibull survival correction if mileage provided
        rul_miles = None
        if current_mileage is not None and life_model is not None:
            weibull_factor = self._weibull_survival_factor(
                current_mileage, life_model.weibull_shape, life_model.weibull_scale
            )
            if estimated_days > 0:
                estimated_days *= weibull_factor
            
            # Convert days to miles (assuming 12,000 miles/year = ~33 miles/day)
            daily_miles = 33
            rul_miles = int(estimated_days * daily_miles) if estimated_days > 0 else None

        # Confidence based on R-squared and data quantity
        r2 = max(0.0, best_params.get("r_squared", 0.0))
        n_points = len(history)
        data_factor = min(1.0, n_points / 30.0)  # Full confidence at 30+ points
        confidence = r2 * 0.7 + data_factor * 0.3

        # Calculate confidence interval
        ci_low, ci_high = self._calculate_confidence_interval(
            estimated_days if estimated_days > 0 else 0,
            confidence
        )

        return {
            "estimated_days": round(estimated_days, 2) if estimated_days >= 0 else -1.0,
            "confidence": round(confidence, 4),
            "degradation_rate": round(degradation_rate, 6),
            "model_type": model_type,
            "current_value": round(current_value, 4),
            "threshold": threshold,
            "confidence_interval": (ci_low, ci_high),
            "rul_miles": rul_miles,
        }

    def fit_degradation_curve(self, history: list) -> dict:
        """
        Fit linear, exponential, and Wiener process degradation models to history.

        Args:
            history: List of dicts with "timestamp" (float) and "value" (float).

        Returns:
            dict with keys "linear", "exponential", and "wiener", each containing
            model parameters and goodness-of-fit metrics:
                linear:  {slope, intercept, r_squared}
                exponential: {a, b, r_squared}
                wiener: {drift, diffusion, r_squared}
        """
        if not history or len(history) < 2:
            return {
                "linear": {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0},
                "exponential": {"a": 0.0, "b": 0.0, "r_squared": 0.0},
                "wiener": {"drift": 0.0, "diffusion": 0.0, "r_squared": 0.0},
            }

        sorted_history = sorted(history, key=lambda p: p["timestamp"])
        timestamps = np.array([p["timestamp"] for p in sorted_history], dtype=np.float64)
        values = np.array([p["value"] for p in sorted_history], dtype=np.float64)

        # Days from first reading
        t0 = timestamps[0]
        days = (timestamps - t0) / 86400.0

        # --- Linear fit: y = slope * t + intercept ---
        linear_params = self._fit_linear(days, values)

        # --- Exponential fit: y = a * exp(b * t) ---
        exp_params = self._fit_exponential(days, values)

        # --- Wiener process fit ---
        wiener_params = self._fit_wiener_process(days, values)

        return {
            "linear": linear_params,
            "exponential": exp_params,
            "wiener": wiener_params,
        }

    def predict_threshold_crossing(
        self,
        current_value: float,
        trend: float,
        threshold: float,
        direction: str = "above",
    ) -> float:
        """
        Predict number of days until a trending value crosses a threshold.

        Args:
            current_value: Current sensor reading.
            trend: Daily rate of change (slope/drift).
            threshold: Failure threshold value.
            direction: "above" or "below" threshold crossing.

        Returns:
            Estimated days until threshold crossing.
            Returns -1.0 if the trend will never cross the threshold.
        """
        if trend == 0.0:
            return -1.0

        if direction == "above":
            if current_value >= threshold:
                return 0.0
            if trend <= 0:
                return -1.0
            days_to_cross = (threshold - current_value) / trend
        else:  # below
            if current_value <= threshold:
                return 0.0
            if trend >= 0:
                return -1.0
            days_to_cross = (current_value - threshold) / abs(trend)

        if days_to_cross < 0:
            return -1.0

        return round(days_to_cross, 2)

    def estimate_rul_with_confidence(
        self,
        vehicle_id: str,
        component_id: str,
        current_value: Optional[float] = None,
        current_mileage: Optional[int] = None,
    ) -> Optional[RULPrediction]:
        """
        Estimate RUL with full confidence interval and component life model.

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
            logger.warning("No model for component: %s", component_id)
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

        # Convert history to format for estimation
        estimation_history = [
            {"timestamp": time.mktime(time.strptime(r['timestamp'], "%Y-%m-%dT%H:%M:%S")) 
             if isinstance(r['timestamp'], str) else r['timestamp'], 
             "value": r['value']}
            for r in history
        ]
        
        if not estimation_history:
            # Create minimal history with current value
            estimation_history = [{"timestamp": time.time(), "value": current_value}]

        # Estimate RUL using main algorithm
        result = self.estimate_rul(
            component_id, 
            estimation_history, 
            current_mileage=current_mileage
        )

        estimated_days = result.get("estimated_days", -1)
        rul_miles = result.get("rul_miles")
        confidence = result.get("confidence", 0.0)
        degradation_rate = result.get("degradation_rate", 0.0)
        deg_model = result.get("model_type", "unknown")
        
        # Determine trend
        trend = self._determine_trend(degradation_rate, model)
        
        # Calculate confidence interval
        ci_low, ci_high = result.get("confidence_interval", (0, 0))

        # Generate recommendation
        recommendation = self._generate_recommendation(
            component_id, health_pct, rul_miles, 
            int(estimated_days) if estimated_days > 0 else None, 
            trend, model
        )

        prediction = RULPrediction(
            component_id=component_id,
            component_name=model.name,
            current_value=round(current_value, 2),
            current_health_pct=round(health_pct, 1),
            predicted_rul_miles=rul_miles,
            predicted_rul_days=int(estimated_days) if estimated_days > 0 else None,
            confidence_interval=(ci_low, ci_high),
            confidence_level=round(confidence, 2),
            degradation_rate=round(degradation_rate, 6),
            degradation_model=deg_model,
            trend=trend,
            recommendation=recommendation,
            timestamp=time.time(),
        )

        # Cache the prediction
        if vehicle_id not in self.cached_predictions:
            self.cached_predictions[vehicle_id] = {}
        self.cached_predictions[vehicle_id][component_id] = prediction

        return prediction

    def add_reading(
        self, 
        vehicle_id: str, 
        component_id: str, 
        value: float,
        mileage: Optional[int] = None,
        timestamp: Optional[float] = None,
    ):
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
            'timestamp': timestamp or time.time(),
        }

        self.degradation_history[vehicle_id][component_id].append(reading)

    def estimate_all_components(
        self, 
        vehicle_id: str,
        current_data: Optional[Dict[str, Any]] = None,
        current_mileage: Optional[int] = None,
    ) -> List[RULPrediction]:
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
            'alternator': ['battery_voltage', 'control_module_voltage'],
            'maf_sensor': ['long_term_fuel_trim_1', 'long_term_fuel_trim']
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
            prediction = self.estimate_rul_with_confidence(
                vehicle_id, comp_id,
                current_value=current_value,
                current_mileage=current_mileage
            )

            if prediction:
                predictions.append(prediction)

        return predictions

    def get_maintenance_schedule(
        self, 
        vehicle_id: str,
        current_mileage: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fit_linear(
        days: np.ndarray,
        values: np.ndarray,
    ) -> Dict[str, float]:
        """Ordinary least-squares linear regression."""
        n = len(days)
        if n < 2:
            return {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0}

        sum_x = np.sum(days)
        sum_y = np.sum(values)
        sum_xy = np.sum(days * values)
        sum_x2 = np.sum(days ** 2)

        denom = n * sum_x2 - sum_x ** 2
        if abs(denom) < 1e-12:
            return {
                "slope": 0.0,
                "intercept": float(np.mean(values)),
                "r_squared": 0.0,
            }

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        # R-squared
        y_pred = slope * days + intercept
        ss_res = np.sum((values - y_pred) ** 2)
        ss_tot = np.sum((values - np.mean(values)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
        r_squared = max(0.0, r_squared)

        return {
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_squared),
        }

    @staticmethod
    def _fit_exponential(
        days: np.ndarray,
        values: np.ndarray,
    ) -> Dict[str, float]:
        """
        Fit exponential curve y = a * exp(b * t) via log-linear regression.
        Only works when all values are positive.
        """
        fallback = {"a": 0.0, "b": 0.0, "r_squared": 0.0}

        if len(days) < 2:
            return fallback

        # Exponential fit requires positive values
        if np.any(values <= 0):
            return fallback

        try:
            log_values = np.log(values)

            n = len(days)
            sum_x = np.sum(days)
            sum_y = np.sum(log_values)
            sum_xy = np.sum(days * log_values)
            sum_x2 = np.sum(days ** 2)

            denom = n * sum_x2 - sum_x ** 2
            if abs(denom) < 1e-12:
                return fallback

            b = (n * sum_xy - sum_x * sum_y) / denom
            log_a = (sum_y - b * sum_x) / n
            a = math.exp(log_a)

            # R-squared in original space
            y_pred = a * np.exp(b * days)
            ss_res = np.sum((values - y_pred) ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
            r_squared = max(0.0, r_squared)

            return {
                "a": float(a),
                "b": float(b),
                "r_squared": float(r_squared),
            }

        except (ValueError, OverflowError) as exc:
            logger.debug("Exponential fit failed: %s", exc)
            return fallback

    @staticmethod
    def _fit_wiener_process(
        days: np.ndarray,
        values: np.ndarray,
    ) -> Dict[str, float]:
        """
        Fit Wiener process (Brownian motion with drift) to degradation data.
        Model: X(t) = X(0) + drift * t + diffusion * W(t)
        where W(t) is standard Brownian motion.
        
        Returns drift and diffusion parameters.
        """
        fallback = {"drift": 0.0, "diffusion": 0.0, "r_squared": 0.0}
        
        if len(days) < 3:
            return fallback
        
        try:
            # Calculate increments
            dt = np.diff(days)
            dx = np.diff(values)
            
            # Avoid division by zero
            dt = np.where(dt < 1e-10, 1e-10, dt)
            
            # Estimate drift as mean of increments/dt
            drift_values = dx / dt
            drift = float(np.mean(drift_values))
            
            # Estimate diffusion (volatility) as std of increments/sqrt(dt)
            diffusion_values = dx / np.sqrt(dt)
            diffusion = float(np.std(diffusion_values))
            
            # Predict values using drift only (expected value)
            t0 = days[0]
            x0 = values[0]
            y_pred = x0 + drift * (days - t0)
            
            # R-squared
            ss_res = np.sum((values - y_pred) ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
            r_squared = max(0.0, r_squared)
            
            return {
                "drift": drift,
                "diffusion": diffusion,
                "r_squared": float(r_squared),
            }
            
        except (ValueError, ZeroDivisionError) as exc:
            logger.debug("Wiener process fit failed: %s", exc)
            return fallback

    def _calculate_health_percentage(
        self, 
        current_value: float,
        model: ComponentLifeModel,
    ) -> float:
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

    def _determine_trend(
        self, 
        degradation_rate: float,
        model: ComponentLifeModel,
    ) -> str:
        """Determine degradation trend based on rate."""
        # Get expected degradation rate
        value_range = abs(model.nominal_value - model.failure_threshold)
        expected_rate = value_range / model.typical_life_miles
        
        if abs(degradation_rate) < expected_rate * 0.1:
            return 'stable'
        elif model.degradation_direction == 'decrease':
            if degradation_rate < -expected_rate * 2:
                return 'rapid_degradation'
            elif degradation_rate < 0:
                return 'degrading'
            else:
                return 'improving'
        else:
            if degradation_rate > expected_rate * 2:
                return 'rapid_degradation'
            elif degradation_rate > 0:
                return 'degrading'
            else:
                return 'improving'

    def _weibull_survival_factor(
        self, 
        current_mileage: int,
        shape: float, 
        scale: float,
    ) -> float:
        """
        Calculate Weibull survival factor to adjust RUL prediction.
        Uses conditional reliability given current mileage.
        """
        # Convert scale from years to miles (assuming 12,000 miles/year)
        scale_miles = scale * 12000

        # Current survival probability
        current_survival = math.exp(-(current_mileage / scale_miles) ** shape)

        if current_survival < 0.01:
            return 0.5  # Component has exceeded expected life

        # Factor to adjust remaining life
        return min(2.0, max(0.5, current_survival))

    def _calculate_confidence_interval(
        self, 
        rul_estimate: float,
        confidence: float,
    ) -> Tuple[int, int]:
        """Calculate confidence interval for RUL estimate."""
        if rul_estimate <= 0:
            return (0, 0)

        # Width of interval based on confidence
        uncertainty = 1 - confidence
        margin = rul_estimate * (0.2 + uncertainty * 0.3)  # 20-50% margin

        low = max(0, int(rul_estimate - margin))
        high = int(rul_estimate + margin)

        return (low, high)

    def _generate_recommendation(
        self, 
        component_id: str, 
        health_pct: float,
        rul_miles: Optional[int], 
        rul_days: Optional[int], 
        trend: str,
        model: ComponentLifeModel,
    ) -> str:
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

    def get_fitted_model(self, component: str) -> Optional[Dict[str, Any]]:
        """Retrieve the last fitted model for a component, if any."""
        return self._fitted_models.get(component)

    def fit_polynomial_degradation(
        self,
        history: list,
        degree: int = 2,
    ) -> Dict[str, float]:
        """
        Fit polynomial degradation curve to history.
        
        Args:
            history: List of dicts with "timestamp" (float) and "value" (float).
            degree: Polynomial degree (default 2 for quadratic).
            
        Returns:
            dict with polynomial coefficients and r_squared.
        """
        fallback = {"coeffs": [0.0], "r_squared": 0.0}
        
        if not history or len(history) < degree + 1:
            return fallback
        
        try:
            sorted_history = sorted(history, key=lambda p: p["timestamp"])
            timestamps = np.array([p["timestamp"] for p in sorted_history], dtype=np.float64)
            values = np.array([p["value"] for p in sorted_history], dtype=np.float64)
            
            # Days from first reading
            t0 = timestamps[0]
            days = (timestamps - t0) / 86400.0
            
            # Fit polynomial
            coeffs = np.polyfit(days, values, degree)
            
            # Calculate R-squared
            y_pred = np.polyval(coeffs, days)
            ss_res = np.sum((values - y_pred) ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
            r_squared = max(0.0, r_squared)
            
            return {
                "coeffs": coeffs.tolist(),
                "r_squared": float(r_squared),
            }
            
        except (ValueError, np.linalg.LinAlgError) as exc:
            logger.debug("Polynomial fit failed: %s", exc)
            return fallback

    # ===== Qatar / Gulf Climate Adjustment =====

    QATAR_HEAT_FACTORS = {
        "battery":             0.70,  # 30% life reduction — heat is #1 battery killer
        "alternator":          0.80,  # 20% reduction — heat stress on diodes/bearings
        "coolant":             0.75,  # 25% reduction — fluid degrades faster in extreme heat
        "spark_plugs":         0.85,  # 15% reduction — heat fouling
        "transmission_fluid":  0.80,  # 20% reduction — ATF breaks down faster
        "fuel_pump":           0.85,  # 15% reduction — fuel vapor lock in extreme heat
        "o2_sensor":           0.85,  # 15% reduction — thermal cycling
        "catalytic_converter": 0.90,  # 10% reduction
        "maf_sensor":          0.85,  # 15% reduction — desert dust accumulation
        "thermostat":          0.80,  # 20% reduction — constant thermal cycling
    }

    def qatar_climate_multiplier(
        self,
        component_id: str,
        ambient_temp_c: float = 45.0,
    ) -> float:
        """
        Get climate-adjusted life multiplier for Qatar/Gulf region.

        In Qatar, summer temperatures regularly exceed 45°C. This causes:
        - Accelerated battery degradation (electrochemical stress)
        - Faster fluid breakdown (coolant, ATF, engine oil)
        - Increased thermal cycling on electrical components
        - Desert dust accumulation on sensors

        Args:
            component_id: Component identifier (must match component_models keys)
            ambient_temp_c: Average ambient temperature in Celsius

        Returns:
            Multiplier (0.0–1.0) to apply to typical_life_miles and typical_life_years.
            1.0 = no penalty (temperate climate), 0.7 = 30% life reduction.
        """
        if ambient_temp_c < 40.0:
            # Temperate climate — no penalty
            return 1.0

        base_factor = self.QATAR_HEAT_FACTORS.get(component_id, 0.90)

        # Scale penalty with temperature: at 45°C use base factor, at 50°C slightly worse
        temp_severity = min(1.0, (ambient_temp_c - 40.0) / 10.0)  # 0.0 at 40°C, 1.0 at 50°C
        multiplier = 1.0 - (1.0 - base_factor) * temp_severity

        return round(max(0.3, min(1.0, multiplier)), 3)

    def first_principles_estimate(
        self,
        component_id: str,
        operating_conditions: Dict[str, Any],
        climate_region: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """
        Estimate RUL based on first principles (physics-based models).
        
        Args:
            component_id: Component identifier
            operating_conditions: Dict with operating condition parameters
            
        Returns:
            Dict with physics-based RUL estimate
        """
        model = self.component_models.get(component_id)
        if not model:
            return None
        
        estimate = {
            "component": component_id,
            "method": "first_principles",
            "typical_life_miles": model.typical_life_miles,
            "typical_life_years": model.typical_life_years,
        }
        
        # Adjust based on operating conditions
        if component_id == "battery":
            # Battery life affected by temperature cycles
            avg_temp = operating_conditions.get("avg_temperature", 20)
            temp_stress = 1.0 + abs(avg_temp - 20) / 50  # Higher stress at extremes
            
            short_trips = operating_conditions.get("short_trip_ratio", 0.3)
            trip_stress = 1.0 + short_trips * 0.5  # Short trips reduce battery life
            
            adjusted_miles = int(model.typical_life_miles / (temp_stress * trip_stress))
            adjusted_years = model.typical_life_years / (temp_stress * trip_stress)
            
            estimate["adjusted_life_miles"] = adjusted_miles
            estimate["adjusted_life_years"] = round(adjusted_years, 1)
            estimate["factors"] = {
                "temperature_stress": round(temp_stress, 2),
                "short_trip_stress": round(trip_stress, 2),
            }
            
        elif component_id == "coolant":
            # Coolant life affected by operating temperature
            avg_coolant_temp = operating_conditions.get("avg_coolant_temp", 90)
            temp_stress = 1.0 + max(0, avg_coolant_temp - 95) / 30
            
            adjusted_miles = int(model.typical_life_miles / temp_stress)
            adjusted_years = model.typical_life_years / temp_stress
            
            estimate["adjusted_life_miles"] = adjusted_miles
            estimate["adjusted_life_years"] = round(adjusted_years, 1)
            estimate["factors"] = {
                "temperature_stress": round(temp_stress, 2),
            }
            
        elif component_id == "spark_plugs":
            # Spark plug life affected by engine load and ignition cycles
            high_load_ratio = operating_conditions.get("high_load_ratio", 0.2)
            load_stress = 1.0 + high_load_ratio * 0.8
            
            adjusted_miles = int(model.typical_life_miles / load_stress)
            adjusted_years = model.typical_life_years / load_stress
            
            estimate["adjusted_life_miles"] = adjusted_miles
            estimate["adjusted_life_years"] = round(adjusted_years, 1)
            estimate["factors"] = {
                "load_stress": round(load_stress, 2),
            }
        
        else:
            # Default: use typical life
            estimate["adjusted_life_miles"] = model.typical_life_miles
            estimate["adjusted_life_years"] = model.typical_life_years
            estimate["factors"] = {}

        # Apply Qatar/Gulf climate adjustment
        if climate_region == "qatar":
            climate_mult = self.qatar_climate_multiplier(component_id)
            adj_miles = estimate.get("adjusted_life_miles", model.typical_life_miles)
            adj_years = estimate.get("adjusted_life_years", model.typical_life_years)
            estimate["adjusted_life_miles"] = int(adj_miles * climate_mult)
            estimate["adjusted_life_years"] = round(adj_years * climate_mult, 1)
            estimate["factors"]["qatar_heat_multiplier"] = climate_mult

        return estimate

    def survival_analysis_estimate(
        self,
        component_id: str,
        current_mileage: int,
        confidence_level: float = 0.95,
    ) -> Optional[Dict[str, Any]]:
        """
        Estimate RUL using survival analysis (Weibull distribution).
        
        Args:
            component_id: Component identifier
            current_mileage: Current vehicle mileage
            confidence_level: Confidence level for interval (default 0.95)
            
        Returns:
            Dict with survival analysis RUL estimate
        """
        model = self.component_models.get(component_id)
        if not model:
            return None
        
        # Weibull parameters
        shape = model.weibull_shape  # beta
        scale_miles = model.weibull_scale * 12000  # Convert years to miles
        
        # Calculate conditional reliability: R(t + x | t) = R(t + x) / R(t)
        current_survival = math.exp(-(current_mileage / scale_miles) ** shape)
        
        # Median remaining life (50th percentile of conditional distribution)
        median_factor = (math.log(2) ** (1 / shape))
        median_life = scale_miles * median_factor
        
        if current_survival > 0.01:
            # Expected remaining life using Weibull mean
            gamma_factor = math.gamma(1 + 1 / shape)
            expected_total_life = scale_miles * gamma_factor
            expected_remaining = max(0, expected_total_life - current_mileage)
            
            # Confidence interval calculation
            # For Weibull, the p-th percentile is: t_p = scale * (-ln(1-p))^(1/shape)
            p_lower = (1 - confidence_level) / 2
            p_upper = 1 - p_lower
            
            total_lower = scale_miles * ((-math.log(1 - p_lower)) ** (1 / shape))
            total_upper = scale_miles * ((-math.log(1 - p_upper)) ** (1 / shape))
            
            remaining_lower = max(0, total_lower - current_mileage)
            remaining_upper = max(0, total_upper - current_mileage)
        else:
            # Component exceeded expected life
            expected_remaining = model.typical_life_miles * 0.1  # Conservative estimate
            remaining_lower = 0
            remaining_upper = model.typical_life_miles * 0.3
        
        return {
            "component": component_id,
            "method": "survival_analysis",
            "current_mileage": current_mileage,
            "expected_remaining_miles": int(expected_remaining),
            "confidence_interval": (int(remaining_lower), int(remaining_upper)),
            "confidence_level": confidence_level,
            "current_survival_probability": round(current_survival, 4),
            "weibull_shape": shape,
            "weibull_scale_miles": int(scale_miles),
        }

    def combine_estimates(
        self,
        degradation_estimate: Dict[str, Any],
        survival_estimate: Optional[Dict[str, Any]] = None,
        first_principles_estimate: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Combine multiple RUL estimates using weighted averaging.
        
        Args:
            degradation_estimate: Output from estimate_rul()
            survival_estimate: Output from survival_analysis_estimate()
            first_principles_estimate: Output from first_principles_estimate()
            
        Returns:
            Combined RUL estimate with confidence
        """
        estimates = []
        weights = []
        
        # Degradation-based estimate (highest weight when data is good)
        deg_conf = degradation_estimate.get("confidence", 0)
        deg_days = degradation_estimate.get("estimated_days", -1)
        if deg_days >= 0:
            estimates.append(deg_days)
            weights.append(deg_conf * 0.5)  # Up to 0.5 weight
        
        # Survival analysis estimate
        if survival_estimate:
            surv_miles = survival_estimate.get("expected_remaining_miles", 0)
            surv_conf = survival_estimate.get("confidence_level", 0.95)
            # Convert miles to days (assuming 33 miles/day)
            surv_days = surv_miles / 33
            estimates.append(surv_days)
            weights.append(0.3 * surv_conf)
        
        # First principles estimate
        if first_principles_estimate:
            fp_years = first_principles_estimate.get("adjusted_life_years", 0)
            fp_days = fp_years * 365
            estimates.append(fp_days)
            weights.append(0.2)  # Lower weight for theoretical estimate
        
        if not estimates:
            return {
                "combined_days": -1.0,
                "confidence": 0.0,
                "method": "none",
            }
        
        # Weighted average
        total_weight = sum(weights)
        if total_weight > 0:
            combined_days = sum(e * w for e, w in zip(estimates, weights)) / total_weight
        else:
            combined_days = sum(estimates) / len(estimates)
        
        # Combined confidence
        combined_confidence = min(0.95, total_weight / len(estimates) if estimates else 0)
        
        return {
            "combined_days": round(combined_days, 2),
            "combined_miles": int(combined_days * 33),
            "confidence": round(combined_confidence, 4),
            "method": "weighted_average",
            "source_estimates": {
                "degradation": deg_days if deg_days >= 0 else None,
                "survival": int(surv_days) if survival_estimate else None,
                "first_principles": int(fp_days) if first_principles_estimate else None,
            },
            "weights": {
                "degradation": round(weights[0], 3) if len(weights) > 0 else 0,
                "survival": round(weights[1], 3) if len(weights) > 1 else 0,
                "first_principles": round(weights[2], 3) if len(weights) > 2 else 0,
            },
        }
