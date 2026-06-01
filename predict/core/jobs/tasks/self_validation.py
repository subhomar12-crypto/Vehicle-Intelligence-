"""
Self-validation cron job — compare prediction snapshots against feedback outcomes.

Runs nightly at 2 AM. Computes accuracy metrics per component and updates a
fleet-wide calibration table used by cold_start_predictor.py.
"""

import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


async def self_validation_job(ctx):
    """
    Nightly job: evaluate prediction accuracy from snapshot vs feedback pairs.

    For each PredictionFeedback record that has a nearby PredictionSnapshot:
    - Compute |predicted_score - outcome_score| as error
    - Aggregate per-component mean error
    - Write ComponentAccuracyStats rows (upsert)
    """
    try:
        from predict.core.db.session import get_session_maker
        from predict.core.db.models.prediction_feedback import (
            PredictionFeedback,
            PredictionSnapshot,
            ComponentAccuracyStats,
        )
        from sqlalchemy import select, func

        session_maker = get_session_maker()
        async with session_maker() as session:
            # Fetch all unprocessed feedback (last 30 days)
            cutoff = time.time() - 30 * 86400
            feedback_rows = (
                await session.execute(
                    select(PredictionFeedback).where(
                        PredictionFeedback.feedback_date >= cutoff
                    )
                )
            ).scalars().all()

            if not feedback_rows:
                logger.info("self_validation_job: no feedback in last 30 days, skipping")
                return {"processed": 0}

            # Map component → list of errors
            component_errors: dict[str, list[float]] = defaultdict(list)
            component_counts: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})

            for fb in feedback_rows:
                # Find nearest snapshot for same vehicle + component (within ±7 days)
                window_start = fb.feedback_date - 7 * 86400
                window_end = fb.feedback_date + 7 * 86400

                snap = (
                    await session.execute(
                        select(PredictionSnapshot)
                        .where(
                            PredictionSnapshot.vehicle_id == fb.vehicle_id,
                            PredictionSnapshot.component == fb.component,
                            PredictionSnapshot.snapshot_date >= window_start,
                            PredictionSnapshot.snapshot_date <= window_end,
                        )
                        .order_by(
                            func.abs(PredictionSnapshot.snapshot_date - fb.feedback_date)
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if snap is None:
                    continue

                # Convert actual_outcome to numeric score
                if fb.actual_outcome == "confirmed_bad":
                    actual_score = 20  # bad = low health
                elif fb.actual_outcome == "confirmed_good":
                    actual_score = 90  # good = high health
                else:
                    continue  # unknown — skip

                error = abs(snap.predicted_score - actual_score)
                component_errors[fb.component].append(error)

                # Directional accuracy: predicted high + confirmed_good OR predicted low + confirmed_bad
                predicted_high = snap.predicted_score >= 60
                outcome_good = fb.actual_outcome == "confirmed_good"
                if predicted_high == outcome_good:
                    component_counts[fb.component]["correct"] += 1
                component_counts[fb.component]["total"] += 1

            # Upsert ComponentAccuracyStats
            updated = 0
            for component, errors in component_errors.items():
                if not errors:
                    continue

                mean_err = sum(errors) / len(errors)
                counts = component_counts[component]
                accuracy = (
                    counts["correct"] / counts["total"]
                    if counts["total"] > 0
                    else 0.0
                )

                # Try update first
                existing = (
                    await session.execute(
                        select(ComponentAccuracyStats).where(
                            ComponentAccuracyStats.component == component
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.mean_absolute_error = mean_err
                    existing.directional_accuracy = accuracy
                    existing.sample_count = len(errors)
                    existing.last_updated = time.time()
                else:
                    stats = ComponentAccuracyStats(
                        component=component,
                        mean_absolute_error=mean_err,
                        directional_accuracy=accuracy,
                        sample_count=len(errors),
                        last_updated=time.time(),
                    )
                    session.add(stats)

                updated += 1

            await session.commit()
            logger.info(
                f"self_validation_job: processed {len(feedback_rows)} feedback records, "
                f"updated {updated} component accuracy stats"
            )
            return {"processed": len(feedback_rows), "updated": updated}

    except Exception as e:
        logger.error(f"self_validation_job failed: {e}", exc_info=True)
        return {"error": str(e)}
