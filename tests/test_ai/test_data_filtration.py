"""Tests for the 3-stage data filtration pipeline."""
import pytest
from predict.core.ai.data_filtration import DataFiltrationPipeline, FilterResult


@pytest.fixture
def pipeline():
    return DataFiltrationPipeline()


def _reading(**overrides) -> dict:
    """Build a valid OBD reading with optional overrides."""
    base = {
        "rpm": 2500.0,
        "speed": 60.0,
        "coolant_temp": 90.0,
        "battery_voltage": 13.5,
        "engine_load": 45.0,
        "throttle_pos": 30.0,
        "maf_rate": 15.0,
        "intake_temp": 35.0,
    }
    base.update(overrides)
    return base


# ===== Stage 1: Physical bounds =====


def test_physical_bounds_rejects_negative_rpm(pipeline):
    """A reading with rpm=-100 must be rejected."""
    batch = [_reading(rpm=-100.0)]
    result = pipeline.filter(batch)
    assert len(result.clean_readings) == 0
    assert result.rejected_count == 1


def test_physical_bounds_accepts_valid_reading(pipeline):
    """A normal reading with all values in range must pass."""
    batch = [_reading()]
    result = pipeline.filter(batch)
    assert len(result.clean_readings) == 1
    assert result.rejected_count == 0


def test_physical_bounds_rejects_high_speed(pipeline):
    """Speed above 300 km/h must be rejected."""
    batch = [_reading(speed=350.0)]
    result = pipeline.filter(batch)
    assert len(result.clean_readings) == 0
    assert result.rejected_count == 1


def test_physical_bounds_accepts_edge_values(pipeline):
    """Values exactly at the boundary should pass."""
    batch = [_reading(rpm=0.0, speed=0.0, coolant_temp=-40.0, battery_voltage=20.0)]
    result = pipeline.filter(batch)
    assert len(result.clean_readings) == 1
    assert result.rejected_count == 0


# ===== Stage 2: Spike detection =====


def test_spike_detection_removes_rpm_jump(pipeline):
    """3 readings where middle one jumps 7200 RPM (above MAX_RATE 3000)."""
    batch = [
        _reading(rpm=800.0),
        _reading(rpm=8000.0),  # +7200 jump, exceeds MAX_RATE 3000
        _reading(rpm=850.0),
    ]
    result = pipeline.filter(batch)
    assert result.spike_count == 1
    # The first and third readings should survive
    assert len(result.clean_readings) == 2
    surviving_rpms = [r["rpm"] for r in result.clean_readings]
    assert 8000.0 not in surviving_rpms


def test_spike_detection_allows_gradual_increase(pipeline):
    """RPM rising 1000 per reading (under MAX_RATE 3000) should all pass."""
    batch = [
        _reading(rpm=1000.0),
        _reading(rpm=2000.0),
        _reading(rpm=3000.0),
    ]
    result = pipeline.filter(batch)
    assert result.spike_count == 0
    assert len(result.clean_readings) == 3


def test_spike_detection_coolant_jump(pipeline):
    """Coolant jumping 10 degrees between readings (above MAX_RATE 2.0) is a spike."""
    batch = [
        _reading(coolant_temp=85.0),
        _reading(coolant_temp=95.0),  # +10, exceeds MAX_RATE 2.0
        _reading(coolant_temp=86.0),
    ]
    result = pipeline.filter(batch)
    assert result.spike_count == 1
    assert len(result.clean_readings) == 2


# ===== Stage 3: Consistency check =====


def test_consistency_check_flags_cold_engine_high_speed(pipeline):
    """Speed=120 with RPM=0 is physically impossible."""
    batch = [_reading(speed=120.0, rpm=0.0)]
    result = pipeline.filter(batch)
    assert result.inconsistent_count == 1
    assert len(result.clean_readings) == 0


def test_consistency_allows_parked_with_engine_off(pipeline):
    """Speed=0 with RPM=0 is perfectly valid (parked, engine off)."""
    batch = [_reading(speed=0.0, rpm=0.0)]
    result = pipeline.filter(batch)
    assert result.inconsistent_count == 0
    assert len(result.clean_readings) == 1


def test_consistency_allows_idle(pipeline):
    """Speed=0 with RPM=800 is a normal idle."""
    batch = [_reading(speed=0.0, rpm=800.0)]
    result = pipeline.filter(batch)
    assert result.inconsistent_count == 0
    assert len(result.clean_readings) == 1


# ===== Edge cases =====


def test_empty_batch_returns_empty(pipeline):
    """Empty input returns empty output with zero counts."""
    result = pipeline.filter([])
    assert len(result.clean_readings) == 0
    assert result.rejected_count == 0
    assert result.spike_count == 0
    assert result.inconsistent_count == 0
    assert result.total_input == 0


def test_filter_result_total_input(pipeline):
    """total_input reflects the original batch size."""
    batch = [_reading(), _reading(rpm=-50.0), _reading()]
    result = pipeline.filter(batch)
    assert result.total_input == 3


def test_readings_missing_sensor_not_rejected(pipeline):
    """Readings that lack a sensor key should not be rejected for that sensor."""
    batch = [{"rpm": 2000.0, "speed": 60.0}]  # no coolant_temp etc.
    result = pipeline.filter(batch)
    assert len(result.clean_readings) == 1
    assert result.rejected_count == 0


def test_pipeline_stages_run_in_order(pipeline):
    """A reading that would fail bounds AND consistency only counts as bounds rejection."""
    # rpm=-100 (fails bounds) AND speed=120 with rpm=-100 (would fail consistency)
    # But bounds check should reject it first, so inconsistent_count stays 0
    batch = [_reading(rpm=-100.0, speed=120.0)]
    result = pipeline.filter(batch)
    assert result.rejected_count == 1
    assert result.inconsistent_count == 0
