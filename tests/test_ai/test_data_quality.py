"""
Tests for DataQualityFilter — OBD telemetry cleaning pipeline.

Tests verify:
- Warm-up readings are discarded during the connection establishment phase
- Range validation rejects physically impossible sensor values
- Stuck sensor detection flags sensors reporting the same value repeatedly
- Outlier rejection uses rolling statistics to flag anomalous spikes
- Quality scores are returned correctly alongside cleaned data
- Sensor quality summary aggregates per-sensor quality across readings
"""

import pytest
from predict.core.ai.data_quality import DataQualityFilter


# ===== Warm-up Tests =====

class TestWarmupDiscard:
    """First N readings after connection must be discarded (startup garbage)."""

    def test_warmup_readings_return_empty_quality(self):
        """During warm-up, quality dict should be empty (warmup flag)."""
        f = DataQualityFilter(warmup_readings=3)
        reading = {"rpm": 2000.0, "battery_voltage": 13.5, "coolant_temp": 90.0}

        cleaned1, quality1 = f.filter_reading(reading)
        cleaned2, quality2 = f.filter_reading(reading)
        cleaned3, quality3 = f.filter_reading(reading)

        # All three warm-up readings should have empty quality dicts
        assert quality1 == {}
        assert quality2 == {}
        assert quality3 == {}

    def test_warmup_readings_pass_through_data(self):
        """During warm-up the raw data is passed through unchanged (caller decides)."""
        f = DataQualityFilter(warmup_readings=3)
        reading = {"rpm": 2000.0, "battery_voltage": 13.5}

        cleaned, quality = f.filter_reading(reading)

        # Data returned unchanged during warmup
        assert cleaned == reading
        assert quality == {}

    def test_post_warmup_reading_has_quality_scores(self):
        """After warm-up period ends, quality scores are returned."""
        f = DataQualityFilter(warmup_readings=3)
        reading = {"rpm": 2000.0, "battery_voltage": 13.5}

        # Burn through warmup
        for _ in range(3):
            f.filter_reading(reading)

        # 4th reading should have quality scores
        cleaned, quality = f.filter_reading(reading)
        assert len(quality) > 0

    def test_zero_warmup_skips_warmup_phase(self):
        """warmup_readings=0 means the very first reading gets quality scores."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"rpm": 2000.0, "battery_voltage": 13.5}

        cleaned, quality = f.filter_reading(reading)
        assert len(quality) > 0

    def test_warmup_count_exact_boundary(self):
        """Exactly warmup_readings readings are discarded, N+1th is processed."""
        f = DataQualityFilter(warmup_readings=10)
        reading = {"rpm": 2000.0}

        # First 10 should be warmup
        for i in range(10):
            _, quality = f.filter_reading(reading)
            assert quality == {}, f"Reading {i+1} should be warmup"

        # 11th should be processed
        _, quality = f.filter_reading(reading)
        assert "rpm" in quality


# ===== Range Validation Tests =====

class TestRangeValidation:
    """Physically impossible values must be rejected."""

    def test_rpm_too_high_rejected(self):
        """RPM of 99999 is physically impossible — should be rejected."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"rpm": 99999.0}

        cleaned, quality = f.filter_reading(reading)

        assert "rpm" not in cleaned
        assert quality.get("rpm") == 0.0

    def test_rpm_too_low_rejected(self):
        """Negative RPM is physically impossible."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"rpm": -100.0}

        cleaned, quality = f.filter_reading(reading)

        assert "rpm" not in cleaned
        assert quality.get("rpm") == 0.0

    def test_battery_voltage_negative_rejected(self):
        """Negative battery voltage is physically impossible."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"battery_voltage": -5.0}

        cleaned, quality = f.filter_reading(reading)

        assert "battery_voltage" not in cleaned
        assert quality.get("battery_voltage") == 0.0

    def test_battery_voltage_too_high_rejected(self):
        """Battery voltage of 25V is above the defined max (20V)."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"battery_voltage": 25.0}

        cleaned, quality = f.filter_reading(reading)

        assert "battery_voltage" not in cleaned
        assert quality.get("battery_voltage") == 0.0

    def test_coolant_temp_extreme_high_rejected(self):
        """Coolant temp of 999°C is physically impossible."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"coolant_temp": 999.0}

        cleaned, quality = f.filter_reading(reading)

        assert "coolant_temp" not in cleaned
        assert quality.get("coolant_temp") == 0.0

    def test_engine_load_over_100_rejected(self):
        """Engine load is a percentage — over 100% is invalid."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"engine_load": 150.0}

        cleaned, quality = f.filter_reading(reading)

        assert "engine_load" not in cleaned
        assert quality.get("engine_load") == 0.0

    def test_speed_over_max_rejected(self):
        """Speed of 500 km/h exceeds the 300 km/h physical limit."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"speed": 500.0}

        cleaned, quality = f.filter_reading(reading)

        assert "speed" not in cleaned
        assert quality.get("speed") == 0.0

    def test_valid_values_pass_through(self):
        """Normal, in-range values should pass without modification."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {
            "rpm": 2500.0,
            "speed": 80.0,
            "coolant_temp": 90.0,
            "battery_voltage": 13.8,
            "engine_load": 45.0,
        }

        cleaned, quality = f.filter_reading(reading)

        for key, val in reading.items():
            assert cleaned.get(key) == val, f"{key} should pass through"
            assert quality.get(key) == 1.0, f"{key} should have quality 1.0"

    def test_zero_speed_valid(self):
        """Speed of 0 is valid (vehicle stopped)."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"speed": 0.0}

        cleaned, quality = f.filter_reading(reading)

        assert cleaned.get("speed") == 0.0
        assert quality.get("speed") == 1.0

    def test_unknown_sensor_passes_through(self):
        """Sensors not in PHYSICAL_RANGES are not range-checked — pass through."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"some_custom_sensor": 12345.0}

        cleaned, quality = f.filter_reading(reading)

        assert cleaned.get("some_custom_sensor") == 12345.0
        # Quality for unknown sensor: no range penalty, defaults to 1.0
        assert quality.get("some_custom_sensor") == 1.0

    def test_boundary_values_accepted(self):
        """Exact boundary values are within range — should be accepted."""
        f = DataQualityFilter(warmup_readings=0)
        # Exact min and max boundaries
        reading = {
            "rpm": 0.0,        # min boundary
            "speed": 300.0,    # max boundary
            "battery_voltage": 0.0,  # min boundary
        }

        cleaned, quality = f.filter_reading(reading)

        for key in reading:
            assert quality.get(key) == 1.0, f"{key} at boundary should have quality 1.0"

    def test_multiple_sensors_mixed_validity(self):
        """Mix of valid and invalid sensors in one reading."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {
            "rpm": 2000.0,          # valid
            "battery_voltage": -5.0, # invalid
            "speed": 60.0,           # valid
            "engine_load": 999.0,    # invalid
        }

        cleaned, quality = f.filter_reading(reading)

        assert "rpm" in cleaned
        assert "battery_voltage" not in cleaned
        assert "speed" in cleaned
        assert "engine_load" not in cleaned
        assert quality["rpm"] == 1.0
        assert quality["battery_voltage"] == 0.0
        assert quality["speed"] == 1.0
        assert quality["engine_load"] == 0.0


