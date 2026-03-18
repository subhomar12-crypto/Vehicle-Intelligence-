"""Tests for auto-retraining triggers."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from predict.core.jobs.tasks.retraining_tasks import (
    RetrainingTrigger,
    weekly_retraining_check,
    retrain_model,
    get_retraining_stats,
    COMPONENT_IDS,
    ACCURACY_DROP_THRESHOLD,
)


class TestRetrainingTrigger:
    """Test RetrainingTrigger class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.trigger = RetrainingTrigger(accuracy_threshold=-0.10)

    def test_component_ids_tuple(self):
        """COMPONENT_IDS is a tuple with canonical IDs."""
        assert isinstance(COMPONENT_IDS, tuple)
        assert len(COMPONENT_IDS) == 10
        assert "engine_oil" in COMPONENT_IDS
        assert "battery" in COMPONENT_IDS
        assert "coolant_system" in COMPONENT_IDS

    def test_accuracy_threshold_default(self):
        """Default accuracy threshold is -0.10 (10% drop)."""
        assert ACCURACY_DROP_THRESHOLD == -0.10

    @pytest.mark.asyncio
    async def test_compute_accuracy_delta_insufficient_data(self):
        """Compute delta with insufficient data returns None."""
        mock_session = AsyncMock()
        
        # Mock empty results
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        delta = await self.trigger.compute_accuracy_delta(
            mock_session, "engine_oil"
        )
        
        assert delta is None

    @pytest.mark.asyncio
    async def test_compute_accuracy_delta_with_data(self):
        """Compute delta with sufficient data."""
        mock_session = AsyncMock()
        
        # Create mock feedback data
        now = datetime.utcnow()
        
        # Last week: 80% valid feedback (8/10 have outcomes)
        last_week_feedback = []
        for i in range(10):
            f = MagicMock()
            f.actual_outcome = "confirmed_good" if i < 8 else "unknown"
            last_week_feedback.append(f)
        
        # Previous weeks: 90% valid feedback (18/20 have outcomes)
        prev_weeks_feedback = []
        for i in range(20):
            f = MagicMock()
            f.actual_outcome = "confirmed_good" if i < 18 else "unknown"
            prev_weeks_feedback.append(f)
        
        # Configure mock to return different results for different queries
        def mock_execute(query):
            result = MagicMock()
            # Determine which query by checking the where clause
            # For simplicity, alternate between the two
            if not hasattr(mock_execute, 'call_count'):
                mock_execute.call_count = 0
            mock_execute.call_count += 1
            
            if mock_execute.call_count % 2 == 1:
                result.scalars.return_value.all.return_value = last_week_feedback
            else:
                result.scalars.return_value.all.return_value = prev_weeks_feedback
            
            return result
        
        mock_session.execute.side_effect = mock_execute
        
        delta = await self.trigger.compute_accuracy_delta(
            mock_session, "engine_oil"
        )
        
        assert delta is not None
        assert delta["component"] == "engine_oil"
        assert delta["last_week_accuracy"] == 0.8
        assert delta["previous_avg_accuracy"] == 0.9
        assert delta["accuracy_delta"] == pytest.approx(-0.1, abs=0.01)
        assert delta["needs_retraining"] is False  # -10% is exactly at threshold, not below

    @pytest.mark.asyncio
    async def test_compute_accuracy_delta_no_retraining_needed(self):
        """Accuracy improvement doesn't trigger retraining."""
        mock_session = AsyncMock()
        
        # Last week: 95% valid feedback
        last_week_feedback = []
        for i in range(20):
            f = MagicMock()
            f.actual_outcome = "confirmed_good" if i < 19 else "unknown"
            last_week_feedback.append(f)
        
        # Previous weeks: 85% valid feedback
        prev_weeks_feedback = []
        for i in range(20):
            f = MagicMock()
            f.actual_outcome = "confirmed_good" if i < 17 else "unknown"
            prev_weeks_feedback.append(f)
        
        def mock_execute(query):
            result = MagicMock()
            if not hasattr(mock_execute, 'call_count'):
                mock_execute.call_count = 0
            mock_execute.call_count += 1
            
            if mock_execute.call_count % 2 == 1:
                result.scalars.return_value.all.return_value = last_week_feedback
            else:
                result.scalars.return_value.all.return_value = prev_weeks_feedback
            
            return result
        
        mock_session.execute.side_effect = mock_execute
        
        delta = await self.trigger.compute_accuracy_delta(
            mock_session, "engine_oil"
        )
        
        assert delta is not None
        assert delta["accuracy_delta"] > 0  # Improved
        assert delta["needs_retraining"] is False

    @pytest.mark.asyncio
    async def test_check_all_components(self):
        """Check all components returns summary."""
        mock_session = AsyncMock()
        
        # Mock compute_accuracy_delta to return different results
        async def mock_compute_delta(session, component, days_back=21):
            if component == "engine_oil":
                return {
                    "component": component,
                    "last_week_accuracy": 0.7,
                    "previous_avg_accuracy": 0.9,
                    "accuracy_delta": -0.2,
                    "needs_retraining": True,
                }
            elif component == "battery":
                return {
                    "component": component,
                    "last_week_accuracy": 0.95,
                    "previous_avg_accuracy": 0.93,
                    "accuracy_delta": 0.02,
                    "needs_retraining": False,
                }
            else:
                return None  # Insufficient data
        
        self.trigger.compute_accuracy_delta = mock_compute_delta
        
        results = await self.trigger.check_all_components(mock_session)
        
        assert "timestamp" in results
        assert "engine_oil" in results["components_triggered"]
        assert "battery" not in results["components_triggered"]
        assert len(results["insufficient_data"]) == 8  # 10 - 2 with data

    @pytest.mark.asyncio
    async def test_trigger_retraining(self):
        """Trigger retraining creates job and enqueues."""
        mock_session = AsyncMock()
        
        with patch('predict.core.jobs.tasks.retraining_tasks._get_pool') as mock_get_pool:
            mock_pool = AsyncMock()
            mock_arq_job = MagicMock()
            mock_arq_job.job_id = "job_456"
            mock_pool.enqueue_job = AsyncMock(return_value=mock_arq_job)
            mock_get_pool.return_value = mock_pool
            
            result = await self.trigger.trigger_retraining(
                mock_session, "engine_oil", model_type="xgboost"
            )
        
        assert result["component"] == "engine_oil"
        assert result["model_type"] == "xgboost"
        assert result["status"] == "queued"


