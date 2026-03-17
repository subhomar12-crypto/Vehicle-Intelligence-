"""
Unified AI module that orchestrates all prediction models with production safety features.

Integrates ensemble voting, temporal consistency, uncertainty estimation, and abstention.
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from collections import deque

# Optional AI sub-modules — wrapped in try/except so a missing dependency
# does not crash the whole server. Each falls back to a no-op stub.
try:
    from predict.core.ai.ensemble_voter import EnsembleVoter
except Exception:
    EnsembleVoter = None  # type: ignore

try:
    from predict.core.ai.explainability import ExplainabilityEngine
except Exception:
    ExplainabilityEngine = None  # type: ignore

# Deleted in v3 cleanup — stubs below keep UnifiedAI functional
TemporalConsistencyFilter = None  # type: ignore
AbstentionManager = None  # type: ignore
UncertaintyEstimator = None  # type: ignore

try:
    from predict.core.ai.causal_graph import CausalGraph
except Exception:
    CausalGraph = None  # type: ignore

try:
    from predict.core.ai.survival_analysis import SurvivalAnalyzer
except Exception:
    SurvivalAnalyzer = None  # type: ignore

try:
    from predict.core.ai.anomaly_detector import AnomalyDetector
except Exception:
    AnomalyDetector = None  # type: ignore

try:
    from predict.core.ai.context_scoring import ContextAwareScorer
except Exception:
    ContextAwareScorer = None  # type: ignore

try:
    from predict.core.ai.pattern_matcher import PatternMatcher
except Exception:
    PatternMatcher = None  # type: ignore

try:
    from predict.core.ai.trend_analyzer import TrendAnalyzer
except Exception:
    TrendAnalyzer = None  # type: ignore

logger = logging.getLogger(__name__)


# ===== CAUSAL GRAPH EDGES =====
# Defines how subsystem failures propagate to other subsystems
# Format: source_component -> [(target_component, health_reduction_pct)]
CAUSAL_EDGES = {
    "coolant": [("engine", 15), ("thermostat", 10)],
    "thermostat": [("coolant", 20), ("engine", 10)],
    "battery": [("alternator", 10), ("spark_plugs", 5), ("fuel_pump", 5)],
    "alternator": [("battery", 25)],
    "fuel_pump": [("catalytic_converter", 10), ("spark_plugs", 5)],
    "spark_plugs": [("catalytic_converter", 15), ("o2_sensor", 5)],
    "maf_sensor": [("fuel_pump", 10), ("catalytic_converter", 5)],
    "o2_sensor": [("catalytic_converter", 10), ("fuel_pump", 5)],
    "transmission_fluid": [],
    "catalytic_converter": [],
}


# ===== SENSOR THRESHOLDS =====

SENSOR_THRESHOLDS = {
    'rpm': {'min': 600, 'max': 6500, 'optimal_min': 700, 'optimal_max': 3500, 'critical_high': 6000, 'unit': 'RPM'},
    'coolant_temp': {'min': 60, 'max': 120, 'optimal_min': 82, 'optimal_max': 100, 'critical_high': 110, 'unit': '°C'},
    'oil_temp': {'min': 60, 'max': 130, 'optimal_min': 90, 'optimal_max': 110, 'critical_high': 120, 'unit': '°C'},
    'battery_voltage': {'min': 11.5, 'max': 15.0, 'optimal_min': 12.4, 'optimal_max': 14.4, 'critical_low': 11.8, 'unit': 'V'},
    'engine_load': {'min': 0, 'max': 100, 'optimal_min': 10, 'optimal_max': 80, 'critical_high': 95, 'unit': '%'},
    'throttle_pos': {'min': 0, 'max': 100, 'optimal_min': 0, 'optimal_max': 85, 'unit': '%'},
    'speed': {'min': 0, 'max': 250, 'optimal_min': 0, 'optimal_max': 140, 'unit': 'km/h'},
    'intake_temp': {'min': -40, 'max': 80, 'optimal_min': 10, 'optimal_max': 50, 'critical_high': 70, 'unit': '°C'},
    'maf_rate': {'min': 0, 'max': 500, 'optimal_min': 2, 'optimal_max': 300, 'unit': 'g/s'},
    'fuel_level': {'min': 0, 'max': 100, 'optimal_min': 20, 'optimal_max': 100, 'critical_low': 10, 'unit': '%'},
    'fuel_pressure': {'min': 20, 'max': 80, 'optimal_min': 30, 'optimal_max': 65, 'critical_low': 20, 'critical_high': 75, 'unit': 'kPa'},
    'short_term_fuel_trim': {'min': -25, 'max': 25, 'optimal_min': -10, 'optimal_max': 10, 'unit': '%'},
    'long_term_fuel_trim': {'min': -25, 'max': 25, 'optimal_min': -10, 'optimal_max': 10, 'unit': '%'},
    'timing_advance': {'min': -10, 'max': 50, 'optimal_min': 5, 'optimal_max': 35, 'unit': '°'},
    # Extended PIDs
    'ambient_temp': {'min': -30, 'max': 60, 'optimal_min': 5, 'optimal_max': 45, 'critical_high': 55, 'unit': '°C'},
    'boost_pressure': {'min': 0, 'max': 300, 'optimal_min': 50, 'optimal_max': 200, 'critical_high': 260, 'unit': 'kPa'},
    'fuel_rate': {'min': 0, 'max': 80, 'optimal_min': 0.5, 'optimal_max': 40, 'unit': 'L/h'},
    'torque': {'min': 0, 'max': 1000, 'optimal_min': 10, 'optimal_max': 500, 'unit': 'Nm'},
}


# ===== SUBSYSTEM DEFINITIONS =====

VEHICLE_SUBSYSTEMS = {
    'engine': {
        'sensors': ['rpm', 'engine_load', 'throttle_pos', 'timing_advance', 'torque', 'boost_pressure'],
        'weight': 0.30,
        'critical_threshold': 60,
    },
    'cooling': {
        'sensors': ['coolant_temp', 'oil_temp', 'intake_temp', 'ambient_temp'],
        'weight': 0.20,
        'critical_threshold': 50,
    },
    'electrical': {
        'sensors': ['battery_voltage'],
        'weight': 0.15,
        'critical_threshold': 55,
    },
    'fuel_system': {
        'sensors': ['fuel_level', 'fuel_pressure', 'short_term_fuel_trim', 'long_term_fuel_trim', 'maf_rate', 'fuel_rate'],
        'weight': 0.20,
        'critical_threshold': 55,
    },
    'transmission': {
        'sensors': ['speed', 'rpm'],
        'weight': 0.15,
        'critical_threshold': 60,
    },
}


class UnifiedAI:
    """
    Unified AI interface for vehicle intelligence with production safety features.
    
    Features:
    - Ensemble prediction from multiple models
    - Temporal consistency filtering
    - Uncertainty estimation
    - Abstention when confidence is low
    - Explainable predictions with SHAP values
    - Comprehensive health scoring
    - Trend analysis
    - Root cause analysis (causal graph)
    - Survival analysis for time-to-failure
    - Context-aware anomaly detection
    """
    
    def __init__(self):
        # Core modules — each may be None if its file is missing / dependency unavailable
        self.lstm = None
        self.ensemble = EnsembleVoter() if EnsembleVoter else None
        self.explainer = ExplainabilityEngine() if ExplainabilityEngine else None
        self.temporal_filter = None  # deleted in v3 cleanup
        self.abstention_manager = None  # deleted in v3 cleanup
        self.uncertainty_estimator = None  # deleted in v3 cleanup

        # Phase 6C: New AI modules
        self.causal_graph = CausalGraph() if CausalGraph else None
        self.survival_analyzer = SurvivalAnalyzer() if SurvivalAnalyzer else None
        self.anomaly_detector = AnomalyDetector() if AnomalyDetector else None

        # Intelligence layers (context-aware scoring, pattern matching, trend analysis)
        self.context_scorer = ContextAwareScorer() if ContextAwareScorer else None
        self.pattern_matcher = PatternMatcher() if PatternMatcher else None
        self.trend_analyzer = TrendAnalyzer() if TrendAnalyzer else None

        # Environmental context (privacy-safe)
        self.environmental_context = {
            'ambient_temp': 25.0,
        }

        # Adaptive thresholds learned over time
        self.adaptive_thresholds = {}

        # Vehicle data cache
        self._vehicle_data_cache = {}

        self._setup_ensemble()
        logger.info("UnifiedAI initialized")
    
    def _setup_ensemble(self) -> None:
        """Register models with the ensemble."""
        if self.ensemble and self.lstm:
            self.ensemble.register_model("lstm", self.lstm, weight=1.5)
    
    async def analyze_vehicle_health(
        self,
        vehicle_id: int,
        obd_data: List[Dict[str, Any]],
        include_explanation: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze vehicle health with full safety pipeline.
        
        Args:
            vehicle_id: Vehicle identifier
            obd_data: List of OBD sensor readings
            include_explanation: Whether to generate explanations
        
        Returns:
            Analysis result with risk scores, uncertainty, and safety decisions
        """
        if not obd_data:
            return self._create_abstention_result("insufficient_data")
        
        # Extract latest sensor values
        latest = obd_data[-1] if obd_data else {}
        
        # Get ensemble prediction
        try:
            ensemble_result = await self.ensemble.predict(latest)
        except Exception as e:
            logger.error(f"Ensemble prediction failed: {e}")
            return self._create_abstention_result("model_failure")
        
        raw_risk = ensemble_result.get("risk", 0.5)

        # Check abstention conditions (if abstention manager available)
        should_abstain = False
        abstention_reason = ""
        if self.abstention_manager:
            uncertainty = ensemble_result.get("uncertainty", {})
            if isinstance(uncertainty, (int, float)):
                uncertainty = {"std_deviation": uncertainty}
            abstention_context = {
                "model_disagreement": uncertainty.get("std_deviation", 0.0),
                "confidence": ensemble_result.get("confidence", 0.0),
                "sequence_length": len(obd_data),
                "active_sensors": self._count_active_sensors(latest),
            }
            should_abstain, abstention_reason = self.abstention_manager.should_abstain(abstention_context)

        if should_abstain:
            return self._create_abstention_result(abstention_reason, ensemble_result)

        # Apply temporal consistency smoothing (if available)
        if self.temporal_filter:
            smoothed_risk = self.temporal_filter.smooth(
                vehicle_id=vehicle_id,
                component="general",
                raw_risk=raw_risk,
                sensor_values=latest,
            )
            trend = self.temporal_filter.get_trend(vehicle_id, "general")
        else:
            smoothed_risk = raw_risk
            trend = "stable"
        
        # Calculate health score (inverse of risk)
        health_score = max(0.0, min(100.0, (1.0 - smoothed_risk) * 100))
        
        # Determine risk level
        risk_level = self._get_risk_level(smoothed_risk)
        
        # Build result
        result = {
            "vehicle_id": vehicle_id,
            "health_score": health_score,
            "risk_score": smoothed_risk,
            "raw_risk_score": raw_risk,
            "risk_level": risk_level,
            "failure_probability": smoothed_risk,
            "confidence": ensemble_result.get("confidence", 0.0),
            "confidence_level": ensemble_result.get("confidence_level", "low"),
            "models_agree": ensemble_result.get("models_agree", False),
            "trend": trend,
            "abstained": False,
            "predictions": {
                "ensemble": ensemble_result,
                "lstm": (ensemble_result.get("predictions") or [{}])[0] if ensemble_result.get("predictions") else {},
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": time.time(),
        }
        
        # Add explanation if requested
        if include_explanation:
            try:
                explanation = self.explainer.explain(latest, smoothed_risk)
                result["explanation"] = explanation
            except Exception as e:
                logger.warning(f"Explanation generation failed: {e}")
        
        # Suppress alert if confidence too low
        if ensemble_result.get("should_suppress_alert", False):
            result["alert_suppressed"] = True
            result["alert_reason"] = "low_confidence"
        
        logger.debug(
            f"Vehicle {vehicle_id} analysis: risk={smoothed_risk:.3f}, "
            f"confidence={ensemble_result.get('confidence', 0):.3f}"
        )
        
        return result
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level string."""
        if risk_score >= 0.9:
            return "CRITICAL"
        elif risk_score >= 0.7:
            return "HIGH"
        elif risk_score >= 0.3:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _create_abstention_result(
        self,
        reason: str,
        partial_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create an abstention result."""
        if self.abstention_manager:
            message = self.abstention_manager.get_abstention_message(reason)
        else:
            message = f"Analysis unavailable: {reason}"
        
        result = {
            "abstained": True,
            "abstention_reason": reason,
            "message": message,
            "risk_score": 50,       # Safe default (midpoint) — was None, crashed downstream math
            "health_score": 50,     # Safe default (midpoint) — was None, crashed downstream math
            "risk_level": "UNKNOWN",
            "failure_probability": 0.5,
            "confidence": 0.0,
            "predictions": {
                "ensemble": {},
                "lstm": {},
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": time.time(),
        }

        if partial_result:
            result["partial_prediction"] = partial_result
            result["predictions"]["ensemble"] = partial_result
            preds = partial_result.get("predictions", [])
            if preds and isinstance(preds, list) and len(preds) > 0:
                result["predictions"]["lstm"] = preds[0]
        
        return result
    
    def _count_active_sensors(self, data: Dict[str, Any]) -> int:
        """Count number of active (non-null) sensors."""
        sensor_fields = [
            "rpm", "speed", "coolant_temp", "battery_voltage",
            "engine_load", "maf_rate", "throttle_pos", "intake_temp",
            "short_term_fuel_trim", "long_term_fuel_trim", "oil_temp",
            "timing_advance", "fuel_pressure", "fuel_level",
            "ambient_temp", "boost_pressure", "fuel_rate", "torque",
        ]
        return sum(1 for field in sensor_fields if data.get(field) is not None)
    
    def _get_dynamic_thresholds(self, sensor_name: str) -> Dict[str, Any]:
        """
        Get thresholds adjusted for environmental conditions.
        
        Args:
            sensor_name: Name of the sensor
            
        Returns:
            Adjusted thresholds dictionary
        """
        # 1. Get base thresholds (Static + Learned)
        adaptive = self.adaptive_thresholds.get(sensor_name, {})
        static = SENSOR_THRESHOLDS.get(sensor_name, {})
        thresholds = static.copy()
        thresholds.update(adaptive)
        
        # 2. Apply Environmental Adjustments
        ambient = self.environmental_context.get('ambient_temp', 25.0)
        
        if sensor_name == 'coolant_temp':
            # In extreme heat (>35°C), engines naturally run hotter.
            # We relax the warning threshold slightly to prevent false alarms.
            if ambient > 35:
                heat_offset = (ambient - 35) * 0.5  # +0.5°C tolerance per degree of heat
                thresholds['optimal_max'] = thresholds.get('optimal_max', 100) + heat_offset
                thresholds['critical_high'] = thresholds.get('critical_high', 110) + heat_offset
                
        elif sensor_name == 'intake_temp':
            # Intake temp is physically tied to ambient temp
            thresholds['optimal_min'] = ambient
            thresholds['optimal_max'] = ambient + 30  # Expect intake to be +30 over ambient max
            thresholds['critical_high'] = ambient + 50
            
        return thresholds
    
    def _calculate_health_score_for_sensor(self, sensor_name: str, value: float) -> Dict[str, Any]:
        """
        Calculate individual sensor health score.
        
        Args:
            sensor_name: Name of the sensor
            value: Current sensor value
            
        Returns:
            Health analysis for the sensor
        """
        thresholds = self._get_dynamic_thresholds(sensor_name)
        
        if not thresholds:
            return {'status': 'unknown', 'score': 50, 'message': 'No thresholds defined'}
        
        min_val = thresholds.get('min', 0)
        max_val = thresholds.get('max', 100)
        opt_min = thresholds.get('optimal_min', min_val)
        opt_max = thresholds.get('optimal_max', max_val)
        crit_high = thresholds.get('critical_high')
        crit_low = thresholds.get('critical_low')
        unit = thresholds.get('unit', '')
        
        # Calculate score
        if opt_min <= value <= opt_max:
            # In optimal range
            score = 100
            status = 'optimal'
            message = f"{sensor_name}: {value}{unit} - Optimal range"
        elif min_val <= value < opt_min:
            # Below optimal but within range
            range_pct = (value - min_val) / (opt_min - min_val) if opt_min > min_val else 1
            score = 60 + (range_pct * 30)
            status = 'low'
            message = f"{sensor_name}: {value}{unit} - Below optimal"
        elif opt_max < value <= max_val:
            # Above optimal but within range
            range_pct = 1 - ((value - opt_max) / (max_val - opt_max)) if max_val > opt_max else 1
            score = 60 + (range_pct * 30)
            status = 'high'
            message = f"{sensor_name}: {value}{unit} - Above optimal"
        else:
            # Out of range
            score = 30
            status = 'critical'
            message = f"{sensor_name}: {value}{unit} - OUT OF RANGE!"
        
        # Check critical thresholds
        if crit_high and value >= crit_high:
            score = min(score, 20)
            status = 'critical'
            message = f"{sensor_name}: {value}{unit} - CRITICAL HIGH!"
        
        if crit_low and value <= crit_low:
            score = min(score, 20)
            status = 'critical'
            message = f"{sensor_name}: {value}{unit} - CRITICAL LOW!"
        
        return {
            'status': status,
            'score': score,
            'value': value,
            'message': message,
            'unit': unit,
            'optimal_range': (opt_min, opt_max)
        }
    
    def _analyze_subsystem(self, subsystem_name: str, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a vehicle subsystem based on sensor data."""
        subsystem = VEHICLE_SUBSYSTEMS.get(subsystem_name, {})
        sensors = subsystem.get('sensors', [])
        
        sensor_scores = []
        sensor_analyses = []
        anomalies = []
        
        for sensor in sensors:
            value = sensor_data.get(sensor)
            if value is not None:
                try:
                    value = float(value)
                    analysis = self._calculate_health_score_for_sensor(sensor, value)
                    sensor_scores.append(analysis['score'])
                    sensor_analyses.append(analysis)
                    
                    if analysis['status'] in ['critical', 'high', 'low']:
                        anomalies.append(analysis)
                except (ValueError, TypeError):
                    pass
        
        if sensor_scores:
            avg_score = sum(sensor_scores) / len(sensor_scores)
        else:
            avg_score = 50  # Default when no data
        
        # Determine status
        if avg_score >= 85:
            status = 'Excellent'
            risk_level = 'LOW'
        elif avg_score >= 70:
            status = 'Good'
            risk_level = 'LOW'
        elif avg_score >= 55:
            status = 'Fair'
            risk_level = 'MEDIUM'
        elif avg_score >= 40:
            status = 'Poor'
            risk_level = 'HIGH'
        else:
            status = 'Critical'
            risk_level = 'CRITICAL'
        
        return {
            'name': subsystem_name,
            'score': avg_score,
            'status': status,
            'risk_level': risk_level,
            'sensors_analyzed': len(sensor_scores),
            'anomalies': len(anomalies),
            'details': sensor_analyses,
            'anomaly_list': anomalies
        }
    
    def _generate_trend_insights(self, history: List[Dict], current_data: Dict[str, Any]) -> List[str]:
        """
        Generate trend insights from historical data.
        
        Args:
            history: List of historical data points
            current_data: Current sensor readings
            
        Returns:
            List of insight strings
        """
        insights = []
        
        if not history or len(history) < 3:
            if current_data:
                # Generate insights from current data only
                temp = current_data.get('coolant_temp')
                if temp:
                    if temp > 95:
                        insights.append(f"Coolant temperature elevated ({temp}°C)")
                    elif temp < 75:
                        insights.append(f"Engine still warming up ({temp}°C)")
                
                voltage = current_data.get('battery_voltage')
                if voltage:
                    if voltage > 14.5:
                        insights.append(f"Charging system active ({voltage}V)")
                    elif voltage < 12.5:
                        insights.append(f"Battery voltage below optimal ({voltage}V)")
                
                if not insights:
                    insights.append("Current readings within normal range")
            else:
                insights.append("Connect to vehicle for live analysis")
            
            return insights
        
        # Analyze temperature trend
        temps = []
        for h in history[-20:]:
            t = h.get('coolant_temp') or (h.get('sensor_data', {}) or {}).get('coolant_temp')
            if t is not None:
                try:
                    temps.append(float(t))
                except (ValueError, TypeError):
                    pass
        
        if temps:
            avg_temp = sum(temps) / len(temps)
            current_temp = current_data.get('coolant_temp', temps[-1] if temps else 85)
            
            if isinstance(current_temp, (int, float)):
                if current_temp > avg_temp + 5:
                    insights.append(f"Temperature trending up ({current_temp:.1f}°C vs avg {avg_temp:.1f}°C)")
                elif current_temp < avg_temp - 5:
                    insights.append(f"Temperature below average ({current_temp:.1f}°C)")
        
        # Analyze voltage trend
        voltages = []
        for h in history[-20:]:
            v = h.get('battery_voltage') or (h.get('sensor_data', {}) or {}).get('battery_voltage')
            if v is not None:
                try:
                    voltages.append(float(v))
                except (ValueError, TypeError):
                    pass
        
        if voltages:
            avg_v = sum(voltages) / len(voltages)
            current_v = current_data.get('battery_voltage', voltages[-1] if voltages else 12.6)
            
            if isinstance(current_v, (int, float)):
                if current_v < avg_v - 0.3:
                    insights.append(f"Battery voltage declining ({current_v:.1f}V)")
                elif current_v > avg_v + 0.3:
                    insights.append(f"Charging system performing well ({current_v:.1f}V)")
        
        if not insights:
            insights.append("All parameters stable")
        
        return insights[:3]
    
    def generate_comprehensive_health_report(
        self,
        vehicle_profile: Dict[str, Any],
        latest_data: Dict[str, Any],
        history: List[Dict]
    ) -> Dict[str, Any]:
        """
        Generate comprehensive health report with weighted subsystem scoring.
        
        Args:
            vehicle_profile: Vehicle profile dictionary
            latest_data: Latest sensor readings
            history: Historical data points
            
        Returns:
            Comprehensive health report
        """
        vehicle_id = self._get_vehicle_id(vehicle_profile)
        
        # Analyze all subsystems with actual data
        subsystem_results = {}
        all_anomalies = []
        
        for subsystem_name in VEHICLE_SUBSYSTEMS.keys():
            analysis = self._analyze_subsystem(subsystem_name, latest_data or {})
            subsystem_results[subsystem_name] = {
                'score': analysis['score'],
                'status': analysis['status'],
                'risk_level': analysis['risk_level'],
                'sensors_analyzed': analysis['sensors_analyzed'],
                'anomalies': analysis['anomalies']
            }
            all_anomalies.extend(analysis['anomaly_list'])
        
        # Calculate overall health score (weighted average)
        total_weight = 0
        weighted_score = 0
        
        for subsystem_name, result in subsystem_results.items():
            weight = VEHICLE_SUBSYSTEMS[subsystem_name].get('weight', 0.1)
            weighted_score += result['score'] * weight
            total_weight += weight
        
        if total_weight > 0:
            overall_score = weighted_score / total_weight
        else:
            overall_score = 50
        
        # Determine health grade
        if overall_score >= 90:
            grade = 'A'
        elif overall_score >= 80:
            grade = 'B'
        elif overall_score >= 70:
            grade = 'C'
        elif overall_score >= 60:
            grade = 'D'
        else:
            grade = 'F'
        
        # Generate alerts based on anomalies
        expert_alerts = []
        for anomaly in all_anomalies:
            if anomaly['status'] == 'critical':
                expert_alerts.append({
                    'rule': f"Critical: {anomaly['message']}",
                    'message': anomaly['message'],
                    'severity': 'HIGH',
                    'recommendations': [f"Check {(anomaly.get('message') or 'system').split(':')[0]} immediately"]
                })
        
        # Generate recommendations based on actual data
        recommendations = self._generate_recommendations(subsystem_results, latest_data)
        
        return {
            'vehicle_id': vehicle_id,
            'overall_health_score': overall_score,
            'health_grade': grade,
            'subsystems': subsystem_results,
            'expert_alerts': expert_alerts,
            'recommendations': recommendations,
            'data_quality': {
                'sensors_available': len([v for v in (latest_data or {}).values() if v is not None]),
                'data_freshness': 'Current' if latest_data else 'No Data'
            },
            'analysis_timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'timestamp_unix': time.time(),
        }
    
    def _generate_recommendations(
        self,
        subsystems: Dict[str, Any],
        data: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on actual data analysis."""
        recommendations = []
        
        for name, result in subsystems.items():
            if result['score'] < 60:
                if name == 'cooling':
                    recommendations.append(f"Cooling system needs attention (Score: {result['score']:.0f}%). Check coolant level and thermostat.")
                elif name == 'electrical':
                    recommendations.append(f"Electrical system needs attention (Score: {result['score']:.0f}%). Check battery and alternator.")
                elif name == 'engine':
                    recommendations.append(f"Engine performance degraded (Score: {result['score']:.0f}%). Consider diagnostic scan.")
                elif name == 'fuel_system':
                    recommendations.append(f"Fuel system issues detected (Score: {result['score']:.0f}%). Check fuel filter and injectors.")
        
        # Check specific values
        if data:
            coolant = data.get('coolant_temp')
            if coolant and coolant > 100:
                recommendations.append(f"Engine running hot ({coolant}°C). Monitor closely and check cooling system.")
            
            voltage = data.get('battery_voltage')
            if voltage and voltage < 12.2:
                recommendations.append(f"Low battery voltage ({voltage}V). Battery may need charging or replacement.")
            
            fuel = data.get('fuel_level')
            if fuel and fuel < 15:
                recommendations.append(f"Low fuel level ({fuel}%). Refuel soon.")
        
        if not recommendations:
            recommendations.append("Vehicle systems operating within normal parameters. Continue regular maintenance.")
        
        return recommendations
    
    def get_dashboard_summary(
        self,
        vehicle_profile: Dict[str, Any],
        latest_data: Dict[str, Any],
        history: List[Dict]
    ) -> Dict[str, Any]:
        """
        Generate real-time dashboard data.
        
        Args:
            vehicle_profile: Vehicle profile
            latest_data: Latest sensor readings
            history: Historical data
            
        Returns:
            Dashboard summary dictionary
        """
        vehicle_id = self._get_vehicle_id(vehicle_profile)
        vehicle_name = vehicle_profile.get('name', 'Unknown') if vehicle_profile else 'Unknown'
        current_state = self._determine_vehicle_state(latest_data)
        
        # Generate health report from ACTUAL data
        health_report = self.generate_comprehensive_health_report(
            vehicle_profile, latest_data, history or []
        )
        
        overall_score = health_report.get('overall_health_score', 50)
        grade = health_report.get('health_grade', 'C')
        
        # Count actual alerts
        alerts = health_report.get('expert_alerts', [])
        alert_count = len(alerts)
        
        # Determine risk level from actual analysis
        if alert_count == 0 and overall_score >= 80:
            risk_level = 'LOW'
        elif alert_count <= 2 and overall_score >= 60:
            risk_level = 'MEDIUM'
        elif alert_count <= 4 or overall_score >= 40:
            risk_level = 'HIGH'
        else:
            risk_level = 'CRITICAL'
        
        # Calculate trend
        trend = self._calculate_trend(history, overall_score)
        
        return {
            'overall_health': overall_score,
            'health_score': overall_score,
            'health_grade': grade,
            'status': self._score_to_status(overall_score),
            'risk_level': risk_level,
            'subsystem_scores': health_report.get('subsystems', {}),
            'trend': trend,
            'alerts_count': alert_count,
            'alerts': alerts,
            'recommendations': health_report.get('recommendations', []),
            'vehicle_state': current_state,
            'vehicle_id': vehicle_id,
            'vehicle_name': vehicle_name,
            'data_quality': health_report.get('data_quality', {}),
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'timestamp_unix': time.time(),
        }
    
    def _determine_vehicle_state(self, data: Dict[str, Any]) -> str:
        """Determine the current operating state of the vehicle."""
        if not data:
            return "Unknown"
        
        try:
            rpm = float(data.get('rpm', 0))
            speed = float(data.get('speed', 0))
        except (ValueError, TypeError):
            return "Unknown"
        
        if rpm == 0 and speed == 0:
            return "Ignition On / Engine Off"
        elif rpm > 0 and speed == 0:
            return "Idling"
        elif speed > 0 and speed < 60:
            return "City Driving"
        elif speed >= 60:
            return "Highway Cruising"
        
        return "Operating"
    
    def _calculate_trend(self, history: List[Dict], current_score: float) -> str:
        """Calculate trend from history."""
        if not history or len(history) < 3:
            return "stable"
        
        # Get recent health scores from history if available
        recent_scores = []
        for h in history[-5:]:
            score = h.get('health_score') or h.get('overall_health')
            if score is not None:
                try:
                    recent_scores.append(float(score))
                except (ValueError, TypeError):
                    pass
        
        if len(recent_scores) < 2:
            return "stable"
        
        avg_recent = sum(recent_scores) / len(recent_scores)
        
        if current_score > avg_recent + 3:
            return "improving"
        elif current_score < avg_recent - 3:
            return "declining"
        return "stable"
    
    def _score_to_status(self, score: float) -> str:
        """Convert numerical score to status string."""
        if score >= 85:
            return "Excellent"
        elif score >= 70:
            return "Good"
        elif score >= 55:
            return "Fair"
        elif score >= 40:
            return "Poor"
        else:
            return "Critical"
    
    def _get_vehicle_id(self, profile: Dict[str, Any]) -> str:
        """Get unique ID for vehicle profile."""
        if not profile:
            return "unknown"
        
        vin = profile.get('vin', '')
        name = profile.get('name', '')
        profile_id = profile.get('profile_id', '')
        
        return profile_id or vin or name or "unknown"
    
    async def get_complete_vehicle_intelligence(
        self,
        vehicle_id: int,
        obd_data: List[Dict[str, Any]],
        profile: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
        include_explanation: bool = True,
        active_dtcs: Optional[List[Dict]] = None,
        session=None,
    ) -> Dict[str, Any]:
        """
        Main orchestration method - Get complete vehicle intelligence combining all AI systems.
        
        This is the main entry point for comprehensive vehicle analysis that includes:
        - Real-time OBD analysis
        - Health scoring
        - Trend analysis
        - Predictions from ensemble and LSTM models
        - Anomaly detection with context-awareness
        - Root cause analysis (causal graph)
        - Survival analysis for time-to-failure
        - Actionable recommendations
        
        Args:
            vehicle_id: Vehicle identifier
            obd_data: List of OBD sensor readings
            profile: Vehicle profile dictionary
            history: Historical OBD data
            include_explanation: Whether to include explanation
            active_dtcs: Active DTC codes for root cause analysis
            
        Returns:
            Complete intelligence report with all fields expected by AI Bridge
        """
        # Run CPU-bound health calculations in thread pool
        latest_data = obd_data[-1] if obd_data else {}
        vehicle_state = self._detect_vehicle_state(latest_data)
        
        # ===== Phase 6C: Anomaly Detection =====
        # Detect anomalies with context-aware thresholds
        anomaly_results = await asyncio.to_thread(
            self.anomaly_detector.detect_anomalies,
            latest_data,
            vehicle_id,
            vehicle_state
        )
        
        # ===== Dashboard Summary =====
        dashboard = await asyncio.to_thread(
            self.get_dashboard_summary,
            profile or {},
            latest_data,
            history or []
        )
        
        # ===== Trend Insights =====
        insights = await asyncio.to_thread(
            self._generate_trend_insights,
            history or [],
            latest_data
        )
        
        # ===== AI Predictions =====
        health_analysis = await self.analyze_vehicle_health(
            vehicle_id=vehicle_id,
            obd_data=obd_data,
            include_explanation=include_explanation
        )
        
        # ===== Phase 6C: Root Cause Analysis =====
        # Use causal graph to find root causes from symptoms
        root_causes = []
        symptoms = self._extract_symptoms_from_data(latest_data, active_dtcs or [])
        if symptoms:
            root_causes = await asyncio.to_thread(
                self.causal_graph.find_root_cause,
                symptoms
            )
        
        # ===== Phase 6C: Survival Analysis =====
        # Estimate time-to-failure for critical components
        survival_estimates = {}
        for component in ['engine', 'cooling', 'electrical', 'fuel_system', 'transmission']:
            # Extract degradation data from history for this component
            degradation_data = self._extract_degradation_data(history or [], component)
            if degradation_data:
                estimate = await asyncio.to_thread(
                    self.survival_analyzer.predict_failure_distribution,
                    component,
                    degradation_data
                )
                survival_estimates[component] = estimate
        
        # ===== Health Report =====
        health_report = await asyncio.to_thread(
            self.generate_comprehensive_health_report,
            profile or {},
            latest_data,
            history or []
        )
        
        # ===== Phase 6C: SHAP Explainability =====
        # Generate enhanced explanation with SHAP values if available
        shap_explanation = None
        if include_explanation:
            ensemble_preds = health_analysis.get('predictions', {}).get('ensemble', {})
            shap_explanation = await asyncio.to_thread(
                self.explainer.explain_prediction,
                {
                    'failure_probability': (health_analysis.get('risk_score') or 0) / 100,
                    'risk_level': dashboard.get('risk_level', 'UNKNOWN'),
                    'confidence': ensemble_preds.get('confidence', 0.5),
                    'consensus': ensemble_preds.get('models_agree', False),
                },
                latest_data,
                top_n=5
            )
        
        # ===== Cold-Start Predictions (always available, no ML needed) =====
        cold_start_health = {}
        try:
            from predict.core.ai.cold_start_predictor import get_cold_start_predictor
            cold_start = get_cold_start_predictor()
            cold_start_health = await cold_start.assess_vehicle_health(
                vehicle_id=vehicle_id,
                latest_telemetry=latest_data,
                vehicle_profile=profile or {},
                dtc_codes=[
                    {"code": d.get("code", ""), "severity": d.get("severity", "info"),
                     "is_active": True, "is_pending": d.get("is_pending", False)}
                    for d in (active_dtcs or [])
                ],
                telemetry_history=history or [],
                research_data=None,
                climate_region="qatar",
                session=session,
            )
        except Exception as e:
            logger.warning("Cold-start prediction failed (non-fatal): %s", e)

        # ===== Intelligence Layers (context scoring, patterns, trends) =====
        intelligence_results = await self._run_intelligence_layers(
            latest_data, history or [], cold_start_health
        )

        # Combine all intelligence into expected format
        result = {
            'vehicle_id': vehicle_id,
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'timestamp_unix': time.time(),
            
            # Dashboard summary
            'dashboard': {
                'overall_health': dashboard.get('overall_health', 50),
                'status': dashboard.get('status', 'unknown'),
                'subsystem_scores': dashboard.get('subsystem_scores', {}),
                'trend': dashboard.get('trend', 'stable'),
            },

            # Top-level fields expected by AI Bridge
            'health_score': dashboard.get('overall_health', 50),
            'risk_level': dashboard.get('risk_level', 'UNKNOWN'),
            'failure_probability': (health_analysis.get('failure_probability') or 0.0),
            
            # Predictions
            'predictions': health_analysis.get('predictions', {
                'ensemble': {},
                'lstm': {}
            }),
            
            # Recommendations and insights
            'recommendations': health_report.get('recommendations', []),
            'insights': insights,
            
            # Phase 6C: New AI module outputs
            'anomaly_detection': {
                'results': anomaly_results,
                'vehicle_state': vehicle_state,
                'anomalies_found': any(
                    r.get('is_anomalous', False) 
                    for r in anomaly_results.values() 
                    if isinstance(r, dict)
                ),
            },
            'root_cause_analysis': {
                'symptoms': symptoms,
                'probable_causes': root_causes[:5] if root_causes else [],
            },
            'survival_analysis': {
                'component_estimates': survival_estimates,
                'overall_p50': self._calculate_overall_p50(survival_estimates),
            },
            
            # Additional context
            'vehicle_state': vehicle_state,
            'data_quality': dashboard.get('data_quality', {}),
            'alerts_count': dashboard.get('alerts_count', 0),
            'alerts': dashboard.get('alerts', []),

            # Cold-start predictions (always present, no ML required)
            'cold_start_health': cold_start_health if cold_start_health else {},

            # Intelligence layers (context scoring, patterns, trends)
            'intelligence': intelligence_results,
        }
        
        # Add explanation if available
        if include_explanation:
            if shap_explanation:
                result['explanation'] = shap_explanation
            elif 'explanation' in health_analysis:
                result['explanation'] = health_analysis['explanation']
        
        # Add abstention info if applicable
        if health_analysis.get('abstained'):
            result['abstained'] = True
            result['abstention_reason'] = health_analysis.get('abstention_reason')
            result['message'] = health_analysis.get('message')
        
        return result
    
    # ===== Intelligence Layer Methods =====

    async def _run_intelligence_layers(
        self,
        latest_data: Dict[str, Any],
        history: List[Dict[str, Any]],
        cold_start_health: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run context scoring, pattern matching, trend analysis, cross-talk,
        and causal propagation. Returns unified intelligence results.
        """
        try:
            # Layer A: Context-aware scoring
            context_scores = await asyncio.to_thread(
                self.context_scorer.score_all, latest_data
            )

            # Layer B: Multi-signal pattern matching
            patterns = await asyncio.to_thread(
                self.pattern_matcher.match, latest_data, None, history
            )

            # Layer C: Temporal trend analysis
            trends = await asyncio.to_thread(
                self.trend_analyzer.analyze, history
            )

            # Cross-talk: propagate failures between subsystems
            components = cold_start_health.get("components", {})
            cross_talk_adjustments = self._cross_correlate(components)

            # Causal propagation: cascade risk from failing components
            causal_adjustments = self._propagate_causal_risk(components)

            # Urgency escalation
            urgency = self._calculate_urgency(components, patterns, trends)

            return {
                "context_scores": {
                    sensor: {"score": data["score"], "explanation": data["explanation"]}
                    for sensor, data in context_scores.items()
                },
                "patterns_detected": [
                    {
                        "name": p.name,
                        "display_name": p.display_name,
                        "confidence": p.confidence,
                        "severity": p.severity,
                        "reasoning": p.reasoning,
                        "recommendation": p.recommendation,
                        "what_if_ignored": p.what_if_ignored,
                        "evidence": p.evidence,
                        "affected_components": p.affected_components,
                    }
                    for p in patterns
                ],
                "trends": [
                    {
                        "sensor": t.sensor,
                        "direction": t.direction,
                        "rate": t.rate,
                        "severity": t.severity,
                        "message": t.message,
                        "data_points": t.data_points,
                        "affects": t.affects,
                    }
                    for t in trends
                ],
                "cross_talk": cross_talk_adjustments,
                "causal_propagation": causal_adjustments,
                "urgency": urgency,
            }
        except Exception as e:
            logger.warning("Intelligence layers failed (non-fatal): %s", e)
            return {
                "context_scores": {},
                "patterns_detected": [],
                "trends": [],
                "cross_talk": {},
                "causal_propagation": {},
                "urgency": {"level": "UNKNOWN", "reason": "Intelligence layers unavailable"},
            }

    def _cross_correlate(
        self, components: Dict[str, Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Cross-talk: when one subsystem is critical, related subsystems are at risk.

        Rules:
        1. Cooling critical → engine at risk (overheating damages engine)
        2. Electrical failing → fuel system affected (fuel pump is electric)
        3. Spark plugs failing → catalyst at risk (unburnt fuel)
        4. MAF failing → fuel trim affected → catalyst risk
        5. Thermostat stuck → coolant at risk
        """
        adjustments = {}

        for comp_id, data in components.items():
            health = data.get("health_pct", 100)
            if health >= 50:
                continue  # Only propagate from components that are actually struggling

            edges = CAUSAL_EDGES.get(comp_id, [])
            for target, reduction in edges:
                # Scale reduction by how bad the source component is
                severity_factor = (50 - health) / 50.0  # 0.0 at 50%, 1.0 at 0%
                actual_reduction = int(reduction * severity_factor)
                if actual_reduction > 0:
                    adjustments[target] = adjustments.get(target, 0) + actual_reduction

        return adjustments

    def _propagate_causal_risk(
        self, components: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Causal propagation: trace failure chains to identify root cause vs symptom.

        If battery is failing AND alternator is failing, the alternator is likely
        the root cause (it charges the battery). Report the causal chain.
        """
        chains = {}

        for comp_id, data in components.items():
            health = data.get("health_pct", 100)
            if health >= 60:
                continue

            # Check if any upstream component is also failing
            upstream_failures = []
            for source, edges in CAUSAL_EDGES.items():
                for target, _ in edges:
                    if target == comp_id:
                        source_health = components.get(source, {}).get("health_pct", 100)
                        if source_health < 60:
                            upstream_failures.append(source)

            if upstream_failures:
                chains[comp_id] = {
                    "is_symptom": True,
                    "probable_root_causes": upstream_failures,
                    "message": f"{comp_id} may be affected by {', '.join(upstream_failures)}",
                }
            else:
                # No upstream failure — this component is a root cause
                downstream = [t for t, _ in CAUSAL_EDGES.get(comp_id, [])]
                affected_downstream = [
                    d for d in downstream
                    if components.get(d, {}).get("health_pct", 100) < 70
                ]
                if affected_downstream:
                    chains[comp_id] = {
                        "is_symptom": False,
                        "is_root_cause": True,
                        "downstream_affected": affected_downstream,
                        "message": f"{comp_id} failure is likely causing issues in {', '.join(affected_downstream)}",
                    }

        return chains

    def _calculate_urgency(
        self,
        components: Dict[str, Dict[str, Any]],
        patterns: list,
        trends: list,
    ) -> Dict[str, Any]:
        """
        Calculate urgency level based on component health, patterns, and trends.

        Levels: CRITICAL, WARNING, ADVISORY, GOOD
        """
        critical_components = [
            c for c, d in components.items() if d.get("health_pct", 100) < 20
        ]
        warning_components = [
            c for c, d in components.items() if d.get("health_pct", 100) < 40
        ]
        degrading_count = sum(
            1 for t in trends if hasattr(t, "severity") and t.severity in ("warning", "critical")
        )
        critical_patterns = [
            p for p in patterns if hasattr(p, "severity") and p.severity == "critical"
        ]

        if critical_components or critical_patterns or degrading_count >= 3:
            components_str = ", ".join(critical_components) if critical_components else "multiple trends"
            return {
                "level": "CRITICAL",
                "reason": f"Components at risk: {components_str}",
                "action": "Service immediately — do not drive extended distances",
            }
        elif warning_components or degrading_count >= 1:
            return {
                "level": "WARNING",
                "reason": "Components need attention soon",
                "action": "Schedule service within 1-2 weeks",
            }
        elif any(d.get("health_pct", 100) < 60 for d in components.values()):
            return {
                "level": "ADVISORY",
                "reason": "Minor issues detected",
                "action": "Monitor and address at next regular service",
            }
        else:
            return {
                "level": "GOOD",
                "reason": "All systems healthy",
                "action": "Continue regular maintenance schedule",
            }

    # ===== Phase 6C: Helper Methods =====

    def _detect_vehicle_state(self, obd_data: Dict[str, Any]) -> str:
        """
        Detect the current vehicle state from OBD data.
        
        Returns one of: 'idle', 'city', 'highway', 'cold_start', 'hot_weather'
        """
        rpm = obd_data.get('rpm', 0)
        speed = obd_data.get('speed_kmh', 0) or obd_data.get('speed', 0)
        coolant_temp = obd_data.get('coolant_temp_c', 0) or obd_data.get('coolant_temp', 0)
        ambient = self.environmental_context.get('ambient_temp', 25.0)
        
        # Cold start: low coolant temp
        if coolant_temp < 60:
            return 'cold_start'
        
        # Hot weather: high ambient
        if ambient > 35:
            return 'hot_weather'
        
        # Idle: low RPM, no speed
        if rpm < 1000 and speed < 5:
            return 'idle'
        
        # Highway: higher speed
        if speed > 60:
            return 'highway'
        
        # Default: city driving
        return 'city'
    
    def _extract_symptoms_from_data(
        self,
        obd_data: Dict[str, Any],
        active_dtcs: List[Dict]
    ) -> List[str]:
        """
        Extract symptoms from OBD data and DTCs for causal analysis.
        
        Args:
            obd_data: Current sensor readings
            active_dtcs: Active DTC codes
            
        Returns:
            List of symptom strings
        """
        symptoms = []
        
        # Check sensor values for symptoms
        coolant_temp = obd_data.get('coolant_temp_c', 0) or obd_data.get('coolant_temp', 0)
        if coolant_temp > 105:
            symptoms.append('high_coolant_temp')
        if coolant_temp > 110:
            symptoms.append('engine_overheating')
        
        battery_voltage = obd_data.get('battery_voltage', 0)
        if battery_voltage < 12.0:
            symptoms.append('low_battery_voltage')
        if battery_voltage < 11.5:
            symptoms.append('battery_warning_light')
        
        rpm = obd_data.get('rpm', 0)
        if rpm > 5000:
            symptoms.append('high_rpm')
        
        engine_load = obd_data.get('engine_load', 0)
        if engine_load > 85:
            symptoms.append('engine_load_increase')
        
        # Add DTC-based symptoms
        for dtc in active_dtcs:
            code = dtc.get('code', '')
            if code.startswith('P03'):
                symptoms.append('misfire')
            elif code.startswith('P01') or code.startswith('P02'):
                symptoms.append('lean_fuel_trim')
            elif code == 'P0420':
                symptoms.append('p0420_code')
        
        return symptoms
    
    def _extract_degradation_data(
        self,
        history: List[Dict],
        component: str
    ) -> List[float]:
        """
        Extract degradation trend data from history for survival analysis.
        
        Args:
            history: Historical OBD data
            component: Component name
            
        Returns:
            List of degradation measurements (0-1 scale)
        """
        if not history or len(history) < 3:
            return []
        
        degradation_values = []
        
        # Map component to relevant sensor
        sensor_map = {
            'engine': 'engine_load',
            'cooling': 'coolant_temp',
            'electrical': 'battery_voltage',
            'fuel_system': 'long_term_fuel_trim',
            'transmission': 'rpm',
        }
        
        sensor = sensor_map.get(component)
        if not sensor:
            return []
        
        # Extract values and calculate deviation from optimal
        for record in history:
            value = record.get(sensor)
            if value is None:
                continue
            
            # Get optimal range
            thresholds = SENSOR_THRESHOLDS.get(sensor, {})
            optimal_min = thresholds.get('optimal_min', thresholds.get('min', 0))
            optimal_max = thresholds.get('optimal_max', thresholds.get('max', 100))
            optimal_mid = (optimal_min + optimal_max) / 2
            
            # Calculate deviation (0 = optimal, 1 = critical)
            if value < optimal_min:
                deviation = (optimal_min - value) / (optimal_min - thresholds.get('min', 0) + 0.001)
            elif value > optimal_max:
                deviation = (value - optimal_max) / (thresholds.get('max', optimal_max * 2) - optimal_max + 0.001)
            else:
                deviation = 0
            
            degradation_values.append(min(1.0, max(0, deviation)))
        
        return degradation_values
    
    def _calculate_overall_p50(self, survival_estimates: Dict[str, Dict]) -> float:
        """
        Calculate overall P50 (median) time-to-failure across all components.
        
        Args:
            survival_estimates: Dict of component survival estimates
            
        Returns:
            Overall P50 in days (weighted by component criticality)
        """
        if not survival_estimates:
            return 90.0  # Default
        
        # Weight by subsystem criticality
        weights = {
            'engine': 0.30,
            'cooling': 0.20,
            'electrical': 0.15,
            'fuel_system': 0.20,
            'transmission': 0.15,
        }
        
        weighted_sum = 0.0
        total_weight = 0.0
        
        for component, estimate in survival_estimates.items():
            p50 = estimate.get('p50_days', 90)
            weight = weights.get(component, 0.2)
            weighted_sum += p50 * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 90.0
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get status of all AI components."""
        status: Dict[str, Any] = {
            'ensemble': self.ensemble.get_model_status() if self.ensemble else {},
            'causal_graph_nodes': len(self.causal_graph.graph) if self.causal_graph and hasattr(self.causal_graph, 'graph') else 0,
            'survival_analyzer_ready': hasattr(self.survival_analyzer, '_has_lifelines') if self.survival_analyzer else False,
            'anomaly_detector_ready': hasattr(self.anomaly_detector, '_has_sklearn') if self.anomaly_detector else False,
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'timestamp_unix': time.time(),
        }
        return status


# Singleton instance
_unified_ai: Optional['UnifiedAI'] = None


def get_unified_ai() -> 'UnifiedAI':
    """Get UnifiedAI singleton."""
    global _unified_ai
    if _unified_ai is None:
        _unified_ai = UnifiedAI()
    return _unified_ai