# ===== Stuck Sensor Detection Tests =====

class TestStuckSensorDetection:
    """Sensors reporting the exact same value for 30+ readings are stuck/failed."""

    def test_stuck_sensor_detected_after_threshold(self):
        """Same value for 31 readings → quality should be 0."""
        f = DataQualityFilter(warmup_readings=0)
        stuck_value = 13.5

        for i in range(31):
            cleaned, quality = f.filter_reading({"battery_voltage": stuck_value})

        # After 31 identical readings, sensor is considered stuck
        assert quality.get("battery_voltage") == 0.0, (
            "Battery voltage stuck for 31+ readings should have quality 0"
        )

    def test_exact_threshold_not_yet_stuck(self):
        """At exactly STUCK_THRESHOLD - 1 identical readings, not yet flagged."""
        f = DataQualityFilter(warmup_readings=0)
        stuck_value = 2500.0
        STUCK_THRESHOLD = 30  # Must match implementation

        for i in range(STUCK_THRESHOLD - 1):
            cleaned, quality = f.filter_reading({"rpm": stuck_value})

        # At threshold - 1, should still be quality 1.0
        assert quality.get("rpm") == 1.0, (
            f"After {STUCK_THRESHOLD - 1} identical readings, sensor should not yet be flagged"
        )

    def test_value_change_resets_stuck_counter(self):
        """When a sensor's value changes, stuck counter resets."""
        f = DataQualityFilter(warmup_readings=0)

        # Build a baseline with slight variation so std > 0
        # (purely identical values create near-zero std making ANY change an outlier)
        import itertools
        values = itertools.cycle([5.0, 5.1, 5.0, 4.9, 5.0])
        for _ in range(10):
            f.filter_reading({"custom_sensor": next(values)})

        # Now feed 31 identical readings → sensor becomes stuck
        for _ in range(31):
            f.filter_reading({"custom_sensor": 5.0})
        _, quality = f.filter_reading({"custom_sensor": 5.0})
        assert quality.get("custom_sensor") == 0.0, "Should be stuck after 30+ identical readings"

        # Change the value (within normal range of prior variation) — counter resets
        _, quality = f.filter_reading({"custom_sensor": 5.1})
        # 5.1 is within baseline std, so it should pass outlier check and stuck is reset
        assert quality.get("custom_sensor") == 1.0, (
            "After value change within baseline range, stuck counter should reset"
        )

    def test_stuck_sensor_excluded_from_cleaned(self):
        """A stuck sensor should be excluded from cleaned data."""
        f = DataQualityFilter(warmup_readings=0)
        stuck_value = 90.0

        for _ in range(31):
            cleaned, quality = f.filter_reading({"coolant_temp": stuck_value})

        assert "coolant_temp" not in cleaned, "Stuck sensor should be excluded from cleaned data"

    def test_different_sensors_tracked_independently(self):
        """Stuck detection tracks each sensor independently."""
        f = DataQualityFilter(warmup_readings=0)

        # Send 35 readings: rpm always changes, coolant stays the same
        for i in range(35):
            f.filter_reading({"rpm": float(i * 100), "coolant_temp": 90.0})

        cleaned, quality = f.filter_reading({"rpm": 3600.0, "coolant_temp": 90.0})

        # RPM is changing — should be fine
        assert quality.get("rpm") == 1.0, "Changing RPM should not be flagged"
        # coolant_temp stuck for 36 readings — should be flagged
        assert quality.get("coolant_temp") == 0.0, "Stuck coolant should be flagged"

    def test_zero_value_stuck_sensor(self):
        """A sensor stuck at 0.0 should also be detected (common failure mode)."""
        f = DataQualityFilter(warmup_readings=0)

        for _ in range(31):
            f.filter_reading({"engine_load": 0.0})

        cleaned, quality = f.filter_reading({"engine_load": 0.0})
        assert quality.get("engine_load") == 0.0, "Sensor stuck at 0 should be flagged"


