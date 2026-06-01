"""Tests for isolation forest engine."""

import json
import tempfile
import os

import numpy as np
import pytest

from predict.core.ai.isolation_forest_engine import (
    IsolationForestEngine,
    AnomalyResult,
)


class TestIsolationForestEngine:
    """Test IsolationForestEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = IsolationForestEngine(contamination=0.1, n_estimators=10)
        
    def test_anomaly_result_dataclass(self):
        """AnomalyResult can be created and converted to dict."""
        result = AnomalyResult(
            timestamp=1234567890.0,
            anomaly_score=-0.5,
            sensors=["rpm", "speed"],
            severity="high",
        )
        
        d = result.to_dict()
        assert d["timestamp"] == 1234567890.0
        assert d["anomaly_score"] == -0.5
        assert d["sensors"] == ["rpm", "speed"]
        assert d["severity"] == "high"

    def test_train_from_baseline_insufficient_data(self):
        """Training with < 50 samples raises error."""
        baseline = np.random.randn(30, 5)
        
        with pytest.raises(ValueError, match="at least 50"):
            self.engine.train_from_baseline(baseline)

    def test_train_from_baseline_success(self):
        """Training succeeds with sufficient data."""
        # Generate normal baseline data
        np.random.seed(42)
        baseline = np.random.randn(100, 5)
        
        model_dict = self.engine.train_from_baseline(baseline)
        
        assert "trees" in model_dict
        assert "n_estimators" in model_dict
        assert "threshold" in model_dict
        assert model_dict["n_estimators"] == 10
        assert self.engine.model is not None
        assert self.engine.threshold is not None

    def test_serialize_model_structure(self):
        """Serialized model has correct structure."""
        np.random.seed(42)
        baseline = np.random.randn(100, 5)
        
        self.engine.train_from_baseline(baseline)
        model_dict = self.engine.serialize_model(self.engine.model)
        
        assert "n_estimators" in model_dict
        assert "trees" in model_dict
        assert "n_features" in model_dict
        assert len(model_dict["trees"]) == 10
        
        # Check tree structure
        tree = model_dict["trees"][0]
        assert "n_nodes" in tree
        assert "children_left" in tree
        assert "children_right" in tree
        assert "feature" in tree
        assert "threshold" in tree

    def test_load_model(self):
        """Model can be loaded from dictionary."""
        np.random.seed(42)
        baseline = np.random.randn(100, 5)
        
        model_dict = self.engine.train_from_baseline(baseline)
        
        # Create new engine and load
        new_engine = IsolationForestEngine()
        new_engine.load_model(model_dict)
        
        assert new_engine.model is not None
        assert new_engine.threshold == pytest.approx(model_dict["threshold"])

    def test_detect_anomalies_no_model(self):
        """Detection without model returns empty list."""
        readings = [{"rpm": 1000, "speed": 50}]
        
        anomalies = self.engine.detect_anomalies(readings, ["rpm", "speed"])
        
        assert anomalies == []

    def test_detect_anomalies_finds_outliers(self):
        """Anomaly detection finds outliers."""
        np.random.seed(42)

        # Train on normal data (2 features)
        baseline = np.random.randn(100, 2) * 10 + 50
        self.engine.train_from_baseline(baseline)

        # Create readings with one clear outlier
        readings = []
        for i in range(20):
            readings.append({
                "rpm": float(50 + np.random.randn() * 5),
                "speed": float(50 + np.random.randn() * 5),
                "timestamp": float(i),
            })

        # Add outlier
        readings.append({
            "rpm": 200.0,  # Far from normal
            "speed": 10.0,
            "timestamp": 20.0,
        })

        anomalies = self.engine.detect_anomalies(readings, ["rpm", "speed"])

        # Should detect at least the outlier
        assert len(anomalies) >= 1

        # Check outlier was detected
        outlier_anomalies = [a for a in anomalies if abs(a.timestamp - 20.0) < 0.1]
        assert len(outlier_anomalies) >= 1

    def test_detect_anomalies_severity_levels(self):
        """Anomalies have appropriate severity."""
        np.random.seed(42)
        
        baseline = np.random.randn(100, 2) * 10 + 50
        self.engine.train_from_baseline(baseline)
        
        # Create reading with extreme outlier
        readings = [{
            "rpm": 500.0,  # Very far from normal
            "speed": 500.0,
            "timestamp": 0.0,
        }]
        
        anomalies = self.engine.detect_anomalies(readings, ["rpm", "speed"])
        
        if anomalies:
            assert anomalies[0].severity in ["low", "medium", "high"]

    def test_detect_anomalies_with_none_values(self):
        """None values are handled gracefully."""
        np.random.seed(42)
        
        baseline = np.random.randn(100, 2) * 10 + 50
        self.engine.train_from_baseline(baseline)
        
        readings = [
            {"rpm": 50.0, "speed": None, "timestamp": 0.0},
            {"rpm": None, "speed": 50.0, "timestamp": 1.0},
            {"rpm": 50.0, "speed": 50.0, "timestamp": 2.0},
        ]
        
        # Should not crash
        anomalies = self.engine.detect_anomalies(readings, ["rpm", "speed"])
        assert isinstance(anomalies, list)

    def test_detect_anomalies_empty_readings(self):
        """Empty readings returns empty list."""
        np.random.seed(42)
        
        baseline = np.random.randn(100, 2)
        self.engine.train_from_baseline(baseline)
        
        anomalies = self.engine.detect_anomalies([], ["rpm", "speed"])
        
        assert anomalies == []

    def test_export_import_for_pi5(self):
        """Model can be exported and imported for Pi5."""
        np.random.seed(42)
        
        # Train model
        baseline = np.random.randn(100, 3)
        self.engine.train_from_baseline(baseline)
        
        # Export to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.engine.export_for_pi5(temp_path)
            
            # Verify file exists and is valid JSON
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                data = json.load(f)
            assert "trees" in data
            
            # Import into new engine
            new_engine = IsolationForestEngine()
            new_engine.import_from_pi5(temp_path)
            
            assert new_engine.model is not None
            assert new_engine.threshold is not None
            
        finally:
            os.unlink(temp_path)

    def test_json_model_inference(self):
        """JSON model can be used for inference."""
        np.random.seed(42)
        
        # Train with sklearn
        baseline = np.random.randn(100, 2) * 10 + 50
        self.engine.train_from_baseline(baseline)
        
        # Get JSON model
        model_dict = self.engine.serialize_model(self.engine.model)
        model_dict["threshold"] = self.engine.threshold
        model_dict["contamination"] = self.engine.contamination
        
        # Load as JSON model
        json_engine = IsolationForestEngine()
        json_engine.load_model(model_dict)
        
        # Test inference
        readings = [
            {"rpm": 50.0, "speed": 50.0, "timestamp": 0.0},
            {"rpm": 200.0, "speed": 200.0, "timestamp": 1.0},
        ]
        
        anomalies = json_engine.detect_anomalies(readings, ["rpm", "speed"])
        
        # Should detect at least one anomaly
        assert isinstance(anomalies, list)
        # The second reading is an outlier
        outlier_anomalies = [a for a in anomalies if abs(a.timestamp - 1.0) < 0.1]
        assert len(outlier_anomalies) >= 1

    def test_traverse_tree_logic(self):
        """Tree traversal works correctly."""
        np.random.seed(42)
        
        baseline = np.random.randn(100, 2)
        self.engine.train_from_baseline(baseline)
        
        # Create a simple tree dict
        tree = {
            "n_nodes": 3,
            "children_left": [1, -1, -1],
            "children_right": [2, -1, -1],
            "feature": [0, 0, 0],
            "threshold": [0.0, 0.0, 0.0],
        }
        
        features = np.array([[1.0, 2.0], [-1.0, 2.0]])
        
        depths = self.engine._traverse_tree(features, tree)
        
        assert len(depths) == 2
        assert depths[0] >= 0
        assert depths[1] >= 0

    def test_json_scores_match_sklearn(self):
        """JSON pure-Python inference matches sklearn score_samples()."""
        np.random.seed(42)

        baseline = np.random.randn(200, 5) * 10 + 50
        model_dict = self.engine.train_from_baseline(baseline)

        # Score with sklearn
        test_data = np.random.randn(30, 5) * 10 + 50
        sklearn_scores = self.engine.model.score_samples(test_data)

        # Score with JSON model
        json_engine = IsolationForestEngine()
        json_engine.load_model(model_dict)
        json_scores = json_engine._score_samples_json(test_data)

        # Scores should be close (not exact due to float precision)
        np.testing.assert_allclose(json_scores, sklearn_scores, atol=0.05)

    def test_sensors_in_anomaly_result(self):
        """Anomaly results include top anomalous sensors."""
        np.random.seed(42)
        
        baseline = np.random.randn(100, 3) * 10 + 50
        self.engine.train_from_baseline(baseline)
        
        # Create reading with one very high sensor
        readings = [{
            "rpm": 50.0,
            "speed": 50.0,
            "maf_rate": 500.0,  # Very high
            "timestamp": 0.0,
        }]
        
        anomalies = self.engine.detect_anomalies(readings, ["rpm", "speed", "maf_rate"])
        
        if anomalies:
            assert len(anomalies[0].sensors) <= 3
            assert "maf_rate" in anomalies[0].sensors
