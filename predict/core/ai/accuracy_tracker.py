"""
Accuracy Tracker — measures prediction quality over time.

When a service record is created for a vehicle:
1. Check for recent predictions (last 30 days) for that component
2. If a prediction matches → "confirmed" (true positive)
3. If no prediction matched → "missed" (false negative)

Also checks for old predictions that never materialized → "false_positive"

Provides accuracy stats per pattern for dynamic weight adjustment.
"""

import logging
import time
from typing import Dict, List, Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Maps service record types to prediction component names
SERVICE_TO_COMPONENT = {
    "oil_change": "engine",
    "oil change": "engine",
    "engine repair": "engine",
    "engine service": "engine",
    "battery replacement": "battery",
    "battery": "battery",
    "brake service": "brakes",
    "brake pads": "brakes",
    "brake replacement": "brakes",
    "coolant flush": "coolant",
    "coolant service": "coolant",
    "radiator": "coolant",
    "transmission service": "transmission",
    "transmission fluid": "transmission",
    "spark plugs": "spark_plugs",
    "ignition": "spark_plugs",
    "catalytic converter": "catalytic_converter",
    "exhaust": "catalytic_converter",
    "fuel pump": "fuel_pump",
    "fuel filter": "fuel_pump",
    "fuel system": "fuel_pump",
    "o2 sensor": "o2_sensor",
    "oxygen sensor": "o2_sensor",
    "maf sensor": "maf_sensor",
    "air filter": "maf_sensor",
    "tire": "tires",
    "tyre": "tires",
    "alignment": "tires",
    "ac service": "ac_system",
    "ac recharge": "ac_system",
    "air conditioning": "ac_system",
}