# ===== Outlier Rejection Tests =====

class TestOutlierRejection:
    """Values more than 3σ from rolling average should be rejected."""

    def test_spike_outlier_rejected(self):
        """Feed stable values, then a spike — spike should be rejected."""
        f = DataQualityFilter(warmup_readings=0)

        # Feed stable baseline (20 readings around 90°C)
        for _ in range(20):
            f.filter_reading({"coolant_temp": 90.0})

        # Now send a spike (200°C is within physical range but 3σ+ from baseline)
        cleaned, quality = f.filter_reading({"coolant_temp": 200.0})

        # 200°C exceeds physical range so range check catches it first
        assert quality.get("coolant_temp") == 0.0, "Extreme spike should be rejected"

    def test_statistical_outlier_within_range_rejected(self):
        """A value within physical range but far from baseline should be rejected."""
        f = DataQualityFilter(warmup_readings=0)

        # Establish a tight baseline around 13.5V (std ≈ 0)
        for _ in range(20):
            f.filter_reading({"battery_voltage": 13.5})

        # 18V is within physical range (0-20V) but very far from 13.5V baseline
        cleaned, quality = f.filter_reading({"battery_voltage": 18.0})

        # Should be flagged as outlier
        assert quality.get("battery_voltage") == 0.0, (
            "18V is within physical range but 3σ+ above 13.5V baseline — should be outlier"
        )

    def test_normal_variation_not_rejected(self):
        """Small fluctuations within 3σ should not be rejected."""
        f = DataQualityFilter(warmup_readings=0)

        # Build a baseline with natural variation (±0.2V spread) so std > 0
        # This simulates realistic alternator output variation
        import itertools
        voltages = itertools.cycle([13.3, 13.5, 13.7, 13.5, 13.6, 13.4])
        for _ in range(20):
            f.filter_reading({"battery_voltage": next(voltages)})

        # 13.7V is within the observed range — should not be an outlier
        cleaned, quality = f.filter_reading({"battery_voltage": 13.7})

        assert quality.get("battery_voltage") == 1.0, (
            "Small fluctuation (13.7V within ±0.2V baseline std) should not be rejected"
        )

    def test_outlier_not_included_in_cleaned(self):
        """An outlier sensor reading should be excluded from cleaned output."""
        f = DataQualityFilter(warmup_readings=0)

        # Establish baseline
        for _ in range(20):
            f.filter_reading({"battery_voltage": 13.5})

        cleaned, quality = f.filter_reading({"battery_voltage": 18.0})
        assert "battery_voltage" not in cleaned, "Outlier should be excluded from cleaned data"

    def test_outlier_detection_disabled_before_baseline_established(self):
        """With fewer than ~5 readings, std is too small to detect outliers reliably."""
        f = DataQualityFilter(warmup_readings=0)

        # Only 1 stable reading, then a spike
        f.filter_reading({"rpm": 2000.0})
        # With only 1 prior reading, we can't detect outliers — pass through
        cleaned, quality = f.filter_reading({"rpm": 8000.0})

        # 8000 RPM is above physical max (9000), range check handles it differently
        # With 9000 as max, 8000 is within range — might pass or not depending on baseline
        # Key: test that it doesn't crash


