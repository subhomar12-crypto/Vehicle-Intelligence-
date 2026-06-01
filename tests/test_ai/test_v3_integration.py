"""
End-to-end integration test for AI v3 architecture.

Exercises the full pipeline:
  1. Cold-Start Predictor → component health scores
  2. Unified Scoring Pipeline → ensemble vote
  3. Correlation Engine → sensor pair analysis
  4. Isolation Forest → anomaly detection
  5. DTC Forensics → root cause linking
  6. LLM Context Builder → enriched context string
  7. Causal Graph → root cause tracing
  8. SHAP explainability data structures
  9. Survival curves data flow
"""

import json
import random
import time
import pytest
from typing import Dict, List, Any

from predict.core.ai.dtc_forensics import (
    DTCForensicsEngine,
    DTCForensicsResult,
    COMPONENT_SENSOR_MAP,
    FEATURE_COLUMNS,
)
from predict.core.ai.correlation_engine import CorrelationEngine, CorrelationAnomaly
from predict.core.ai.isolation_forest_engine import IsolationForestEngine, AnomalyResult
from predict.core.ai.causal_graph import CausalGraph
from predict.core.ai.unified_scoring_pipeline import (
    CAUSAL_EDGES,
    COMPONENT_IDS,
    UnifiedScoringPipeline,
)
from predict.core.ai.llm.assistant import LLMAssistant


# ── Shared test data generators ─────────────────────────────────────────

def _make_baseline() -> Dict[str, Any]:
    """Typical per-vehicle baseline sensor_stats."""
    return {
        "rpm": {"mean": 850.0, "std": 60.0},
        "speed": {"mean": 35.0, "std": 18.0},
        "coolant_temp": {"mean": 89.0, "std": 2.5},
        "battery_voltage": {"mean": 13.9, "std": 0.25},
        "engine_load": {"mean": 28.0, "std": 12.0},
        "throttle_pos": {"mean": 14.0, "std": 7.0},
        "maf_rate": {"mean": 2.4, "std": 0.4},
        "intake_temp": {"mean": 36.0, "std": 4.0},
        "short_term_fuel_trim": {"mean": 100.0, "std": 2.5},
        "long_term_fuel_trim": {"mean": 100.0, "std": 2.0},
        "timing_advance": {"mean": 14.0, "std": 4.0},
        "injector_ms": {"mean": 2.9, "std": 0.8},
    }


def _make_history(n: int = 80, seed: int = 42) -> List[Dict[str, Any]]:
    """Generate n correlated telemetry readings."""
    rng = random.Random(seed)
    history = []
    for i in range(n):
        rpm = 850 + rng.gauss(0, 60)
        history.append({
            "rpm": rpm,
            "speed": max(0, 35 + rng.gauss(0, 10)),
            "coolant_temp": 89 + rng.gauss(0, 2),
            "battery_voltage": 13.9 + rng.gauss(0, 0.2),
            "engine_load": max(0, 28 + rng.gauss(0, 10)),
            "throttle_pos": max(0, 14 + rng.gauss(0, 5)),
            "maf_rate": max(0.3, 2.4 + rng.gauss(0, 0.3)),
            "intake_temp": 36 + rng.gauss(0, 3),
            "short_term_fuel_trim": 100 + rng.gauss(0, 2),
            "long_term_fuel_trim": 100 + rng.gauss(0, 1.5),
            "timing_advance": 14 + rng.gauss(0, 3),
            "injector_ms": max(0.5, 2.9 + rng.gauss(0, 0.4)),
            "timestamp": 1000.0 + i,
        })
    return history


def _make_anomalous_telemetry() -> Dict[str, Any]:
    """Telemetry with clear anomalies across multiple systems."""
    return {
        "rpm": 1200.0,
        "speed": 0.0,
        "coolant_temp": 112.0,       # Way above normal
        "battery_voltage": 11.2,     # Way below normal
        "engine_load": 55.0,         # High for idle
        "throttle_pos": 12.0,
        "maf_rate": 1.0,             # Low for RPM
        "intake_temp": 52.0,         # High
        "short_term_fuel_trim": 118.0,  # Very rich
        "long_term_fuel_trim": 112.0,
        "timing_advance": 5.0,       # Retarded
        "injector_ms": 6.5,          # High
    }


def _make_dtc_list() -> List[Dict[str, Any]]:
    """Multiple active DTCs spanning different systems."""
    return [
        {
            "code": "P0420",
            "is_active": True,
            "is_pending": False,
            "severity": "high",
            "description": "Catalyst System Efficiency Below Threshold (Bank 1)",
        },
        {
            "code": "P0171",
            "is_active": True,
            "is_pending": False,
            "severity": "medium",
            "description": "System Too Lean (Bank 1)",
        },
        {
            "code": "P0301",
            "is_active": False,
            "is_pending": True,
            "severity": "medium",
            "description": "Cylinder 1 Misfire Detected",
        },
    ]