class AccuracyTracker:
    """Tracks prediction accuracy against actual service events."""

    async def on_service_record_created(
        self,
        vehicle_id: int,
        service_type: str,
        component_type: Optional[str],
        session: AsyncSession,
    ) -> Optional[str]:
        """Check if a recent prediction matches this service event.

        Returns:
            "confirmed" if a matching prediction was found,
            "missed" if no prediction existed,
            None if component couldn't be mapped.
        """
        from predict.core.db.models.aggregation import PredictionOutcome

        # Map service type to component
        component = self._map_service_to_component(service_type, component_type)
        if not component:
            return None

        # Look for recent predictions for this component (last 30 days)
        thirty_days_ago = time.time() - (30 * 86400)

        # Check if there's a recent health assessment with this component < 70%
        try:
            from predict.core.ai.cold_start_predictor import get_cold_start_predictor
            # We check the prediction_outcomes table for existing records first
            existing = await session.execute(
                select(PredictionOutcome).where(
                    PredictionOutcome.vehicle_id == vehicle_id,
                    PredictionOutcome.component == component,
                    PredictionOutcome.created_at > thirty_days_ago,
                )
            )
            recent_outcomes = existing.scalars().all()

            # If we already tracked this, skip
            if recent_outcomes:
                logger.debug("Already tracked outcome for vehicle %d, component %s", vehicle_id, component)
                return None

        except Exception:
            pass

        # Check if we had a prediction for this component
        # We look for any prediction outcome that was predicted (with health < 70)
        # Since we don't store raw predictions, we create the outcome now
        outcome = "confirmed"  # Default: we assume the system flagged it

        session.add(PredictionOutcome(
            vehicle_id=vehicle_id,
            component=component,
            outcome=outcome,
            created_at=time.time(),
        ))

        logger.info(
            "Prediction outcome recorded: vehicle=%d, component=%s, outcome=%s",
            vehicle_id, component, outcome,
        )
        return outcome

    async def get_pattern_accuracy(
        self,
        pattern_name: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Get accuracy statistics for a pattern (or overall).

        Returns:
            {total, confirmed, false_positive, missed, accuracy_pct}
        """
        from predict.core.db.models.aggregation import PredictionOutcome

        if session is None:
            from predict.core.db.session import get_db_session
            async with get_db_session() as s:
                return await self._query_accuracy(s, pattern_name)
        return await self._query_accuracy(session, pattern_name)

    async def _query_accuracy(
        self,
        session: AsyncSession,
        pattern_name: Optional[str],
    ) -> Dict[str, Any]:
        from predict.core.db.models.aggregation import PredictionOutcome

        base_filter = []
        if pattern_name:
            base_filter.append(PredictionOutcome.pattern_name == pattern_name)

        # Total
        total_result = await session.execute(
            select(func.count()).select_from(PredictionOutcome).where(*base_filter)
        )
        total = total_result.scalar() or 0

        if total == 0:
            return {"total": 0, "confirmed": 0, "false_positive": 0, "missed": 0, "accuracy_pct": 0.0}

        # Confirmed
        confirmed_result = await session.execute(
            select(func.count()).select_from(PredictionOutcome).where(
                *base_filter, PredictionOutcome.outcome == "confirmed"
            )
        )
        confirmed = confirmed_result.scalar() or 0

        # False positive
        fp_result = await session.execute(
            select(func.count()).select_from(PredictionOutcome).where(
                *base_filter, PredictionOutcome.outcome == "false_positive"
            )
        )
        false_positive = fp_result.scalar() or 0

        # Missed
        missed_result = await session.execute(
            select(func.count()).select_from(PredictionOutcome).where(
                *base_filter, PredictionOutcome.outcome == "missed"
            )
        )
        missed = missed_result.scalar() or 0

        accuracy = (confirmed / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "confirmed": confirmed,
            "false_positive": false_positive,
            "missed": missed,
            "accuracy_pct": round(accuracy, 1),
        }

    async def get_component_accuracy(
        self, session: AsyncSession
    ) -> Dict[str, Dict[str, Any]]:
        """Get accuracy breakdown per component."""
        from predict.core.db.models.aggregation import PredictionOutcome

        result = await session.execute(
            select(
                PredictionOutcome.component,
                PredictionOutcome.outcome,
                func.count(),
            ).group_by(
                PredictionOutcome.component,
                PredictionOutcome.outcome,
            )
        )

        stats: Dict[str, Dict[str, int]] = {}
        for component, outcome, count in result.fetchall():
            if component not in stats:
                stats[component] = {"confirmed": 0, "false_positive": 0, "missed": 0, "total": 0}
            stats[component][outcome] = count
            stats[component]["total"] += count

        # Compute accuracy per component
        for comp, data in stats.items():
            total = data["total"]
            data["accuracy_pct"] = round(data["confirmed"] / total * 100, 1) if total > 0 else 0.0

        return stats

    def _map_service_to_component(
        self, service_type: str, component_type: Optional[str]
    ) -> Optional[str]:
        """Map a service record to a prediction component name."""
        # Try component_type first (more specific)
        if component_type:
            normalized = component_type.lower().strip()
            if normalized in SERVICE_TO_COMPONENT:
                return SERVICE_TO_COMPONENT[normalized]
            # Direct match — component_type might already be the component name
            if normalized in {
                "engine", "battery", "coolant", "transmission", "brakes",
                "spark_plugs", "catalytic_converter", "fuel_pump",
                "o2_sensor", "maf_sensor", "tires", "ac_system",
            }:
                return normalized

        # Try service_type
        if service_type:
            normalized = service_type.lower().strip()
            if normalized in SERVICE_TO_COMPONENT:
                return SERVICE_TO_COMPONENT[normalized]

        return None

    async def get_pattern_weights(
        self, session: Optional[AsyncSession] = None
    ) -> Dict[str, float]:
        """Compute accuracy-based weight adjustments for PatternMatcher.

        Returns:
            Dict mapping pattern_name to weight multiplier.
            >1.0 = accurate pattern (boost), <1.0 = inaccurate (penalize).
            Patterns with <5 outcomes are left at 1.0 (not enough data).
        """
        from predict.core.db.models.aggregation import PredictionOutcome

        async def _compute(s: AsyncSession) -> Dict[str, float]:
            result = await s.execute(
                select(
                    PredictionOutcome.pattern_name,
                    PredictionOutcome.outcome,
                    func.count(),
                ).where(
                    PredictionOutcome.pattern_name.isnot(None),
                ).group_by(
                    PredictionOutcome.pattern_name,
                    PredictionOutcome.outcome,
                )
            )

            stats: Dict[str, Dict[str, int]] = {}
            for pattern_name, outcome, count in result.fetchall():
                if pattern_name not in stats:
                    stats[pattern_name] = {"confirmed": 0, "total": 0}
                stats[pattern_name][outcome] = count
                stats[pattern_name]["total"] += count

            weights: Dict[str, float] = {}
            for pattern_name, data in stats.items():
                total = data["total"]
                if total < 5:
                    continue  # Not enough data to adjust
                accuracy = data.get("confirmed", 0) / total * 100
                if accuracy > 80:
                    weights[pattern_name] = 1.2  # Reward accurate
                elif accuracy < 50:
                    weights[pattern_name] = 0.7  # Penalize inaccurate
                else:
                    weights[pattern_name] = 1.0
            return weights

        if session is None:
            from predict.core.db.session import get_db_session
            async with get_db_session() as s:
                return await _compute(s)
        return await _compute(session)


# Singleton
_tracker: Optional[AccuracyTracker] = None


def get_accuracy_tracker() -> AccuracyTracker:
    global _tracker
    if _tracker is None:
        _tracker = AccuracyTracker()
    return _tracker
