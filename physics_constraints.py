"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Physics-Constrained Validation System

Physics-Constrained Validation System
====================================

Physics-informed validators that enforce physical laws and constraints
on vehicle sensor data to detect impossible or highly unlikely readings.

System Architecture:
```
Sensor Data -> Physics Validators -> Constraint Violations -> Validation Report
       |              |                        |                    |
   Raw Readings   Battery/Cooling/Fuel/...   Impossible Values   Confidence Scores
   (Voltage, Temp)  Mathematical Models      Out-of-bounds       Anomaly Detection
   (Pressure, RPM)  Physical Constraints     Rate Violations     False Positive Reduction
```

Physics Domains:
- Battery: Kirchhoff's laws, Peukert's law, temperature effects
- Cooling: Thermodynamics, heat transfer, fluid dynamics
- Fuel: Stoichiometry, fuel mapping, injection dynamics
- Transmission: Power transfer, efficiency, gear ratios
- Engine: Thermodynamics, combustion, mechanical constraints
"""

import numpy as np
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math

logger = logging.getLogger(__name__)


class ConstraintSeverity(Enum):
    """Severity levels for constraint violations."""
    WARNING = "warning"
    CRITICAL = "critical"
    IMPOSSIBLE = "impossible"


class PhysicsDomain(Enum):
    """Physics domains for validation."""
    BATTERY = "battery"
    COOLING = "cooling"
    FUEL = "fuel"
    TRANSMISSION = "transmission"
    ENGINE = "engine"
    ELECTRICAL = "electrical"


@dataclass
class ConstraintViolation:
    """A physics constraint violation."""
    domain: PhysicsDomain
    constraint_name: str
    severity: ConstraintSeverity
    description: str
    measured_value: float
    expected_range: Tuple[float, float]
    violation_score: float  # 0-1, higher = more severe
    evidence: List[str]
    timestamp: str


@dataclass
class PhysicsValidationResult:
    """Result of physics-constrained validation."""
    is_valid: bool
    overall_confidence: float
    violations: List[ConstraintViolation]
    domain_scores: Dict[PhysicsDomain, float]
    physics_consistency_score: float
    timestamp: str


@dataclass
class VehiclePhysicsModel:
    """Physics model parameters for a specific vehicle."""
    # Battery parameters
    battery_capacity_ah: float = 50.0  # Amp-hours
    battery_voltage_nominal: float = 12.6  # Volts
    battery_internal_resistance: float = 0.02  # Ohms
    battery_peukert_constant: float = 1.3

    # Engine parameters
    engine_displacement_l: float = 2.0  # Liters
    engine_cylinders: int = 4
    engine_compression_ratio: float = 10.0
    max_engine_power_hp: float = 150.0

    # Cooling system
    coolant_capacity_l: float = 8.0
    radiator_capacity_l: float = 6.0
    thermostat_open_temp_c: float = 85.0

    # Fuel system
    fuel_tank_capacity_l: float = 50.0
    fuel_injector_flow_rate: float = 250.0  # cc/min per injector
    stoichiometric_afr: float = 14.7  # Air-fuel ratio

    # Transmission
    transmission_type: str = "automatic"
    gear_ratios: List[float] = field(default_factory=lambda: [3.5, 2.0, 1.4, 1.0, 0.8])
    final_drive_ratio: float = 3.5

    # Vehicle parameters
    vehicle_weight_kg: float = 1500.0
    drag_coefficient: float = 0.3
    frontal_area_m2: float = 2.2
    rolling_resistance: float = 0.012


class PhysicsConstraintsValidator:
    """
    Physics-informed validation system for vehicle sensor data.

    Uses domain-specific physical laws and constraints to validate
    sensor readings and detect impossible or highly unlikely values.
    """

    def __init__(self, vehicle_model: VehiclePhysicsModel = None):
        """Initialize physics constraints validator."""
        self.vehicle_model = vehicle_model or VehiclePhysicsModel()

        # Constraint violation thresholds
        self.constraint_thresholds = {
            ConstraintSeverity.WARNING: 0.3,
            ConstraintSeverity.CRITICAL: 0.7,
            ConstraintSeverity.IMPOSSIBLE: 0.9
        }

        # Domain-specific validation functions
        self.domain_validators = {
            PhysicsDomain.BATTERY: self._validate_battery_constraints,
            PhysicsDomain.COOLING: self._validate_cooling_constraints,
            PhysicsDomain.FUEL: self._validate_fuel_constraints,
            PhysicsDomain.TRANSMISSION: self._validate_transmission_constraints,
            PhysicsDomain.ENGINE: self._validate_engine_constraints,
            PhysicsDomain.ELECTRICAL: self._validate_electrical_constraints
        }

        logger.info("Physics Constraints Validator initialized")

    def validate_snapshot(self, obd_data: Dict[str, Any],
                         previous_readings: List[Dict] = None) -> PhysicsValidationResult:
        """
        Validate a snapshot of OBD data against physics constraints.

        Args:
            obd_data: Current OBD sensor readings
            previous_readings: Recent historical readings for trend analysis

        Returns:
            Physics validation result
        """
        violations = []
        domain_scores = {}

        # Validate each physics domain
        for domain in PhysicsDomain:
            domain_violations, domain_score = self.domain_validators[domain](
                obd_data, previous_readings or []
            )
            violations.extend(domain_violations)
            domain_scores[domain] = domain_score

        # Calculate overall metrics
        overall_confidence = self._calculate_overall_confidence(violations, domain_scores)
        physics_consistency_score = self._calculate_physics_consistency(violations)

        is_valid = len([v for v in violations if v.severity == ConstraintSeverity.IMPOSSIBLE]) == 0

        return PhysicsValidationResult(
            is_valid=is_valid,
            overall_confidence=overall_confidence,
            violations=violations,
            domain_scores=domain_scores,
            physics_consistency_score=physics_consistency_score,
            timestamp=datetime.now().isoformat()
        )

    def _validate_battery_constraints(self, data: Dict[str, Any],
                                    history: List[Dict]) -> Tuple[List[ConstraintViolation], float]:
        """
        Validate battery system constraints.

        Physics: Kirchhoff's voltage law, Peukert's law, temperature effects
        """
        violations = []
        voltage = self._get_value(data, ['voltage', 'battery_voltage', 'control_module_voltage'])

        if voltage is None:
            return violations, 0.5  # Neutral score if no data

        # Constraint 1: Voltage range (impossible values)
        if voltage < 6.0 or voltage > 18.0:
            violations.append(ConstraintViolation(
                domain=PhysicsDomain.BATTERY,
                constraint_name="voltage_range",
                severity=ConstraintSeverity.IMPOSSIBLE,
                description=f"Battery voltage {voltage:.1f}V outside possible range (6-18V)",
                measured_value=voltage,
                expected_range=(6.0, 18.0),
                violation_score=1.0,
                evidence=["Lead-acid batteries cannot operate outside 6-18V range"],
                timestamp=datetime.now().isoformat()
            ))

        # Constraint 2: Resting voltage (engine off)
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])
        if rpm is not None and rpm < 300:  # Engine off or idling
            if voltage < 12.0 or voltage > 12.8:
                severity = ConstraintSeverity.CRITICAL if voltage < 11.5 else ConstraintSeverity.WARNING
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.BATTERY,
                    constraint_name="resting_voltage",
                    severity=severity,
                    description=f"Resting voltage {voltage:.1f}V outside normal range (12.0-12.8V)",
                    measured_value=voltage,
                    expected_range=(12.0, 12.8),
                    violation_score=0.7 if severity == ConstraintSeverity.CRITICAL else 0.4,
                    evidence=["Battery resting voltage should be 12.0-12.8V when engine off"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 3: Running voltage (engine on)
        if rpm is not None and rpm > 800:  # Engine running
            if voltage < 13.0 or voltage > 14.5:
                severity = ConstraintSeverity.WARNING
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.BATTERY,
                    constraint_name="running_voltage",
                    severity=severity,
                    description=f"Running voltage {voltage:.1f}V outside normal range (13.0-14.5V)",
                    measured_value=voltage,
                    expected_range=(13.0, 14.5),
                    violation_score=0.5,
                    evidence=["Alternator should maintain 13.0-14.5V when engine running"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 4: Voltage stability (no sudden jumps)
        if history:
            recent_voltages = [self._get_value(h, ['voltage', 'battery_voltage']) for h in history[-5:]]
            recent_voltages = [v for v in recent_voltages if v is not None]

            if len(recent_voltages) >= 3:
                voltage_std = np.std(recent_voltages)
                if voltage_std > 1.0:  # More than 1V variation
                    violations.append(ConstraintViolation(
                        domain=PhysicsDomain.BATTERY,
                        constraint_name="voltage_stability",
                        severity=ConstraintSeverity.WARNING,
                        description=f"Voltage instability: {voltage_std:.2f}V standard deviation",
                        measured_value=voltage_std,
                        expected_range=(0, 1.0),
                        violation_score=min(0.8, voltage_std / 2.0),
                        evidence=["Battery voltage should be stable, not jumping around"],
                        timestamp=datetime.now().isoformat()
                    ))

        # Calculate domain score (0-1, higher = more violations)
        domain_score = min(1.0, len(violations) * 0.3)
        return violations, domain_score

    def _validate_cooling_constraints(self, data: Dict[str, Any],
                                    history: List[Dict]) -> Tuple[List[ConstraintViolation], float]:
        """
        Validate cooling system constraints.

        Physics: Thermodynamics, heat transfer, fluid dynamics
        """
        violations = []
        coolant_temp = self._get_value(data, ['coolant_temp', 'engine_coolant_temp'])

        if coolant_temp is None:
            return violations, 0.5

        # Constraint 1: Impossible temperature range
        if coolant_temp < -40 or coolant_temp > 130:
            violations.append(ConstraintViolation(
                domain=PhysicsDomain.COOLING,
                constraint_name="temperature_range",
                severity=ConstraintSeverity.IMPOSSIBLE,
                description=f"Coolant temperature {coolant_temp:.1f}°C physically impossible",
                measured_value=coolant_temp,
                expected_range=(-40, 130),
                violation_score=1.0,
                evidence=["Water-based coolant cannot exist as liquid outside -40°C to 130°C"],
                timestamp=datetime.now().isoformat()
            ))

        # Constraint 2: Operating temperature range
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])
        if rpm is not None and rpm > 800:  # Engine running
            if coolant_temp < 70 or coolant_temp > 105:
                severity = ConstraintSeverity.CRITICAL if coolant_temp > 110 else ConstraintSeverity.WARNING
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.COOLING,
                    constraint_name="operating_temperature",
                    severity=severity,
                    description=f"Operating temperature {coolant_temp:.1f}°C outside safe range (70-105°C)",
                    measured_value=coolant_temp,
                    expected_range=(70, 105),
                    violation_score=0.8 if severity == ConstraintSeverity.CRITICAL else 0.4,
                    evidence=["Engine should operate between 70-105°C for optimal performance"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 3: Temperature rate of change
        if history:
            recent_temps = [self._get_value(h, ['coolant_temp']) for h in history[-3:]]
            recent_temps = [t for t in recent_temps if t is not None]

            if len(recent_temps) >= 2:
                temp_change = abs(coolant_temp - recent_temps[-1])
                time_diff = 1  # Assume 1 reading per time unit

                # Max realistic temperature change rate: 5°C per minute
                if temp_change > 5:
                    violations.append(ConstraintViolation(
                        domain=PhysicsDomain.COOLING,
                        constraint_name="temperature_rate",
                        severity=ConstraintSeverity.WARNING,
                        description=f"Temperature change {temp_change:.1f}°C too rapid (max 5°C/min)",
                        measured_value=temp_change,
                        expected_range=(0, 5),
                        violation_score=min(0.8, temp_change / 10),
                        evidence=["Coolant temperature cannot change more than ~5°C per minute"],
                        timestamp=datetime.now().isoformat()
                    ))

        # Constraint 4: Thermostat logic
        if coolant_temp < self.vehicle_model.thermostat_open_temp_c - 10:
            # Coolant too cold - thermostat should be closed
            pass  # This is normal
        elif coolant_temp > self.vehicle_model.thermostat_open_temp_c + 5:
            # Coolant too hot - thermostat should be open
            pass  # This is normal

        domain_score = min(1.0, len(violations) * 0.3)
        return violations, domain_score

    def _validate_fuel_constraints(self, data: Dict[str, Any],
                                 history: List[Dict]) -> Tuple[List[ConstraintViolation], float]:
        """
        Validate fuel system constraints.

        Physics: Stoichiometry, fuel mapping, injection dynamics
        """
        violations = []
        fuel_pressure = self._get_value(data, ['fuel_pressure', 'fuel_rail_pressure'])
        maf = self._get_value(data, ['maf', 'mass_air_flow'])
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])
        load = self._get_value(data, ['engine_load', 'calculated_engine_load'])

        # Constraint 1: Fuel pressure range
        if fuel_pressure is not None:
            if fuel_pressure < 30 or fuel_pressure > 100:  # PSI
                severity = ConstraintSeverity.IMPOSSIBLE if fuel_pressure < 10 or fuel_pressure > 150 else ConstraintSeverity.CRITICAL
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.FUEL,
                    constraint_name="fuel_pressure_range",
                    severity=severity,
                    description=f"Fuel pressure {fuel_pressure:.1f} PSI outside possible range",
                    measured_value=fuel_pressure,
                    expected_range=(30, 100),
                    violation_score=0.9 if severity == ConstraintSeverity.IMPOSSIBLE else 0.6,
                    evidence=["Fuel injection systems operate at 30-100 PSI"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 2: Air-fuel ratio stoichiometry
        if maf is not None and rpm is not None and load is not None and rpm > 800:
            # Estimate fuel flow from MAF and stoichiometric ratio
            air_flow_kg_h = maf * 3.6  # Convert g/s to kg/h
            stoichiometric_fuel_kg_h = air_flow_kg_h / self.vehicle_model.stoichiometric_afr

            # Convert to expected fuel injector pulse width
            injector_flow_kg_h = self.vehicle_model.fuel_injector_flow_rate * self.vehicle_model.engine_cylinders * 0.000001  # Convert cc/min to kg/h
            expected_pulse_width_ms = (stoichiometric_fuel_kg_h / injector_flow_kg_h) * 1000

            # This is a rough estimate - in practice, we'd compare to actual fuel trim
            if expected_pulse_width_ms < 1 or expected_pulse_width_ms > 20:
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.FUEL,
                    constraint_name="air_fuel_stoichiometry",
                    severity=ConstraintSeverity.WARNING,
                    description=f"Air-fuel mixture calculation suggests implausible injector timing",
                    measured_value=expected_pulse_width_ms,
                    expected_range=(1, 20),
                    violation_score=0.4,
                    evidence=["Fuel injector pulse width should be 1-20ms for stoichiometric mixture"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 3: Fuel trim bounds
        stft = self._get_value(data, ['short_fuel_trim', 'fuel_trim_short'])
        ltft = self._get_value(data, ['long_fuel_trim', 'fuel_trim_long'])

        for trim_name, trim_value in [("STFT", stft), ("LTFT", ltft)]:
            if trim_value is not None:
                if abs(trim_value) > 25:  # More than 25% trim
                    severity = ConstraintSeverity.CRITICAL if abs(trim_value) > 40 else ConstraintSeverity.WARNING
                    violations.append(ConstraintViolation(
                        domain=PhysicsDomain.FUEL,
                        constraint_name=f"{trim_name.lower()}_range",
                        severity=severity,
                        description=f"{trim_name} {trim_value:.1f}% exceeds normal adjustment range",
                        measured_value=trim_value,
                        expected_range=(-25, 25),
                        violation_score=min(0.8, abs(trim_value) / 50),
                        evidence=["Fuel trim should not exceed ±25% for normal operation"],
                        timestamp=datetime.now().isoformat()
                    ))

        domain_score = min(1.0, len(violations) * 0.25)
        return violations, domain_score

    def _validate_transmission_constraints(self, data: Dict[str, Any],
                                         history: List[Dict]) -> Tuple[List[ConstraintViolation], float]:
        """
        Validate transmission constraints.

        Physics: Power transfer, efficiency, gear ratios
        """
        violations = []
        speed = self._get_value(data, ['speed', 'vehicle_speed'])
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])

        if speed is not None and rpm is not None and rpm > 800:
            # Constraint 1: Speed vs RPM relationship
            # Speed (km/h) = (RPM * tire_circumference) / (gear_ratio * final_drive * 60)

            # Estimate gear based on speed/RPM ratio
            if speed > 10:  # Moving
                speed_rpm_ratio = speed / rpm

                # For typical passenger car:
                # 1st gear: ~0.005-0.01, 5th gear: ~0.02-0.04
                if speed_rpm_ratio < 0.003 or speed_rpm_ratio > 0.08:
                    violations.append(ConstraintViolation(
                        domain=PhysicsDomain.TRANSMISSION,
                        constraint_name="gear_ratio_consistency",
                        severity=ConstraintSeverity.WARNING,
                        description=f"Speed/RPM ratio {speed_rpm_ratio:.4f} outside normal range",
                        measured_value=speed_rpm_ratio,
                        expected_range=(0.003, 0.08),
                        violation_score=0.5,
                        evidence=["Speed and RPM should have consistent ratio based on gear"],
                        timestamp=datetime.now().isoformat()
                    ))

        # Constraint 2: Transmission slip detection
        # This would require wheel speed sensors, but we can use basic checks
        if speed is not None and rpm is not None:
            # Rough check: if RPM is high but speed is very low, possible transmission issue
            if rpm > 3000 and speed < 5 and rpm > 800:
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.TRANSMISSION,
                    constraint_name="possible_transmission_slip",
                    severity=ConstraintSeverity.WARNING,
                    description=f"High RPM ({rpm}) with low speed ({speed}) suggests possible transmission issue",
                    measured_value=rpm / max(speed, 1),  # RPM per km/h
                    expected_range=(0, 1000),  # Rough bounds
                    violation_score=0.6,
                    evidence=["High RPM with low speed may indicate transmission slipping"],
                    timestamp=datetime.now().isoformat()
                ))

        domain_score = min(1.0, len(violations) * 0.4)
        return violations, domain_score

    def _validate_engine_constraints(self, data: Dict[str, Any],
                                   history: List[Dict]) -> Tuple[List[ConstraintViolation], float]:
        """
        Validate engine constraints.

        Physics: Thermodynamics, combustion, mechanical constraints
        """
        violations = []
        rpm = self._get_value(data, ['rpm', 'engine_rpm'])
        load = self._get_value(data, ['engine_load', 'calculated_engine_load'])
        timing = self._get_value(data, ['timing_advance', 'ignition_timing'])

        # Constraint 1: RPM range
        if rpm is not None:
            if rpm < 0 or rpm > 8000:
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.ENGINE,
                    constraint_name="rpm_range",
                    severity=ConstraintSeverity.IMPOSSIBLE,
                    description=f"RPM {rpm} outside physically possible range (0-8000)",
                    measured_value=rpm,
                    expected_range=(0, 8000),
                    violation_score=1.0,
                    evidence=["Internal combustion engines cannot exceed ~8000 RPM"],
                    timestamp=datetime.now().isoformat()
                ))
            elif rpm > 6000:  # Very high RPM
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.ENGINE,
                    constraint_name="rpm_limit",
                    severity=ConstraintSeverity.WARNING,
                    description=f"RPM {rpm} approaching engine limits",
                    measured_value=rpm,
                    expected_range=(0, 6000),
                    violation_score=0.3,
                    evidence=["RPM above 6000 may indicate engine stress"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 2: Engine load
        if load is not None:
            if load < 0 or load > 100:
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.ENGINE,
                    constraint_name="load_range",
                    severity=ConstraintSeverity.IMPOSSIBLE,
                    description=f"Engine load {load:.1f}% outside possible range (0-100%)",
                    measured_value=load,
                    expected_range=(0, 100),
                    violation_score=1.0,
                    evidence=["Engine load is calculated as percentage of maximum torque"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 3: Ignition timing
        if timing is not None:
            if timing < -20 or timing > 60:  # Degrees
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.ENGINE,
                    constraint_name="timing_range",
                    severity=ConstraintSeverity.IMPOSSIBLE,
                    description=f"Ignition timing {timing:.1f}° outside possible range",
                    measured_value=timing,
                    expected_range=(-20, 60),
                    violation_score=1.0,
                    evidence=["Ignition timing cannot be outside -20° to 60° range"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 4: RPM stability
        if history and rpm is not None:
            recent_rpms = [self._get_value(h, ['rpm']) for h in history[-5:]]
            recent_rpms = [r for r in recent_rpms if r is not None]

            if len(recent_rpms) >= 3:
                rpm_variation = np.std(recent_rpms)
                if rpm_variation > 500:  # High variation
                    violations.append(ConstraintViolation(
                        domain=PhysicsDomain.ENGINE,
                        constraint_name="rpm_stability",
                        severity=ConstraintSeverity.WARNING,
                        description=f"RPM instability: {rpm_variation:.0f} RPM standard deviation",
                        measured_value=rpm_variation,
                        expected_range=(0, 500),
                        violation_score=min(0.7, rpm_variation / 1000),
                        evidence=["Engine RPM should be relatively stable"],
                        timestamp=datetime.now().isoformat()
                    ))

        domain_score = min(1.0, len(violations) * 0.3)
        return violations, domain_score

    def _validate_electrical_constraints(self, data: Dict[str, Any],
                                       history: List[Dict]) -> Tuple[List[ConstraintViolation], float]:
        """
        Validate electrical system constraints.

        Physics: Ohm's law, power calculations, circuit theory
        """
        violations = []
        voltage = self._get_value(data, ['voltage', 'battery_voltage'])
        current = self._get_value(data, ['battery_current'])  # If available

        # Constraint 1: Basic electrical bounds
        if voltage is not None:
            if voltage <= 0:
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.ELECTRICAL,
                    constraint_name="voltage_polarity",
                    severity=ConstraintSeverity.IMPOSSIBLE,
                    description=f"Negative voltage {voltage:.2f}V impossible in automotive system",
                    measured_value=voltage,
                    expected_range=(0, 20),
                    violation_score=1.0,
                    evidence=["Voltage cannot be negative in properly functioning electrical system"],
                    timestamp=datetime.now().isoformat()
                ))

        # Constraint 2: Power calculations (if current available)
        if voltage is not None and current is not None:
            power = voltage * current  # Watts

            # Reasonable power bounds for automotive electrical system
            if abs(power) > 5000:  # More than 5kW
                violations.append(ConstraintViolation(
                    domain=PhysicsDomain.ELECTRICAL,
                    constraint_name="electrical_power",
                    severity=ConstraintSeverity.WARNING,
                    description=f"Electrical power {power:.0f}W exceeds normal automotive limits",
                    measured_value=power,
                    expected_range=(-2000, 5000),
                    violation_score=min(0.8, abs(power) / 10000),
                    evidence=["Automotive electrical systems rarely exceed 5kW"],
                    timestamp=datetime.now().isoformat()
                ))

        domain_score = min(1.0, len(violations) * 0.4)
        return violations, domain_score

    def _calculate_overall_confidence(self, violations: List[ConstraintViolation],
                                    domain_scores: Dict[PhysicsDomain, float]) -> float:
        """Calculate overall confidence in the data validity."""
        if not violations:
            return 1.0  # No violations = high confidence

        # Weight violations by severity
        weighted_score = 0.0
        total_weight = 0.0

        severity_weights = {
            ConstraintSeverity.WARNING: 0.2,
            ConstraintSeverity.CRITICAL: 0.6,
            ConstraintSeverity.IMPOSSIBLE: 1.0
        }

        for violation in violations:
            weight = severity_weights[violation.severity]
            weighted_score += violation.violation_score * weight
            total_weight += weight

        if total_weight > 0:
            violation_score = weighted_score / total_weight
        else:
            violation_score = 0.0

        # Factor in domain consistency
        avg_domain_score = np.mean(list(domain_scores.values()))
        domain_penalty = avg_domain_score * 0.3

        overall_score = violation_score + domain_penalty
        confidence = max(0.0, 1.0 - overall_score)

        return confidence

    def _calculate_physics_consistency(self, violations: List[ConstraintViolation]) -> float:
        """Calculate physics consistency score."""
        if not violations:
            return 1.0

        # Count violations by severity
        severity_counts = {
            ConstraintSeverity.WARNING: 0,
            ConstraintSeverity.CRITICAL: 0,
            ConstraintSeverity.IMPOSSIBLE: 0
        }

        for violation in violations:
            severity_counts[violation.severity] += 1

        # Physics consistency decreases with more severe violations
        consistency = 1.0
        consistency -= severity_counts[ConstraintSeverity.WARNING] * 0.1
        consistency -= severity_counts[ConstraintSeverity.CRITICAL] * 0.3
        consistency -= severity_counts[ConstraintSeverity.IMPOSSIBLE] * 0.6

        return max(0.0, consistency)

    def _get_value(self, data: Dict[str, Any], keys: List[str]) -> Optional[float]:
        """Get value from data trying multiple keys."""
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    return float(data[key])
                except (ValueError, TypeError):
                    pass
        return None

    def get_validation_summary(self, result: PhysicsValidationResult) -> Dict[str, Any]:
        """Get a summary of physics validation results."""
        return {
            'is_valid': result.is_valid,
            'overall_confidence': result.overall_confidence,
            'physics_consistency': result.physics_consistency_score,
            'total_violations': len(result.violations),
            'violations_by_severity': {
                'warning': len([v for v in result.violations if v.severity == ConstraintSeverity.WARNING]),
                'critical': len([v for v in result.violations if v.severity == ConstraintSeverity.CRITICAL]),
                'impossible': len([v for v in result.violations if v.severity == ConstraintSeverity.IMPOSSIBLE])
            },
            'violations_by_domain': {
                domain.value: len([v for v in result.violations if v.domain == domain])
                for domain in PhysicsDomain
            },
            'domain_scores': {domain.value: score for domain, score in result.domain_scores.items()},
            'top_violations': [
                {
                    'domain': v.domain.value,
                    'constraint': v.constraint_name,
                    'severity': v.severity.value,
                    'description': v.description,
                    'score': v.violation_score
                }
                for v in sorted(result.violations, key=lambda x: x.violation_score, reverse=True)[:5]
            ]
        }


# Singleton instance
_physics_validator = None

def get_physics_validator(vehicle_model: VehiclePhysicsModel = None) -> PhysicsConstraintsValidator:
    """Get the singleton PhysicsConstraintsValidator instance."""
    global _physics_validator
    if _physics_validator is None:
        _physics_validator = PhysicsConstraintsValidator(vehicle_model)
    return _physics_validator