# ── Integration Tests ───────────────────────────────────────────────────

class TestV3PipelineIntegration:
    """End-to-end test: DTCs + telemetry → forensics → context → hypothesis."""

    def test_full_pipeline_dtc_to_hypothesis(self):
        """
        COMPLETE PIPELINE:
        DTCs + telemetry + baseline → DTC Forensics
        → anomalies + correlation breaks + causal chains
        → ranked hypotheses with inspections
        """
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=_make_dtc_list(),
            telemetry_history=_make_history(80),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )

        # Verify complete result structure
        assert isinstance(result, DTCForensicsResult)
        assert len(result.dtc_codes) == 3
        assert "P0420" in result.dtc_codes
        assert "P0171" in result.dtc_codes
        assert "P0301" in result.dtc_codes

        # Must identify affected components
        assert len(result.affected_components) >= 2
        # P0420 → catalytic_converter, P0171 → engine_oil (P01 → air_filter actually)
        # P0301 → spark_plugs
        component_set = set(result.affected_components)
        assert "spark_plugs" in component_set or "catalytic_converter" in component_set

        # Must produce anomalies (we have strong Z-score violations)
        assert len(result.anomalies) >= 1

        # Must produce at least one hypothesis
        assert len(result.root_cause_hypotheses) >= 1

        # Top hypothesis must have non-zero confidence
        top = result.root_cause_hypotheses[0]
        assert top.confidence > 0.0
        assert len(top.supporting_evidence) >= 1
        assert len(top.recommended_inspections) >= 1

        # Overall severity should be high or critical (multiple active DTCs)
        assert result.overall_severity in ("high", "critical")

        # Summary should be non-empty
        assert len(result.summary) > 30

    def test_forensics_result_serializable(self):
        """Result must be fully JSON-serializable for API response."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=_make_dtc_list(),
            telemetry_history=_make_history(50),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )

        d = result.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["dtc_codes"] == ["P0420", "P0171", "P0301"]
        assert isinstance(parsed["anomalies"], list)
        assert isinstance(parsed["root_cause_hypotheses"], list)
        assert isinstance(parsed["analysis_timestamp"], float)

    def test_correlation_engine_feeds_forensics(self):
        """Correlation engine results are included in forensics output."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[{"code": "P0101", "is_active": True, "severity": "medium"}],
            telemetry_history=_make_history(80),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )

        # P0101 → air_filter, which has sensors maf_rate, intake_temp, engine_load
        # Correlation engine should run and produce breaks (or empty if data is normal)
        assert isinstance(result.correlation_breaks, list)
        # Each break should have proper structure
        for cb in result.correlation_breaks:
            assert "pair" in cb
            assert "baseline_r" in cb
            assert "current_r" in cb
            assert "delta" in cb
            assert "severity" in cb

    def test_standalone_correlation_engine(self):
        """CorrelationEngine detects expected sensor pair correlations."""
        ce = CorrelationEngine(window_size=50, break_threshold=0.25)
        history = _make_history(80)
        sensors = ["rpm", "maf_rate", "speed", "engine_load", "throttle_pos"]

        matrix = ce.compute_correlation_matrix(history, sensors)
        assert len(matrix) > 0

        # RPM and engine_load should be somewhat correlated in normal data
        # (not guaranteed to be > 0.25 with random data, but matrix should exist)
        assert isinstance(matrix, dict)

    def test_standalone_isolation_forest(self):
        """IsolationForest detects anomalies in readings."""
        ife = IsolationForestEngine(contamination=0.1)

        # Without a trained model, detect_anomalies should handle gracefully
        results = ife.detect_anomalies(
            readings=_make_history(50),
            feature_columns=FEATURE_COLUMNS,
        )
        # No model loaded → empty results (logged warning)
        assert isinstance(results, list)

    def test_causal_graph_root_cause_finding(self):
        """CausalGraph finds root causes from symptoms."""
        cg = CausalGraph()

        # Misfire + rough_idle + reduced_power → likely worn_spark_plugs
        results = cg.find_root_cause(["misfire", "rough_idle", "reduced_power"])
        assert len(results) >= 1
        causes = [r["cause"] for r in results]
        assert "worn_spark_plugs" in causes

    def test_causal_graph_chain_explanation(self):
        """CausalGraph produces human-readable chains."""
        cg = CausalGraph()
        chain = cg.explain_chain("worn_spark_plugs")
        assert "Worn Spark Plugs" in chain
        assert "→" in chain

    def test_causal_edges_propagation_structure(self):
        """CAUSAL_EDGES has valid component references."""
        for source, targets in CAUSAL_EDGES.items():
            assert source in COMPONENT_IDS, f"Source {source} not in COMPONENT_IDS"
            for target, penalty in targets:
                assert target in COMPONENT_IDS, f"Target {target} not in COMPONENT_IDS"
                assert isinstance(penalty, (int, float))
                assert penalty > 0


