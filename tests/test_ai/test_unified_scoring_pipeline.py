"""Tests for the unified scoring pipeline — weighted ensemble of all AI scorers."""

import pytest
from unittest.mock import AsyncMock, patch

from predict.core.ai.unified_scoring_pipeline import (
    UnifiedScoringPipeline,
    COMPONENT_IDS,
    CAUSAL_EDGES,
)


# ---------------------------------------------------------------------------
# Component constants
# ---------------------------------------------------------------------------


def test_component_ids_length():
    assert len(COMPONENT_IDS) == 10


def test_causal_edges_cover_all_components():
    """Every component must appear as a key in CAUSAL_EDGES."""
    for comp in COMPONENT_IDS:
        assert comp in CAUSAL_EDGES, f"{comp} missing from CAUSAL_EDGES"


# ---------------------------------------------------------------------------
# Weight computation
# ---------------------------------------------------------------------------


def test_compute_weights_cold_start_only():
    pipeline = UnifiedScoringPipeline()
    weights = pipeline._compute_weights(
        cold_start={"engine_oil": 85}, lstm=None, xgb=None, survival=None,
    )
    assert weights["cold_start"] > 0.5
    assert "lstm" not in weights
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_compute_weights_full_ensemble():
    pipeline = UnifiedScoringPipeline()
    weights = pipeline._compute_weights(
        cold_start={"engine_oil": 85},
        lstm={"engine_oil": 80},
        xgb={"engine_oil": 75},
        survival={"engine_oil": {"p50_days": 90}},
    )
    assert "lstm" in weights and "xgboost" in weights
    assert "survival" in weights and "cold_start" in weights
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_compute_weights_partial_ensemble():
    """Only cold_start + lstm available."""
    pipeline = UnifiedScoringPipeline()
    weights = pipeline._compute_weights(
        cold_start={"engine_oil": 85},
        lstm={"engine_oil": 80},
        xgb=None,
        survival=None,
    )
    assert "lstm" in weights
    assert "xgboost" not in weights
    assert "survival" not in weights
    assert abs(sum(weights.values()) - 1.0) < 0.01


