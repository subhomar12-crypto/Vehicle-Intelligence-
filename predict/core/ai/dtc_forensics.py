"""
DTC Forensics Engine — Root cause analysis linking DTCs to sensor anomalies.

Connects DTC codes to:
  1. Sensor correlation breaks (via CorrelationEngine)
  2. Isolation Forest anomaly scores
  3. LSTM autoencoder reconstruction errors
  4. Baseline Z-score violations
  5. Causal chain tracing (via CausalGraph + CAUSAL_EDGES)

Produces ranked root-cause hypotheses with confidence scores and
recommended inspections.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from predict.core.ai.causal_graph import CausalGraph
from predict.core.ai.correlation_engine import CorrelationEngine, CorrelationAnomaly
from predict.core.ai.isolation_forest_engine import IsolationForestEngine, AnomalyResult
from predict.core.ai.unified_scoring_pipeline import CAUSAL_EDGES, COMPONENT_IDS

logger = logging.getLogger(__name__)

# ── DTC prefix → canonical component ────────────────────────────────────
DTC_COMPONENT_MAP: Dict[str, str] = {
    "P00": "engine_oil",
    "P01": "air_filter",          # MAF / intake metering
    "P02": "fuel_system",         # Fuel injectors
    "P03": "spark_plugs",         # Ignition / misfire
    "P04": "catalytic_converter", # Emissions
    "P05": "engine_oil",          # Speed / idle
    "P06": "engine_oil",          # ECU
    "P07": "transmission_fluid",  # Transmission
    "P0A": "battery",             # Hybrid / HV battery
    "B0":  "engine_oil",          # Body
    "C0":  "brakes",              # Chassis
    "U0":  "engine_oil",          # CAN network
}

# ── DTC → expected symptoms (for causal graph cross-reference) ──────────
DTC_SYMPTOM_MAP: Dict[str, List[str]] = {
    "P0101": ["inaccurate_air_flow_reading", "poor_fuel_economy", "rough_idle"],
    "P0102": ["inaccurate_air_flow_reading"],
    "P0103": ["inaccurate_air_flow_reading"],
    "P0107": ["inaccurate_air_flow_reading", "engine_hesitation"],
    "P0108": ["inaccurate_air_flow_reading", "engine_hesitation"],
    "P0171": ["lean_fuel_trim", "rough_idle"],
    "P0172": ["rich_fuel_trim"],
    "P0174": ["lean_fuel_trim", "rough_idle"],
    "P0175": ["rich_fuel_trim"],
    "P0300": ["misfire", "rough_idle", "reduced_power"],
    "P0301": ["misfire"],
    "P0302": ["misfire"],
    "P0303": ["misfire"],
    "P0304": ["misfire"],
    "P0305": ["misfire"],
    "P0306": ["misfire"],
    "P0420": ["high_emissions", "reduced_power", "p0420_code"],
    "P0430": ["high_emissions", "reduced_power"],
    "P0440": ["high_emissions"],
    "P0441": ["high_emissions"],
    "P0442": ["high_emissions"],
    "P0443": ["high_emissions"],
    "P0500": ["inaccurate_speed_reading"],
    "P0505": ["erratic_idle", "rough_idle"],
    "P0700": ["harsh_shifting", "transmission_slippage"],
    "P0715": ["harsh_shifting"],
    "P0720": ["harsh_shifting", "delayed_engagement"],
    "P0730": ["transmission_slippage", "harsh_shifting"],
}

# ── Sensor groups affected by each component ────────────────────────────
COMPONENT_SENSOR_MAP: Dict[str, List[str]] = {
    "engine_oil":           ["rpm", "engine_load", "coolant_temp"],
    "coolant_system":       ["coolant_temp", "intake_temp", "engine_load"],
    "battery":              ["battery_voltage", "rpm"],
    "brakes":               ["speed"],
    "transmission_fluid":   ["speed", "rpm"],
    "spark_plugs":          ["rpm", "engine_load", "short_term_fuel_trim"],
    "catalytic_converter":  ["short_term_fuel_trim", "long_term_fuel_trim"],
    "o2_sensors":           ["short_term_fuel_trim", "long_term_fuel_trim"],
    "air_filter":           ["maf_rate", "intake_temp", "engine_load"],
    "fuel_system":          ["injector_ms", "short_term_fuel_trim", "maf_rate"],
}

# ── Recommended inspections per component ───────────────────────────────
INSPECTION_MAP: Dict[str, List[str]] = {
    "engine_oil":           ["Check oil level and condition", "Inspect for oil leaks", "Verify oil pressure"],
    "coolant_system":       ["Check coolant level", "Inspect thermostat", "Test radiator cap pressure", "Check water pump"],
    "battery":              ["Load-test battery", "Check alternator output", "Inspect terminals"],
    "brakes":               ["Measure pad thickness", "Inspect rotors", "Check brake fluid level"],
    "transmission_fluid":   ["Check ATF level/color", "Inspect for leaks", "Check shift solenoids"],
    "spark_plugs":          ["Inspect/replace spark plugs", "Check ignition coils", "Verify plug gap"],
    "catalytic_converter":  ["Back-pressure test", "Upstream/downstream O2 comparison", "Check for rattling"],
    "o2_sensors":           ["Live-data O2 waveform check", "Compare bank 1 vs bank 2", "Check wiring/connectors"],
    "air_filter":           ["Inspect air filter element", "Check MAF sensor", "Verify intake for leaks"],
    "fuel_system":          ["Check fuel pressure", "Test injector balance", "Inspect fuel lines"],
}

# ── Sensor thresholds for Z-score flagging ──────────────────────────────
# 15 FEATURE_COLUMNS used across the AI pipeline
FEATURE_COLUMNS: List[str] = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "maf_rate", "intake_temp", "short_term_fuel_trim",
    "long_term_fuel_trim", "timing_advance", "injector_ms", "fuel_trim_b2",
    "accel_pedal", "ambient_temp",
]

# Map sensors back to the component(s) they reflect
SENSOR_COMPONENT_MAP: Dict[str, List[str]] = {}
for _comp, _sensors in COMPONENT_SENSOR_MAP.items():
    for _s in _sensors:
        SENSOR_COMPONENT_MAP.setdefault(_s, []).append(_comp)


# ── Data classes ────────────────────────────────────────────────────────

@dataclass
class ForensicsAnomaly:
    """A sensor anomaly linked to a DTC."""
    sensor: str
    component: str
    anomaly_type: str       # "z_score", "isolation_forest", "correlation_break", "lstm_reconstruction"
    severity: str           # "low", "medium", "high"
    value: float            # Current reading
    expected: float         # Baseline mean or expected value
    deviation: float        # Z-score or reconstruction error
    message: str


@dataclass
class CausalChain:
    """A traced causal chain from root cause to symptom."""
    root_cause: str
    chain: List[str]        # [root, intermediate..., symptom]
    confidence: float       # 0.0 – 1.0
    explanation: str


@dataclass
class RootCauseHypothesis:
    """Ranked hypothesis for a DTC's root cause."""
    component: str
    hypothesis: str
    confidence: float       # 0.0 – 1.0
    supporting_evidence: List[str]
    causal_chains: List[CausalChain] = field(default_factory=list)
    recommended_inspections: List[str] = field(default_factory=list)