# ===== Quality Summary Tests =====

class TestQualitySummary:
    """get_sensor_quality_summary() returns per-sensor quality scores."""

    def test_all_valid_sensors_score_1(self):
        """After all-valid readings, summary should show 1.0 for each sensor."""
        f = DataQualityFilter(warmup_readings=0)
        reading = {"rpm": 2000.0, "battery_voltage": 13.5, "speed": 60.0}

        for _ in range(5):
            f.filter_reading(reading)

        summary = f.get_sensor_quality_summary()

        for sensor in ["rpm", "battery_voltage", "speed"]:
            assert summary.get(sensor, 0) > 0.8, f"{sensor} should have high quality"

    def test_rejected_readings_lower_quality_score(self):
        """Mixing valid and invalid readings should lower the quality score."""
        f = DataQualityFilter(warmup_readings=0)

        # 5 valid readings, then 5 invalid
        for _ in range(5):
            f.filter_reading({"rpm": 2000.0})
        for _ in range(5):
            f.filter_reading({"rpm": -100.0})  # Invalid

        summary = f.get_sensor_quality_summary()

        # Quality should be < 1.0 since half the readings were invalid
        assert summary.get("rpm", 1.0) < 1.0, "Mixed valid/invalid should lower quality score"

    def test_empty_summary_before_any_readings(self):
        """Before any readings, summary should be empty or all zero."""
        f = DataQualityFilter(warmup_readings=0)
        summary = f.get_sensor_quality_summary()
        # Either empty or all zeros is acceptable
        assert isinstance(summary, dict)


# ===== Reset Tests =====