def test_compute_weights_exception_treated_as_none():
    """A scorer that returned an Exception is treated the same as None."""
    pipeline = UnifiedScoringPipeline()
    weights = pipeline._compute_weights(
        cold_start={"engine_oil": 85},
        lstm=RuntimeError("boom"),
        xgb=None,
        survival=None,
    )
    assert "lstm" not in weights
    assert abs(sum(weights.values()) - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Causal propagation
# ---------------------------------------------------------------------------


def test_causal_propagation():
    pipeline = UnifiedScoringPipeline()
    scores = {
        "coolant_system": 30,
        "engine_oil": 90,
        "spark_plugs": 85,
        "battery": 95,
        "brakes": 90,
        "transmission_fluid": 88,
        "catalytic_converter": 92,
        "o2_sensors": 87,
        "air_filter": 80,
        "fuel_system": 85,
    }
    propagated = pipeline._propagate_causal(scores)
    # coolant_system at 30 should drag down engine_oil and spark_plugs
    assert propagated["engine_oil"] < 90
    assert propagated["spark_plugs"] < 85
    # brakes has no incoming edges from a failing component, stays the same
    assert propagated["brakes"] == 90


def test_causal_propagation_no_penalty_when_healthy():
    """When all sources are healthy (>=50), no penalty is applied."""
    pipeline = UnifiedScoringPipeline()
    scores = {comp: 90 for comp in COMPONENT_IDS}
    propagated = pipeline._propagate_causal(scores)
    for comp in COMPONENT_IDS:
        assert propagated[comp] == 90


# ---------------------------------------------------------------------------
# Ensemble voting
# ---------------------------------------------------------------------------


def test_ensemble_vote_cold_start_only():
    pipeline = UnifiedScoringPipeline()
    cold_start = {c: 80 for c in COMPONENT_IDS}
    result = pipeline._ensemble_vote(
        cold_start=cold_start, lstm=None, xgb=None, survival=None,
        weights={"cold_start": 1.0},
    )
    for comp in COMPONENT_IDS:
        assert result[comp] == 80


def test_ensemble_vote_weighted_average():
    pipeline = UnifiedScoringPipeline()
    cold_start = {c: 90 for c in COMPONENT_IDS}
    lstm = {c: 70 for c in COMPONENT_IDS}
    result = pipeline._ensemble_vote(
        cold_start=cold_start, lstm=lstm, xgb=None, survival=None,
        weights={"cold_start": 0.3, "lstm": 0.7},
    )
    # 0.3*90 + 0.7*70 = 27 + 49 = 76
    for comp in COMPONENT_IDS:
        assert abs(result[comp] - 76.0) < 0.1


# ---------------------------------------------------------------------------
# Full pipeline (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cold_start_only_scoring():
    pipeline = UnifiedScoringPipeline()
    mock_session = AsyncMock()

    # Mock the cold-start predictor to return a known result
    mock_cs_result = {
        "success": True,
        "health_score": 82,
        "components": {
            "battery": {"health_pct": 95},
            "coolant": {"health_pct": 88},
            "engine": {"health_pct": 80},
            "fuel_pump": {"health_pct": 85},
            "spark_plugs": {"health_pct": 75},
            "o2_sensor": {"health_pct": 82},
            "catalytic_converter": {"health_pct": 90},
            "maf_sensor": {"health_pct": 87},
            "transmission_fluid": {"health_pct": 78},
            "alternator": {"health_pct": 92},
        },
    }

    with patch.object(
        pipeline, "_score_cold_start", new_callable=AsyncMock, return_value=mock_cs_result
    ), patch.object(
        pipeline, "_get_ambient_temp", new_callable=AsyncMock, return_value=35.0
    ), patch.object(
        pipeline, "_get_baseline", new_callable=AsyncMock, return_value=None
    ):
        result = await pipeline.score_vehicle(
            session=mock_session,
            profile_id=1,
            latest_telemetry={"rpm": 800, "coolant_temp": 92, "battery_voltage": 14.1},
            telemetry_history=[],
            vehicle_profile={"make": "Nissan", "model": "Patrol", "year": 2019},
        )

    assert result is not None
    assert "components" in result
    assert len(result["components"]) == 10
    assert result["scoring_weights"]["cold_start"] > 0.5


@pytest.mark.asyncio
async def test_ambient_temp_used():
    pipeline = UnifiedScoringPipeline()

    mock_cs_result = {
        "success": True,
        "health_score": 80,
        "components": {c: {"health_pct": 80} for c in [
            "battery", "coolant", "engine", "fuel_pump", "spark_plugs",
            "o2_sensor", "catalytic_converter", "maf_sensor",
            "transmission_fluid", "alternator",
        ]},
    }

    with patch.object(
        pipeline, "_score_cold_start", new_callable=AsyncMock, return_value=mock_cs_result
    ), patch.object(
        pipeline, "_get_ambient_temp", new_callable=AsyncMock, return_value=45.0
    ), patch.object(
        pipeline, "_get_baseline", new_callable=AsyncMock, return_value=None
    ):
        result = await pipeline.score_vehicle(
            session=AsyncMock(),
            profile_id=1,
            latest_telemetry={"rpm": 800, "coolant_temp": 95},
            telemetry_history=[],
            vehicle_profile={"make": "Nissan", "model": "Patrol", "year": 2019},
        )

    assert result["ambient_temp"] == 45.0


@pytest.mark.asyncio
async def test_scorer_failure_is_graceful():
    """If cold-start raises, pipeline returns a degraded but valid result."""
    pipeline = UnifiedScoringPipeline()

    with patch.object(
        pipeline, "_score_cold_start", new_callable=AsyncMock,
        side_effect=RuntimeError("predictor crashed"),
    ), patch.object(
        pipeline, "_get_ambient_temp", new_callable=AsyncMock, return_value=35.0
    ), patch.object(
        pipeline, "_get_baseline", new_callable=AsyncMock, return_value=None
    ):
        result = await pipeline.score_vehicle(
            session=AsyncMock(),
            profile_id=1,
            latest_telemetry={"rpm": 800},
            telemetry_history=[],
            vehicle_profile={"make": "Nissan", "model": "Patrol", "year": 2019},
        )

    # Should still return a valid structure with fallback scores
    assert result is not None
    assert "components" in result
    assert len(result["components"]) == 10


@pytest.mark.asyncio
async def test_driving_context_detection():
    pipeline = UnifiedScoringPipeline()
    # Highway driving: speed > 80
    ctx = pipeline._classify_driving({"speed": 110, "rpm": 2500})
    assert ctx == "highway"

    # Aggressive driving: rpm > 3500
    ctx = pipeline._classify_driving({"speed": 60, "rpm": 4000})
    assert ctx == "aggressive"

    # City driving: default
    ctx = pipeline._classify_driving({"speed": 40, "rpm": 1500})
    assert ctx == "city"

    # Idle
    ctx = pipeline._classify_driving({"speed": 0, "rpm": 750})
    assert ctx == "idle"
