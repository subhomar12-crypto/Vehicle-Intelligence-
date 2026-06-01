"""
Multi-Signal Pattern Matcher (Layer B)

Detects compound failure signatures by matching multiple sensor signals
simultaneously. Each pattern represents a known failure mode that becomes
visible only when multiple sensors tell a consistent story.

Patterns are evidence-based: each detection records which specific readings
triggered it and why.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class DetectedPattern:
    name: str
    display_name: str
    confidence: float          # 0.0-1.0
    affected_components: Dict[str, int]   # component -> health_delta (negative = penalty)
    evidence: List[Dict[str, Any]]        # which readings triggered this
    reasoning: str
    recommendation: str
    what_if_ignored: str
    severity: str              # "info", "warning", "critical"


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------
# Each pattern has:
#   "signals"     — required triggers (all must match for base confidence)
#   "boosts"      — optional conditions that increase confidence
#   "affects"     — component -> health penalty (-int)
#   "reasoning"   — human-readable explanation
#   "recommendation" — what to do
#   "what_if_ignored" — consequence of ignoring
#   "display_name"  — friendly name
#   "severity"      — info / warning / critical
# ---------------------------------------------------------------------------

FAILURE_PATTERNS = {
    "thermostat_stuck_closed": {
        "display_name": "Thermostat Stuck Closed",
        "signals": {
            "coolant_temp": (">", 108),
            "speed": (">", 60),
            "engine_load": ("<", 50),
        },
        "boosts": {
            "ambient_temp": ("<", 35),  # More suspicious in cool weather
        },
        "affects": {"coolant": -30, "thermostat": -50, "engine": -15},
        "reasoning": "Coolant overheating despite highway airflow and low load suggests thermostat stuck closed, preventing coolant from reaching radiator",
        "recommendation": "Replace thermostat. Stop driving until engine cools — sustained overheating causes head gasket failure.",
        "what_if_ignored": "Head gasket failure, warped cylinder head, engine seizure — $3,000-$8,000 repair",
        "severity": "critical",
    },
    "alternator_failing_under_heat": {
        "display_name": "Alternator Failing Under Heat",
        "signals": {
            "battery_voltage": ("<", 12.8),
            "rpm": (">", 800),
            "engine_load": (">", 40),
        },
        "boosts": {
            "ambient_temp": (">", 40),  # Heat accelerates alternator failure
        },
        "affects": {"battery": -25, "alternator": -40},
        "reasoning": "Battery not maintaining charge while engine running at load — alternator output is insufficient, common in Gulf heat",
        "recommendation": "Test alternator output (should be 13.8-14.8V at idle). Replace alternator if below 13.5V.",
        "what_if_ignored": "Vehicle strands you when battery depletes — typically within 1-2 hours of driving",
        "severity": "warning",
    },
    "transmission_slip": {
        "display_name": "Transmission Slipping",
        "signals": {
            "speed_rpm_ratio": ("<", 0.7),  # Special: computed ratio
        },
        "boosts": {},
        "affects": {"transmission_fluid": -45},
        "reasoning": "Speed-to-RPM ratio is abnormally low — transmission is not efficiently transferring engine power to wheels",
        "recommendation": "Check transmission fluid level and condition. Book a transmission service.",
        "what_if_ignored": "Progressive transmission damage leading to full failure — $2,000-$5,000 rebuild",
        "severity": "warning",
    },
    "compound_heat_stress": {
        "display_name": "Compound Heat Stress",
        "signals": {
            "ambient_temp": (">", 42),
            "coolant_temp": (">", 98),
            "battery_voltage": ("<", 13.0),
            "speed": ("<", 20),
        },
        "boosts": {},
        "affects": {"battery": -15, "coolant": -15, "alternator": -10, "engine": -10},
        "reasoning": "Multiple systems simultaneously stressed in extreme heat conditions — coolant high, battery weak, slow speed reducing airflow",
        "recommendation": "Reduce AC load if possible. Check coolant level. Park in shade. Service battery.",
        "what_if_ignored": "Simultaneous failure of cooling and electrical systems — expensive cascade failure",
        "severity": "critical",
    },
    "catalytic_converter_degradation": {
        "display_name": "Catalyst Degradation",
        "signals": {
            "long_term_fuel_trim": (">", 10),
        },
        "boosts": {
            "short_term_fuel_trim": (">", 8),
        },
        "affects": {"catalytic_converter": -35, "o2_sensor": -15},
        "reasoning": "High long-term fuel trim corrections suggest catalyst is not processing exhaust efficiently, forcing ECU to compensate",
        "recommendation": "Inspect catalytic converter. Check for P0420/P0430 codes. O2 sensor test.",
        "what_if_ignored": "Emissions test failure, reduced performance, eventual engine management issues",
        "severity": "warning",
    },
    "lean_running_vacuum_leak": {
        "display_name": "Vacuum Leak / MAF Issue",
        "signals": {
            "short_term_fuel_trim": (">", 15),
        },
        "boosts": {
            "long_term_fuel_trim": (">", 10),
            "engine_load": ("<", 30),
        },
        "affects": {"engine": -20, "maf_sensor": -15, "fuel_pump": -10},
        "reasoning": "High positive fuel trim corrections mean ECU is adding extra fuel to compensate for unmetered air — vacuum leak or dirty/failing MAF sensor",
        "recommendation": "Clean MAF sensor. Inspect vacuum lines and intake hoses for cracks. Check intake manifold gaskets.",
        "what_if_ignored": "Worsening misfires, catalyst damage from unburnt fuel, eventual ECU fault codes",
        "severity": "warning",
    },
    "spark_plug_degradation": {
        "display_name": "Spark Plug Wear",
        "signals": {
            "long_term_fuel_trim": (">", 5),
            "engine_load": (">", 60),
        },
        "boosts": {
            "short_term_fuel_trim": (">", 5),
            "rpm": (">", 2500),
        },
        "affects": {"spark_plugs": -40, "engine": -15, "catalytic_converter": -10},
        "reasoning": "Fuel trim adjustments combined with high load suggest incomplete combustion — worn spark plugs causing misfires under load",
        "recommendation": "Check spark plug condition (interval typically 60,000-100,000km). Replace if worn.",
        "what_if_ignored": "Unburnt fuel enters catalyst causing overheating damage. Increasing fuel consumption.",
        "severity": "warning",
    },
}


class PatternMatcher:
    """
    Matches current telemetry against known multi-signal failure patterns.

    Usage:
        matcher = PatternMatcher()
        patterns = matcher.match(telemetry, context, history)
        for p in patterns:
            print(p.display_name, p.confidence, p.reasoning)
    """

    def __init__(self, accuracy_weights: Optional[Dict[str, float]] = None):
        # Pattern name → weight multiplier from accuracy tracking
        # >1.0 = reward accurate patterns, <1.0 = penalize inaccurate ones
        self._accuracy_weights = accuracy_weights or {}

    def match(
        self,
        telemetry: Dict[str, float],
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict]] = None,
    ) -> List[DetectedPattern]:
        """
        Run all patterns against current data. Return list of matched patterns.

        Args:
            telemetry: Current sensor readings {sensor_name: value}
            context:   Driving context (ambient_temp, speed, etc.)
                       Merges with telemetry if not separately provided.
            history:   Optional list of recent readings for oscillation/trend checks.
        """
        if context is None:
            context = {}

        # Merge telemetry into context for signal evaluation
        merged = dict(telemetry)
        merged.update(context)

        # Compute derived signals
        derived = self._compute_derived(telemetry)
        merged.update(derived)

        detected = []
        for pattern_id, pattern_def in FAILURE_PATTERNS.items():
            result = self._evaluate_pattern(pattern_id, pattern_def, merged)
            if result is not None:
                detected.append(result)

        # Sort by confidence descending
        detected.sort(key=lambda p: p.confidence, reverse=True)
        return detected

    # -----------------------------------------------------------------------
    # Internals
    # -----------------------------------------------------------------------

    def _compute_derived(self, telemetry: Dict[str, float]) -> Dict[str, float]:
        """Compute derived signals from raw telemetry."""
        derived = {}

        rpm = telemetry.get("rpm", 0.0)
        speed = telemetry.get("speed", 0.0)

        # Speed-RPM ratio: at highway speeds with good transmission,
        # speed/rpm should be roughly consistent. Low ratio = slipping.
        if rpm > 1000 and speed > 20:
            derived["speed_rpm_ratio"] = speed / (rpm / 1000.0)
        else:
            derived["speed_rpm_ratio"] = 1.0  # neutral/unknown

        return derived

    def _evaluate_pattern(
        self,
        pattern_id: str,
        pattern_def: Dict,
        merged: Dict[str, float],
    ) -> Optional[DetectedPattern]:
        """
        Evaluate a single pattern against merged telemetry+context.
        Returns DetectedPattern if matched, None otherwise.
        """
        signals = pattern_def.get("signals", {})
        boosts = pattern_def.get("boosts", {})

        evidence = []
        signals_met = 0
        signals_total = len(signals)

        for sensor, (op, threshold) in signals.items():
            value = merged.get(sensor)
            if value is None:
                # Missing sensor — partial match
                continue
            if self._check_condition(value, op, threshold):
                signals_met += 1
                evidence.append({
                    "sensor": sensor,
                    "observed": round(value, 2),
                    "threshold": f"{op} {threshold}",
                    "condition": f"{sensor} is {op} {threshold}",
                })

        # Need at least 75% of signals to match
        if signals_total == 0 or signals_met / signals_total < 0.75:
            return None

        # Base confidence from signal match ratio
        base_confidence = (signals_met / signals_total) * 0.7

        # Apply boosts for confirming conditions
        boost_confidence = 0.0
        for sensor, (op, threshold) in boosts.items():
            value = merged.get(sensor)
            if value is not None and self._check_condition(value, op, threshold):
                boost_confidence += 0.15
                evidence.append({
                    "sensor": sensor,
                    "observed": round(value, 2),
                    "threshold": f"{op} {threshold}",
                    "condition": f"Confirming: {sensor} is {op} {threshold}",
                })

        confidence = min(1.0, base_confidence + boost_confidence)

        # Apply accuracy-based weight adjustment
        accuracy_weight = self._accuracy_weights.get(pattern_id, 1.0)
        confidence = min(1.0, confidence * accuracy_weight)

        # Minimum confidence threshold
        if confidence < 0.4:
            return None

        return DetectedPattern(
            name=pattern_id,
            display_name=pattern_def.get("display_name", pattern_id),
            confidence=round(confidence, 2),
            affected_components=pattern_def.get("affects", {}),
            evidence=evidence,
            reasoning=pattern_def.get("reasoning", ""),
            recommendation=pattern_def.get("recommendation", ""),
            what_if_ignored=pattern_def.get("what_if_ignored", ""),
            severity=pattern_def.get("severity", "warning"),
        )

    def _check_condition(self, value: float, op: str, threshold: float) -> bool:
        """Check if value satisfies the condition (op, threshold)."""
        if op == ">":
            return value > threshold
        elif op == ">=":
            return value >= threshold
        elif op == "<":
            return value < threshold
        elif op == "<=":
            return value <= threshold
        elif op == "==":
            return abs(value - threshold) < 0.01
        return False
