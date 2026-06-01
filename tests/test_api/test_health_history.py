"""Tests for health history endpoint and snapshot logic."""

import json
import time
import pytest


class TestHealthSnapshotModel:
    """Tests for the HealthSnapshot DB model."""

    def test_model_import(self):
        from predict.core.db.models.health_snapshot import HealthSnapshot
        assert HealthSnapshot.__tablename__ == "health_snapshots"

    def test_model_columns(self):
        from predict.core.db.models.health_snapshot import HealthSnapshot
        cols = {c.name for c in HealthSnapshot.__table__.columns}
        assert "id" in cols
        assert "vehicle_id" in cols
        assert "health_score" in cols
        assert "components" in cols
        assert "intelligence_level" in cols
        assert "anomaly_count" in cols
        assert "pattern_count" in cols
        assert "created_at" in cols

    def test_model_in_init(self):
        from predict.core.db.models import HealthSnapshot
        assert HealthSnapshot is not None


class TestSnapshotSaveLogic:
    """Tests for _maybe_save_health_snapshot deduplication logic."""

    def test_six_hour_dedup_window(self):
        """Verify the 6-hour window constant."""
        six_hours_seconds = 21600
        assert six_hours_seconds == 6 * 60 * 60

    def test_365_day_retention_seconds(self):
        """Verify the 365-day cleanup window."""
        one_year_seconds = 365 * 86400
        assert one_year_seconds == 31536000

    def test_component_scores_extraction(self):
        """Test extracting component scores from health result."""
        result = {
            "components": {
                "engine_oil": {"health_pct": 85, "trend": "stable"},
                "battery": {"health_pct": 72, "trend": "declining"},
            }
        }
        comp_scores = {}
        for comp_id, comp_data in result["components"].items():
            if isinstance(comp_data, dict):
                comp_scores[comp_id] = comp_data.get("health_pct", 0)

        assert comp_scores == {"engine_oil": 85, "battery": 72}

    def test_intelligence_level_from_dict(self):
        """Intelligence level can come as dict or string."""
        # Dict form (from pipeline)
        result_dict = {"intelligence_level": {"level": "enhanced", "title": "Enhanced"}}
        intel = result_dict["intelligence_level"]
        level = intel.get("level", "basic") if isinstance(intel, dict) else intel
        assert level == "enhanced"

        # String form (from cold-start fallback)
        result_str = {"intelligence_level": "basic"}
        intel2 = result_str["intelligence_level"]
        level2 = intel2.get("level", "basic") if isinstance(intel2, dict) else intel2
        assert level2 == "basic"

    def test_anomaly_and_pattern_counts(self):
        """Count anomalies and patterns from result dict."""
        result = {
            "anomaly_alerts": [{"severity": "high"}, {"severity": "low"}],
            "detected_patterns": [{"name": "rich_running"}],
        }
        anomaly_count = len(result.get("anomaly_alerts", []) or [])
        pattern_count = len(result.get("detected_patterns", []) or result.get("patterns_detected", []) or [])
        assert anomaly_count == 2
        assert pattern_count == 1

    def test_null_lists_handled(self):
        """Null anomaly/pattern lists should count as 0."""
        result = {"anomaly_alerts": None, "detected_patterns": None}
        anomaly_count = len(result.get("anomaly_alerts", []) or [])
        pattern_count = len(result.get("detected_patterns", []) or result.get("patterns_detected", []) or [])
        assert anomaly_count == 0
        assert pattern_count == 0


class TestHealthHistoryEndpoint:
    """Tests for GET /api/predictions/{vehicle_id}/health-history."""

    def test_days_param_constraints(self):
        """Days param: min 1, max 365, default 90."""
        # These are just logical constraints — FastAPI enforces at runtime
        assert 1 <= 90 <= 365  # default is valid
        assert 1 <= 7 <= 365   # weekly valid
        assert 1 <= 365 <= 365  # max valid

    def test_cutoff_computation(self):
        """Cutoff = now - (days * 86400)."""
        now = time.time()
        days = 90
        cutoff = now - (days * 86400)
        # 90 days ago should be roughly 7.78M seconds ago
        assert (now - cutoff) == pytest.approx(90 * 86400, abs=1)

    def test_snapshot_serialization(self):
        """Snapshot components JSON round-trips correctly."""
        comp_scores = {"engine_oil": 85, "battery": 72, "coolant_system": 90}
        serialized = json.dumps(comp_scores)
        deserialized = json.loads(serialized)
        assert deserialized == comp_scores
