"""Tests for the Multi-Signal Pattern Matcher."""
import pytest
from predict.core.ai.pattern_matcher import PatternMatcher, DetectedPattern


@pytest.fixture
def matcher():
    return PatternMatcher()


def _names(patterns):
    return [p.name for p in patterns]


# ===== Alternator failing pattern =====

def test_alternator_pattern_matches(matcher):
    """Low voltage + high RPM + high load should trigger alternator pattern."""
    telemetry = {
        "battery_voltage": 12.4,    # < 12.8 ✓
        "rpm": 2000.0,              # > 800 ✓
        "engine_load": 60.0,        # > 40 ✓
        "ambient_temp": 44.0,       # > 40 — boost
        "coolant_temp": 90.0,
        "speed": 60.0,
    }
    patterns = matcher.match(telemetry)
    assert "alternator_failing_under_heat" in _names(patterns), (
        f"Expected alternator pattern, got: {_names(patterns)}"
    )
    alt = next(p for p in patterns if p.name == "alternator_failing_under_heat")
    assert alt.confidence > 0.5
    assert alt.severity in ("warning", "critical")


def test_alternator_no_match_good_voltage(matcher):
    """Good voltage should NOT trigger alternator pattern."""
    telemetry = {
        "battery_voltage": 14.2,
        "rpm": 2000.0,
        "engine_load": 60.0,
        "ambient_temp": 44.0,
    }
    patterns = matcher.match(telemetry)
    assert "alternator_failing_under_heat" not in _names(patterns)


# ===== Compound heat stress =====

def test_compound_heat_detected(matcher):
    """All heat stress signals should trigger compound heat pattern."""
    telemetry = {
        "ambient_temp": 47.0,       # > 42 ✓
        "coolant_temp": 105.0,      # > 98 ✓
        "battery_voltage": 12.5,    # < 13.0 ✓
        "speed": 5.0,               # < 20 ✓ (traffic jam)
        "rpm": 800.0,
        "engine_load": 50.0,
    }
    patterns = matcher.match(telemetry)
    assert "compound_heat_stress" in _names(patterns), (
        f"Expected compound_heat_stress, got: {_names(patterns)}"
    )
    heat = next(p for p in patterns if p.name == "compound_heat_stress")
    assert heat.confidence >= 0.6
    assert heat.severity == "critical"


def test_compound_heat_not_triggered_cool_weather(matcher):
    """Cool ambient with good stats should NOT trigger compound heat."""
    telemetry = {
        "ambient_temp": 22.0,       # < 42
        "coolant_temp": 88.0,
        "battery_voltage": 14.0,
        "speed": 60.0,
        "rpm": 2000.0,
        "engine_load": 45.0,
    }
    patterns = matcher.match(telemetry)
    assert "compound_heat_stress" not in _names(patterns)


# ===== Thermostat stuck closed =====

def test_thermostat_pattern_matches(matcher):
    """High coolant on highway with low load = thermostat stuck."""
    telemetry = {
        "coolant_temp": 115.0,   # > 108 ✓
        "speed": 90.0,           # > 60 ✓
        "engine_load": 35.0,     # < 50 ✓
        "ambient_temp": 28.0,    # < 35 — boost (even more suspicious in cool weather)
    }
    patterns = matcher.match(telemetry)
    assert "thermostat_stuck_closed" in _names(patterns), (
        f"Expected thermostat pattern, got: {_names(patterns)}"
    )


# ===== Vacuum leak pattern =====

def test_lean_running_vacuum_leak(matcher):
    """High STFT should trigger lean running / vacuum leak pattern."""
    telemetry = {
        "short_term_fuel_trim": 18.0,   # > 15 ✓
        "long_term_fuel_trim": 12.0,    # boost
        "engine_load": 20.0,            # < 30 — boost
        "rpm": 1000.0,
        "speed": 30.0,
        "coolant_temp": 88.0,
    }
    patterns = matcher.match(telemetry)
    assert "lean_running_vacuum_leak" in _names(patterns), (
        f"Expected lean_running pattern, got: {_names(patterns)}"
    )


# ===== No false positives on healthy data =====

def test_no_false_positive_on_normal_data(matcher):
    """All sensors healthy — zero patterns should be detected."""
    telemetry = {
        "rpm": 2000.0,
        "speed": 80.0,
        "coolant_temp": 89.0,
        "battery_voltage": 14.1,
        "engine_load": 45.0,
        "throttle_pos": 30.0,
        "fuel_level": 60.0,
        "short_term_fuel_trim": 2.5,
        "long_term_fuel_trim": -1.0,
        "intake_temp": 38.0,
        "ambient_temp": 35.0,
    }
    patterns = matcher.match(telemetry)
    assert len(patterns) == 0, (
        f"False positives on healthy data: {_names(patterns)}"
    )


# ===== Evidence is populated =====

def test_evidence_populated(matcher):
    """Each detected pattern should have evidence entries."""
    telemetry = {
        "battery_voltage": 12.3,
        "rpm": 1800.0,
        "engine_load": 55.0,
        "ambient_temp": 43.0,
    }
    patterns = matcher.match(telemetry)
    if patterns:
        for p in patterns:
            assert len(p.evidence) > 0, f"Pattern {p.name} has no evidence"
            for e in p.evidence:
                assert "sensor" in e
                assert "observed" in e


# ===== Recommendations are populated =====

def test_recommendation_populated(matcher):
    """All matched patterns should have non-empty recommendation and what_if_ignored."""
    telemetry = {
        "ambient_temp": 48.0,
        "coolant_temp": 106.0,
        "battery_voltage": 12.4,
        "speed": 8.0,
        "rpm": 700.0,
        "engine_load": 45.0,
    }
    patterns = matcher.match(telemetry)
    for p in patterns:
        assert p.recommendation, f"Pattern {p.name} missing recommendation"
        assert p.what_if_ignored, f"Pattern {p.name} missing what_if_ignored"
        assert p.reasoning, f"Pattern {p.name} missing reasoning"
