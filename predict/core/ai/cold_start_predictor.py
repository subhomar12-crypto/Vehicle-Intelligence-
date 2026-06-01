"""
Cold Start Prediction Engine — 5-Layer Hybrid System.

Provides real, useful vehicle health predictions from day one WITHOUT trained ML models.
This system is NEVER removed. When ML models are trained, they become Layer 0 (highest priority),
and this system provides fallback predictions for components/scenarios with insufficient ML data.

Layer 1: Sensor Threshold Rules (real-time OBD values vs known safe ranges)
Layer 2: Statistical Lifespan + Qatar Heat (component age/mileage vs Weibull curves)
Layer 3: Self-Baseline Anomaly Detection (current readings vs vehicle's own historical average)
Layer 4: DTC Intelligence (active fault codes → deterministic component impact)
Layer 5: Vehicle Research Context (known problems, recalls, reliability for make/model/year)
Layer 6: Service History Intelligence (maintenance records → overdue detection + health adjustment)
"""

import logging
import time
import math
from datetime import datetime as _dt
from typing import Dict, Any, List, Optional

import numpy as np

from predict.core.ai.rul_estimation import RULEstimator, estimate_mileage
from predict.core.ai.pattern_matcher import PatternMatcher
from predict.core.ai.context_scoring import ContextAwareScorer

logger = logging.getLogger(__name__)

# ===== Penalty-Based Scoring Constants (Intelligence Engine v2) =====

AGE_DECAY_RATES = {
    "battery": 2.0, "spark_plugs": 1.5, "catalytic_converter": 0.8,
    "transmission_fluid": 1.2, "alternator": 1.0, "o2_sensor": 1.3,
    "maf_sensor": 0.5, "thermostat": 1.5, "coolant": 1.8, "fuel_pump": 0.8,
}
QATAR_AGE_MULTIPLIER = 1.3
MAX_AGE_PENALTY = 15


class ConfidenceTier:
    MEASURED = "measured"
    INFERRED = "inferred"
    ESTIMATED = "estimated"


# Components with direct OBD sensor data
MEASURED_COMPONENTS = {
    "battery": ["battery_voltage"],
    "coolant": ["coolant_temp"],
    "engine": ["rpm", "engine_load", "throttle_pos"],
    "fuel_pump": ["fuel_level", "short_term_fuel_trim", "long_term_fuel_trim"],
    "maf_sensor": ["maf_rate", "intake_temp"],
}

# Components inferred from related sensors
INFERRED_COMPONENTS = {
    "alternator": {"sensors": ["battery_voltage"], "condition": "voltage stable under load"},
    "thermostat": {"sensors": ["coolant_temp"], "condition": "reaches operating temp normally"},
    "transmission_fluid": {"sensors": ["speed", "rpm"], "condition": "consistent gear ratios"},
}

# Components with no sensor — age/mileage only
ESTIMATED_COMPONENTS = ["spark_plugs", "catalytic_converter", "o2_sensor"]


# ===== Sensor → Component Mapping =====
# Maps OBD sensor names to the component they primarily monitor

SENSOR_TO_COMPONENT = {
    "battery_voltage": "battery",
    "coolant_temp": "coolant",
    "oil_temp": "engine",
    "rpm": "engine",
    "engine_load": "engine",
    "throttle_pos": "engine",
    "intake_temp": "maf_sensor",
    "maf_rate": "maf_sensor",
    "short_term_fuel_trim": "fuel_pump",
    "long_term_fuel_trim": "fuel_pump",
    "speed": "transmission_fluid",
    "fuel_level": "fuel_pump",
    # Extended PIDs
    "ambient_temp": "coolant",       # Informs expected coolant temp
    "boost_pressure": "engine",      # Turbo/supercharger health
    "fuel_rate": "fuel_pump",        # Fuel system efficiency
    "torque": "engine",              # Engine output health
    "obd_odometer": "engine",        # Context only — age signal
}

# Sensor thresholds imported from unified_ai_module concept
SENSOR_THRESHOLDS = {
    'rpm': {'min': 600, 'max': 6500, 'optimal_min': 700, 'optimal_max': 3500, 'critical_high': 6000},
    'coolant_temp': {'min': 60, 'max': 120, 'optimal_min': 82, 'optimal_max': 100, 'critical_high': 110},
    'oil_temp': {'min': 60, 'max': 130, 'optimal_min': 90, 'optimal_max': 110, 'critical_high': 120},
    'battery_voltage': {'min': 11.5, 'max': 15.0, 'optimal_min': 12.4, 'optimal_max': 14.4, 'critical_low': 11.8},
    'engine_load': {'min': 0, 'max': 100, 'optimal_min': 10, 'optimal_max': 80, 'critical_high': 95},
    'throttle_pos': {'min': 0, 'max': 100, 'optimal_min': 0, 'optimal_max': 85},
    'speed': {'min': 0, 'max': 250, 'optimal_min': 0, 'optimal_max': 140},
    'intake_temp': {'min': -40, 'max': 80, 'optimal_min': 10, 'optimal_max': 50, 'critical_high': 70},
    'maf_rate': {'min': 0, 'max': 500, 'optimal_min': 2, 'optimal_max': 300},
    'fuel_level': {'min': 0, 'max': 100, 'optimal_min': 20, 'optimal_max': 100, 'critical_low': 10},
    'short_term_fuel_trim': {'min': -25, 'max': 25, 'optimal_min': -10, 'optimal_max': 10},
    'long_term_fuel_trim': {'min': -25, 'max': 25, 'optimal_min': -10, 'optimal_max': 10},
    # Extended PIDs
    'ambient_temp': {'min': -30, 'max': 60},  # Context only — no health score
    'boost_pressure': {'min': 0, 'max': 300, 'optimal_min': 50, 'optimal_max': 200, 'critical_high': 260},
    'fuel_rate': {'min': 0, 'max': 80},  # Vehicle-specific, context only
    'torque': {'min': 0, 'max': 1000},   # Vehicle-specific, context only
}

# DTC prefix → component mapping
DTC_COMPONENT_MAP = {
    "P00": "engine",           # General powertrain
    "P01": "maf_sensor",       # Fuel/air metering (MAF, MAP, intake)
    "P02": "fuel_pump",        # Fuel injectors
    "P03": "spark_plugs",      # Ignition/misfire
    "P04": "catalytic_converter",  # Emissions (EGR, EVAP, catalytic)
    "P05": "engine",           # Speed/idle control
    "P06": "engine",           # ECU/computer
    "P07": "transmission_fluid",  # Transmission
    "P0A": "battery",          # Hybrid/EV battery
    "B0": "engine",            # Body
    "C0": "brakes",            # Chassis/Brakes
    "U0": "engine",            # Communication network
}

# All 10 components we track health for
ALL_COMPONENTS = [
    "battery", "alternator", "thermostat", "fuel_pump", "spark_plugs",
    "o2_sensor", "catalytic_converter", "maf_sensor", "coolant", "transmission_fluid",
]


