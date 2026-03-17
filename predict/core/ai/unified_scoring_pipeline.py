"""
Unified Scoring Pipeline v3 — weighted ensemble of all AI scorers.

Replaces the monolithic ``unified_ai_module.py`` (1,497 lines, 10 structural bugs).

Architecture:
    1. Gather ambient temperature (weather API > OBD > 35 C default)
    2. Classify driving context (idle / city / highway / aggressive)
    3. Fetch per-vehicle baseline (VehicleLearner, if available)
    4. Run up to 4 scorers in parallel via ``asyncio.gather``:
       - Cold-start predictor  (Layer 0 — always available)
       - LSTM model            (Phase E — placeholder)
       - XGBoost model         (Phase G — placeholder)
       - Survival analysis     (Phase I — placeholder)
    5. Compute dynamic weights (available scorers share 1.0)
    6. Ensemble vote — weighted average per component
    7. Causal propagation — upstream failures drag down dependents
    8. Return rich response dict consumed by the health-assessment endpoint

When a scorer is not yet implemented (returns ``None``) or fails at runtime,
its weight is redistributed to the remaining scorers automatically.  This
means the pipeline degrades gracefully and gains accuracy as new scorers
come online — no wiring changes needed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── The 10 canonical component IDs ───────────────────────────────────────

COMPONENT_IDS: List[str] = [
    "engine_oil",
    "coolant_system",
    "battery",
    "brakes",
    "transmission_fluid",
    "spark_plugs",
    "catalytic_converter",
    "o2_sensors",
    "air_filter",
    "fuel_system",
]

# ── Causal graph (source → [(target, max_penalty)]) ─────────────────────
# When a *source* component drops below 50 health, each *target* receives
# a penalty proportional to the deficit.  ``max_penalty`` is the ceiling.

CAUSAL_EDGES: Dict[str, List[tuple]] = {
    "coolant_system": [("engine_oil", 10), ("spark_plugs", 5)],
    "battery": [("spark_plugs", 5), ("fuel_system", 5)],
    "spark_plugs": [("catalytic_converter", 15), ("o2_sensors", 5)],
    "o2_sensors": [("catalytic_converter", 10), ("fuel_system", 5)],
    "fuel_system": [("catalytic_converter", 5)],
    "air_filter": [("fuel_system", 10), ("engine_oil", 5)],
    # Leaves — no outgoing causal edges
    "engine_oil": [],
    "brakes": [],
    "transmission_fluid": [],
    "catalytic_converter": [],
}

# ── Mapping from ColdStartPredictor component names to pipeline IDs ─────
# The cold-start predictor uses a different component naming scheme
# (e.g. "battery", "coolant", "engine") than the pipeline canonical IDs.

_CS_TO_PIPELINE: Dict[str, str] = {
    "battery": "battery",
    "coolant": "coolant_system",
    "engine": "engine_oil",
    "fuel_pump": "fuel_system",
    "spark_plugs": "spark_plugs",
    "o2_sensor": "o2_sensors",
    "catalytic_converter": "catalytic_converter",
    "maf_sensor": "air_filter",
    "transmission_fluid": "transmission_fluid",
    "alternator": "brakes",  # closest proxy — alternator maps to brakes slot
}

# ── Base weights (before normalisation) ──────────────────────────────────

_BASE_WEIGHTS = {
    "cold_start": 0.15,
    "lstm": 0.35,
    "xgboost": 0.25,
    "survival": 0.20,
}

# When only cold-start + survival are available
_FALLBACK_WEIGHTS = {
    "cold_start": 0.80,
    "survival": 0.20,
}


class UnifiedScoringPipeline:
    """Weighted ensemble of all vehicle-health AI scorers."""

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def score_vehicle(
        self,
        session,
        profile_id: int,
        latest_telemetry: Dict[str, Any],
        telemetry_history: List[Dict[str, Any]],
        vehicle_profile: Dict[str, Any],
        dtc_codes: Optional[List[Dict[str, Any]]] = None,
        service_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the full ensemble and return a rich health-assessment dict."""
        start = time.time()

        # 1. Ambient temperature
        ambient_temp = await self._get_ambient_temp(
            session, latest_telemetry, vehicle_profile,
        )

        # 2. Driving context
        driving_context = self._classify_driving(latest_telemetry)

        # 3. Per-vehicle baseline (non-blocking)
        baseline = await self._get_baseline(session, profile_id)

        # 4. Run scorers in parallel
        cold_start_coro = self._score_cold_start(
            session=session,
            profile_id=profile_id,
            latest_telemetry=latest_telemetry,
            telemetry_history=telemetry_history,
            vehicle_profile=vehicle_profile,
            dtc_codes=dtc_codes,
            service_records=service_records,
        )
        lstm_coro = self._score_lstm(
            session=session,
            profile_id=profile_id,
            latest_telemetry=latest_telemetry,
            telemetry_history=telemetry_history,
        )
        xgb_coro = self._score_xgboost(
            session=session,
            profile_id=profile_id,
            latest_telemetry=latest_telemetry,
            telemetry_history=telemetry_history,
            vehicle_profile=vehicle_profile,
        )
        survival_coro = self._score_survival(
            session=session,
            profile_id=profile_id,
            vehicle_profile=vehicle_profile,
            service_records=service_records,
        )

        results = await asyncio.gather(
            cold_start_coro, lstm_coro, xgb_coro, survival_coro,
            return_exceptions=True,
        )

        cold_start_raw = results[0] if not isinstance(results[0], Exception) else None
        lstm_raw = results[1] if not isinstance(results[1], Exception) else None
        xgb_raw = results[2] if not isinstance(results[2], Exception) else None
        survival_raw = results[3] if not isinstance(results[3], Exception) else None

        # Log any scorer exceptions
        for name, res in zip(
            ["cold_start", "lstm", "xgboost", "survival"], results,
        ):
            if isinstance(res, Exception):
                logger.warning("Scorer '%s' failed: %s", name, res)

        # 5. Normalise cold-start result into pipeline component IDs
        cold_start_scores = self._normalise_cold_start(cold_start_raw)

        # 6. Compute dynamic weights
        weights = self._compute_weights(
            cold_start=cold_start_scores,
            lstm=lstm_raw,
            xgb=xgb_raw,
            survival=survival_raw,
        )

        # 7. Ensemble vote
        raw_scores = self._ensemble_vote(
            cold_start=cold_start_scores,
            lstm=lstm_raw,
            xgb=xgb_raw,
            survival=survival_raw,
            weights=weights,
        )

        # 8. Causal propagation
        final_scores = self._propagate_causal(raw_scores)

        # 9. Build component dicts
        components = self._build_component_dicts(
            final_scores, cold_start_raw, weights,
        )

        # Overall score
        health_score = round(
            sum(final_scores.values()) / max(len(final_scores), 1),
        )

        # Data quality
        data_quality = {
            "telemetry_points": len(telemetry_history),
            "baseline_established": baseline is not None,
            "has_live_data": bool(latest_telemetry),
            "active_dtcs": len(dtc_codes) if dtc_codes else 0,
            "service_records_count": len(service_records) if service_records else 0,
        }

        elapsed = round(time.time() - start, 3)
        logger.info(
            "UnifiedScoringPipeline: vehicle %d, score=%d, scorers=%s, %.3fs",
            profile_id, health_score, list(weights.keys()), elapsed,
        )

        return {
            "success": True,
            "health_score": health_score,
            "vehicle_id": profile_id,
            "components": components,
            "ambient_temp": ambient_temp,
            "driving_context": driving_context,
            "scoring_weights": weights,
            "data_quality": data_quality,
            "assessment_time_ms": int(elapsed * 1000),
            "is_cold_start": lstm_raw is None and xgb_raw is None,
            # Pass through the full cold-start result for downstream
            # enrichment (baseline, urgency, patterns, trends, etc.)
            "_cold_start_raw": cold_start_raw,
        }

    # ------------------------------------------------------------------
    # Weight computation
    # ------------------------------------------------------------------

    def _compute_weights(
        self,
        cold_start: Optional[Dict],
        lstm: Any,
        xgb: Any,
        survival: Any,
    ) -> Dict[str, float]:
        """Return normalised weights for the available scorers.

        Rules:
        - A scorer counts as *available* if it is not ``None`` and not an
          ``Exception``.
        - If only cold_start is available, it gets 0.80 and survival gets
          the remaining 0.20 (but survival is also checked).
        - Otherwise, use ``_BASE_WEIGHTS`` and normalise to 1.0.
        """
        available: Dict[str, float] = {}

        # Check each scorer
        if cold_start is not None and not isinstance(cold_start, Exception):
            available["cold_start"] = _BASE_WEIGHTS["cold_start"]
        if lstm is not None and not isinstance(lstm, Exception):
            available["lstm"] = _BASE_WEIGHTS["lstm"]
        if xgb is not None and not isinstance(xgb, Exception):
            available["xgboost"] = _BASE_WEIGHTS["xgboost"]
        if survival is not None and not isinstance(survival, Exception):
            available["survival"] = _BASE_WEIGHTS["survival"]

        # Fallback: if only cold_start (and optionally survival)
        if "cold_start" in available and "lstm" not in available and "xgboost" not in available:
            result: Dict[str, float] = {}
            if "survival" in available:
                result["cold_start"] = _FALLBACK_WEIGHTS["cold_start"]
                result["survival"] = _FALLBACK_WEIGHTS["survival"]
            else:
                result["cold_start"] = 1.0
            return result

        # Nothing available at all — cold_start fallback with weight 1.0
        if not available:
            return {"cold_start": 1.0}

        # Normalise so weights sum to 1.0
        total = sum(available.values())
        if total <= 0:
            return {"cold_start": 1.0}
        return {k: v / total for k, v in available.items()}

    # ------------------------------------------------------------------
    # Ensemble voting
    # ------------------------------------------------------------------

    def _ensemble_vote(
        self,
        cold_start: Optional[Dict[str, float]],
        lstm: Optional[Dict[str, float]],
        xgb: Optional[Dict[str, float]],
        survival: Any,
        weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Compute weighted average score per component.

        Each scorer dict maps ``component_id -> score (0-100)``.
        Survival analysis is a dict of ``component_id -> {..., p50_days}``;
        we treat p50_days > 365 as 90, > 180 as 70, else 50 for blending.
        """
        result: Dict[str, float] = {}

        for comp in COMPONENT_IDS:
            weighted_sum = 0.0
            weight_sum = 0.0

            # Cold start
            if cold_start and "cold_start" in weights:
                score = cold_start.get(comp)
                if score is not None:
                    weighted_sum += weights["cold_start"] * score
                    weight_sum += weights["cold_start"]

            # LSTM
            if lstm and not isinstance(lstm, Exception) and "lstm" in weights:
                score = lstm.get(comp)
                if score is not None:
                    weighted_sum += weights["lstm"] * score
                    weight_sum += weights["lstm"]

            # XGBoost
            if xgb and not isinstance(xgb, Exception) and "xgboost" in weights:
                score = xgb.get(comp)
                if score is not None:
                    weighted_sum += weights["xgboost"] * score
                    weight_sum += weights["xgboost"]

            # Survival
            if survival and not isinstance(survival, Exception) and "survival" in weights:
                surv_data = survival.get(comp)
                if surv_data is not None:
                    # Convert p50_days to a 0-100 score
                    p50 = surv_data.get("p50_days", 365) if isinstance(surv_data, dict) else 365
                    surv_score = 90.0 if p50 > 365 else (70.0 if p50 > 180 else 50.0)
                    weighted_sum += weights["survival"] * surv_score
                    weight_sum += weights["survival"]

            if weight_sum > 0:
                result[comp] = round(weighted_sum / weight_sum, 1)
            else:
                result[comp] = 75.0  # safe default

        return result

    # ------------------------------------------------------------------
    # Causal propagation
    # ------------------------------------------------------------------

    def _propagate_causal(self, scores: Dict[str, float]) -> Dict[str, float]:
        """Apply causal penalties: failing upstream components drag down dependents.

        When a source component scores below 50, each target receives:
            penalty = min(deficit * max_penalty / 50, max_penalty)
        where ``deficit = 50 - source_score``.
        """
        out = dict(scores)

        for source, edges in CAUSAL_EDGES.items():
            source_score = scores.get(source, 75.0)
            if source_score >= 50:
                continue  # healthy enough — no propagation

            deficit = 50 - source_score  # 0..50

            for target, max_penalty in edges:
                if target not in out:
                    continue
                penalty = min(deficit * max_penalty / 50.0, float(max_penalty))
                out[target] = max(0.0, round(out[target] - penalty, 1))

        return out

    # ------------------------------------------------------------------
    # Driving context
    # ------------------------------------------------------------------

    def _classify_driving(self, telemetry) -> str:
        """Heuristic driving-context classification."""
        # If we have a window of readings, use the full classifier
        if isinstance(telemetry, list):
            try:
                from predict.core.ai.driving_classifier import DrivingContextClassifier
                classifier = DrivingContextClassifier()
                result = classifier.classify(telemetry)
                return result["context"]
            except Exception:
                pass  # Fall back to single-reading heuristic
            
            # Fallback: use last reading from list
            if telemetry:
                telemetry = telemetry[-1]
            else:
                return "city"
        
        # Single reading heuristic
        speed = telemetry.get("speed") or 0
        rpm = telemetry.get("rpm") or 0

        if speed == 0 and rpm > 0 and rpm < 1200:
            return "idle"
        if rpm > 3500:
            return "aggressive"
        if speed > 80:
            return "highway"
        return "city"

    # ------------------------------------------------------------------
    # Ambient temperature
    # ------------------------------------------------------------------

    async def _get_ambient_temp(
        self,
        session,
        telemetry: Dict[str, Any],
        profile: Dict[str, Any],
    ) -> float:
        """Get ambient temperature: OBD > weather API > 35.0 C default."""
        # 1. OBD ambient temp sensor
        obd_ambient = telemetry.get("ambient_temp")
        if obd_ambient is not None:
            try:
                return float(obd_ambient)
            except (TypeError, ValueError):
                pass

        # 2. Weather service
        try:
            from predict.core.ai.weather_service import get_weather_service

            ws = get_weather_service()
            # Default to Doha, Qatar (25.3, 51.5) if no GPS
            lat = profile.get("latitude", 25.3)
            lon = profile.get("longitude", 51.5)
            return await ws.get_current_temp(lat, lon)
        except Exception as e:
            logger.debug("Weather service unavailable: %s", e)

        # 3. Qatar default
        return 35.0

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------

    async def _get_baseline(self, session, profile_id: int) -> Optional[Dict]:
        """Load per-vehicle baseline from VehicleLearner (None on failure)."""
        try:
            from predict.core.ai.vehicle_learner import VehicleLearner

            learner = VehicleLearner()
            return await learner.get_baseline_info(session, profile_id)
        except Exception as e:
            logger.debug("Baseline unavailable for %d: %s", profile_id, e)
            return None

    # ------------------------------------------------------------------
    # Scorer delegates
    # ------------------------------------------------------------------

    async def _score_cold_start(
        self,
        session,
        profile_id: int,
        latest_telemetry: Dict[str, Any],
        telemetry_history: List[Dict],
        vehicle_profile: Dict[str, Any],
        dtc_codes: Optional[List[Dict]] = None,
        service_records: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Delegate to the existing ColdStartPredictor."""
        from predict.core.ai.cold_start_predictor import get_cold_start_predictor

        predictor = get_cold_start_predictor()
        return await predictor.assess_vehicle_health(
            vehicle_id=profile_id,
            latest_telemetry=latest_telemetry,
            vehicle_profile=vehicle_profile,
            dtc_codes=dtc_codes or [],
            telemetry_history=telemetry_history,
            research_data=None,  # pipeline doesn't need to pass this through
            climate_region="qatar",
            service_records=service_records,
            session=session,
        )

    async def _score_lstm(self, **kwargs) -> Optional[Dict[str, float]]:
        """Phase E placeholder — returns None (not yet implemented)."""
        return None

    async def _score_xgboost(self, **kwargs) -> Optional[Dict[str, float]]:
        """Phase G placeholder — returns None (not yet implemented)."""
        return None

    async def _score_survival(self, **kwargs) -> Optional[Dict[str, float]]:
        """Phase I placeholder — returns None (not yet implemented)."""
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalise_cold_start(
        self, raw: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, float]]:
        """Map ColdStartPredictor component names to pipeline IDs.

        Returns a dict of ``{pipeline_component_id: score}`` or ``None``
        if the raw result is missing / invalid.
        """
        if raw is None or not isinstance(raw, dict):
            return None

        components = raw.get("components")
        if not components:
            return None

        mapped: Dict[str, float] = {}
        for cs_name, pipeline_id in _CS_TO_PIPELINE.items():
            comp_data = components.get(cs_name)
            if comp_data is not None:
                score = comp_data.get("health_pct", 75) if isinstance(comp_data, dict) else 75
                mapped[pipeline_id] = float(score)

        # Fill any missing components with a safe default
        for comp in COMPONENT_IDS:
            if comp not in mapped:
                mapped[comp] = 75.0

        return mapped

    def _build_component_dicts(
        self,
        final_scores: Dict[str, float],
        cold_start_raw: Optional[Dict[str, Any]],
        weights: Dict[str, float],
    ) -> Dict[str, Dict[str, Any]]:
        """Build per-component response dicts for the API."""
        components: Dict[str, Dict[str, Any]] = {}

        # Reverse map for looking up cold-start detail
        pipeline_to_cs = {v: k for k, v in _CS_TO_PIPELINE.items()}

        cs_components = (cold_start_raw or {}).get("components", {})

        for comp_id in COMPONENT_IDS:
            score = final_scores.get(comp_id, 75.0)

            # Pull through rich data from cold-start if available
            cs_key = pipeline_to_cs.get(comp_id)
            cs_data = cs_components.get(cs_key, {}) if cs_key else {}

            components[comp_id] = {
                "health_pct": round(score, 1),
                "trend": cs_data.get("trend", "stable"),
                "confidence_tier": cs_data.get("confidence_tier", "estimated"),
                "data_source": cs_data.get("data_source", "cold_start"),
                "reason": cs_data.get("reason", ""),
                "penalties": cs_data.get("penalties", []),
                "recommendation": cs_data.get("recommendation", ""),
                "projection_summary": cs_data.get("projection_summary", ""),
                "projected_score": cs_data.get("projected_score", score),
                "timeframe_days": cs_data.get("timeframe_days", 0),
                "timeframe_label": cs_data.get("timeframe_label", ""),
                "scoring_method": "ensemble" if len(weights) > 1 else "cold_start",
            }

        return components


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_pipeline_instance: Optional[UnifiedScoringPipeline] = None


def get_unified_pipeline() -> UnifiedScoringPipeline:
    """Return the module-level UnifiedScoringPipeline singleton."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = UnifiedScoringPipeline()
    return _pipeline_instance
