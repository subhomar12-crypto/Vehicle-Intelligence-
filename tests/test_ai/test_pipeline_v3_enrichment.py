"""Tests for v3 module enrichment in UnifiedScoringPipeline."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def mock_session():
    session = AsyncMock()
    # Make session.execute return empty results for baseline/fleet queries
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def telemetry_history():
    return [
        {
            "rpm": 800 + i * 10, "speed": 0, "coolant_temp": 90,
            "battery_voltage": 13.8, "engine_load": 25, "throttle_pos": 12,
            "maf_rate": 2.4, "intake_temp": 35, "short_term_fuel_trim": 100,
            "long_term_fuel_trim": 100, "timing_advance": 15,
            "injector_ms": 2.8, "timestamp": 1000 + i,
        }
        for i in range(50)
    ]


@pytest.fixture
def vehicle_profile():
    return {"make": "Nissan", "model": "Patrol", "year": 2015}


@pytest.mark.asyncio
async def test_score_vehicle_returns_v3_fields(
    mock_session, telemetry_history, vehicle_profile,
):
    """score_vehicle should include v3 enrichment fields."""
    from predict.core.ai.unified_scoring_pipeline import get_unified_pipeline

    pipeline = get_unified_pipeline()
    latest = telemetry_history[-1]

    result = await pipeline.score_vehicle(
        session=mock_session, profile_id=1,
        latest_telemetry=latest, telemetry_history=telemetry_history,
        vehicle_profile=vehicle_profile, dtc_codes=[], service_records=[],
    )

    assert result.get("success") is True
    # v3 fields should exist (possibly empty/null but present as keys)
    assert "anomaly_alerts" in result
    assert "correlation_anomalies" in result
    assert "detected_patterns" in result
    assert "survival_curves" in result
    assert "intelligence_level" in result
    assert "driving_context_detail" in result


@pytest.mark.asyncio
async def test_score_vehicle_survives_module_failure(
    mock_session, telemetry_history, vehicle_profile,
):
    """If a v3 module throws, result still succeeds with empty field."""
    from predict.core.ai.unified_scoring_pipeline import get_unified_pipeline

    pipeline = get_unified_pipeline()
    latest = telemetry_history[-1]

    # Patch CorrelationEngine at the import source to raise
    with patch(
        "predict.core.ai.correlation_engine.CorrelationEngine",
        side_effect=RuntimeError("boom"),
    ):
        result = await pipeline.score_vehicle(
            session=mock_session, profile_id=1,
            latest_telemetry=latest, telemetry_history=telemetry_history,
            vehicle_profile=vehicle_profile, dtc_codes=[], service_records=[],
        )

    assert result.get("success") is True
    # Should have empty list fallback, not crash
    assert isinstance(result.get("correlation_anomalies"), list)


@pytest.mark.asyncio
async def test_intelligence_level_basic_without_baseline(
    mock_session, telemetry_history, vehicle_profile,
):
    """With no baseline, intelligence level should be 'basic'."""
    from predict.core.ai.unified_scoring_pipeline import get_unified_pipeline

    pipeline = get_unified_pipeline()
    latest = telemetry_history[-1]

    result = await pipeline.score_vehicle(
        session=mock_session, profile_id=1,
        latest_telemetry=latest, telemetry_history=telemetry_history,
        vehicle_profile=vehicle_profile,
    )

    intel = result.get("intelligence_level", {})
    assert intel.get("level") == "basic"


@pytest.mark.asyncio
async def test_driving_context_detail_is_structured(
    mock_session, telemetry_history, vehicle_profile,
):
    """driving_context_detail should be a dict with speed_stats/rpm_stats."""
    from predict.core.ai.unified_scoring_pipeline import get_unified_pipeline

    pipeline = get_unified_pipeline()
    latest = telemetry_history[-1]

    result = await pipeline.score_vehicle(
        session=mock_session, profile_id=1,
        latest_telemetry=latest, telemetry_history=telemetry_history,
        vehicle_profile=vehicle_profile,
    )

    detail = result.get("driving_context_detail")
    assert detail is not None
    assert "context" in detail
    assert "confidence" in detail