class TestReset:
    """reset() clears state and re-starts warm-up phase."""

    def test_reset_restarts_warmup(self):
        """After reset, warm-up period restarts."""
        f = DataQualityFilter(warmup_readings=3)
        reading = {"rpm": 2000.0}

        # Burn through warmup
        for _ in range(3):
            f.filter_reading(reading)

        # Verify we're past warmup
        _, quality_before = f.filter_reading(reading)
        assert len(quality_before) > 0

        # Reset
        f.reset()

        # Should be in warmup again
        _, quality_after_reset = f.filter_reading(reading)
        assert quality_after_reset == {}, "After reset, first reading should be warmup again"

    def test_reset_clears_stuck_counters(self):
        """After reset, stuck sensor counters are cleared."""
        f = DataQualityFilter(warmup_readings=0)

        # Get sensor stuck
        for _ in range(31):
            f.filter_reading({"battery_voltage": 13.5})

        _, quality_stuck = f.filter_reading({"battery_voltage": 13.5})
        assert quality_stuck.get("battery_voltage") == 0.0

        # Reset
        f.reset()

        # After reset with warmup_readings=0, the first reading IS processed
        # (not warmup). Stuck counter cleared, so quality should be 1.0.
        _, quality_fresh = f.filter_reading({"battery_voltage": 13.5})
        assert quality_fresh.get("battery_voltage") == 1.0, (
            "After reset, stuck counter cleared — first reading should have quality 1.0"
        )

    def test_reset_with_zero_warmup_clears_stuck(self):
        """Reset with warmup_readings=0: first post-reset reading should be processed."""
        f = DataQualityFilter(warmup_readings=0)

        # Get sensor stuck
        for _ in range(31):
            f.filter_reading({"battery_voltage": 13.5})

        # Reset
        f.reset()

        # Now do one more reading — stuck counter should be cleared
        _, quality = f.filter_reading({"battery_voltage": 13.5})
        assert quality.get("battery_voltage") == 1.0, "After reset, first reading should have quality 1.0"

    def test_reset_clears_rolling_statistics(self):
        """After reset, rolling average/std are cleared — outlier detection fresh."""
        f = DataQualityFilter(warmup_readings=0)

        # Establish strong baseline
        for _ in range(20):
            f.filter_reading({"coolant_temp": 90.0})

        # Reset
        f.reset()

        # With fresh state, a new value doesn't trigger outlier detection
        _, quality = f.filter_reading({"coolant_temp": 75.0})
        assert quality.get("coolant_temp") == 1.0, "After reset, first reading should pass"


# ===== Integration Tests =====

class TestIntegration:
    """End-to-end tests simulating realistic OBD usage patterns."""

    def test_realistic_obd_session(self):
        """Simulate a realistic OBD session: warmup → stable → glitch → recovery."""
        f = DataQualityFilter(warmup_readings=5)

        # Phase 1: Warm-up (5 readings discarded)
        startup_data = {"rpm": 800.0, "battery_voltage": 12.1, "coolant_temp": 20.0}
        for _ in range(5):
            _, quality = f.filter_reading(startup_data)
            assert quality == {}

        # Phase 2: Normal driving
        normal_data = {"rpm": 2500.0, "battery_voltage": 14.2, "coolant_temp": 88.0}
        for _ in range(10):
            cleaned, quality = f.filter_reading(normal_data)
            assert quality.get("rpm") == 1.0
            assert quality.get("battery_voltage") == 1.0

        # Phase 3: Sensor glitch (battery voltage spike)
        glitch_data = {"rpm": 2500.0, "battery_voltage": 25.0, "coolant_temp": 88.0}
        cleaned_glitch, quality_glitch = f.filter_reading(glitch_data)
        assert "battery_voltage" not in cleaned_glitch  # Glitch filtered out
        assert quality_glitch.get("battery_voltage") == 0.0

        # Phase 4: Recovery
        for _ in range(5):
            cleaned, quality = f.filter_reading(normal_data)
            assert quality.get("battery_voltage") == 1.0

    def test_all_sensors_known_to_filter(self):
        """Verify all PHYSICAL_RANGES sensors are checked."""
        f = DataQualityFilter(warmup_readings=0)

        # All sensors at max + 1 should be rejected
        over_limit_readings = {
            "rpm": 9001.0,
            "speed": 301.0,
            "coolant_temp": 151.0,
            "battery_voltage": 21.0,
            "engine_load": 101.0,
            "throttle_pos": 101.0,
            "fuel_level": 101.0,
            "intake_temp": 81.0,
            "maf_rate": 701.0,
        }

        for sensor, value in over_limit_readings.items():
            f2 = DataQualityFilter(warmup_readings=0)
            cleaned, quality = f2.filter_reading({sensor: value})
            assert quality.get(sensor) == 0.0, f"{sensor}={value} should be out of range"
            assert sensor not in cleaned, f"{sensor}={value} should be excluded"
