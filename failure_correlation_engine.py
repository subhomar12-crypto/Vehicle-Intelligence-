"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Failure Correlation Rules Engine

Failure Correlation Rules Engine
================================
Combines multiple OBD-II parameters to detect failures that no single sensor can identify.

Features:
- Multi-sensor correlation rules
- Root cause analysis
- Failure chain detection
- Component relationship mapping
- Physics-based failure detection
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path
from config import get_config

CONFIG = get_config()
logger = logging.getLogger(__name__)


class FailureSeverity(Enum):
    """Severity levels for detected failures."""
    INFO = 1
    WARNING = 2
    SERIOUS = 3
    CRITICAL = 4
    EMERGENCY = 5


class FailureCategory(Enum):
    """Categories of vehicle failures."""
    ENGINE = "engine"
    COOLING = "cooling"
    ELECTRICAL = "electrical"
    FUEL_SYSTEM = "fuel_system"
    TRANSMISSION = "transmission"
    EMISSIONS = "emissions"
    IGNITION = "ignition"
    SENSORS = "sensors"
    INTAKE = "intake"
    EXHAUST = "exhaust"


@dataclass
class CorrelationRule:
    """Defines a correlation rule for failure detection."""
    rule_id: str
    name: str
    description: str
    category: FailureCategory
    conditions: List[Dict[str, Any]]
    severity: FailureSeverity
    confidence_base: float  # Base confidence (0-1)
    repair_urgency: str  # "immediate", "soon", "scheduled"
    typical_repair: str
    estimated_cost_range: Tuple[int, int]  # (min, max) in USD
    can_cause: List[str] = field(default_factory=list)  # Other failures this can trigger
    caused_by: List[str] = field(default_factory=list)  # Failures that can cause this


@dataclass
class FailureDetection:
    """Represents a detected failure."""
    rule_id: str
    name: str
    description: str
    category: str
    severity: int
    confidence: float
    evidence: List[str]
    repair_urgency: str
    typical_repair: str
    estimated_cost: Tuple[int, int]
    timestamp: str
    related_dtcs: List[str] = field(default_factory=list)
    root_cause_candidates: List[str] = field(default_factory=list)