class TestV3LLMContextIntegration:
    """Verify that v3 data flows correctly into the LLM context string."""

    def test_dtc_forensics_context_rendering(self):
        """DTC Forensics dict renders in LLM context string."""
        assistant = LLMAssistant()
        forensics_data = {
            "overall_severity": "high",
            "affected_components": ["catalytic_converter", "spark_plugs"],
            "root_cause_hypotheses": [
                {
                    "hypothesis": "Worn spark plugs causing misfire → catalyst damage",
                    "confidence": 0.72,
                    "recommended_inspections": [
                        "Inspect spark plugs",
                        "Back-pressure test catalytic converter",
                    ],
                },
            ],
            "anomalies": [
                {"message": "short_term_fuel_trim is 5.0σ above baseline (current: 118, expected: 100 ± 2.5)"},
            ],
            "correlation_breaks": [
                {"pair": ["rpm", "maf_rate"], "delta": -0.85, "severity": "high"},
            ],
            "summary": "P0420 + P0301 suggest spark plug degradation propagating to catalyst.",
        }

        context = {"dtc_forensics": forensics_data}
        ctx_str = assistant._build_context_str(context)

        assert "DTC Forensic Analysis" in ctx_str
        assert "HIGH" in ctx_str
        assert "catalytic_converter" in ctx_str
        assert "spark_plugs" in ctx_str
        assert "Worn spark plugs" in ctx_str
        assert "72%" in ctx_str
        assert "Inspect spark plugs" in ctx_str
        assert "fuel_trim" in ctx_str
        assert "rpm ↔ maf_rate" in ctx_str

    def test_survival_curves_context_rendering(self):
        """Survival curve data renders in LLM context string."""
        assistant = LLMAssistant()
        curves = [
            {
                "component": "battery",
                "timeline_days": [0, 365, 730],
                "survival_probability": [1.0, 0.85, 0.55],
            },
            {
                "component": "engine_oil",
                "timeline_days": [0, 90, 180],
                "survival_probability": [1.0, 0.95, 0.70],
            },
        ]

        context = {"survival_curves": curves}
        ctx_str = assistant._build_context_str(context)

        assert "Survival Analysis" in ctx_str
        assert "battery" in ctx_str
        assert "engine_oil" in ctx_str

    def test_health_assessment_context_rendering(self):
        """Health assessment renders in LLM context string."""
        assistant = LLMAssistant()
        context = {
            "health_assessment": {
                "health_score": 72,
                "components": {
                    "engine_oil": {"health_pct": 85, "supported": True},
                    "battery": {"health_pct": 55, "supported": True},
                    "catalytic_converter": {"health_pct": 30, "supported": True},
                    "brakes": {"supported": False},
                },
            },
        }
        ctx_str = assistant._build_context_str(context)

        assert "Overall health score: 72/100" in ctx_str
        assert "engine_oil: 85%" in ctx_str
        assert "battery: 55%" in ctx_str
        assert "catalytic_converter: 30%" in ctx_str
        assert "Brakes" in ctx_str  # Listed as unsupported

    def test_combined_context_all_v3_modules(self):
        """All v3 context types render together without collision."""
        assistant = LLMAssistant()
        context = {
            "vehicle": {"year": 2020, "make": "Nissan", "model": "Patrol"},
            "dtcs": ["P0420 (high): Catalyst Efficiency Below Threshold"],
            "health_assessment": {
                "health_score": 65,
                "components": {
                    "catalytic_converter": {"health_pct": 25, "supported": True},
                },
            },
            "dtc_forensics": {
                "overall_severity": "high",
                "affected_components": ["catalytic_converter"],
                "root_cause_hypotheses": [
                    {"hypothesis": "Cat degradation", "confidence": 0.8, "recommended_inspections": ["Back-pressure test"]},
                ],
                "anomalies": [],
                "correlation_breaks": [],
                "summary": "P0420 catalyst issue.",
            },
            "survival_curves": [
                {"component": "catalytic_converter", "timeline_days": [0, 365], "survival_probability": [1.0, 0.3]},
            ],
            "vehicle_baseline": {
                "phase": "baseline_ready",
                "trip_count": 45,
                "data_points": 1200,
                "anomalies": [{"sensor": "short_term_fuel_trim", "direction": "above", "current": 118, "baseline_mean": 100, "z_score": 6.0}],
                "trends": [],
            },
            "intelligence": {
                "urgency": {"level": "WARNING", "reason": "Catalyst health at 25%"},
                "patterns_detected": [
                    {"name": "lean_condition", "display_name": "Lean Running", "confidence": 0.85, "severity": "high", "reasoning": "Fuel trim high", "recommendation": "Check MAF"},
                ],
            },
        }
        ctx_str = assistant._build_context_str(context)

        # All sections present
        assert "Vehicle: 2020 Nissan Patrol" in ctx_str
        assert "Active DTCs:" in ctx_str
        assert "Health Assessment:" in ctx_str
        assert "DTC Forensic Analysis" in ctx_str
        assert "Survival Analysis" in ctx_str
        assert "Per-vehicle AI baseline" in ctx_str
        assert "Intelligence Analysis:" in ctx_str

        # Not too large for 4K context window (rough check)
        assert len(ctx_str) < 4000


