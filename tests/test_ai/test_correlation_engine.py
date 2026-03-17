"""Tests for correlation engine."""

import pytest
import numpy as np

from predict.core.ai.correlation_engine import (
    CorrelationEngine,
    CorrelationAnomaly,
    EXPECTED_PAIRS,
)


class TestCorrelationEngine:
    """Test CorrelationEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = CorrelationEngine(window_size=100, break_threshold=0.25)

    def test_expected_pairs_defined(self):
        """EXPECTED_PAIRS contains the 5 specified pairs."""
        assert len(EXPECTED_PAIRS) == 5
        
        pairs = [(s1, s2) for s1, s2, _ in EXPECTED_PAIRS]
        assert ("rpm", "maf_rate") in pairs
        assert ("rpm", "injector_ms") in pairs
        assert ("speed", "rpm") in pairs
        assert ("throttle_pos", "engine_load") in pairs
        assert ("coolant_temp", "ambient_temp") in pairs

    def test_compute_correlation_matrix_basic(self):
        """Basic correlation computation works."""
        # Create perfectly correlated data
        readings = [
            {"rpm": i * 100, "speed": i * 2, "maf_rate": i * 10}
            for i in range(20)
        ]
        
        correlations = self.engine.compute_correlation_matrix(
            readings, ["rpm", "speed", "maf_rate"]
        )
        
        # Should have 3 pairs
        assert len(correlations) == 3
        assert ("rpm", "speed") in correlations
        assert ("rpm", "maf_rate") in correlations
        assert ("speed", "maf_rate") in correlations

    def test_compute_correlation_matrix_values(self):
        """Correlation values are accurate."""
        # Perfect positive correlation
        readings = [
            {"sensor1": i, "sensor2": i * 2}
            for i in range(50)
        ]
        
        correlations = self.engine.compute_correlation_matrix(
            readings, ["sensor1", "sensor2"]
        )
        
        assert correlations[("sensor1", "sensor2")] == pytest.approx(1.0, abs=0.01)

    def test_compute_correlation_matrix_negative(self):
        """Negative correlation is detected."""
        readings = [
            {"sensor1": i, "sensor2": 50 - i}
            for i in range(50)
        ]
        
        correlations = self.engine.compute_correlation_matrix(
            readings, ["sensor1", "sensor2"]
        )
        
        assert correlations[("sensor1", "sensor2")] == pytest.approx(-1.0, abs=0.01)

    def test_compute_correlation_matrix_no_correlation(self):
        """No correlation is detected."""
        np.random.seed(42)
        readings = [
            {"sensor1": np.random.randn(), "sensor2": np.random.randn()}
            for _ in range(100)
        ]
        
        correlations = self.engine.compute_correlation_matrix(
            readings, ["sensor1", "sensor2"]
        )
        
        # Should be close to 0
        assert abs(correlations[("sensor1", "sensor2")]) < 0.3

    def test_compute_correlation_matrix_insufficient_data(self):
        """Less than 10 readings returns empty dict."""
        readings = [{"sensor1": i, "sensor2": i} for i in range(5)]
        
        correlations = self.engine.compute_correlation_matrix(
            readings, ["sensor1", "sensor2"]
        )
        
        assert correlations == {}

    def test_compute_correlation_matrix_with_nans(self):
        """NaN values are handled gracefully."""
        # Create more data with some NaN values interspersed
        readings = []
        for i in range(20):
            if i % 5 == 0:
                readings.append({"sensor1": None, "sensor2": i * 2})
            elif i % 5 == 1:
                readings.append({"sensor1": i, "sensor2": None})
            else:
                readings.append({"sensor1": i, "sensor2": i * 2})
        
        correlations = self.engine.compute_correlation_matrix(
            readings, ["sensor1", "sensor2"]
        )
        
        # Should still compute with available pairs (12 valid pairs)
        assert ("sensor1", "sensor2") in correlations
        assert correlations[("sensor1", "sensor2")] > 0.9  # Strong positive correlation

    def test_detect_anomalies_no_breaks(self):
        """No anomalies when correlations match baseline."""
        baseline = {("s1", "s2"): 0.8}
        current = {("s1", "s2"): 0.82}
        
        anomalies = self.engine.detect_anomalies(baseline, current)
        
        assert len(anomalies) == 0

    def test_detect_anomalies_with_break(self):
        """Anomaly detected when correlation breaks."""
        baseline = {("s1", "s2"): 0.8}
        current = {("s1", "s2"): 0.5}  # Drop of 0.3 > threshold 0.25
        
        anomalies = self.engine.detect_anomalies(baseline, current)
        
        assert len(anomalies) == 1
        assert anomalies[0].pair == ("s1", "s2")
        assert anomalies[0].baseline_r == 0.8
        assert anomalies[0].current_r == 0.5
        assert anomalies[0].delta == pytest.approx(-0.3)

    def test_detect_anomalies_severity_low(self):
        """Small break = low severity."""
        baseline = {("s1", "s2"): 0.8}
        current = {("s1", "s2"): 0.54}  # Drop of 0.26 (> 0.25 threshold)
        
        anomalies = self.engine.detect_anomalies(baseline, current)
        
        assert len(anomalies) == 1
        assert anomalies[0].severity == "low"

    def test_detect_anomalies_severity_medium(self):
        """Medium break = medium severity."""
        baseline = {("s1", "s2"): 0.8}
        current = {("s1", "s2"): 0.40}  # Drop of 0.4
        
        anomalies = self.engine.detect_anomalies(baseline, current)
        
        assert anomalies[0].severity == "medium"

    def test_detect_anomalies_severity_high(self):
        """Large break = high severity."""
        baseline = {("s1", "s2"): 0.8}
        current = {("s1", "s2"): 0.20}  # Drop of 0.6
        
        anomalies = self.engine.detect_anomalies(baseline, current)
        
        assert anomalies[0].severity == "high"

    def test_detect_anomalies_interpretation(self):
        """Interpretation includes relevant info."""
        baseline = {("rpm", "maf_rate"): 0.85}
        current = {("rpm", "maf_rate"): 0.40}
        
        anomalies = self.engine.detect_anomalies(baseline, current)
        
        assert "maf_rate" in anomalies[0].interpretation
        assert "0.85" in anomalies[0].interpretation
        assert "0.40" in anomalies[0].interpretation

    def test_analyze_expected_pairs_insufficient_data(self):
        """Less than 50 readings returns empty list."""
        readings = [{"rpm": i} for i in range(30)]
        
        anomalies = self.engine.analyze_expected_pairs(readings)
        
        assert anomalies == []

    def test_analyze_expected_pairs_with_anomaly(self):
        """Detects anomaly in expected pairs."""
        # Create data where rpm-maf_rate correlation is broken
        np.random.seed(42)
        readings = []
        for i in range(100):
            rpm = i * 100
            # maf_rate not correlated with rpm
            maf_rate = np.random.randn() * 100
            speed = rpm / 30  # speed correlated with rpm
            readings.append({
                "rpm": rpm,
                "maf_rate": maf_rate,
                "speed": speed,
                "injector_ms": rpm / 1000,
                "throttle_pos": 50,
                "engine_load": 60,
                "coolant_temp": 90,
                "ambient_temp": 35,
            })
        
        anomalies = self.engine.analyze_expected_pairs(readings)
        
        # Should detect broken rpm-maf_rate correlation
        rpm_maf_anomalies = [a for a in anomalies if a.pair == ("rpm", "maf_rate")]
        assert len(rpm_maf_anomalies) > 0

    def test_get_correlation_summary(self):
        """Summary includes all expected fields."""
        readings = [
            {"rpm": i * 100, "speed": i * 2, "maf_rate": i * 10}
            for i in range(100)
        ]
        
        summary = self.engine.get_correlation_summary(
            readings, ["rpm", "speed", "maf_rate"]
        )
        
        assert "correlations" in summary
        assert "health_score" in summary
        assert "num_analyzed" in summary
        assert "anomalies" in summary
        assert summary["num_analyzed"] == 3
        assert 0 <= summary["health_score"] <= 100

    def test_health_score_with_anomalies(self):
        """Health score decreases with anomalies."""
        # Create data with broken correlations
        baseline_corr = {
            ("s1", "s2"): 0.8,
            ("s2", "s3"): 0.7,
        }
        current_corr = {
            ("s1", "s2"): 0.5,  # high severity drop
            ("s2", "s3"): 0.65,  # small drop
        }
        
        anomalies = self.engine.detect_anomalies(baseline_corr, current_corr)
        
        # Calculate expected health score manually
        health = 100.0
        for a in anomalies:
            if a.severity == "high":
                health -= 20
            elif a.severity == "medium":
                health -= 10
            else:
                health -= 5
        
        assert health < 100

    def test_empty_readings(self):
        """Empty readings handled gracefully."""
        correlations = self.engine.compute_correlation_matrix([], ["s1", "s2"])
        assert correlations == {}

    def test_single_sensor(self):
        """Single sensor returns empty correlations."""
        readings = [{"sensor1": i} for i in range(20)]
        correlations = self.engine.compute_correlation_matrix(readings, ["sensor1"])
        assert correlations == {}