class ColdStartPredictor:
    """
    5-layer hybrid prediction engine for vehicles without trained ML models.
    Provides useful health scores from day one using statistical + rule-based methods.

    This is a PERMANENT system — not removed when ML models are trained.
    When ML is available, it becomes Layer 0 and this provides fallback.
    """

    def __init__(self):
        self.rul_estimator = RULEstimator()
        self.context_scorer = ContextAwareScorer()
        logger.info("ColdStartPredictor initialized with %d components", len(ALL_COMPONENTS))

    async def assess_vehicle_health(
        self,
        vehicle_id: int,
        latest_telemetry: Dict[str, Any],
        vehicle_profile: Dict[str, Any],
        dtc_codes: List[Dict[str, Any]],
        telemetry_history: List[Dict[str, Any]],
        research_data: Optional[Dict[str, Any]] = None,
        climate_region: str = "qatar",
        service_records: Optional[List[Dict[str, Any]]] = None,
        mode06_results: Optional[List[Dict[str, Any]]] = None,
        session=None,
    ) -> Dict[str, Any]:
        """
        Run all layers and merge into per-component health scores.

        Args:
            vehicle_id: Vehicle profile ID
            latest_telemetry: Most recent OBD reading (dict of sensor: value)
            vehicle_profile: Vehicle info dict (make, model, year, mileage_km, etc.)
            dtc_codes: List of active/pending DTC dicts (code, severity, is_pending, is_active)
            telemetry_history: Last N OBD readings for baseline calculation
            research_data: Vehicle research data if available (common_problems, recalls, etc.)
            climate_region: Climate region ("qatar" for Gulf, "default" for temperate)
            service_records: Vehicle service/maintenance history from DB

        Returns:
            Complete health assessment dict with per-component scores
        """
        start_time = time.time()

        # Check for retroactively inferred cold-start data from baseline
        cold_start_available = False
        resting_voltage = None
        # baseline_data may be passed via telemetry_history or research_data context
        # The batch_v2 endpoint stores cold-start snapshot in VehicleBaseline.sensor_stats["_cold_start"]
        # The /explain endpoint reads this and includes it — here we check telemetry_history
        # for a first-reading with low coolant as a secondary check
        if telemetry_history and len(telemetry_history) > 0:
            first_reading = telemetry_history[-1] if telemetry_history else {}  # oldest in desc order
            first_coolant = first_reading.get("coolant_temp")
            first_voltage = first_reading.get("battery_voltage")
            if first_coolant is not None and first_coolant < 60.0 and first_voltage is not None:
                cold_start_available = True
                resting_voltage = first_voltage

        # Layer 1: Sensor threshold rules
        layer1 = self._layer1_sensor_thresholds(latest_telemetry)

        # Mileage estimation (priority chain)
        mileage_km, mileage_source = estimate_mileage(vehicle_profile)
        vehicle_profile["_estimated_mileage"] = mileage_km
        vehicle_profile["_mileage_source"] = mileage_source

        # Layer 2: Statistical lifespan + climate adjustment
        year = vehicle_profile.get("year")
        layer2 = self._layer2_statistical_lifespan(mileage_km, year, climate_region)

        # Layer 3: Self-baseline anomaly detection
        layer3 = self._layer3_baseline_anomaly(latest_telemetry, telemetry_history)

        # Layer 4: DTC intelligence
        layer4 = self._layer4_dtc_intelligence(dtc_codes)

        # Layer 5: Vehicle research context
        layer5 = self._layer5_research_context(research_data)

        # Layer 4.5: Mode 06 ECU test results (most authoritative data source)
        layer45 = self._layer45_mode06_tests(mode06_results)

        # Layer 6: Service history intelligence
        layer6 = self._layer6_service_history(service_records, mileage_km)

        # Detect driving context
        context = self._detect_driving_context(latest_telemetry)

        # Run pattern matcher (wire previously dead module)
        patterns = []
        try:
            pm = PatternMatcher()
            patterns = pm.match(latest_telemetry, None, telemetry_history or [])
        except Exception as e:
            logger.warning("Pattern matcher error: %s", e)

        # Load fleet penalty adjustments (non-blocking — skip on failure)
        fleet_adjustments: Dict[str, float] = {}
        try:
            from predict.core.db.models.prediction_feedback import FleetPenaltyAdjustment
            from sqlalchemy import select as sa_select
            if session:
                rows = (await session.execute(sa_select(FleetPenaltyAdjustment))).scalars().all()
                fleet_adjustments = {r.component: r.penalty_multiplier for r in rows}
        except Exception as _fa_err:
            logger.debug("Fleet adjustments unavailable: %s", _fa_err)

        # Merge all layers with penalty-based scoring
        components = self._merge_layers(
            layer1, layer2, layer3, layer4, layer5, layer6, layer45,
            latest_telemetry=latest_telemetry,
            vehicle_profile=vehicle_profile,
            patterns=patterns,
            fleet_adjustments=fleet_adjustments,
        )

        # Compute projection summaries per component
        projections = self._compute_projection_summaries(
            components, telemetry_history or [], vehicle_profile, mileage_km
        )
        for comp_id, proj in projections.items():
            if comp_id in components:
                components[comp_id]["projection_summary"] = proj.get("summary", "")
                components[comp_id]["projected_score"] = proj.get("projected_score", components[comp_id]["health_pct"])
                components[comp_id]["timeframe_days"] = proj.get("timeframe_days", 0)
                components[comp_id]["timeframe_label"] = proj.get("timeframe_label", "")

        # Cross-sensor correlation: detect complex failure patterns
        self._cross_sensor_correlation(components, latest_telemetry, dtc_codes)

        # Calculate overall health score (weighted by component importance)
        overall_score = self._calculate_overall_score(components)

        # Determine data quality
        data_quality = {
            "telemetry_points": len(telemetry_history),
            "baseline_established": len(telemetry_history) >= 10,
            "has_research": research_data is not None,
            "has_mileage": mileage_km is not None and mileage_km > 0,
            "has_live_data": bool(latest_telemetry),
            "active_dtcs": len([d for d in dtc_codes if d.get("is_active")]),
            "service_records_count": len(service_records) if service_records else 0,
        }

        elapsed = round(time.time() - start_time, 3)
        logger.info(
            "Health assessment for vehicle %d: score=%d, components=%d, time=%.3fs",
            vehicle_id, overall_score, len(components), elapsed,
        )

        return {
            "success": True,
            "health_score": overall_score,
            "is_cold_start": not cold_start_available,
            "cold_start_available": cold_start_available,
            "resting_voltage": resting_voltage,
            "vehicle_id": vehicle_id,
            "components": components,
            "active_dtcs": [d.get("code", "") for d in dtc_codes if d.get("is_active")],
            "climate_region": climate_region,
            "driving_context": context,
            "mileage_km": mileage_km,
            "mileage_source": mileage_source,
            "detected_patterns": [
                {"name": p.display_name, "severity": p.severity, "confidence": p.confidence,
                 "reasoning": p.reasoning, "recommendation": p.recommendation}
                for p in patterns
            ],
            "data_quality": data_quality,
            "assessment_time_ms": int(elapsed * 1000),
        }

    # =====================================================
    # LAYER 1: Sensor Threshold Rules
    # =====================================================

    def _layer1_sensor_thresholds(
        self, telemetry: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Check real-time OBD sensor values against known safe ranges.
        Uses context-aware scoring for sensors that benefit from driving context
        (coolant, battery, oil temp, engine load, intake temp, boost pressure),
        falling back to static threshold scoring for other sensors.
        Returns health score (0-100) per component based on sensor readings.
        """
        component_scores: Dict[str, List[float]] = {}

        if not telemetry:
            return {}

        # Get context-aware scores for supported sensors
        context_results = self.context_scorer.score_all(telemetry)

        for sensor_name, value in telemetry.items():
            if value is None or sensor_name not in SENSOR_THRESHOLDS:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            component = SENSOR_TO_COMPONENT.get(sensor_name)
            if not component:
                continue

            # Use context-aware score if available, else fall back to threshold
            if sensor_name in context_results:
                score = context_results[sensor_name]["score"]
            else:
                thresholds = SENSOR_THRESHOLDS[sensor_name]
                score = self._score_sensor_value(value, thresholds)

            if component not in component_scores:
                component_scores[component] = []
            component_scores[component].append(score)

        # Average scores per component
        result = {}
        for comp, scores in component_scores.items():
            result[comp] = round(sum(scores) / len(scores), 1)

        return result

    def _score_sensor_value(self, value: float, thresholds: dict) -> float:
        """Score a single sensor reading 0-100 based on thresholds."""
        opt_min = thresholds.get("optimal_min", thresholds["min"])
        opt_max = thresholds.get("optimal_max", thresholds["max"])
        abs_min = thresholds["min"]
        abs_max = thresholds["max"]

        # In optimal range → 100
        if opt_min <= value <= opt_max:
            return 100.0

        # Check critical thresholds
        critical_high = thresholds.get("critical_high")
        critical_low = thresholds.get("critical_low")

        if critical_high and value >= critical_high:
            return 10.0  # Critical danger
        if critical_low and value <= critical_low:
            return 10.0  # Critical danger

        # Below optimal but above minimum → 50-100
        if value < opt_min and value >= abs_min:
            range_size = opt_min - abs_min
            if range_size > 0:
                return 50.0 + 50.0 * (value - abs_min) / range_size
            return 50.0

        # Above optimal but below maximum → 50-100
        if value > opt_max and value <= abs_max:
            range_size = abs_max - opt_max
            if range_size > 0:
                return 50.0 + 50.0 * (abs_max - value) / range_size
            return 50.0

        # Outside absolute range → 0-20
        if value < abs_min:
            return max(0, 20.0 * (1 - abs(value - abs_min) / max(1, abs(abs_min))))
        if value > abs_max:
            return max(0, 20.0 * (1 - abs(value - abs_max) / max(1, abs(abs_max))))

        return 50.0

    # =====================================================
    # LAYER 2: Statistical Lifespan + Qatar Climate
    # =====================================================

    def _layer2_statistical_lifespan(
        self,
        mileage_km: Optional[float],
        vehicle_year: Optional[int],
        climate_region: str = "qatar",
    ) -> Dict[str, Dict[str, Any]]:
        """
        Estimate component health based on age/mileage using Weibull survival curves.
        Applies Qatar heat multiplier when climate_region is 'qatar'.
        """
        result = {}
        current_year = _dt.now().year

        # Convert km to miles for RUL estimator
        mileage_miles = int(mileage_km * 0.621371) if mileage_km else None
        vehicle_age_years = (current_year - vehicle_year) if vehicle_year else None

        for comp_id in ALL_COMPONENTS:
            model = self.rul_estimator.component_models.get(comp_id)
            if not model:
                continue

            comp_result = {"health_pct": 75.0, "rul_days": None, "rul_miles": None}

            # Use survival analysis if we have mileage
            if mileage_miles and mileage_miles > 0:
                survival = self.rul_estimator.survival_analysis_estimate(
                    comp_id, mileage_miles
                )
                if survival:
                    remaining_miles = survival.get("expected_remaining_miles", 0)
                    survival_prob = survival.get("current_survival_probability", 1.0)
                    comp_result["health_pct"] = round(survival_prob * 100, 1)
                    comp_result["rul_miles"] = remaining_miles
                    comp_result["rul_days"] = int(remaining_miles / 33) if remaining_miles > 0 else 0

            # Use first-principles if we have year
            elif vehicle_age_years is not None:
                life_years = model.typical_life_years
                if climate_region == "qatar":
                    mult = self.rul_estimator.qatar_climate_multiplier(comp_id)
                    life_years *= mult

                if vehicle_age_years > 0:
                    pct_used = vehicle_age_years / life_years
                    health = max(0, min(100, (1.0 - pct_used) * 100))
                    comp_result["health_pct"] = round(health, 1)
                    remaining_years = max(0, life_years - vehicle_age_years)
                    comp_result["rul_days"] = int(remaining_years * 365)

            # Qatar climate adjustment removed from Layer 2 (was double-penalizing).
            # Age decay is now handled exclusively in _merge_layers via AGE_DECAY_RATES.
            # Layer 2 still provides RUL estimates but its health_pct is informational only.

            result[comp_id] = comp_result

        return result

    # =====================================================
    # LAYER 3: Self-Baseline Anomaly Detection
    # =====================================================

    def _layer3_baseline_anomaly(
        self,
        latest_telemetry: Dict[str, Any],
        telemetry_history: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """
        Compare current readings to this vehicle's own historical averages.
        Requires at least 10 readings (about 3-5 drives) to establish a baseline.

        Returns health score per component. Skipped if insufficient data.
        """
        if len(telemetry_history) < 10 or not latest_telemetry:
            return {}  # Not enough data — skip this layer

        # Build per-sensor historical stats
        sensor_stats: Dict[str, Dict[str, float]] = {}
        numeric_sensors = [
            "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
            "throttle_pos", "fuel_level", "intake_temp", "maf_rate", "oil_temp",
            "short_term_fuel_trim", "long_term_fuel_trim",
        ]

        for sensor in numeric_sensors:
            values = []
            for reading in telemetry_history:
                val = reading.get(sensor)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (TypeError, ValueError):
                        continue

            if len(values) >= 5:
                arr = np.array(values)
                sensor_stats[sensor] = {
                    "mean": float(np.mean(arr)),
                    "std": float(np.std(arr)),
                }

        # Score current readings against baseline
        component_scores: Dict[str, List[float]] = {}

        for sensor, stats in sensor_stats.items():
            current = latest_telemetry.get(sensor)
            if current is None:
                continue
            try:
                current = float(current)
            except (TypeError, ValueError):
                continue

            mean = stats["mean"]
            std = max(stats["std"], 0.001)  # Avoid division by zero

            # Z-score: how many standard deviations from mean
            z_score = abs(current - mean) / std

            # Map z-score to health: 0 stddev → 100, 2 stddev → 50, 4+ stddev → 0
            if z_score <= 1.0:
                score = 100.0
            elif z_score <= 2.0:
                score = 100.0 - (z_score - 1.0) * 50.0  # 100→50
            elif z_score <= 4.0:
                score = 50.0 - (z_score - 2.0) * 25.0  # 50→0
            else:
                score = 0.0

            component = SENSOR_TO_COMPONENT.get(sensor)
            if component:
                if component not in component_scores:
                    component_scores[component] = []
                component_scores[component].append(score)

        result = {}
        for comp, scores in component_scores.items():
            result[comp] = round(sum(scores) / len(scores), 1)

        return result

    # =====================================================
    # LAYER 4: DTC Intelligence
    # =====================================================

    def _layer4_dtc_intelligence(
        self, dtc_codes: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Map active/pending DTC codes to component health impacts.
        Active DTCs reduce health by 20-50 points. Pending DTCs reduce by 10-20.
        """
        if not dtc_codes:
            return {}

        component_penalties: Dict[str, List[float]] = {}

        for dtc in dtc_codes:
            code = dtc.get("code", "").upper()
            is_active = dtc.get("is_active", True)
            is_pending = dtc.get("is_pending", False)
            severity = dtc.get("severity", "info").lower()

            # Determine which component this DTC affects
            component = None
            for prefix, comp in DTC_COMPONENT_MAP.items():
                if code.startswith(prefix):
                    component = comp
                    break

            if not component:
                # Generic powertrain code
                if code.startswith("P"):
                    component = "engine"
                elif code.startswith("B"):
                    component = "engine"
                elif code.startswith("C"):
                    component = "brakes"
                elif code.startswith("U"):
                    component = "engine"
                else:
                    continue

            # Calculate penalty based on severity and active/pending status
            if is_active and not is_pending:
                if severity in ("critical", "high"):
                    penalty = 50.0
                elif severity in ("medium", "warning"):
                    penalty = 35.0
                else:
                    penalty = 20.0
            elif is_pending:
                if severity in ("critical", "high"):
                    penalty = 20.0
                else:
                    penalty = 10.0
            else:
                continue  # Cleared DTC — no penalty

            if component not in component_penalties:
                component_penalties[component] = []
            component_penalties[component].append(penalty)

        # Convert penalties to health scores (100 minus total penalty, capped)
        result = {}
        for comp, penalties in component_penalties.items():
            total_penalty = min(80, sum(penalties))  # Cap at 80 points of reduction
            result[comp] = round(100.0 - total_penalty, 1)

        return result

    # =====================================================
    # LAYER 4.5: Mode 06 ECU Test Results
    # =====================================================

    # Map Mode 06 component names → our health component IDs
    MODE06_COMPONENT_MAP = {
        "catalyst": "catalytic_converter",
        "catalyst monitor": "catalytic_converter",
        "o2 sensor": "o2_sensor",
        "oxygen sensor": "o2_sensor",
        "egr": "engine",
        "egr system": "engine",
        "evap": "fuel_pump",
        "evap system": "fuel_pump",
        "misfire": "spark_plugs",
        "misfire monitor": "spark_plugs",
        "fuel system": "fuel_pump",
        "heated catalyst": "catalytic_converter",
        "secondary air": "engine",
        "a/c refrigerant": "engine",
    }

    def _layer45_mode06_tests(
        self, mode06_results: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, float]:
        """
        Layer 4.5: ECU's own on-board test verdicts.

        These are the most authoritative signals we have — the ECU ran its own
        calibrated tests and reports pass/fail with exact limits. We give this
        layer high weight in the merge.

        Scoring:
        - All tests PASS → health boost (95%)
        - Test MARGINAL (value >75% of limit range) → health penalty (65%)
        - Test FAIL → health penalty (30%)
        - No Mode 06 data → empty dict (layer skipped)
        """
        if not mode06_results:
            return {}

        component_scores: Dict[str, List[float]] = {}

        for test in mode06_results:
            passed = test.get("passed", True)
            component_name = (test.get("component_name") or "").lower().strip()
            test_value = test.get("test_value")
            max_limit = test.get("max_limit")
            min_limit = test.get("min_limit")

            # Map to our component ID
            comp_id = None
            for key, mapped in self.MODE06_COMPONENT_MAP.items():
                if key in component_name:
                    comp_id = mapped
                    break

            if not comp_id:
                continue

            if comp_id not in component_scores:
                component_scores[comp_id] = []

            if not passed:
                # Failed ECU test — significant health reduction
                component_scores[comp_id].append(30.0)
            elif test_value is not None and max_limit is not None and max_limit > 0:
                # Check if marginal (value approaching limit)
                usage_pct = abs(test_value) / abs(max_limit) if max_limit != 0 else 0
                if usage_pct > 0.90:
                    component_scores[comp_id].append(50.0)   # Near-fail
                elif usage_pct > 0.75:
                    component_scores[comp_id].append(65.0)   # Marginal
                else:
                    component_scores[comp_id].append(95.0)   # Healthy pass
            elif test_value is not None and min_limit is not None and min_limit > 0:
                # For sensors with minimum limits
                if test_value < min_limit * 1.1:
                    component_scores[comp_id].append(55.0)   # Near-fail low
                else:
                    component_scores[comp_id].append(95.0)
            else:
                # Passed with no limit context
                component_scores[comp_id].append(90.0)

        result = {}
        for comp, scores in component_scores.items():
            # Use minimum score (worst test result dominates)
            result[comp] = round(min(scores), 1)

        return result

    # =====================================================
    # LAYER 5: Vehicle Research Context
    # =====================================================

    def _layer5_research_context(
        self, research_data: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Use vehicle research data (common problems, recalls, reliability) to adjust health context.
        This layer provides CONTEXT adjustments, not direct scoring.

        Returns a confidence multiplier per component (0.8-1.0).
        """
        if not research_data:
            return {}

        adjustments = {}

        # Check common problems / failure-prone parts
        common_problems = research_data.get("common_problems") or research_data.get("failure_prone_parts") or []
        if isinstance(common_problems, list):
            problem_text = " ".join(str(p) for p in common_problems).lower()

            keyword_component_map = {
                "battery": "battery",
                "alternator": "alternator",
                "thermostat": "thermostat",
                "fuel pump": "fuel_pump",
                "spark plug": "spark_plugs",
                "ignition": "spark_plugs",
                "o2 sensor": "o2_sensor",
                "oxygen sensor": "o2_sensor",
                "catalytic": "catalytic_converter",
                "maf": "maf_sensor",
                "mass air": "maf_sensor",
                "coolant": "coolant",
                "radiator": "coolant",
                "transmission": "transmission_fluid",
                "gearbox": "transmission_fluid",
                "brake": "brakes",
                "engine": "engine",
            }

            for keyword, comp in keyword_component_map.items():
                if keyword in problem_text:
                    adjustments[comp] = adjustments.get(comp, 1.0) * 0.9  # 10% confidence reduction

        # Check active recalls
        recalls = research_data.get("recalls") or research_data.get("active_recalls") or []
        if isinstance(recalls, list) and len(recalls) > 0:
            recall_text = " ".join(str(r) for r in recalls).lower()
            for keyword, comp in {
                "battery": "battery", "alternator": "alternator",
                "fuel": "fuel_pump", "brake": "brakes",
                "transmission": "transmission_fluid", "engine": "engine",
                "airbag": "engine", "electrical": "battery",
            }.items():
                if keyword in recall_text:
                    adjustments[comp] = adjustments.get(comp, 1.0) * 0.85  # Recall = bigger adjustment

        return adjustments

    # =====================================================
    # LAYER 6: SERVICE HISTORY INTELLIGENCE
    # =====================================================

    SERVICE_INTERVALS = {
        "oil_change":    {"component": "engine",              "interval_km": 10000},
        "oil_filter":    {"component": "engine",              "interval_km": 10000},
        "air_filter":    {"component": "maf_sensor",          "interval_km": 20000},
        "brake_pads":    {"component": "brakes",              "interval_km": 40000},
        "brake_fluid":   {"component": "brakes",              "interval_km": 40000},
        "coolant_flush": {"component": "coolant",             "interval_km": 60000},
        "transmission":  {"component": "transmission_fluid",  "interval_km": 80000},
        "spark_plugs":   {"component": "spark_plugs",         "interval_km": 50000},
        "battery":       {"component": "battery",             "interval_km": 80000},
        "catalytic":     {"component": "catalytic_converter", "interval_km": 150000},
        "o2_sensor":     {"component": "o2_sensor",           "interval_km": 100000},
        "fuel_filter":   {"component": "fuel_pump",           "interval_km": 40000},
        "thermostat":    {"component": "thermostat",          "interval_km": 100000},
        "alternator":    {"component": "alternator",          "interval_km": 120000},
    }

    def _layer6_service_history(
        self,
        service_records: Optional[List[Dict[str, Any]]],
        current_odometer: Optional[float],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Layer 6: Service History Intelligence.

        Uses maintenance records to adjust component health. If oil hasn't been
        changed in 15,000 km, engine health should drop. If brakes were just
        replaced, brakes health should be high.

        Returns dict of component_id -> {health_pct, recommendation, km_since_service}
        """
        results: Dict[str, Dict[str, Any]] = {}

        if not service_records:
            # No service history — if vehicle has significant mileage, assume overdue
            if current_odometer and current_odometer > 30000:
                for svc_type, info in self.SERVICE_INTERVALS.items():
                    comp = info["component"]
                    if comp not in results:
                        # Assume service was done at half current odometer (generous estimate)
                        assumed_km_since = current_odometer * 0.5
                        interval = info["interval_km"]
                        overdue_ratio = assumed_km_since / interval
                        health = max(20, 100 - (overdue_ratio * 50))
                        results[comp] = {
                            "health_pct": round(health, 1),
                            "recommendation": f"No {svc_type.replace('_', ' ')} records found — consider checking",
                            "km_since_service": None,
                            "overdue": overdue_ratio > 1.0,
                        }
            return results

        # Build a map: component -> most recent service record
        best_per_component: Dict[str, Dict[str, Any]] = {}

        for record in service_records:
            svc_type = (record.get("service_type") or "").lower().strip()
            service_km = record.get("service_km") or 0

            # Match service type to component
            matched_component = None
            for known_type, info in self.SERVICE_INTERVALS.items():
                if known_type in svc_type or svc_type in known_type:
                    matched_component = info["component"]
                    interval_km = info["interval_km"]
                    break

            # Also try component_type field directly
            if not matched_component:
                comp_type = (record.get("component_type") or "").lower().strip()
                for known_type, info in self.SERVICE_INTERVALS.items():
                    if known_type in comp_type or comp_type in known_type:
                        matched_component = info["component"]
                        interval_km = info["interval_km"]
                        break

            if not matched_component:
                continue

            # Keep the most recent (highest service_km) per component
            existing = best_per_component.get(matched_component)
            if not existing or service_km > existing.get("service_km", 0):
                best_per_component[matched_component] = {
                    "service_km": service_km,
                    "interval_km": interval_km,
                    "service_type": svc_type,
                    "expected_lifespan_km": record.get("expected_lifespan_km"),
                }

        # Calculate health per component based on km since service
        for comp, svc_data in best_per_component.items():
            service_km = svc_data["service_km"]
            interval = svc_data.get("expected_lifespan_km") or svc_data["interval_km"]

            if current_odometer and service_km > 0:
                km_since = current_odometer - service_km
                usage_ratio = km_since / interval if interval > 0 else 1.0

                if usage_ratio <= 0.5:
                    health = 95.0  # Recently serviced
                elif usage_ratio <= 0.8:
                    health = 85.0 - (usage_ratio - 0.5) * 30  # Gradual decline
                elif usage_ratio <= 1.0:
                    health = 70.0 - (usage_ratio - 0.8) * 50  # Approaching due
                else:
                    # Overdue — steeper drop
                    overdue_factor = min(usage_ratio - 1.0, 1.0)
                    health = max(15, 60.0 - overdue_factor * 45)

                overdue = usage_ratio > 1.0
                svc_name = svc_data["service_type"].replace("_", " ").title()
                if overdue:
                    overdue_km = int(km_since - interval)
                    recommendation = f"{svc_name} overdue by {overdue_km:,} km"
                elif usage_ratio > 0.8:
                    remaining = int(interval - km_since)
                    recommendation = f"{svc_name} due in {remaining:,} km"
                else:
                    recommendation = f"{svc_name} — {int(km_since):,} km since last service"

                results[comp] = {
                    "health_pct": round(health, 1),
                    "recommendation": recommendation,
                    "km_since_service": int(km_since),
                    "overdue": overdue,
                }
            else:
                # Have a record but no odometer to calculate delta
                results[comp] = {
                    "health_pct": 80.0,
                    "recommendation": f"Service recorded at {service_km:,} km",
                    "km_since_service": None,
                    "overdue": False,
                }

        return results

    # =====================================================
    # LAYER MERGER
    # =====================================================

    def _merge_layers(
        self,
        layer1: Dict[str, float],
        layer2: Dict[str, Dict[str, Any]],
        layer3: Dict[str, float],
        layer4: Dict[str, float],
        layer5: Dict[str, float],
        layer6: Optional[Dict[str, Dict[str, Any]]] = None,
        layer45: Optional[Dict[str, float]] = None,
        latest_telemetry: Optional[Dict[str, Any]] = None,
        vehicle_profile: Optional[Dict[str, Any]] = None,
        patterns: Optional[List] = None,
        fleet_adjustments: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Penalty-based merge: 100% - evidence of problems.

        Score = 100 - DTC_penalty - sensor_penalty - anomaly_penalty
                    - mode06_penalty - service_penalty - age_penalty
                    - pattern_penalty - research_penalty

        Each penalty source is capped to prevent a single source from
        overwhelming the score.
        """
        layer6 = layer6 or {}
        layer45 = layer45 or {}
        latest_telemetry = latest_telemetry or {}
        vehicle_profile = vehicle_profile or {}
        patterns = patterns or []
        fleet_adjustments = fleet_adjustments or {}
        components = {}
        component_ages = vehicle_profile.get("component_ages") or {}

        for comp_id in ALL_COMPONENTS:
            score = 100
            penalties = []
            active_layers = []
            confidence_tier = ConfidenceTier.ESTIMATED  # default

            # Determine confidence tier
            if comp_id in MEASURED_COMPONENTS:
                sensor_keys = MEASURED_COMPONENTS[comp_id]
                has_sensor = any(latest_telemetry.get(s) is not None for s in sensor_keys)
                if has_sensor:
                    confidence_tier = ConfidenceTier.MEASURED
            if comp_id in INFERRED_COMPONENTS and confidence_tier != ConfidenceTier.MEASURED:
                info = INFERRED_COMPONENTS[comp_id]
                has_related = any(latest_telemetry.get(s) is not None for s in info["sensors"])
                if has_related:
                    confidence_tier = ConfidenceTier.INFERRED

            # Penalty 1: DTC (Layer 4) — max -50
            if comp_id in layer4:
                dtc_health = layer4[comp_id] if isinstance(layer4[comp_id], (int, float)) else layer4[comp_id].get("health_pct", 100)
                dtc_penalty = max(0, 100 - dtc_health)
                if dtc_penalty > 0:
                    reason = layer4[comp_id].get("reason", "DTC detected") if isinstance(layer4[comp_id], dict) else "DTC detected"
                    penalties.append(("dtc", min(50, dtc_penalty), reason))
                    active_layers.append("dtc_intelligence")

            # Penalty 2: Sensor out of range (Layer 1) — max -40
            if comp_id in layer1 and confidence_tier == ConfidenceTier.MEASURED:
                sensor_health = layer1[comp_id] if isinstance(layer1[comp_id], (int, float)) else layer1[comp_id].get("health_pct", 100)
                sensor_penalty = max(0, 100 - sensor_health)
                if sensor_penalty > 0:
                    reason = layer1[comp_id].get("reason", "Sensor reading outside optimal range") if isinstance(layer1[comp_id], dict) else "Sensor reading outside optimal range"
                    penalties.append(("sensor", min(40, sensor_penalty), reason))
                    active_layers.append("sensor_threshold")

            # Penalty 3: Baseline anomaly (Layer 3) — max -25
            if comp_id in layer3:
                anomaly_health = layer3[comp_id] if isinstance(layer3[comp_id], (int, float)) else layer3[comp_id].get("health_pct", 100)
                anomaly_penalty = max(0, 100 - anomaly_health)
                if anomaly_penalty > 0:
                    reason = layer3[comp_id].get("reason", "Deviation from baseline") if isinstance(layer3[comp_id], dict) else "Deviation from baseline"
                    penalties.append(("anomaly", min(25, anomaly_penalty), reason))
                    active_layers.append("baseline_anomaly")

            # Penalty 4: Mode 06 failure (Layer 4.5) — max -30
            if comp_id in layer45:
                mode06_health = layer45[comp_id] if isinstance(layer45[comp_id], (int, float)) else layer45[comp_id].get("health_pct", 100)
                mode06_penalty = max(0, 100 - mode06_health)
                if mode06_penalty > 0:
                    reason = layer45[comp_id].get("reason", "ECU test threshold exceeded") if isinstance(layer45[comp_id], dict) else "ECU test threshold exceeded"
                    penalties.append(("mode06", min(30, mode06_penalty), reason))
                    active_layers.append("ecu_test_results")

            # Penalty 5: Service overdue (Layer 6) — max -15
            layer6_data = layer6.get(comp_id, {})
            if layer6_data.get("health_pct") is not None:
                service_health = layer6_data["health_pct"]
                service_penalty = max(0, 100 - service_health)
                if service_penalty > 0:
                    penalties.append(("service", min(15, service_penalty), layer6_data.get("reason", "Service interval exceeded")))
                    active_layers.append("service_history")

            # Penalty 6: Age decay — ONLY for unmonitored components, max -15
            if confidence_tier == ConfidenceTier.ESTIMATED:
                comp_age_info = component_ages.get(comp_id)
                if comp_age_info and comp_age_info.get("replaced_date"):
                    try:
                        replaced = _dt.fromisoformat(comp_age_info["replaced_date"])
                        age_years = (_dt.now() - replaced).days / 365.25
                    except (ValueError, TypeError):
                        age_years = max(0, _dt.now().year - vehicle_profile.get("year", 2020))
                else:
                    age_years = max(0, _dt.now().year - vehicle_profile.get("year", 2020))

                decay_rate = AGE_DECAY_RATES.get(comp_id, 1.0)
                age_penalty = min(MAX_AGE_PENALTY, age_years * decay_rate * QATAR_AGE_MULTIPLIER)
                if age_penalty > 1:
                    penalties.append(("age", age_penalty, f"Estimated from age ({age_years:.0f}yr), no direct sensor data"))

            # Penalty 7: Pattern matcher — max -20 per pattern
            for pattern in patterns:
                if hasattr(pattern, 'affected_components') and comp_id in pattern.affected_components:
                    delta = abs(pattern.affected_components[comp_id])
                    penalties.append(("pattern", min(20, delta),
                                     f"Pattern: {pattern.display_name} ({pattern.confidence:.0%} confidence)"))

            # Penalty 8: Research context (Layer 5) — max -10
            if comp_id in layer5:
                research_val = layer5[comp_id]
                if isinstance(research_val, dict):
                    research_health = research_val.get("health_pct", 100)
                    research_penalty = max(0, 100 - research_health)
                    if research_penalty > 0:
                        penalties.append(("research", min(10, research_penalty), research_val.get("reason", "Known issue for this make/model")))
                        active_layers.append("research_context")
                elif isinstance(research_val, (int, float)) and research_val < 1.0:
                    # Layer 5 returns confidence multiplier < 1.0 for known-problematic components
                    research_penalty = min(10, (1.0 - research_val) * 20)
                    if research_penalty > 1:
                        penalties.append(("research", research_penalty, "Known issue for this make/model"))
                        active_layers.append("research_context")

            # Apply all penalties, with optional fleet-learned calibration multiplier
            total_penalty = sum(p[1] for p in penalties)
            fleet_mult = fleet_adjustments.get(comp_id, 1.0)
            if fleet_mult != 1.0 and total_penalty > 0:
                total_penalty = total_penalty * fleet_mult
            score = max(0, int(100 - total_penalty))

            # Build reason string
            if not penalties:
                if confidence_tier == ConfidenceTier.MEASURED:
                    reason = "All sensor readings in optimal range"
                elif confidence_tier == ConfidenceTier.INFERRED:
                    reason = INFERRED_COMPONENTS.get(comp_id, {}).get("condition", "Inferred healthy from related sensors")
                else:
                    reason = "No evidence of problems"
            else:
                biggest = max(penalties, key=lambda p: p[1])
                reason = biggest[2]

            # Get RUL data from Layer 2
            layer2_data = layer2.get(comp_id, {})
            rul_days = layer2_data.get("rul_days")
            rul_miles = layer2_data.get("rul_miles")

            # Determine trend
            trend = self._determine_trend(comp_id, layer3)

            # Generate recommendation
            svc_rec = layer6_data.get("recommendation")
            svc_overdue = layer6_data.get("overdue", False)
            model = self.rul_estimator.component_models.get(comp_id)
            if svc_overdue and svc_rec:
                recommendation = svc_rec
            elif model:
                recommendation = self.rul_estimator._generate_recommendation(
                    comp_id, score, rul_miles, rul_days, trend, model
                )
                if svc_rec and not svc_overdue:
                    recommendation = f"{recommendation}. {svc_rec}"
            else:
                recommendation = svc_rec or f"Component health: {score}%"

            supported = len(penalties) > 0 or confidence_tier != ConfidenceTier.ESTIMATED

            components[comp_id] = {
                "health_pct": score,
                "confidence_tier": confidence_tier,
                "data_source": confidence_tier,  # backward compat
                "reason": reason,
                "penalties": [{"source": p[0], "amount": round(p[1], 1), "detail": p[2]} for p in penalties],
                "trend": trend,
                "rul_days": rul_days,
                "rul_miles": rul_miles,
                "recommendation": recommendation if supported else "Not enough data for this component",
                "confidence": min(0.95, 0.3 + 0.15 * (len(active_layers) + (1 if confidence_tier == ConfidenceTier.MEASURED else 0))),
                "active_layers": active_layers,
                "supported": supported,
                "data_sources": [l for l in active_layers if l != "default_estimate"],
            }

        return components

    def _determine_trend(self, comp_id: str, layer3: Dict) -> str:
        """Determine trend from baseline layer."""
        if comp_id in layer3:
            val = layer3[comp_id]
            if isinstance(val, dict):
                trend = val.get("trend", "stable")
            elif isinstance(val, (int, float)):
                # Baseline score — compare to 100 (perfect)
                if val < 60:
                    return "degrading"
                elif val > 90:
                    return "stable"
                else:
                    return "stable"
            else:
                return "stable"
            if trend in ("improving", "degrading", "stable", "rapid_degradation"):
                return trend
        return "stable"

    def _detect_driving_context(self, telemetry: Dict[str, Any]) -> str:
        """Detect current driving context from telemetry."""
        speed = telemetry.get("speed", 0) or 0
        rpm = telemetry.get("rpm", 0) or 0
        throttle = telemetry.get("throttle_pos", 0) or 0
        if throttle > 70:
            return "aggressive"
        if speed == 0 and rpm < 900:
            return "idle"
        if 0 < speed < 40:
            return "city"
        if 40 <= speed < 80:
            return "suburban"
        if speed >= 80:
            return "highway"
        return "normal"

    def _compute_projection_summaries(
        self,
        components: Dict[str, Dict[str, Any]],
        telemetry_history: List[Dict[str, Any]],
        vehicle_profile: Dict[str, Any],
        mileage_km: int,
    ) -> Dict[str, Dict[str, Any]]:
        """Compute a one-line projection summary per component.

        Returns: {comp_id: {"projected_score": int, "timeframe_days": int,
                             "timeframe_label": str, "summary": str}}
        """
        projections = {}

        for comp_id, comp_data in components.items():
            score = comp_data.get("health_pct", 100)
            trend = comp_data.get("trend", "stable")
            tier = comp_data.get("confidence_tier", "estimated")
            penalties = comp_data.get("penalties", [])

            degradation_per_month = 0.0
            reason_parts = []

            # Source 1: Sensor trend from baseline (most reliable)
            if trend == "degrading" and tier == "measured":
                degradation_per_month = 2.0
                reason_parts.append("sensor readings trending down")

            # Source 2: Age-based decay (for unmonitored components)
            if tier == "estimated":
                decay_rate = AGE_DECAY_RATES.get(comp_id, 1.0)
                monthly_age_decay = (decay_rate * QATAR_AGE_MULTIPLIER) / 12
                degradation_per_month += monthly_age_decay
                component_reasons = {
                    "spark_plugs": "electrode wear",
                    "catalytic_converter": "thermal cycling degradation",
                    "o2_sensor": "thermal cycling in Gulf heat",
                }
                reason_parts.append(component_reasons.get(comp_id, "age-based wear estimate"))

            # Source 3: Mileage-based service intervals
            for p in penalties:
                if p["source"] == "service" and p["amount"] > 0:
                    degradation_per_month += 1.0
                    reason_parts.append("service interval approaching")
                    break

            # Source 4: Active DTC acceleration
            for p in penalties:
                if p["source"] == "dtc" and p["amount"] > 0:
                    degradation_per_month += 5.0
                    reason_parts.append("active fault code accelerating wear")
                    break

            if degradation_per_month < 0.3:
                projections[comp_id] = {
                    "projected_score": score,
                    "timeframe_days": 90,
                    "timeframe_label": "3 months",
                    "summary": "Stable — no significant change expected",
                }
            else:
                points_to_drop = 10
                months_to_drop = points_to_drop / degradation_per_month
                days = int(months_to_drop * 30)
                projected = max(0, int(score - points_to_drop))

                if days > 365:
                    timeframe = f"{days // 365}+ years"
                elif days > 60:
                    timeframe = f"{days // 30} months"
                elif days > 14:
                    timeframe = f"{days // 7} weeks"
                else:
                    timeframe = f"{days} days"

                reason = " + ".join(reason_parts) if reason_parts else "normal wear"

                projections[comp_id] = {
                    "projected_score": projected,
                    "timeframe_days": days,
                    "timeframe_label": timeframe,
                    "summary": f"\u2192 {projected}% in {timeframe} \u2014 {reason}",
                }

        return projections

    # =====================================================
    # CROSS-SENSOR CORRELATION (Post-Merge Enhancement)
    # =====================================================

    # DTC prefix → (component, health penalty, recommendation)
    DTC_COMPONENT_MAP = {
        "P0420": ("catalyst", -30, "Catalyst efficiency below threshold — likely degraded"),
        "P0430": ("catalyst", -30, "Catalyst efficiency below threshold (Bank 2)"),
        "P0171": ("fuel_pump", -25, "Fuel system running lean — check intake/fuel pressure"),
        "P0172": ("fuel_pump", -25, "Fuel system running rich — check injectors/O2 sensors"),
        "P0174": ("fuel_pump", -25, "Fuel system lean (Bank 2)"),
        "P0175": ("fuel_pump", -25, "Fuel system rich (Bank 2)"),
        "P0128": ("coolant", -15, "Thermostat stuck open — coolant not reaching operating temp"),
        "P0455": ("evap_system", -20, "EVAP system large leak"),
        "P0456": ("evap_system", -20, "EVAP system small leak"),
        "P0440": ("evap_system", -15, "EVAP system malfunction"),
        "P0401": ("egr_system", -20, "EGR insufficient flow"),
        "P0402": ("egr_system", -15, "EGR excessive flow"),
        "P0507": ("engine", -10, "Idle RPM too high"),
        "P0300": ("spark_plugs", -25, "Random misfire detected — multiple cylinders"),
        "P0301": ("spark_plugs", -20, "Cylinder 1 misfire"),
        "P0302": ("spark_plugs", -20, "Cylinder 2 misfire"),
        "P0303": ("spark_plugs", -20, "Cylinder 3 misfire"),
        "P0304": ("spark_plugs", -20, "Cylinder 4 misfire"),
        "P0305": ("spark_plugs", -20, "Cylinder 5 misfire"),
        "P0306": ("spark_plugs", -20, "Cylinder 6 misfire"),
        "P0307": ("spark_plugs", -15, "Cylinder 7 misfire"),
        "P0308": ("spark_plugs", -15, "Cylinder 8 misfire"),
    }

    def _cross_sensor_correlation(
        self,
        components: Dict[str, Dict[str, Any]],
        telemetry: Dict[str, Any],
        dtc_codes: List[Dict[str, Any]],
    ) -> None:
        """
        Post-merge enhancement: detect complex failure patterns by correlating
        multiple sensor readings and DTC codes. Modifies components in-place.
        """
        coolant = telemetry.get("coolant_temp")
        battery = telemetry.get("battery_voltage")
        engine_load = telemetry.get("engine_load")
        intake_temp = telemetry.get("intake_temp")
        maf = telemetry.get("maf_rate")
        rpm = telemetry.get("rpm")
        speed = telemetry.get("speed")
        throttle = telemetry.get("throttle_pos")
        stft = telemetry.get("short_term_fuel_trim")

        # Rule 1: High coolant + low battery = water pump bearing failing
        if coolant and battery and coolant > 105 and battery < 13.5:
            self._apply_correlation_penalty(
                components, "coolant", -10,
                "High coolant temp with low charging voltage — possible water pump or belt issue"
            )

        # Rule 2: High engine load + lean fuel trim = intake leak
        if engine_load and stft and engine_load > 70 and stft and stft > 15:
            self._apply_correlation_penalty(
                components, "fuel_pump", -10,
                "High load with lean fuel trim — possible intake or vacuum leak"
            )

        # Rule 3: High intake temp + low MAF = clogged air filter
        if intake_temp and maf and intake_temp > 55 and maf < 5:
            self._apply_correlation_penalty(
                components, "maf_sensor", -10,
                "High intake temp with low airflow — check air filter"
            )

        # Rule 4: High RPM + low speed + high throttle = transmission slipping
        if rpm and speed and throttle and rpm > 3000 and speed < 30 and throttle > 50:
            self._apply_correlation_penalty(
                components, "transmission_fluid", -15,
                "High RPM at low speed with open throttle — possible transmission slip"
            )

        # Rule 5: DTC-to-component health mapping
        for dtc_entry in dtc_codes:
            code = (dtc_entry.get("code") or "").upper()
            is_active = dtc_entry.get("is_active", False)
            is_pending = dtc_entry.get("is_pending", False)
            if not code:
                continue

            # Direct DTC match
            if code in self.DTC_COMPONENT_MAP:
                comp, penalty, rec = self.DTC_COMPONENT_MAP[code]
                # Pending DTCs get half penalty (not confirmed yet)
                actual_penalty = penalty if is_active else penalty // 2
                self._apply_correlation_penalty(components, comp, actual_penalty, f"DTC {code}: {rec}")

            # Generic prefix matches for DTCs not in the explicit map
            elif code.startswith("P01"):  # Fuel/air metering
                self._apply_correlation_penalty(
                    components, "fuel_pump", -10 if is_active else -5,
                    f"DTC {code}: Fuel/air metering issue"
                )
            elif code.startswith("P03"):  # Ignition system
                self._apply_correlation_penalty(
                    components, "spark_plugs", -10 if is_active else -5,
                    f"DTC {code}: Ignition system issue"
                )

        logger.debug("Cross-sensor correlation complete")

    def _apply_correlation_penalty(
        self,
        components: Dict[str, Dict[str, Any]],
        component_id: str,
        penalty: int,
        recommendation: str,
    ) -> None:
        """Apply a health penalty to a component from correlation analysis."""
        if component_id not in components:
            return
        comp = components[component_id]
        current = comp.get("health_pct", 75)
        new_health = max(0, min(100, current + penalty))
        comp["health_pct"] = new_health
        # Append recommendation if not already present
        existing_rec = comp.get("recommendation", "")
        if recommendation not in existing_rec:
            comp["recommendation"] = f"{existing_rec}; {recommendation}" if existing_rec else recommendation
        if new_health < 50:
            comp["trend"] = "degrading"

    def _calculate_overall_score(self, components: Dict[str, Dict[str, Any]]) -> int:
        """Calculate overall vehicle health score from component scores."""
        if not components:
            return 75  # No data = conservative default

        # Component importance weights
        COMPONENT_WEIGHTS = {
            "battery": 0.12,
            "alternator": 0.08,
            "thermostat": 0.06,
            "fuel_pump": 0.10,
            "spark_plugs": 0.08,
            "o2_sensor": 0.06,
            "catalytic_converter": 0.08,
            "maf_sensor": 0.06,
            "coolant": 0.12,
            "transmission_fluid": 0.12,
            "engine": 0.12,  # Extra for engine if present from sensors
        }

        weighted_sum = 0.0
        total_weight = 0.0

        for comp_id, data in components.items():
            weight = COMPONENT_WEIGHTS.get(comp_id, 0.05)
            weighted_sum += data["health_pct"] * weight
            total_weight += weight

        if total_weight > 0:
            return int(round(weighted_sum / total_weight))
        return 75


# Singleton
_cold_start_predictor: Optional[ColdStartPredictor] = None

def get_cold_start_predictor() -> ColdStartPredictor:
    """Get or create singleton ColdStartPredictor instance."""
    global _cold_start_predictor
    if _cold_start_predictor is None:
        _cold_start_predictor = ColdStartPredictor()
    return _cold_start_predictor
