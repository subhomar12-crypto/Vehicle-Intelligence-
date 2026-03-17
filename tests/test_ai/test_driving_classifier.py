"""Tests for driving context classifier."""

import pytest
from predict.core.ai.driving_classifier import DrivingContextClassifier


class TestDrivingContextClassifier:
    """Test DrivingContextClassifier."""

    def setup_method(self):
        """Set up test fixtures."""
        self.classifier = DrivingContextClassifier()

    def test_idle_classification(self):
        """Low speed and RPM → idle context."""
        telemetry = [
            {"speed": 0, "rpm": 800},
            {"speed": 0, "rpm": 850},
            {"speed": 2, "rpm": 900},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "idle"
        assert result["speed_stats"]["mean"] == pytest.approx(0.67, rel=0.1)
        assert result["confidence"] == 0.85

    def test_city_classification(self):
        """Many stops and low speed → city context."""
        telemetry = [
            {"speed": 0, "rpm": 800},
            {"speed": 10, "rpm": 1200},
            {"speed": 20, "rpm": 1500},
            {"speed": 0, "rpm": 900},   # stop
            {"speed": 15, "rpm": 1300},
            {"speed": 25, "rpm": 1600},
            {"speed": 0, "rpm": 850},   # stop
            {"speed": 12, "rpm": 1250},
            {"speed": 18, "rpm": 1400},
            {"speed": 0, "rpm": 800},   # stop
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "city"
        assert result["stop_count"] == 3

    def test_highway_classification(self):
        """High speed, few stops → highway context."""
        telemetry = [
            {"speed": 80, "rpm": 2500},
            {"speed": 82, "rpm": 2550},
            {"speed": 79, "rpm": 2480},
            {"speed": 81, "rpm": 2520},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "highway"
        assert result["speed_stats"]["mean"] == pytest.approx(80.5, rel=0.01)

    def test_aggressive_classification_high_rpm(self):
        """RPM > 4500 → aggressive context."""
        telemetry = [
            {"speed": 60, "rpm": 4800},
            {"speed": 65, "rpm": 5000},
            {"speed": 70, "rpm": 4600},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "aggressive"

    def test_aggressive_classification_hard_accel(self):
        """Many hard accelerations → aggressive context."""
        telemetry = [
            {"speed": 20, "rpm": 1500},
            {"speed": 25, "rpm": 1600},
            {"speed": 40, "rpm": 3200},  # +1600 RPM
            {"speed": 45, "rpm": 3300},
            {"speed": 60, "rpm": 4800},  # +1500 RPM
            {"speed": 65, "rpm": 4900},
            {"speed": 80, "rpm": 6400},  # +1500 RPM
            {"speed": 85, "rpm": 6500},
            {"speed": 100, "rpm": 8000}, # +1500 RPM
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "aggressive"
        assert result["hard_accel_count"] > 3

    def test_aggressive_classification_hard_brake(self):
        """Many hard brakes → aggressive context."""
        telemetry = [
            {"speed": 80, "rpm": 2500},
            {"speed": 82, "rpm": 2550},
            {"speed": 55, "rpm": 2400},  # -25 km/h
            {"speed": 57, "rpm": 2450},
            {"speed": 30, "rpm": 2300},  # -25 km/h
            {"speed": 32, "rpm": 2350},
            {"speed": 5, "rpm": 2200},   # -25 km/h
            {"speed": 7, "rpm": 2250},
            {"speed": 0, "rpm": 800},    # -25 km/h
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "aggressive"
        assert result["hard_brake_count"] > 3

    def test_mixed_classification(self):
        """Moderate speed, moderate stops → mixed context."""
        telemetry = [
            {"speed": 50, "rpm": 2000},
            {"speed": 52, "rpm": 2050},
            {"speed": 48, "rpm": 1980},
            {"speed": 50, "rpm": 2000},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "mixed"

    def test_stop_counting(self):
        """Correctly count transitions from moving to stopped."""
        telemetry = [
            {"speed": 10, "rpm": 1200},  # moving
            {"speed": 0, "rpm": 800},    # stop 1
            {"speed": 0, "rpm": 800},    # still stopped
            {"speed": 15, "rpm": 1300},  # moving
            {"speed": 20, "rpm": 1500},  # moving
            {"speed": 0, "rpm": 850},    # stop 2
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["stop_count"] == 2

    def test_empty_telemetry(self):
        """Empty telemetry returns zeros and idle context."""
        telemetry = []
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "idle"
        assert result["speed_stats"]["mean"] == 0.0
        assert result["rpm_stats"]["mean"] == 0.0
        assert result["stop_count"] == 0

    def test_single_reading(self):
        """Single reading doesn't crash."""
        telemetry = [{"speed": 50, "rpm": 2000}]
        result = self.classifier.classify(telemetry)
        
        assert result["context"] == "mixed"
        assert result["hard_accel_count"] == 0
        assert result["hard_brake_count"] == 0

    def test_none_values(self):
        """None values are treated as 0."""
        telemetry = [
            {"speed": None, "rpm": None},
            {"speed": 0, "rpm": 800},
            {"speed": None, "rpm": None},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["speed_stats"]["mean"] == 0.0
        assert result["rpm_stats"]["mean"] == pytest.approx(266.67, rel=0.01)

    def test_speed_stats_accuracy(self):
        """Speed statistics are calculated correctly."""
        telemetry = [
            {"speed": 10, "rpm": 1000},
            {"speed": 20, "rpm": 1500},
            {"speed": 30, "rpm": 2000},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["speed_stats"]["mean"] == 20.0
        assert result["speed_stats"]["max"] == 30.0
        assert result["speed_stats"]["std"] > 0

    def test_rpm_stats_accuracy(self):
        """RPM statistics are calculated correctly."""
        telemetry = [
            {"speed": 10, "rpm": 1000},
            {"speed": 20, "rpm": 2000},
            {"speed": 30, "rpm": 3000},
        ]
        result = self.classifier.classify(telemetry)
        
        assert result["rpm_stats"]["mean"] == 2000.0
        assert result["rpm_stats"]["max"] == 3000.0
        assert result["rpm_stats"]["std"] > 0