class FailureCorrelationEngine:
    """
    Engine for detecting failures through multi-sensor correlation.
    Uses rule-based logic with physics-informed thresholds.
    """

    def __init__(self, config=None):
        """Initialize the correlation engine."""
        self.config = config
        self.rules = self._define_correlation_rules()
        self.active_detections: Dict[str, FailureDetection] = {}
        self.detection_history: List[FailureDetection] = []

        # DTC to failure mapping
        self.dtc_failure_map = self._define_dtc_mappings()

        # Storage path
        self.storage_path = CONFIG.AI_DIR / "failure_correlations"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Failure Correlation Engine initialized with {len(self.rules)} rules")

    def _define_correlation_rules(self) -> Dict[str, CorrelationRule]:
        """Define all correlation rules for failure detection."""
        rules = {}

        # ===============================
        # COOLING SYSTEM RULES
        # ===============================

        rules['thermostat_stuck_open'] = CorrelationRule(
            rule_id='thermostat_stuck_open',
            name='Thermostat Stuck Open',
            description='Engine not reaching operating temperature within expected time',
            category=FailureCategory.COOLING,
            conditions=[
                {'sensor': 'coolant_temp', 'operator': '<', 'value': 80, 'duration_minutes': 15},
                {'sensor': 'runtime', 'operator': '>', 'value': 600},  # 10 minutes
                {'sensor': 'speed', 'operator': '>', 'value': 30}  # Moving, not just idling
            ],
            severity=FailureSeverity.WARNING,
            confidence_base=0.75,
            repair_urgency='scheduled',
            typical_repair='Replace thermostat',
            estimated_cost_range=(100, 300),
            can_cause=['poor_fuel_economy', 'heater_not_working']
        )

        rules['thermostat_stuck_closed'] = CorrelationRule(
            rule_id='thermostat_stuck_closed',
            name='Thermostat Stuck Closed',
            description='Engine overheating - coolant not circulating properly',
            category=FailureCategory.COOLING,
            conditions=[
                {'sensor': 'coolant_temp', 'operator': '>', 'value': 105},
                {'sensor': 'speed', 'operator': '>', 'value': 40}  # Not stuck in traffic
            ],
            severity=FailureSeverity.CRITICAL,
            confidence_base=0.85,
            repair_urgency='immediate',
            typical_repair='Replace thermostat, check for head gasket damage',
            estimated_cost_range=(100, 2000),
            can_cause=['head_gasket_failure', 'engine_damage']
        )

        rules['coolant_leak'] = CorrelationRule(
            rule_id='coolant_leak',
            name='Possible Coolant Leak',
            description='Temperature rising faster than normal, possible coolant loss',
            category=FailureCategory.COOLING,
            conditions=[
                {'derived': 'coolant_temp_rate', 'operator': '>', 'value': 3.0},  # 3C/min rise
                {'sensor': 'coolant_temp', 'operator': '>', 'value': 95}
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.70,
            repair_urgency='soon',
            typical_repair='Pressure test cooling system, repair leak',
            estimated_cost_range=(100, 800)
        )

        rules['cooling_fan_failure'] = CorrelationRule(
            rule_id='cooling_fan_failure',
            name='Cooling Fan Failure',
            description='Temperature rises when stopped but normal when moving',
            category=FailureCategory.COOLING,
            conditions=[
                {'sensor': 'coolant_temp', 'operator': '>', 'value': 100},
                {'sensor': 'speed', 'operator': '<', 'value': 10},
                {'sensor': 'engine_load', 'operator': '<', 'value': 30}  # Not high load
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.80,
            repair_urgency='soon',
            typical_repair='Replace cooling fan or fan relay',
            estimated_cost_range=(150, 600)
        )

        # ===============================
        # ELECTRICAL SYSTEM RULES
        # ===============================

        rules['alternator_undercharging'] = CorrelationRule(
            rule_id='alternator_undercharging',
            name='Alternator Undercharging',
            description='Battery voltage low while engine running',
            category=FailureCategory.ELECTRICAL,
            conditions=[
                {'sensor': 'battery_voltage', 'operator': '<', 'value': 13.5},
                {'sensor': 'rpm', 'operator': '>', 'value': 1000}
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.85,
            repair_urgency='soon',
            typical_repair='Test and replace alternator',
            estimated_cost_range=(300, 800),
            can_cause=['dead_battery', 'electrical_system_failure']
        )

        rules['alternator_overcharging'] = CorrelationRule(
            rule_id='alternator_overcharging',
            name='Alternator Overcharging',
            description='Battery voltage too high - voltage regulator failure',
            category=FailureCategory.ELECTRICAL,
            conditions=[
                {'sensor': 'battery_voltage', 'operator': '>', 'value': 15.0},
                {'sensor': 'rpm', 'operator': '>', 'value': 1500}
            ],
            severity=FailureSeverity.CRITICAL,
            confidence_base=0.90,
            repair_urgency='immediate',
            typical_repair='Replace alternator voltage regulator or alternator',
            estimated_cost_range=(200, 700),
            can_cause=['battery_damage', 'electronics_damage']
        )

        rules['battery_failing'] = CorrelationRule(
            rule_id='battery_failing',
            name='Battery Failing',
            description='Low voltage at rest or slow recovery after starting',
            category=FailureCategory.ELECTRICAL,
            conditions=[
                {'sensor': 'battery_voltage', 'operator': '<', 'value': 12.2},
                {'sensor': 'rpm', 'operator': '<', 'value': 500}  # Engine off or just started
            ],
            severity=FailureSeverity.WARNING,
            confidence_base=0.75,
            repair_urgency='scheduled',
            typical_repair='Test and replace battery',
            estimated_cost_range=(100, 250)
        )

        rules['voltage_drop_under_load'] = CorrelationRule(
            rule_id='voltage_drop_under_load',
            name='Excessive Voltage Drop Under Load',
            description='Electrical system struggling under high load - alternator or wiring issue',
            category=FailureCategory.ELECTRICAL,
            conditions=[
                {'derived': 'voltage_load_deviation', 'operator': '<', 'value': -1.0},
                {'sensor': 'engine_load', 'operator': '>', 'value': 60}
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.70,
            repair_urgency='soon',
            typical_repair='Check alternator output and electrical connections',
            estimated_cost_range=(100, 500)
        )

        # ===============================
        # FUEL SYSTEM RULES
        # ===============================

        rules['vacuum_leak'] = CorrelationRule(
            rule_id='vacuum_leak',
            name='Vacuum Leak Detected',
            description='High fuel trim with unstable idle indicates vacuum leak',
            category=FailureCategory.FUEL_SYSTEM,
            conditions=[
                {'sensor': 'fuel_trim_long', 'operator': '>', 'value': 15},
                {'derived': 'rpm_stability', 'operator': '>', 'value': 50},  # Unstable RPM
                {'sensor': 'speed', 'operator': '<', 'value': 5}  # At idle
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.75,
            repair_urgency='soon',
            typical_repair='Smoke test intake, replace gaskets or hoses',
            estimated_cost_range=(100, 500),
            can_cause=['rough_idle', 'poor_performance', 'check_engine_light']
        )

        rules['fuel_trim_bank_imbalance'] = CorrelationRule(
            rule_id='fuel_trim_bank_imbalance',
            name='Bank-to-Bank Fuel Trim Imbalance',
            description='Fuel delivery difference between cylinder banks',
            category=FailureCategory.FUEL_SYSTEM,
            conditions=[
                {'derived': 'fuel_trim_bank_imbalance', 'operator': '>', 'value': 8}
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.80,
            repair_urgency='soon',
            typical_repair='Check injectors, intake manifold, exhaust leaks',
            estimated_cost_range=(200, 1000)
        )

        rules['fuel_pump_weak'] = CorrelationRule(
            rule_id='fuel_pump_weak',
            name='Weak Fuel Pump',
            description='Fuel trim increasing at high load suggests inadequate fuel pressure',
            category=FailureCategory.FUEL_SYSTEM,
            conditions=[
                {'sensor': 'fuel_trim_short', 'operator': '>', 'value': 20},
                {'sensor': 'engine_load', 'operator': '>', 'value': 80},
                {'sensor': 'rpm', 'operator': '>', 'value': 4000}
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.70,
            repair_urgency='soon',
            typical_repair='Check fuel pressure, replace fuel pump if low',
            estimated_cost_range=(400, 1200)
        )

        rules['rich_running'] = CorrelationRule(
            rule_id='rich_running',
            name='Engine Running Rich',
            description='Excessive fuel being injected',
            category=FailureCategory.FUEL_SYSTEM,
            conditions=[
                {'sensor': 'fuel_trim_long', 'operator': '<', 'value': -15}
            ],
            severity=FailureSeverity.WARNING,
            confidence_base=0.80,
            repair_urgency='scheduled',
            typical_repair='Check MAF sensor, fuel pressure regulator, injectors',
            estimated_cost_range=(100, 600),
            can_cause=['catalytic_converter_damage', 'poor_fuel_economy']
        )

        # ===============================
        # TRANSMISSION RULES
        # ===============================

        rules['transmission_slip'] = CorrelationRule(
            rule_id='transmission_slip',
            name='Transmission Slipping',
            description='Inconsistent speed/RPM ratio indicates clutch or band slippage',
            category=FailureCategory.TRANSMISSION,
            conditions=[
                {'derived': 'transmission_slip_indicator', 'operator': '>', 'value': 0.15},
                {'sensor': 'speed', 'operator': '>', 'value': 30}
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.75,
            repair_urgency='soon',
            typical_repair='Transmission fluid service or rebuild',
            estimated_cost_range=(150, 4000)
        )

        rules['torque_converter_issue'] = CorrelationRule(
            rule_id='torque_converter_issue',
            name='Torque Converter Issue',
            description='RPM fluctuation at steady speed indicates torque converter problem',
            category=FailureCategory.TRANSMISSION,
            conditions=[
                {'derived': 'rpm_stability', 'operator': '>', 'value': 100},
                {'sensor': 'speed', 'operator': '>', 'value': 60},
                {'sensor': 'throttle_position', 'operator': '<', 'value': 20}  # Steady cruise
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.65,
            repair_urgency='scheduled',
            typical_repair='Replace torque converter',
            estimated_cost_range=(500, 2000)
        )

        # ===============================
        # ENGINE PERFORMANCE RULES
        # ===============================

        rules['poor_idle_quality'] = CorrelationRule(
            rule_id='poor_idle_quality',
            name='Poor Idle Quality',
            description='Engine idling rough or unstable',
            category=FailureCategory.ENGINE,
            conditions=[
                {'derived': 'idle_quality_score', 'operator': '<', 'value': 60},
                {'sensor': 'speed', 'operator': '<', 'value': 5}
            ],
            severity=FailureSeverity.WARNING,
            confidence_base=0.75,
            repair_urgency='scheduled',
            typical_repair='Check spark plugs, injectors, IAC valve',
            estimated_cost_range=(50, 400),
            caused_by=['vacuum_leak', 'ignition_misfire', 'dirty_injectors']
        )

        rules['engine_overload'] = CorrelationRule(
            rule_id='engine_overload',
            name='Engine Overload Condition',
            description='Engine consistently operating at high load',
            category=FailureCategory.ENGINE,
            conditions=[
                {'sensor': 'engine_load', 'operator': '>', 'value': 90},
                {'derived': 'engine_load_mean', 'operator': '>', 'value': 80}
            ],
            severity=FailureSeverity.WARNING,
            confidence_base=0.70,
            repair_urgency='monitor',
            typical_repair='Check for towing load, catalytic converter restriction, exhaust blockage',
            estimated_cost_range=(0, 1000)
        )

        rules['maf_sensor_dirty'] = CorrelationRule(
            rule_id='maf_sensor_dirty',
            name='MAF Sensor Dirty or Failing',
            description='Fuel trims adjusting for inaccurate air flow reading',
            category=FailureCategory.SENSORS,
            conditions=[
                {'sensor': 'fuel_trim_long', 'operator': '>', 'value': 10},
                {'sensor': 'fuel_trim_short', 'operator': '>', 'value': 5}
            ],
            severity=FailureSeverity.WARNING,
            confidence_base=0.65,
            repair_urgency='scheduled',
            typical_repair='Clean or replace MAF sensor',
            estimated_cost_range=(20, 300)
        )

        # ===============================
        # EMISSIONS SYSTEM RULES
        # ===============================

        rules['catalytic_converter_efficiency'] = CorrelationRule(
            rule_id='catalytic_converter_efficiency',
            name='Catalytic Converter Efficiency Low',
            description='Catalyst not effectively treating exhaust',
            category=FailureCategory.EMISSIONS,
            conditions=[
                # This would normally check O2 sensor switching, using fuel trim as proxy
                {'sensor': 'fuel_trim_long', 'operator': '>', 'value': 8},
                {'sensor': 'runtime', 'operator': '>', 'value': 300}  # After warmup
            ],
            severity=FailureSeverity.SERIOUS,
            confidence_base=0.60,
            repair_urgency='scheduled',
            typical_repair='Replace catalytic converter',
            estimated_cost_range=(500, 2500),
            caused_by=['rich_running', 'ignition_misfire', 'coolant_leak_internal']
        )

        return rules

    def _define_dtc_mappings(self) -> Dict[str, List[str]]:
        """Map DTCs to related correlation rules."""
        return {
            'P0115': ['thermostat_stuck_open', 'thermostat_stuck_closed', 'coolant_temp_sensor'],
            'P0116': ['thermostat_stuck_open', 'thermostat_stuck_closed'],
            'P0117': ['coolant_temp_sensor'],
            'P0118': ['coolant_temp_sensor'],
            'P0125': ['thermostat_stuck_open'],
            'P0128': ['thermostat_stuck_open'],
            'P0217': ['thermostat_stuck_closed', 'cooling_fan_failure'],
            'P0562': ['alternator_undercharging', 'battery_failing'],
            'P0563': ['alternator_overcharging'],
            'P0171': ['vacuum_leak', 'maf_sensor_dirty', 'fuel_pump_weak'],
            'P0172': ['rich_running'],
            'P0174': ['vacuum_leak', 'maf_sensor_dirty'],
            'P0175': ['rich_running'],
            'P0300': ['ignition_misfire', 'vacuum_leak', 'fuel_pump_weak'],
            'P0420': ['catalytic_converter_efficiency'],
            'P0430': ['catalytic_converter_efficiency'],
            'P0700': ['transmission_slip', 'torque_converter_issue'],
            'P0740': ['torque_converter_issue'],
        }

    def analyze(self, data: Dict[str, Any], derived_features: Dict[str, Any] = None,
                active_dtcs: List[str] = None) -> List[FailureDetection]:
        """
        Analyze current data for failure patterns.

        Args:
            data: Current OBD-II sensor data
            derived_features: Features from AdvancedFeatureEngineering
            active_dtcs: Currently active DTC codes

        Returns:
            List of detected failures
        """
        detections = []
        active_dtcs = active_dtcs or []

        # Merge data and derived features
        analysis_data = data.copy()
        if derived_features:
            for key, value in derived_features.items():
                if key != 'anomaly_scores':  # Keep anomaly scores separate
                    analysis_data[f'derived_{key}' if not key.startswith('derived') else key] = value

        # Check each rule
        for rule_id, rule in self.rules.items():
            confidence, evidence = self._evaluate_rule(rule, analysis_data)

            if confidence > 0.5:  # Threshold for detection
                # Boost confidence if related DTCs are present
                dtc_boost = 0
                related_dtcs = []
                for dtc in active_dtcs:
                    dtc_code = dtc.upper() if isinstance(dtc, str) else str(dtc)
                    if dtc_code in self.dtc_failure_map:
                        if rule_id in self.dtc_failure_map[dtc_code]:
                            dtc_boost += 0.15
                            related_dtcs.append(dtc_code)

                final_confidence = min(1.0, confidence + dtc_boost)

                detection = FailureDetection(
                    rule_id=rule_id,
                    name=rule.name,
                    description=rule.description,
                    category=rule.category.value,
                    severity=rule.severity.value,
                    confidence=round(final_confidence, 2),
                    evidence=evidence,
                    repair_urgency=rule.repair_urgency,
                    typical_repair=rule.typical_repair,
                    estimated_cost=rule.estimated_cost_range,
                    timestamp=datetime.now().isoformat(),
                    related_dtcs=related_dtcs,
                    root_cause_candidates=rule.caused_by
                )

                detections.append(detection)
                self.active_detections[rule_id] = detection

        # Perform root cause analysis
        detections = self._identify_root_causes(detections)

        return detections

    def _evaluate_rule(self, rule: CorrelationRule, data: Dict) -> Tuple[float, List[str]]:
        """
        Evaluate a single correlation rule against data.

        Returns:
            Tuple of (confidence, evidence_list)
        """
        conditions_met = 0
        total_conditions = len(rule.conditions)
        evidence = []

        for condition in rule.conditions:
            met, reason = self._check_condition(condition, data)
            if met:
                conditions_met += 1
                evidence.append(reason)

        if conditions_met == 0:
            return 0.0, []

        # Calculate confidence based on conditions met
        condition_ratio = conditions_met / total_conditions
        confidence = rule.confidence_base * condition_ratio

        return confidence, evidence

    def _check_condition(self, condition: Dict, data: Dict) -> Tuple[bool, str]:
        """Check if a single condition is met."""
        # Get the value to check
        if 'sensor' in condition:
            key = condition['sensor']
            # Try multiple possible key names
            value = data.get(key)
            if value is None:
                # Try alternative names
                alternates = {
                    'coolant_temp': ['engine_coolant_temp', 'coolant_temperature'],
                    'battery_voltage': ['control_module_voltage', 'voltage'],
                    'rpm': ['engine_rpm', 'engine_speed'],
                    'speed': ['vehicle_speed'],
                    'engine_load': ['calculated_engine_load', 'load'],
                    'fuel_trim_long': ['long_term_fuel_trim_1', 'ltft1'],
                    'fuel_trim_short': ['short_term_fuel_trim_1', 'stft1'],
                    'runtime': ['run_time_since_engine_start', 'engine_runtime'],
                    'throttle_position': ['throttle_pos', 'throttle']
                }
                for alt in alternates.get(key, []):
                    value = data.get(alt)
                    if value is not None:
                        break

        elif 'derived' in condition:
            key = condition['derived']
            # Check for derived features
            value = data.get(key) or data.get(f'derived_{key}')
        else:
            return False, ""

        if value is None:
            return False, ""

        try:
            value = float(value)
        except (ValueError, TypeError):
            return False, ""

        # Evaluate the condition
        operator = condition.get('operator', '==')
        threshold = condition.get('value', 0)

        met = False
        if operator == '>':
            met = value > threshold
        elif operator == '<':
            met = value < threshold
        elif operator == '>=':
            met = value >= threshold
        elif operator == '<=':
            met = value <= threshold
        elif operator == '==':
            met = abs(value - threshold) < 0.001

        if met:
            return True, f"{key}: {value:.2f} {operator} {threshold}"

        return False, ""

    def _identify_root_causes(self, detections: List[FailureDetection]) -> List[FailureDetection]:
        """Identify which detections might be root causes vs symptoms."""
        detection_ids = {d.rule_id for d in detections}

        for detection in detections:
            rule = self.rules.get(detection.rule_id)
            if not rule:
                continue

            # Check if any detected failures could have caused this one
            potential_causes = []
            for cause_id in rule.caused_by:
                if cause_id in detection_ids:
                    potential_causes.append(cause_id)

            if potential_causes:
                detection.root_cause_candidates = potential_causes

        return detections

    def get_failure_chain(self, rule_id: str) -> Dict[str, Any]:
        """Get the chain of failures that can be caused by or cause this failure."""
        rule = self.rules.get(rule_id)
        if not rule:
            return {}

        return {
            'rule_id': rule_id,
            'name': rule.name,
            'can_cause': rule.can_cause,
            'caused_by': rule.caused_by,
            'category': rule.category.value,
            'severity': rule.severity.value
        }

    def get_all_rules_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all correlation rules."""
        return [
            {
                'rule_id': rule.rule_id,
                'name': rule.name,
                'category': rule.category.value,
                'severity': rule.severity.value,
                'repair_urgency': rule.repair_urgency,
                'typical_repair': rule.typical_repair,
                'cost_range': rule.estimated_cost_range
            }
            for rule in self.rules.values()
        ]

    def clear_active_detections(self):
        """Clear active detections."""
        self.active_detections.clear()