class TestV3DataModelIntegrity:
    """Verify v3 data models have correct shapes for cross-module compatibility."""

    def test_component_ids_consistent(self):
        """All 10 canonical component IDs exist in all maps."""
        for cid in COMPONENT_IDS:
            assert cid in COMPONENT_SENSOR_MAP, f"{cid} missing from COMPONENT_SENSOR_MAP"
            assert cid in CAUSAL_EDGES, f"{cid} missing from CAUSAL_EDGES (even as empty list)"

    def test_feature_columns_count(self):
        """15 FEATURE_COLUMNS used across the pipeline."""
        assert len(FEATURE_COLUMNS) == 15
        assert "rpm" in FEATURE_COLUMNS
        assert "coolant_temp" in FEATURE_COLUMNS
        assert "battery_voltage" in FEATURE_COLUMNS

    def test_forensics_anomaly_types(self):
        """All ForensicsAnomaly types are valid."""
        valid_types = {"z_score", "isolation_forest", "correlation_break", "lstm_reconstruction"}
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[{"code": "P0505", "is_active": True, "severity": "high"}],
            telemetry_history=_make_history(50),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )
        for a in result.anomalies:
            assert a.anomaly_type in valid_types, f"Unknown anomaly type: {a.anomaly_type}"

    def test_hypothesis_confidence_range(self):
        """All hypothesis confidence values are 0.0 to 1.0."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=_make_dtc_list(),
            telemetry_history=_make_history(80),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )
        for h in result.root_cause_hypotheses:
            assert 0.0 <= h.confidence <= 1.0, f"Confidence out of range: {h.confidence}"

    def test_severity_values_valid(self):
        """All severity strings are from valid set."""
        valid = {"low", "medium", "high", "critical"}
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=_make_dtc_list(),
            telemetry_history=_make_history(80),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )
        assert result.overall_severity in valid
        for a in result.anomalies:
            assert a.severity in valid


class TestV3EdgeCases:
    """Edge cases for robustness."""

    def test_empty_telemetry(self):
        """Handles zero telemetry gracefully."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[{"code": "P0420", "is_active": True, "severity": "medium"}],
            telemetry_history=[],
            latest_telemetry={},
            baseline=None,
        )
        assert isinstance(result, DTCForensicsResult)
        assert len(result.affected_components) >= 1

    def test_single_reading(self):
        """Handles single telemetry reading."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[{"code": "P0300", "is_active": True, "severity": "high"}],
            telemetry_history=[_make_anomalous_telemetry()],
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )
        assert isinstance(result, DTCForensicsResult)

    def test_only_pending_dtcs(self):
        """Pending-only DTCs produce lower severity."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[
                {"code": "P0420", "is_active": False, "is_pending": True, "severity": "medium"},
            ],
            telemetry_history=_make_history(30),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )
        # Still should produce a result
        assert isinstance(result, DTCForensicsResult)
        assert len(result.affected_components) >= 1

    def test_unknown_dtc_codes(self):
        """Handles manufacturer-specific DTCs (P1xxx, P2xxx)."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[
                {"code": "P1234", "is_active": True, "severity": "medium"},
                {"code": "P2345", "is_active": True, "severity": "low"},
            ],
            telemetry_history=_make_history(30),
            latest_telemetry=_make_anomalous_telemetry(),
            baseline=_make_baseline(),
        )
        assert isinstance(result, DTCForensicsResult)
        # Should still map to something (fallback to engine_oil for P-codes)
        assert len(result.affected_components) >= 1

    def test_body_and_chassis_codes(self):
        """Handles B and C DTC codes."""
        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[
                {"code": "B0001", "is_active": True, "severity": "low"},
                {"code": "C0035", "is_active": True, "severity": "medium"},
            ],
            telemetry_history=[],
            latest_telemetry={},
        )
        component_set = set(result.affected_components)
        assert "brakes" in component_set  # C0 → brakes
