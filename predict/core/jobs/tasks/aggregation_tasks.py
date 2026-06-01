"""
GDPR-safe daily aggregation task.

Runs nightly to:
1. Compute per-vehicle per-sensor daily min/max/avg/count
2. Store in daily_sensor_summary table
3. Raw telemetry can then be safely deleted (GDPR cleanup)
   while preserving long-term trend visibility

Called by APScheduler (Task 20) at 8 PM daily.
"""

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select, func, and_

logger = logging.getLogger(__name__)

# Sensors to aggregate
AGGREGATED_SENSORS = [
    "rpm", "speed", "coolant_temp", "battery_voltage", "engine_load",
    "throttle_pos", "fuel_level", "intake_temp", "maf_rate", "oil_temp",
    "short_term_fuel_trim", "long_term_fuel_trim", "ambient_temp",
    "boost_pressure", "fuel_rate", "torque",
]


async def aggregate_daily_stats():
    """Aggregate yesterday's sensor readings into daily summaries."""
    from predict.core.db.session import get_db_session
    from predict.core.db.models.vehicle import VehicleData
    from predict.core.db.models.aggregation import DailySensorSummary

    yesterday = datetime.utcnow().date() - timedelta(days=1)
    date_str = yesterday.isoformat()  # YYYY-MM-DD

    # Time range: yesterday 00:00 → today 00:00 (Unix timestamps)
    day_start = datetime.combine(yesterday, datetime.min.time()).timestamp()
    day_end = day_start + 86400

    logger.info("Aggregating sensor data for %s (%.0f → %.0f)", date_str, day_start, day_end)

    async with get_db_session() as session:
        # Get all vehicle IDs that had data yesterday
        vehicle_ids_result = await session.execute(
            select(VehicleData.profile_id)
            .where(VehicleData.timestamp >= day_start)
            .where(VehicleData.timestamp < day_end)
            .distinct()
        )
        vehicle_ids = [row[0] for row in vehicle_ids_result.fetchall() if row[0]]

        if not vehicle_ids:
            logger.info("No vehicle data found for %s", date_str)
            return

        logger.info("Aggregating for %d vehicles on %s", len(vehicle_ids), date_str)

        total_summaries = 0
        for vid in vehicle_ids:
            for sensor in AGGREGATED_SENSORS:
                col = getattr(VehicleData, sensor, None)
                if col is None:
                    continue

                # Compute aggregate
                agg_result = await session.execute(
                    select(
                        func.min(col),
                        func.max(col),
                        func.avg(col),
                        func.count(col),
                    ).where(
                        and_(
                            VehicleData.profile_id == vid,
                            VehicleData.timestamp >= day_start,
                            VehicleData.timestamp < day_end,
                            col.isnot(None),
                        )
                    )
                )
                row = agg_result.fetchone()
                if not row or row[3] == 0:  # No readings for this sensor
                    continue

                min_val, max_val, avg_val, count = row

                # Upsert (check if already exists)
                existing = await session.execute(
                    select(DailySensorSummary).where(
                        DailySensorSummary.vehicle_id == vid,
                        DailySensorSummary.date == date_str,
                        DailySensorSummary.sensor == sensor,
                    )
                )
                summary = existing.scalar_one_or_none()

                if summary:
                    summary.min_value = float(min_val)
                    summary.max_value = float(max_val)
                    summary.avg_value = float(avg_val)
                    summary.reading_count = int(count)
                else:
                    session.add(DailySensorSummary(
                        vehicle_id=vid,
                        date=date_str,
                        sensor=sensor,
                        min_value=float(min_val),
                        max_value=float(max_val),
                        avg_value=float(avg_val),
                        reading_count=int(count),
                    ))
                    total_summaries += 1

        await session.commit()
        logger.info("Created %d daily sensor summaries for %s", total_summaries, date_str)


async def get_long_term_trends(vehicle_id: int, sensor: str, days: int = 90):
    """Get aggregated trend data for a sensor over many days.

    Used by the trend analyzer for long-term analysis (31-365 days)
    where raw telemetry may have been deleted by GDPR cleanup.
    """
    from predict.core.db.session import get_db_session
    from predict.core.db.models.aggregation import DailySensorSummary
    from datetime import datetime, timedelta

    cutoff = (datetime.utcnow().date() - timedelta(days=days)).isoformat()

    async with get_db_session() as session:
        result = await session.execute(
            select(DailySensorSummary)
            .where(
                DailySensorSummary.vehicle_id == vehicle_id,
                DailySensorSummary.sensor == sensor,
                DailySensorSummary.date >= cutoff,
            )
            .order_by(DailySensorSummary.date)
        )
        rows = result.scalars().all()

        return [
            {
                "date": r.date,
                "min": r.min_value,
                "max": r.max_value,
                "avg": r.avg_value,
                "count": r.reading_count,
            }
            for r in rows
        ]
