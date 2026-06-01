"""Tests for the Context-Aware Scoring Engine."""
import pytest
from predict.core.ai.context_scoring import ContextAwareScorer


@pytest.fixture
def scorer():
    return ContextAwareScorer()


# ===== Coolant temperature =====

def test_coolant_normal_in_qatar_heat(scorer):
    """102°C is normal when ambient is 47°C + low speed + high load."""
    score, explanation = scorer.score_sensor(
        "coolant_temp", 102,
        {"ambient_temp": 47, "speed": 10, "engine_load": 60}
    )
    assert score >= 80, f"Expected ≥80 for normal Qatar traffic temp, got {score}: {explanation}"


def test_coolant_critical_in_cool_weather(scorer):
    """102°C is concerning when ambient is 20°C + highway speed + low load."""
    score, explanation = scorer.score_sensor(
        "coolant_temp", 102,
        {"ambient_temp": 20, "speed": 80, "engine_load": 30}
    )
    assert score <= 50, f"Expected ≤50 for elevated temp in cool weather, got {score}: {explanation}"


def test_coolant_warming_up(scorer):
    """60°C is fine — engine is still warming up."""
    score, explanation = scorer.score_sensor(
        "coolant_temp", 60,
        {"ambient_temp": 25, "speed": 30, "engine_load": 20}
    )
    assert score >= 70, f"Expected ≥70 for warming engine, got {score}: {explanation}"


def test_coolant_critical_overheating(scorer):
    """120°C in any condition is critical."""
    score, explanation = scorer.score_sensor(
        "coolant_temp", 125,
        {"ambient_temp": 25, "speed": 60, "engine_load": 50}
    )
    assert score <= 35, f"Expected ≤35 for overheating, got {score}: {explanation}"


# ===== Battery voltage =====

def test_battery_normal_engine_running(scorer):
    """13.8V while engine running is perfect."""
    score, explanation = scorer.score_sensor(
        "battery_voltage", 13.8,
        {"rpm": 1500, "ambient_temp": 35}
    )
    assert score >= 90, f"Expected ≥90 for normal charging voltage, got {score}: {explanation}"


def test_battery_not_charging(scorer):
    """11.8V while engine running means alternator is failing."""
    score, explanation = scorer.score_sensor(
        "battery_voltage", 11.8,
        {"rpm": 2000, "ambient_temp": 35}
    )
    assert score <= 50, f"Expected ≤50 for no charging, got {score}: {explanation}"


def test_battery_engine_off_full(scorer):
    """12.6V with engine off is a healthy fully charged battery."""
    score, explanation = scorer.score_sensor(
        "battery_voltage", 12.6,
        {"rpm": 0, "ambient_temp": 25}
    )
    assert score >= 90, f"Expected ≥90 for full battery, got {score}: {explanation}"


def test_battery_engine_off_low(scorer):
    """11.5V with engine off is critically low."""
    score, explanation = scorer.score_sensor(
        "battery_voltage", 11.5,
        {"rpm": 0, "ambient_temp": 25}
    )
    assert score <= 20, f"Expected ≤20 for critical discharge, got {score}: {explanation}"


# ===== Oil temperature =====

def test_oil_temp_optimal(scorer):
    """100°C oil temp is optimal."""
    score, explanation = scorer.score_sensor(
        "oil_temp", 100,
        {"ambient_temp": 30, "engine_load": 50}
    )
    assert score >= 90, f"Expected ≥90 for optimal oil temp, got {score}: {explanation}"


def test_oil_temp_critical(scorer):
    """140°C oil temp is critical — oil is degrading."""
    score, explanation = scorer.score_sensor(
        "oil_temp", 140,
        {"ambient_temp": 45, "engine_load": 80}
    )
    assert score <= 15, f"Expected ≤15 for critical oil temp, got {score}: {explanation}"


# ===== Batch scoring =====

def test_score_all_returns_dict(scorer):
    """score_all should return a dict of sensor results."""
    telemetry = {
        "coolant_temp": 95.0,
        "battery_voltage": 14.0,
        "oil_temp": 105.0,
        "engine_load": 60.0,
        "rpm": 2000.0,
        "speed": 80.0,
        "ambient_temp": 35.0,
    }
    results = scorer.score_all(telemetry)
    assert isinstance(results, dict)
    assert "coolant_temp" in results
    assert "battery_voltage" in results
    for sensor, data in results.items():
        assert "score" in data
        assert "explanation" in data
        assert 0 <= data["score"] <= 100


def test_score_all_no_false_positives_normal_data(scorer):
    """All sensors in normal range should score ≥75."""
    telemetry = {
        "coolant_temp": 90.0,
        "battery_voltage": 14.1,
        "oil_temp": 100.0,
        "engine_load": 45.0,
        "rpm": 2000.0,
        "speed": 60.0,
        "ambient_temp": 35.0,
    }
    results = scorer.score_all(telemetry)
    for sensor, data in results.items():
        assert data["score"] >= 70, (
            f"False positive: {sensor} scored {data['score']} on normal data: {data['explanation']}"
        )
