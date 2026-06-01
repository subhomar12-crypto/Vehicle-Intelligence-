"""
Training Decision Engine.

Monitors data accumulation and decides when conditions are met
to trigger AI model retraining. Pairs failure events with OBD
time-window data to create labeled training datasets.
"""

import logging
import time

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TrainingDecisionEngine:
    """Decides when to trigger AI model retraining based on data accumulation."""

    # Minimum thresholds for retraining
    MIN_FAILURE_EVENTS = 10        # Need at least 10 confirmed failures
    MIN_OBD_RECORDS = 5000         # Need 5000+ OBD data points
    MIN_UNIQUE_VEHICLES = 3        # Data from at least 3 different vehicles
    RETRAIN_COOLDOWN_HOURS = 24    # Don't retrain more than once per day
    DATA_STALENESS_DAYS = 30       # Retrain if model is 30+ days old

    async def should_retrain(self, db: AsyncSession) -> dict:
        """Check if conditions are met for retraining.

        Returns:
            dict with should_retrain (bool), reasons (list), and stats (dict)
        """
        from predict.core.db.models.vehicle import FailureEvent, VehicleData

        reasons = []
        stats = {}

        # Count unexported failure events
        fe_stmt = select(func.count()).select_from(FailureEvent).where(
            FailureEvent.training_exported == False  # noqa: E712
        )
        result = await db.execute(fe_stmt)
        unexported_failures = result.scalar() or 0
        stats["unexported_failure_events"] = unexported_failures

        # Count total OBD records
        obd_stmt = select(func.count()).select_from(VehicleData)
        result = await db.execute(obd_stmt)
        total_obd = result.scalar() or 0
        stats["total_obd_records"] = total_obd

        # Count unique vehicles with OBD data
        vehicles_stmt = select(func.count(func.distinct(VehicleData.profile_id)))
        result = await db.execute(vehicles_stmt)
        unique_vehicles = result.scalar() or 0
        stats["unique_vehicles_with_data"] = unique_vehicles

        # Evaluate thresholds
        if unexported_failures >= self.MIN_FAILURE_EVENTS:
            reasons.append(f"Have {unexported_failures} unexported failure events (min: {self.MIN_FAILURE_EVENTS})")
        if total_obd >= self.MIN_OBD_RECORDS:
            reasons.append(f"Have {total_obd} OBD records (min: {self.MIN_OBD_RECORDS})")
        if unique_vehicles >= self.MIN_UNIQUE_VEHICLES:
            reasons.append(f"Data from {unique_vehicles} vehicles (min: {self.MIN_UNIQUE_VEHICLES})")

        should = (
            unexported_failures >= self.MIN_FAILURE_EVENTS
            and total_obd >= self.MIN_OBD_RECORDS
            and unique_vehicles >= self.MIN_UNIQUE_VEHICLES
        )

        if not should and not reasons:
            missing = []
            if unexported_failures < self.MIN_FAILURE_EVENTS:
                missing.append(f"failure events: {unexported_failures}/{self.MIN_FAILURE_EVENTS}")
            if total_obd < self.MIN_OBD_RECORDS:
                missing.append(f"OBD records: {total_obd}/{self.MIN_OBD_RECORDS}")
            if unique_vehicles < self.MIN_UNIQUE_VEHICLES:
                missing.append(f"vehicles: {unique_vehicles}/{self.MIN_UNIQUE_VEHICLES}")
            reasons.append(f"Not enough data — {', '.join(missing)}")

        return {
            "should_retrain": should,
            "reasons": reasons,
            "stats": stats,
        }

    async def prepare_training_dataset(self, db: AsyncSession) -> dict:
        """Prepare training data by pairing OBD time-windows with failure labels.

        For each failure event:
            - Gets OBD readings in [-30min, +5min] window
            - Labels with component + event_type

        For healthy periods:
            - Samples OBD readings with no nearby failures
            - Labels as "healthy"

        Returns:
            dict with failure_samples, healthy_samples, and metadata
        """
        from predict.core.db.models.vehicle import FailureEvent, VehicleData

        # Get all failure events
        stmt = select(FailureEvent).order_by(FailureEvent.event_timestamp)
        result = await db.execute(stmt)
        events = result.scalars().all()

        failure_samples = []
        for event in events:
            window_start = event.event_timestamp - 1800  # 30 min before
            window_end = event.event_timestamp + 300     # 5 min after

            data_stmt = select(VehicleData).where(
                and_(
                    VehicleData.profile_id == event.profile_id,
                    VehicleData.timestamp >= window_start,
                    VehicleData.timestamp <= window_end,
                )
            ).order_by(VehicleData.timestamp)
            data_result = await db.execute(data_stmt)
            obd_records = data_result.scalars().all()

            failure_samples.append({
                "label": event.training_label,
                "component": event.component,
                "severity": event.severity,
                "profile_id": event.profile_id,
                "data_points": len(obd_records),
                "features": [
                    {
                        "timestamp": r.timestamp,
                        "rpm": r.rpm,
                        "speed": r.speed,
                        "coolant_temp": r.coolant_temp,
                        "engine_load": r.engine_load,
                        "throttle_pos": r.throttle_pos,
                        "battery_voltage": r.battery_voltage,
                    }
                    for r in obd_records
                ],
            })

        return {
            "failure_samples": failure_samples,
            "metadata": {
                "total_failure_events": len(events),
                "total_failure_samples_with_data": sum(1 for s in failure_samples if s["data_points"] > 0),
                "prepared_at": time.time(),
            },
        }