class TestARQJobs:
    """Test ARQ job functions."""

    @pytest.mark.asyncio
    async def test_weekly_retraining_check(self):
        """Weekly check job runs without error."""
        # This is an integration test that would need real DB
        # For unit test, we mock the session
        with patch('predict.core.jobs.tasks.retraining_tasks.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            # Mock check_all_components to return empty
            with patch.object(RetrainingTrigger, 'check_all_components', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = {
                    "components_checked": [],
                    "components_triggered": [],
                    "insufficient_data": [],
                    "accuracy_stats": {},
                }
                
                result = await weekly_retraining_check()
                
                assert "components_checked" in result

    @pytest.mark.asyncio
    async def test_retrain_model_runs(self):
        """Retrain job runs without error."""
        with patch('predict.core.jobs.tasks.retraining_tasks.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            # Mock XGBoost predictor
            with patch('predict.core.ai.xgboost_predictor.XGBoostFailurePredictor') as mock_predictor_class:
                mock_predictor = MagicMock()
                mock_predictor.train_from_db = AsyncMock(return_value={"components_trained": ["engine_oil"]})
                mock_predictor.serialize = MagicMock(return_value={"engine_oil": "/path/to/model.joblib"})
                mock_predictor_class.return_value = mock_predictor
                
                result = await retrain_model("engine_oil", "xgboost")
                
                assert result["component"] == "engine_oil"
                assert result["model_type"] == "xgboost"
                assert "started_at" in result
                assert "completed_at" in result

    @pytest.mark.asyncio
    async def test_get_retraining_stats(self):
        """Get stats returns aggregated data."""
        with patch('predict.core.jobs.tasks.retraining_tasks.get_session_maker') as mock_session_maker:
            mock_session = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=False)
            mock_session_maker.return_value = MagicMock(return_value=mock_context)
            
            # Create mock ComponentAccuracyStats
            stats_records = []
            for i, component in enumerate(["engine_oil", "battery", "brakes"]):
                stat = MagicMock()
                stat.component = component
                stat.mean_absolute_error = 5.0 + i
                stat.directional_accuracy = 0.8 + i * 0.05
                stat.sample_count = 100 + i * 50
                stat.last_updated = datetime.utcnow().timestamp()
                stats_records.append(stat)
            
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = stats_records
            mock_session.execute.return_value = mock_result
            
            result = await get_retraining_stats(days=30)
            
            assert result["period_days"] == 30
            assert result["components_tracked"] == 3
            assert "engine_oil" in result["by_component"]
            assert "battery" in result["by_component"]
            assert result["by_component"]["engine_oil"]["mean_absolute_error"] == 5.0


class TestThresholdLogic:
    """Test accuracy threshold logic."""

    def test_accuracy_drop_calculation(self):
        """Accuracy delta calculation is correct."""
        last_week = 0.75
        prev_avg = 0.90
        delta = last_week - prev_avg
        
        assert delta == pytest.approx(-0.15, abs=0.001)
        assert delta < ACCURACY_DROP_THRESHOLD  # -0.15 < -0.10
        assert abs(delta) > 0.10  # More than 10% drop

    def test_accuracy_improvement(self):
        """Accuracy improvement doesn't trigger retraining."""
        last_week = 0.95
        prev_avg = 0.85
        delta = last_week - prev_avg
        
        assert delta == pytest.approx(0.10, abs=0.001)
        assert delta > ACCURACY_DROP_THRESHOLD  # 0.10 > -0.10

    def test_small_drop_no_trigger(self):
        """Small accuracy drop doesn't trigger retraining."""
        last_week = 0.88
        prev_avg = 0.90
        delta = last_week - prev_avg

        assert delta == pytest.approx(-0.02, abs=0.001)
        assert delta > ACCURACY_DROP_THRESHOLD  # -0.02 > -0.10
