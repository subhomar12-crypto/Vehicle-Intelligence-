"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Component Prediction Models

Component Prediction Models
Specialized prediction models for specific vehicle components:
- Brake wear prediction
- Oil life prediction
- Battery health prediction

These models use physics-based calculations combined with
machine learning for accurate remaining useful life (RUL) estimation.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# BRAKE PREDICTION MODEL
# =============================================================================

@dataclass
class BrakeWearResult:
    """Result of brake wear prediction"""
    remaining_life_percent: float
    predicted_failure_date: Optional[datetime]
    failure_window_days: Tuple[int, int]
    confidence: float
    severity: str  # 'normal', 'warning', 'critical'
    recommendation: str
    wear_rate_km_per_percent: float
    estimated_remaining_km: float
    front_rear_balance: str  # 'balanced', 'front_heavy', 'rear_heavy'


class BrakePredictionModel:
    """
    Predicts brake pad/rotor wear based on sensor data and driving patterns.

    Uses multiple factors:
    - Distance since last service
    - Brake temperature patterns
    - Deceleration intensity
    - Driving style (city vs highway)
    - Vehicle weight/type
    """

    # Default specifications (can be overridden per vehicle)
    DEFAULT_BRAKE_LIFE_KM = 50000  # Average brake pad life
    MAX_SAFE_BRAKE_TEMP = 300  # Celsius
    CRITICAL_TEMP_THRESHOLD = 400  # Fade temperature

    # Wear acceleration factors
    HIGH_TEMP_WEAR_MULTIPLIER = 1.5
    AGGRESSIVE_BRAKING_MULTIPLIER = 1.3
    CITY_DRIVING_MULTIPLIER = 1.2

    def __init__(self, vehicle_spec: Dict[str, Any] = None):
        """
        Initialize brake prediction model.

        Args:
            vehicle_spec: Vehicle-specific parameters including:
                - brake_life_km: Expected brake life in km
                - vehicle_weight_kg: Vehicle weight
                - brake_type: 'disc', 'drum', 'ceramic'
        """
        spec = vehicle_spec or {}
        self.brake_life_km = spec.get('brake_life_km', self.DEFAULT_BRAKE_LIFE_KM)
        self.vehicle_weight_kg = spec.get('vehicle_weight_kg', 1500)
        self.brake_type = spec.get('brake_type', 'disc')

    def calculate_wear(self, telemetry_data: List[Dict[str, Any]]) -> Optional[BrakeWearResult]:
        """
        Calculate brake wear and predict remaining life.

        Args:
            telemetry_data: List of readings with:
                - brake_temp_front (float): Front brake temperature in Celsius
                - brake_temp_rear (float): Rear brake temperature in Celsius
                - deceleration (float): Deceleration rate in m/s²
                - speed (float): Vehicle speed in km/h
                - mileage_km (float): Current odometer reading
                - last_brake_service_km (float): Mileage at last brake service
                - timestamp (str): Reading timestamp

        Returns:
            BrakeWearResult or None if insufficient data
        """
        if not telemetry_data or len(telemetry_data) < 7:
            logger.warning("Insufficient data for brake prediction")
            return None

        try:
            # Extract metrics
            front_temps = [r.get('brake_temp_front', 0) for r in telemetry_data if r.get('brake_temp_front')]
            rear_temps = [r.get('brake_temp_rear', 0) for r in telemetry_data if r.get('brake_temp_rear')]
            decels = [abs(r.get('deceleration', 0)) for r in telemetry_data if r.get('deceleration')]
            speeds = [r.get('speed', 0) for r in telemetry_data]

            current_km = telemetry_data[-1].get('mileage_km', 0)
            last_service_km = telemetry_data[0].get('last_brake_service_km', 0)

            # If no last service recorded, estimate from average
            if last_service_km == 0:
                last_service_km = max(0, current_km - 30000)  # Assume 30k km since service

            km_since_service = current_km - last_service_km

            # 1. Distance-based wear (base factor)
            distance_wear = km_since_service / self.brake_life_km

            # 2. Temperature stress factor
            temps = front_temps + rear_temps
            if temps:
                avg_temp = statistics.mean(temps)
                max_temp = max(temps)
                high_temp_events = sum(1 for t in temps if t > 200) / len(temps)

                temp_factor = 1.0
                if avg_temp > 150:
                    temp_factor += (avg_temp - 150) / 200  # Increase with avg temp
                if high_temp_events > 0.1:
                    temp_factor *= self.HIGH_TEMP_WEAR_MULTIPLIER
            else:
                temp_factor = 1.0
                avg_temp = 0
                max_temp = 0

            # 3. Braking intensity factor
            if decels:
                avg_decel = statistics.mean(decels)
                hard_braking_ratio = sum(1 for d in decels if d > 4.0) / len(decels)

                decel_factor = 1.0
                if avg_decel > 3.0:
                    decel_factor *= self.AGGRESSIVE_BRAKING_MULTIPLIER
                if hard_braking_ratio > 0.1:
                    decel_factor *= 1.2
            else:
                decel_factor = 1.0

            # 4. Driving pattern factor (city vs highway)
            if speeds:
                low_speed_ratio = sum(1 for s in speeds if s < 50) / len(speeds)
                stop_start_events = sum(1 for i in range(1, len(speeds))
                                       if speeds[i-1] > 10 and speeds[i] < 5)

                pattern_factor = 1.0
                if low_speed_ratio > 0.6:
                    pattern_factor *= self.CITY_DRIVING_MULTIPLIER
                if stop_start_events > len(speeds) * 0.05:
                    pattern_factor *= 1.1
            else:
                pattern_factor = 1.0

            # Calculate effective wear
            effective_wear = distance_wear * temp_factor * decel_factor * pattern_factor
            remaining_life_percent = max(0, min(100, (1 - effective_wear) * 100))

            # Estimate remaining km
            if effective_wear > 0 and km_since_service > 0:
                wear_rate = effective_wear / km_since_service
                estimated_remaining_km = (1 - effective_wear) / wear_rate if wear_rate > 0 else 0
            else:
                estimated_remaining_km = self.brake_life_km * (remaining_life_percent / 100)

            # Calculate failure window
            avg_daily_km = self._estimate_daily_km(telemetry_data)
            if avg_daily_km > 0:
                min_days = int(estimated_remaining_km * 0.8 / avg_daily_km)
                max_days = int(estimated_remaining_km * 1.2 / avg_daily_km)
            else:
                min_days = int(remaining_life_percent * 3)  # Rough estimate
                max_days = int(remaining_life_percent * 5)

            # Predicted failure date
            predicted_failure = datetime.now() + timedelta(days=(min_days + max_days) // 2)

            # Calculate confidence based on data quality
            confidence = self._calculate_confidence(telemetry_data, temps, decels)

            # Determine severity
            if remaining_life_percent <= 10 or min_days <= 7:
                severity = 'critical'
                recommendation = "Replace brake pads immediately. Unsafe for driving."
            elif remaining_life_percent <= 25 or min_days <= 30:
                severity = 'warning'
                recommendation = "Schedule brake service within 2 weeks."
            elif remaining_life_percent <= 40 or min_days <= 60:
                severity = 'warning'
                recommendation = "Plan brake service in the next 1-2 months."
            else:
                severity = 'normal'
                recommendation = "Brakes in good condition. Continue regular monitoring."

            # Front/rear balance
            if front_temps and rear_temps:
                front_avg = statistics.mean(front_temps)
                rear_avg = statistics.mean(rear_temps)
                if front_avg > rear_avg * 1.3:
                    balance = 'front_heavy'
                elif rear_avg > front_avg * 1.3:
                    balance = 'rear_heavy'
                else:
                    balance = 'balanced'
            else:
                balance = 'balanced'

            return BrakeWearResult(
                remaining_life_percent=round(remaining_life_percent, 1),
                predicted_failure_date=predicted_failure,
                failure_window_days=(max(0, min_days), max(0, max_days)),
                confidence=confidence,
                severity=severity,
                recommendation=recommendation,
                wear_rate_km_per_percent=km_since_service / max(1, 100 - remaining_life_percent),
                estimated_remaining_km=round(estimated_remaining_km, 0),
                front_rear_balance=balance
            )

        except Exception as e:
            logger.error(f"Brake prediction failed: {e}")
            return None

    def _estimate_daily_km(self, telemetry: List[Dict]) -> float:
        """Estimate average daily kilometers driven"""
        try:
            if len(telemetry) < 2:
                return 50  # Default

            first_km = telemetry[0].get('mileage_km', 0)
            last_km = telemetry[-1].get('mileage_km', 0)

            first_time = datetime.fromisoformat(telemetry[0].get('timestamp', ''))
            last_time = datetime.fromisoformat(telemetry[-1].get('timestamp', ''))

            days = (last_time - first_time).days
            if days > 0:
                return (last_km - first_km) / days
            return 50
        except:
            return 50

    def _calculate_confidence(self, telemetry: List[Dict], temps: List, decels: List) -> float:
        """Calculate prediction confidence based on data quality"""
        confidence = 0.5  # Base confidence

        # More data = higher confidence
        if len(telemetry) >= 30:
            confidence += 0.2
        elif len(telemetry) >= 14:
            confidence += 0.1

        # Temperature data improves confidence
        if temps and len(temps) > len(telemetry) * 0.5:
            confidence += 0.15

        # Deceleration data improves confidence
        if decels and len(decels) > len(telemetry) * 0.3:
            confidence += 0.15

        return min(0.95, confidence)


# =============================================================================
# OIL LIFE PREDICTION MODEL
# =============================================================================

@dataclass
class OilLifeResult:
    """Result of oil life prediction"""
    remaining_life_percent: float
    predicted_change_date: Optional[datetime]
    days_until_change: Tuple[int, int]
    km_until_change: float
    confidence: float
    severity: str
    recommendation: str
    oil_condition: str  # 'good', 'degrading', 'contaminated'
    contributing_factors: List[str]


class OilPredictionModel:
    """
    Predicts oil life and degradation based on:
    - Distance since last change
    - Engine operating conditions
    - Temperature patterns
    - Oil analysis data (if available)
    """

    # Default oil change intervals
    DEFAULT_OIL_LIFE_KM = 10000  # Standard oil
    SYNTHETIC_OIL_LIFE_KM = 15000  # Synthetic oil

    # Degradation factors
    HIGH_TEMP_DEGRADATION = 1.3
    SHORT_TRIP_DEGRADATION = 1.4
    HEAVY_LOAD_DEGRADATION = 1.2

    def __init__(self, vehicle_spec: Dict[str, Any] = None):
        spec = vehicle_spec or {}
        self.oil_type = spec.get('oil_type', 'synthetic')
        self.oil_life_km = spec.get('oil_life_km',
            self.SYNTHETIC_OIL_LIFE_KM if self.oil_type == 'synthetic' else self.DEFAULT_OIL_LIFE_KM)

    def calculate_oil_life(self, telemetry_data: List[Dict[str, Any]]) -> Optional[OilLifeResult]:
        """
        Calculate remaining oil life.

        Args:
            telemetry_data: List of readings with:
                - oil_temp (float): Oil temperature in Celsius
                - coolant_temp (float): Coolant temperature in Celsius
                - engine_load (float): Engine load percentage
                - rpm (float): Engine RPM
                - mileage_km (float): Current odometer
                - last_oil_change_km (float): Mileage at last oil change
                - trip_distance_km (float): Current trip distance
        """
        if not telemetry_data or len(telemetry_data) < 7:
            return None

        try:
            # Extract metrics
            oil_temps = [r.get('oil_temp', r.get('coolant_temp', 90)) for r in telemetry_data]
            engine_loads = [r.get('engine_load', 30) for r in telemetry_data]
            rpms = [r.get('rpm', 2000) for r in telemetry_data]

            current_km = telemetry_data[-1].get('mileage_km', 0)
            last_change_km = telemetry_data[0].get('last_oil_change_km', 0)

            if last_change_km == 0:
                last_change_km = max(0, current_km - 5000)

            km_since_change = current_km - last_change_km
            contributing_factors = []

            # 1. Base distance wear
            distance_wear = km_since_change / self.oil_life_km

            # 2. Temperature factor
            if oil_temps:
                avg_temp = statistics.mean(oil_temps)
                high_temp_ratio = sum(1 for t in oil_temps if t > 110) / len(oil_temps)

                temp_factor = 1.0
                if avg_temp > 100:
                    temp_factor *= 1 + (avg_temp - 100) / 50
                    contributing_factors.append("High operating temperatures")
                if high_temp_ratio > 0.2:
                    temp_factor *= self.HIGH_TEMP_DEGRADATION
                    contributing_factors.append("Frequent high-temperature operation")
            else:
                temp_factor = 1.0

            # 3. Engine load factor
            if engine_loads:
                avg_load = statistics.mean(engine_loads)
                high_load_ratio = sum(1 for l in engine_loads if l > 70) / len(engine_loads)

                load_factor = 1.0
                if avg_load > 50:
                    load_factor *= 1 + (avg_load - 50) / 100
                if high_load_ratio > 0.3:
                    load_factor *= self.HEAVY_LOAD_DEGRADATION
                    contributing_factors.append("Heavy engine loads")
            else:
                load_factor = 1.0

            # 4. Short trip factor (lots of cold starts)
            trip_distances = [r.get('trip_distance_km', 20) for r in telemetry_data]
            if trip_distances:
                short_trips = sum(1 for d in trip_distances if d < 10) / len(trip_distances)
                if short_trips > 0.5:
                    short_trip_factor = self.SHORT_TRIP_DEGRADATION
                    contributing_factors.append("Frequent short trips")
                else:
                    short_trip_factor = 1.0
            else:
                short_trip_factor = 1.0

            # Calculate effective wear
            effective_wear = distance_wear * temp_factor * load_factor * short_trip_factor
            remaining_life_percent = max(0, min(100, (1 - effective_wear) * 100))

            # Estimate remaining km
            remaining_km = self.oil_life_km * (remaining_life_percent / 100)

            # Calculate days until change
            avg_daily_km = self._estimate_daily_km(telemetry_data)
            if avg_daily_km > 0:
                min_days = int(remaining_km * 0.85 / avg_daily_km)
                max_days = int(remaining_km * 1.15 / avg_daily_km)
            else:
                min_days = int(remaining_life_percent * 1)
                max_days = int(remaining_life_percent * 2)

            predicted_change = datetime.now() + timedelta(days=(min_days + max_days) // 2)

            # Determine oil condition
            if effective_wear > 0.9:
                oil_condition = 'contaminated'
            elif effective_wear > 0.7:
                oil_condition = 'degrading'
            else:
                oil_condition = 'good'

            # Determine severity
            if remaining_life_percent <= 5 or min_days <= 3:
                severity = 'critical'
                recommendation = "Change oil immediately to prevent engine damage."
            elif remaining_life_percent <= 15 or min_days <= 14:
                severity = 'warning'
                recommendation = "Schedule oil change within 2 weeks."
            elif remaining_life_percent <= 30 or min_days <= 30:
                severity = 'warning'
                recommendation = "Plan oil change in the next month."
            else:
                severity = 'normal'
                recommendation = "Oil in good condition. Continue regular monitoring."

            confidence = self._calculate_confidence(telemetry_data, oil_temps)

            return OilLifeResult(
                remaining_life_percent=round(remaining_life_percent, 1),
                predicted_change_date=predicted_change,
                days_until_change=(max(0, min_days), max(0, max_days)),
                km_until_change=round(remaining_km, 0),
                confidence=confidence,
                severity=severity,
                recommendation=recommendation,
                oil_condition=oil_condition,
                contributing_factors=contributing_factors if contributing_factors else ["Normal operating conditions"]
            )

        except Exception as e:
            logger.error(f"Oil prediction failed: {e}")
            return None

    def _estimate_daily_km(self, telemetry: List[Dict]) -> float:
        try:
            if len(telemetry) < 2:
                return 40
            first_km = telemetry[0].get('mileage_km', 0)
            last_km = telemetry[-1].get('mileage_km', 0)
            first_time = datetime.fromisoformat(telemetry[0].get('timestamp', ''))
            last_time = datetime.fromisoformat(telemetry[-1].get('timestamp', ''))
            days = (last_time - first_time).days
            return (last_km - first_km) / days if days > 0 else 40
        except:
            return 40

    def _calculate_confidence(self, telemetry: List[Dict], temps: List) -> float:
        confidence = 0.6
        if len(telemetry) >= 30:
            confidence += 0.15
        if temps and len([t for t in temps if t > 0]) > len(telemetry) * 0.5:
            confidence += 0.2
        return min(0.95, confidence)


# =============================================================================
# BATTERY HEALTH PREDICTION MODEL
# =============================================================================

@dataclass
class BatteryHealthResult:
    """Result of battery health prediction"""
    state_of_health: float  # 0-100%
    remaining_life_months: Tuple[int, int]
    predicted_failure_date: Optional[datetime]
    confidence: float
    severity: str
    recommendation: str
    voltage_status: str  # 'normal', 'low', 'high', 'unstable'
    charging_status: str  # 'good', 'weak', 'failing'
    cold_start_capability: str  # 'excellent', 'good', 'marginal', 'poor'


class BatteryPredictionModel:
    """
    Predicts battery health and remaining life based on:
    - Voltage readings under various conditions
    - Charging behavior
    - Temperature effects
    - Age and usage patterns
    """

    # Battery specifications
    NOMINAL_VOLTAGE = 12.6  # Fully charged resting voltage
    MIN_HEALTHY_VOLTAGE = 12.2  # Below this = weak
    CRITICAL_VOLTAGE = 11.8  # Below this = failing
    OVERCHARGE_VOLTAGE = 14.8  # Above this = overcharging

    # Average battery life
    DEFAULT_BATTERY_LIFE_MONTHS = 48  # 4 years

    def __init__(self, vehicle_spec: Dict[str, Any] = None):
        spec = vehicle_spec or {}
        self.battery_age_months = spec.get('battery_age_months', 24)
        self.battery_type = spec.get('battery_type', 'lead_acid')  # lead_acid, agm, lithium

    def calculate_battery_health(self, telemetry_data: List[Dict[str, Any]]) -> Optional[BatteryHealthResult]:
        """
        Calculate battery health and predict remaining life.

        Args:
            telemetry_data: List of readings with:
                - battery_voltage (float): Battery voltage
                - alternator_voltage (float): Charging voltage (optional)
                - ambient_temp (float): Outside temperature (optional)
                - engine_running (bool): Engine state (optional)
                - cold_start_voltage (float): Voltage during cranking (optional)
        """
        if not telemetry_data or len(telemetry_data) < 3:
            return None

        try:
            # Extract voltage readings
            voltages = [r.get('battery_voltage', 0) for r in telemetry_data if r.get('battery_voltage')]

            if not voltages:
                logger.warning("No voltage data available")
                return None

            # Separate resting and running voltages
            resting_voltages = []
            running_voltages = []

            for r in telemetry_data:
                v = r.get('battery_voltage', 0)
                if v <= 0:
                    continue

                if r.get('engine_running', True) or r.get('rpm', 0) > 500:
                    running_voltages.append(v)
                else:
                    resting_voltages.append(v)

            # Use all voltages if we can't distinguish
            if not resting_voltages:
                resting_voltages = [v for v in voltages if v < 13.5]
            if not running_voltages:
                running_voltages = [v for v in voltages if v >= 13.0]

            # Calculate metrics
            avg_resting = statistics.mean(resting_voltages) if resting_voltages else statistics.mean(voltages)
            min_voltage = min(voltages)
            max_voltage = max(voltages)
            voltage_variance = statistics.stdev(voltages) if len(voltages) > 1 else 0

            # Voltage status
            if avg_resting < self.CRITICAL_VOLTAGE:
                voltage_status = 'low'
            elif avg_resting < self.MIN_HEALTHY_VOLTAGE:
                voltage_status = 'low'
            elif max_voltage > self.OVERCHARGE_VOLTAGE:
                voltage_status = 'high'
            elif voltage_variance > 1.0:
                voltage_status = 'unstable'
            else:
                voltage_status = 'normal'

            # Charging status (from running voltages)
            if running_voltages:
                avg_charging = statistics.mean(running_voltages)
                if avg_charging >= 13.8 and avg_charging <= 14.4:
                    charging_status = 'good'
                elif avg_charging >= 13.5:
                    charging_status = 'weak'
                else:
                    charging_status = 'failing'
            else:
                charging_status = 'good'  # Assume good if no data

            # Cold start capability
            cold_start_voltages = [r.get('cold_start_voltage', 0) for r in telemetry_data if r.get('cold_start_voltage')]
            if cold_start_voltages:
                min_crank = min(cold_start_voltages)
                if min_crank >= 10.5:
                    cold_start = 'excellent'
                elif min_crank >= 10.0:
                    cold_start = 'good'
                elif min_crank >= 9.5:
                    cold_start = 'marginal'
                else:
                    cold_start = 'poor'
            else:
                # Estimate from resting voltage
                if avg_resting >= 12.4:
                    cold_start = 'good'
                elif avg_resting >= 12.0:
                    cold_start = 'marginal'
                else:
                    cold_start = 'poor'

            # Calculate State of Health (SOH)
            # Based on voltage, charging, and age
            voltage_health = self._voltage_to_health(avg_resting)
            charging_health = {'good': 100, 'weak': 70, 'failing': 40}.get(charging_status, 80)

            # Age factor
            age_factor = max(0, 1 - (self.battery_age_months / self.DEFAULT_BATTERY_LIFE_MONTHS))
            age_health = age_factor * 100

            # Combined SOH
            state_of_health = (voltage_health * 0.5 + charging_health * 0.3 + age_health * 0.2)
            state_of_health = max(0, min(100, state_of_health))

            # Estimate remaining life
            remaining_capacity = state_of_health / 100
            months_used = self.battery_age_months
            if months_used > 0 and remaining_capacity > 0:
                degradation_rate = (1 - remaining_capacity) / months_used
                if degradation_rate > 0:
                    # Months until 50% SOH (typical end-of-life)
                    remaining_months = int((remaining_capacity - 0.5) / degradation_rate)
                else:
                    remaining_months = self.DEFAULT_BATTERY_LIFE_MONTHS - months_used
            else:
                remaining_months = int(state_of_health / 100 * 24)

            min_months = max(0, int(remaining_months * 0.7))
            max_months = max(1, int(remaining_months * 1.3))

            predicted_failure = datetime.now() + timedelta(days=remaining_months * 30)

            # Severity and recommendations
            if state_of_health <= 30 or remaining_months <= 3:
                severity = 'critical'
                recommendation = "Replace battery immediately. Risk of failure."
            elif state_of_health <= 50 or remaining_months <= 6:
                severity = 'warning'
                recommendation = "Plan battery replacement in the next 3-6 months."
            elif state_of_health <= 70 or remaining_months <= 12:
                severity = 'warning'
                recommendation = "Monitor battery condition. Consider replacement within a year."
            else:
                severity = 'normal'
                recommendation = "Battery in good health. Continue regular monitoring."

            confidence = 0.7
            if len(voltages) >= 30:
                confidence += 0.15
            if cold_start_voltages:
                confidence += 0.1
            confidence = min(0.95, confidence)

            return BatteryHealthResult(
                state_of_health=round(state_of_health, 1),
                remaining_life_months=(min_months, max_months),
                predicted_failure_date=predicted_failure,
                confidence=confidence,
                severity=severity,
                recommendation=recommendation,
                voltage_status=voltage_status,
                charging_status=charging_status,
                cold_start_capability=cold_start
            )

        except Exception as e:
            logger.error(f"Battery prediction failed: {e}")
            return None

    def _voltage_to_health(self, voltage: float) -> float:
        """Convert resting voltage to health percentage"""
        if voltage >= 12.6:
            return 100
        elif voltage >= 12.4:
            return 75 + (voltage - 12.4) / 0.2 * 25
        elif voltage >= 12.2:
            return 50 + (voltage - 12.2) / 0.2 * 25
        elif voltage >= 12.0:
            return 25 + (voltage - 12.0) / 0.2 * 25
        else:
            return max(0, (voltage - 11.0) / 1.0 * 25)


# =============================================================================
# UNIFIED COMPONENT PREDICTOR
# =============================================================================

class ComponentPredictor:
    """
    Unified interface for all component predictions.
    """

    def __init__(self, vehicle_spec: Dict[str, Any] = None):
        self.vehicle_spec = vehicle_spec or {}
        self.brake_model = BrakePredictionModel(vehicle_spec)
        self.oil_model = OilPredictionModel(vehicle_spec)
        self.battery_model = BatteryPredictionModel(vehicle_spec)

    def predict_all(self, telemetry_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run all component predictions.

        Returns:
            Dictionary with predictions for each component
        """
        results = {
            'generated_at': datetime.now().isoformat(),
            'components': {}
        }

        # Brake prediction
        brake_result = self.brake_model.calculate_wear(telemetry_data)
        if brake_result:
            results['components']['brakes'] = {
                'remaining_life_percent': brake_result.remaining_life_percent,
                'severity': brake_result.severity,
                'recommendation': brake_result.recommendation,
                'failure_window_days': brake_result.failure_window_days,
                'confidence': brake_result.confidence,
                'estimated_remaining_km': brake_result.estimated_remaining_km
            }

        # Oil prediction
        oil_result = self.oil_model.calculate_oil_life(telemetry_data)
        if oil_result:
            results['components']['oil'] = {
                'remaining_life_percent': oil_result.remaining_life_percent,
                'severity': oil_result.severity,
                'recommendation': oil_result.recommendation,
                'days_until_change': oil_result.days_until_change,
                'km_until_change': oil_result.km_until_change,
                'confidence': oil_result.confidence,
                'condition': oil_result.oil_condition
            }

        # Battery prediction
        battery_result = self.battery_model.calculate_battery_health(telemetry_data)
        if battery_result:
            results['components']['battery'] = {
                'state_of_health': battery_result.state_of_health,
                'severity': battery_result.severity,
                'recommendation': battery_result.recommendation,
                'remaining_months': battery_result.remaining_life_months,
                'confidence': battery_result.confidence,
                'voltage_status': battery_result.voltage_status,
                'charging_status': battery_result.charging_status
            }

        # Overall health score
        health_scores = []
        severities = []

        for comp_name, comp_data in results['components'].items():
            if 'remaining_life_percent' in comp_data:
                health_scores.append(comp_data['remaining_life_percent'])
            elif 'state_of_health' in comp_data:
                health_scores.append(comp_data['state_of_health'])
            severities.append(comp_data.get('severity', 'normal'))

        if health_scores:
            results['overall_health'] = round(statistics.mean(health_scores), 1)

        if 'critical' in severities:
            results['overall_severity'] = 'critical'
        elif 'warning' in severities:
            results['overall_severity'] = 'warning'
        else:
            results['overall_severity'] = 'normal'

        return results