@dataclass
class DTCForensicsResult:
    """Complete forensic analysis for one or more DTCs."""
    dtc_codes: List[str]
    affected_components: List[str]
    anomalies: List[ForensicsAnomaly]
    correlation_breaks: List[Dict[str, Any]]
    root_cause_hypotheses: List[RootCauseHypothesis]
    overall_severity: str   # "low", "medium", "high", "critical"
    summary: str
    analysis_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe dict."""
        return {
            "dtc_codes": self.dtc_codes,
            "affected_components": self.affected_components,
            "anomalies": [asdict(a) for a in self.anomalies],
            "correlation_breaks": self.correlation_breaks,
            "root_cause_hypotheses": [
                {
                    "component": h.component,
                    "hypothesis": h.hypothesis,
                    "confidence": round(h.confidence, 3),
                    "supporting_evidence": h.supporting_evidence,
                    "causal_chains": [asdict(c) for c in h.causal_chains],
                    "recommended_inspections": h.recommended_inspections,
                }
                for h in self.root_cause_hypotheses
            ],
            "overall_severity": self.overall_severity,
            "summary": self.summary,
            "analysis_timestamp": self.analysis_timestamp,
        }


# ── DTCForensicsEngine ─────────────────────────────────────────────────

class DTCForensicsEngine:
    """
    Links DTC codes to sensor anomalies and produces root-cause hypotheses.

    Usage::

        engine = DTCForensicsEngine()
        result = engine.analyze(
            dtc_codes=[{"code": "P0420", "is_active": True}],
            telemetry_history=[...],
            latest_telemetry={...},
            baseline={"sensor_stats": {"rpm": {"mean": 800, "std": 50}, ...}},
        )
    """

    def __init__(self):
        self.correlation_engine = CorrelationEngine(window_size=100, break_threshold=0.25)
        self.isolation_forest = IsolationForestEngine(contamination=0.1)
        self.causal_graph = CausalGraph()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        dtc_codes: List[Dict[str, Any]],
        telemetry_history: List[Dict[str, Any]],
        latest_telemetry: Dict[str, Any],
        baseline: Optional[Dict[str, Any]] = None,
    ) -> DTCForensicsResult:
        """
        Run full DTC forensic analysis.

        Args:
            dtc_codes: List of DTC dicts ``{code, is_active, is_pending, severity, description}``
            telemetry_history: Recent telemetry readings (list of sensor dicts)
            latest_telemetry: Most recent single reading
            baseline: VehicleBaseline ``sensor_stats`` dict (per-sensor mean/std)

        Returns:
            DTCForensicsResult with ranked root-cause hypotheses
        """
        if not dtc_codes:
            return DTCForensicsResult(
                dtc_codes=[],
                affected_components=[],
                anomalies=[],
                correlation_breaks=[],
                root_cause_hypotheses=[],
                overall_severity="low",
                summary="No DTC codes to analyze.",
            )

        codes = [d.get("code", "").upper() for d in dtc_codes]

        # Step 1: Map DTCs → affected components
        affected = self._map_dtcs_to_components(dtc_codes)

        # Step 2: Detect sensor anomalies
        anomalies: List[ForensicsAnomaly] = []

        # 2a: Baseline Z-score violations
        if baseline:
            z_anomalies = self._detect_zscore_violations(
                latest_telemetry, baseline, affected,
            )
            anomalies.extend(z_anomalies)

        # 2b: Isolation Forest anomalies
        if len(telemetry_history) >= 20:
            iso_anomalies = self._detect_isolation_forest_anomalies(
                telemetry_history, affected,
            )
            anomalies.extend(iso_anomalies)

        # Step 3: Correlation breaks
        corr_breaks = self._detect_correlation_breaks(telemetry_history, affected)

        # Step 4: Causal chain tracing
        causal_chains = self._trace_causal_chains(codes, anomalies, corr_breaks)

        # Step 5: Build root-cause hypotheses
        hypotheses = self._build_hypotheses(
            dtc_codes, affected, anomalies, corr_breaks, causal_chains,
        )

        # Step 6: Overall severity
        severity = self._compute_overall_severity(dtc_codes, anomalies, corr_breaks)

        # Step 7: Summary
        summary = self._generate_summary(codes, affected, anomalies, hypotheses, severity)

        return DTCForensicsResult(
            dtc_codes=codes,
            affected_components=list(affected),
            anomalies=anomalies,
            correlation_breaks=[
                {
                    "pair": list(cb.pair),
                    "baseline_r": round(cb.baseline_r, 3),
                    "current_r": round(cb.current_r, 3),
                    "delta": round(cb.delta, 3),
                    "severity": cb.severity,
                    "interpretation": cb.interpretation,
                }
                for cb in corr_breaks
            ],
            root_cause_hypotheses=hypotheses,
            overall_severity=severity,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Step 1: DTC → component mapping
    # ------------------------------------------------------------------

    def _map_dtcs_to_components(
        self, dtc_codes: List[Dict[str, Any]],
    ) -> List[str]:
        """Map DTC codes to canonical component IDs."""
        affected: set[str] = set()

        for dtc in dtc_codes:
            code = dtc.get("code", "").upper()
            component = None

            # Try longest-prefix-first for specificity
            for prefix in sorted(DTC_COMPONENT_MAP.keys(), key=len, reverse=True):
                if code.startswith(prefix):
                    component = prefix
                    break

            if component:
                affected.add(DTC_COMPONENT_MAP[component])
            else:
                # Fallback by letter
                if code.startswith("P"):
                    affected.add("engine_oil")
                elif code.startswith("C"):
                    affected.add("brakes")
                elif code.startswith("U"):
                    affected.add("engine_oil")

        return sorted(affected)

    # ------------------------------------------------------------------
    # Step 2a: Baseline Z-score violations
    # ------------------------------------------------------------------

    def _detect_zscore_violations(
        self,
        latest: Dict[str, Any],
        baseline: Dict[str, Any],
        affected_components: List[str],
    ) -> List[ForensicsAnomaly]:
        """Flag sensors whose current value deviates > 2σ from baseline."""
        sensor_stats = baseline
        if isinstance(sensor_stats, str):
            try:
                sensor_stats = json.loads(sensor_stats)
            except (json.JSONDecodeError, TypeError):
                return []

        # Some baselines wrap stats under "sensor_stats" key
        if "sensor_stats" in sensor_stats:
            sensor_stats = sensor_stats["sensor_stats"]

        anomalies: List[ForensicsAnomaly] = []

        # Only check sensors related to affected components
        relevant_sensors = set()
        for comp in affected_components:
            relevant_sensors.update(COMPONENT_SENSOR_MAP.get(comp, []))

        for sensor in relevant_sensors:
            stats = sensor_stats.get(sensor)
            if not stats:
                continue

            mean = stats.get("mean", 0.0)
            std = stats.get("std", 0.0)
            if std < 1e-6:
                continue  # Skip zero-variance sensors

            current = latest.get(sensor)
            if current is None:
                continue

            try:
                current = float(current)
            except (ValueError, TypeError):
                continue

            z = abs(current - mean) / std

            if z >= 2.0:
                severity = "high" if z >= 3.5 else ("medium" if z >= 2.5 else "low")
                direction = "above" if current > mean else "below"
                components = SENSOR_COMPONENT_MAP.get(sensor, ["unknown"])

                anomalies.append(ForensicsAnomaly(
                    sensor=sensor,
                    component=components[0],
                    anomaly_type="z_score",
                    severity=severity,
                    value=round(current, 2),
                    expected=round(mean, 2),
                    deviation=round(z, 2),
                    message=(
                        f"{sensor} is {z:.1f}σ {direction} baseline "
                        f"(current: {current:.1f}, expected: {mean:.1f} ± {std:.1f})"
                    ),
                ))

        return anomalies

    # ------------------------------------------------------------------
    # Step 2b: Isolation Forest anomalies
    # ------------------------------------------------------------------

    def _detect_isolation_forest_anomalies(
        self,
        telemetry_history: List[Dict[str, Any]],
        affected_components: List[str],
    ) -> List[ForensicsAnomaly]:
        """Run Isolation Forest on recent telemetry and flag anomalies."""
        try:
            results: List[AnomalyResult] = self.isolation_forest.detect_anomalies(
                readings=telemetry_history,
                feature_columns=FEATURE_COLUMNS,
            )
        except Exception as e:
            logger.warning("Isolation Forest failed: %s", e)
            return []

        anomalies: List[ForensicsAnomaly] = []
        relevant_sensors = set()
        for comp in affected_components:
            relevant_sensors.update(COMPONENT_SENSOR_MAP.get(comp, []))

        for result in results:
            if result.anomaly_score < 0.6:
                continue  # Only flag significant anomalies

            # Check if this anomaly involves sensors related to our DTCs
            related = set(result.sensors) & relevant_sensors
            if not related:
                continue

            for sensor in related:
                components = SENSOR_COMPONENT_MAP.get(sensor, ["unknown"])
                anomalies.append(ForensicsAnomaly(
                    sensor=sensor,
                    component=components[0],
                    anomaly_type="isolation_forest",
                    severity=result.severity,
                    value=round(result.anomaly_score, 3),
                    expected=0.5,
                    deviation=round(result.anomaly_score, 3),
                    message=(
                        f"Isolation Forest flagged {sensor} with anomaly score "
                        f"{result.anomaly_score:.2f} ({result.severity})"
                    ),
                ))

        return anomalies

    # ------------------------------------------------------------------
    # Step 3: Correlation breaks
    # ------------------------------------------------------------------

    def _detect_correlation_breaks(
        self,
        telemetry_history: List[Dict[str, Any]],
        affected_components: List[str],
    ) -> List[CorrelationAnomaly]:
        """Detect sensor correlation breaks related to affected components."""
        if len(telemetry_history) < 20:
            return []

        try:
            all_breaks = self.correlation_engine.analyze_expected_pairs(
                readings=telemetry_history,
            )
        except Exception as e:
            logger.warning("Correlation analysis failed: %s", e)
            return []

        # Filter to breaks involving sensors of affected components
        relevant_sensors = set()
        for comp in affected_components:
            relevant_sensors.update(COMPONENT_SENSOR_MAP.get(comp, []))

        filtered: List[CorrelationAnomaly] = []
        for cb in all_breaks:
            if cb.pair[0] in relevant_sensors or cb.pair[1] in relevant_sensors:
                filtered.append(cb)

        return filtered

    # ------------------------------------------------------------------
    # Step 4: Causal chain tracing
    # ------------------------------------------------------------------

    def _trace_causal_chains(
        self,
        dtc_codes: List[str],
        anomalies: List[ForensicsAnomaly],
        corr_breaks: List[CorrelationAnomaly],
    ) -> List[CausalChain]:
        """
        Trace causal chains using two mechanisms:
        1. CausalGraph: DTC symptoms → root causes
        2. CAUSAL_EDGES (component graph): upstream component failures → downstream effects
        """
        chains: List[CausalChain] = []

        # ── Mechanism 1: CausalGraph symptom-based ──
        # Collect symptoms from DTC symptom map
        all_symptoms: List[str] = []
        for code in dtc_codes:
            all_symptoms.extend(DTC_SYMPTOM_MAP.get(code, []))

        if all_symptoms:
            try:
                root_causes = self.causal_graph.find_root_cause(all_symptoms)
                for rc in root_causes[:5]:
                    cause = rc["cause"]
                    explanation = self.causal_graph.explain_chain(cause)
                    chains.append(CausalChain(
                        root_cause=cause,
                        chain=[cause] + rc.get("matched_symptoms", []),
                        confidence=rc.get("confidence", 0.0),
                        explanation=explanation,
                    ))
            except Exception as e:
                logger.warning("CausalGraph tracing failed: %s", e)

        # ── Mechanism 2: CAUSAL_EDGES component propagation ──
        # Find upstream components that could be dragging down affected ones
        affected_set = set()
        for a in anomalies:
            affected_set.add(a.component)
        for code in dtc_codes:
            for prefix in sorted(DTC_COMPONENT_MAP.keys(), key=len, reverse=True):
                if code.startswith(prefix):
                    affected_set.add(DTC_COMPONENT_MAP[prefix])
                    break

        for source, targets in CAUSAL_EDGES.items():
            target_names = [t[0] for t in targets]
            # Check if any affected component is downstream of this source
            overlap = affected_set & set(target_names)
            if overlap and source not in affected_set:
                for downstream in overlap:
                    chains.append(CausalChain(
                        root_cause=source,
                        chain=[source, downstream],
                        confidence=0.3,  # Lower confidence — speculative upstream
                        explanation=(
                            f"If {_fmt(source)} is degrading, it can drag "
                            f"down {_fmt(downstream)} via causal propagation"
                        ),
                    ))

        return chains

    # ------------------------------------------------------------------
    # Step 5: Build root-cause hypotheses
    # ------------------------------------------------------------------

    def _build_hypotheses(
        self,
        dtc_codes: List[Dict[str, Any]],
        affected_components: List[str],
        anomalies: List[ForensicsAnomaly],
        corr_breaks: List[CorrelationAnomaly],
        causal_chains: List[CausalChain],
    ) -> List[RootCauseHypothesis]:
        """Build and rank root-cause hypotheses from all evidence."""
        # Group evidence by component
        component_evidence: Dict[str, Dict[str, Any]] = {}

        for comp in affected_components:
            component_evidence[comp] = {
                "dtc_count": 0,
                "anomaly_count": 0,
                "corr_break_count": 0,
                "causal_chain_count": 0,
                "evidence": [],
                "max_severity": "low",
                "causal_chains": [],
                "has_active_dtc": False,
            }

        # Count DTC evidence
        for dtc in dtc_codes:
            code = dtc.get("code", "").upper()
            comp = self._code_to_component(code)
            if comp in component_evidence:
                component_evidence[comp]["dtc_count"] += 1
                if dtc.get("is_active", True) and not dtc.get("is_pending", False):
                    component_evidence[comp]["has_active_dtc"] = True
                desc = dtc.get("description", code)
                component_evidence[comp]["evidence"].append(f"DTC {code}: {desc}")

        # Count anomaly evidence
        for a in anomalies:
            if a.component in component_evidence:
                component_evidence[a.component]["anomaly_count"] += 1
                component_evidence[a.component]["evidence"].append(a.message)
                component_evidence[a.component]["max_severity"] = _max_sev(
                    component_evidence[a.component]["max_severity"], a.severity,
                )

        # Count correlation break evidence
        for cb in corr_breaks:
            for comp in affected_components:
                comp_sensors = set(COMPONENT_SENSOR_MAP.get(comp, []))
                if cb.pair[0] in comp_sensors or cb.pair[1] in comp_sensors:
                    component_evidence[comp]["corr_break_count"] += 1
                    component_evidence[comp]["evidence"].append(
                        f"Correlation break: {cb.pair[0]} ↔ {cb.pair[1]} "
                        f"(Δr = {cb.delta:.2f}, {cb.severity})"
                    )
                    component_evidence[comp]["max_severity"] = _max_sev(
                        component_evidence[comp]["max_severity"], cb.severity,
                    )

        # Attach causal chains
        for chain in causal_chains:
            # Find which affected component this chain targets
            for comp in affected_components:
                comp_lower = comp.lower().replace("_", "")
                root_lower = chain.root_cause.lower().replace("_", "")
                if comp_lower in root_lower or root_lower in comp_lower:
                    component_evidence[comp]["causal_chain_count"] += 1
                    component_evidence[comp]["causal_chains"].append(chain)
                    break
            else:
                # Attach to first component in chain path if it matches
                for comp in affected_components:
                    if comp in chain.chain:
                        component_evidence[comp]["causal_chain_count"] += 1
                        component_evidence[comp]["causal_chains"].append(chain)
                        break

        # Build hypotheses with confidence scores
        hypotheses: List[RootCauseHypothesis] = []

        for comp, ev in component_evidence.items():
            if ev["dtc_count"] == 0 and ev["anomaly_count"] == 0:
                continue  # No evidence at all

            # Confidence scoring:
            #   DTC present:     +0.30 (active) or +0.15 (pending)
            #   Anomaly found:   +0.20 per anomaly (max 0.40)
            #   Corr break:      +0.10 per break (max 0.20)
            #   Causal chain:    +0.05 per chain (max 0.10)
            conf = 0.0
            if ev["has_active_dtc"]:
                conf += 0.30
            elif ev["dtc_count"] > 0:
                conf += 0.15
            conf += min(ev["anomaly_count"] * 0.20, 0.40)
            conf += min(ev["corr_break_count"] * 0.10, 0.20)
            conf += min(ev["causal_chain_count"] * 0.05, 0.10)

            conf = min(conf, 1.0)

            # Generate hypothesis text
            hypothesis = self._generate_hypothesis_text(comp, ev)

            hypotheses.append(RootCauseHypothesis(
                component=comp,
                hypothesis=hypothesis,
                confidence=round(conf, 3),
                supporting_evidence=ev["evidence"][:10],
                causal_chains=ev["causal_chains"][:3],
                recommended_inspections=INSPECTION_MAP.get(comp, []),
            ))

        # Sort by confidence descending
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        return hypotheses

    # ------------------------------------------------------------------
    # Step 6: Overall severity
    # ------------------------------------------------------------------

    def _compute_overall_severity(
        self,
        dtc_codes: List[Dict[str, Any]],
        anomalies: List[ForensicsAnomaly],
        corr_breaks: List[CorrelationAnomaly],
    ) -> str:
        """Determine overall severity of the DTC situation."""
        has_critical = any(
            d.get("severity", "").lower() in ("critical", "high")
            and d.get("is_active", True)
            for d in dtc_codes
        )
        has_high_anomaly = any(a.severity == "high" for a in anomalies)
        has_high_corr = any(cb.severity == "high" for cb in corr_breaks)
        n_active = sum(1 for d in dtc_codes if d.get("is_active", True))

        if has_critical or (n_active >= 3 and has_high_anomaly):
            return "critical"
        if has_high_anomaly or has_high_corr or n_active >= 2:
            return "high"
        if any(a.severity == "medium" for a in anomalies) or n_active >= 1:
            return "medium"
        return "low"

    # ------------------------------------------------------------------
    # Step 7: Summary
    # ------------------------------------------------------------------

    def _generate_summary(
        self,
        codes: List[str],
        affected: List[str],
        anomalies: List[ForensicsAnomaly],
        hypotheses: List[RootCauseHypothesis],
        severity: str,
    ) -> str:
        """Generate a human-readable forensic summary."""
        parts: List[str] = []

        codes_str = ", ".join(codes[:5])
        if len(codes) > 5:
            codes_str += f" (+{len(codes) - 5} more)"
        parts.append(f"Forensic analysis of {codes_str}.")

        parts.append(
            f"Affected systems: {', '.join(_fmt(c) for c in affected)}. "
            f"Overall severity: {severity.upper()}."
        )

        n_anomalies = len(anomalies)
        if n_anomalies:
            high_count = sum(1 for a in anomalies if a.severity == "high")
            parts.append(
                f"Detected {n_anomalies} sensor anomal{'y' if n_anomalies == 1 else 'ies'}"
                + (f" ({high_count} high-severity)" if high_count else "")
                + "."
            )

        if hypotheses:
            top = hypotheses[0]
            parts.append(
                f"Most likely root cause: {_fmt(top.component)} "
                f"(confidence: {top.confidence:.0%}). {top.hypothesis}"
            )

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _code_to_component(self, code: str) -> str:
        """Map a single DTC code to a component ID."""
        for prefix in sorted(DTC_COMPONENT_MAP.keys(), key=len, reverse=True):
            if code.startswith(prefix):
                return DTC_COMPONENT_MAP[prefix]
        if code.startswith("P"):
            return "engine_oil"
        if code.startswith("C"):
            return "brakes"
        return "engine_oil"

    def _generate_hypothesis_text(
        self, comp: str, ev: Dict[str, Any],
    ) -> str:
        """Generate a short hypothesis sentence."""
        name = _fmt(comp)

        if ev["has_active_dtc"] and ev["anomaly_count"] > 0 and ev["corr_break_count"] > 0:
            return (
                f"{name} shows active DTC(s) with {ev['anomaly_count']} sensor anomal"
                f"{'y' if ev['anomaly_count'] == 1 else 'ies'} and "
                f"{ev['corr_break_count']} correlation break(s) — "
                f"strongly suggests {name.lower()} degradation."
            )
        if ev["has_active_dtc"] and ev["anomaly_count"] > 0:
            return (
                f"Active DTC(s) confirmed by {ev['anomaly_count']} sensor anomal"
                f"{'y' if ev['anomaly_count'] == 1 else 'ies'} — "
                f"likely {name.lower()} issue."
            )
        if ev["has_active_dtc"]:
            return f"Active DTC(s) point to {name.lower()} — sensor data needed to confirm."
        if ev["anomaly_count"] > 0:
            return (
                f"Sensor anomalies detected in {name.lower()} area "
                f"without active DTC — possible early-stage issue."
            )
        return f"Pending evidence for {name.lower()} — monitor closely."


# ── Module-level helpers ────────────────────────────────────────────────

def _fmt(component_id: str) -> str:
    """Format component_id for display: 'engine_oil' → 'Engine Oil'."""
    return component_id.replace("_", " ").title()


_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max_sev(a: str, b: str) -> str:
    """Return the higher of two severity strings."""
    return a if _SEVERITY_ORDER.get(a, 0) >= _SEVERITY_ORDER.get(b, 0) else b


# ── Singleton ───────────────────────────────────────────────────────────

_forensics_instance: Optional[DTCForensicsEngine] = None


def get_dtc_forensics() -> DTCForensicsEngine:
    """Return module-level singleton."""
    global _forensics_instance
    if _forensics_instance is None:
        _forensics_instance = DTCForensicsEngine()
    return _forensics_instance
