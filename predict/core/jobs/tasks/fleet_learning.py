"""
Fleet learning cron job — aggregate cross-fleet penalty calibration.

Runs nightly at 2:30 AM (after self_validation_job at 2:00 AM).

Reads ComponentAccuracyStats and PredictionFeedback to compute
fleet-wide penalty adjustment factors per component. These are
stored as FleetPenaltyAdjustment rows and read by cold_start_predictor.py.
"""

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)

# Minimum feedback samples required before adjusting penalty
MIN_SAMPLES = 10

# Maximum adjustment factor (clamp to ±30% correction)
MAX_ADJUSTMENT = 0.30


async def fleet_learning_job(ctx):
    """
    Nightly job: compute fleet-wide penalty calibration factors.

    For each component with enough feedback:
    - If directional_accuracy < 0.6 → model is wrong more than right → inflate penalties
    - If mean_absolute_error > 20 → large magnitude errors → scale penalties
    - Write FleetPenaltyAdjustment rows for cold_start_predictor.py to load
    """
    try:
        from predict.core.db.session import get_session_maker
        from predict.core.db.models.prediction_feedback import (
            ComponentAccuracyStats,
            FleetPenaltyAdjustment,
        )
        from sqlalchemy import select

        session_maker = get_session_maker()
        async with session_maker() as session:
            # Load all component accuracy stats
            stats_rows = (
                await session.execute(select(ComponentAccuracyStats))
            ).scalars().all()

            if not stats_rows:
                logger.info("fleet_learning_job: no accuracy stats yet, skipping")
                return {"updated": 0}

            updated = 0
            for stat in stats_rows:
                if stat.sample_count < MIN_SAMPLES:
                    continue

                # Compute adjustment factor
                # directional_accuracy of 1.0 = perfect → factor 1.0 (no change)
                # directional_accuracy of 0.5 = random → factor 1.3 (inflate penalties)
                direction_factor = 1.0 + MAX_ADJUSTMENT * max(
                    0.0, (0.75 - stat.directional_accuracy) / 0.25
                )
                direction_factor = min(direction_factor, 1.0 + MAX_ADJUSTMENT)

                # Mean absolute error penalty scaling
                # MAE of 0 → 1.0, MAE of 40+ → 1.3
                mae_factor = 1.0 + MAX_ADJUSTMENT * min(1.0, stat.mean_absolute_error / 40.0)

                # Combined factor — geometric mean to avoid double-counting
                adjustment_factor = (direction_factor * mae_factor) ** 0.5

                # Clamp
                adjustment_factor = max(0.7, min(1.3, adjustment_factor))

                # Upsert FleetPenaltyAdjustment
                existing = (
                    await session.execute(
                        select(FleetPenaltyAdjustment).where(
                            FleetPenaltyAdjustment.component == stat.component
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.penalty_multiplier = adjustment_factor
                    existing.sample_count = stat.sample_count
                    existing.directional_accuracy = stat.directional_accuracy
                    existing.mean_absolute_error = stat.mean_absolute_error
                    existing.last_updated = time.time()
                else:
                    adj = FleetPenaltyAdjustment(
                        component=stat.component,
                        penalty_multiplier=adjustment_factor,
                        sample_count=stat.sample_count,
                        directional_accuracy=stat.directional_accuracy,
                        mean_absolute_error=stat.mean_absolute_error,
                        last_updated=time.time(),
                    )
                    session.add(adj)

                updated += 1
                logger.debug(
                    f"fleet_learning: {stat.component} "
                    f"accuracy={stat.directional_accuracy:.2f} "
                    f"mae={stat.mean_absolute_error:.1f} "
                    f"→ multiplier={adjustment_factor:.3f}"
                )

            await session.commit()
            logger.info(
                f"fleet_learning_job: updated {updated} penalty adjustments "
                f"from {len(stats_rows)} component stats"
            )
            return {"updated": updated, "total_components": len(stats_rows)}

    except Exception as e:
        logger.error(f"fleet_learning_job failed: {e}", exc_info=True)
        return {"error": str(e)}
