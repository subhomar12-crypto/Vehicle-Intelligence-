"""Auto-retraining triggers — ARQ jobs for periodic model retraining.

Monitors prediction accuracy trends and triggers model retraining when
accuracy drops below threshold. Tracks per-component accuracy statistics.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.jobs.queue import _get_pool
from predict.core.db.session import get_session_maker

logger = logging.getLogger(__name__)

# Canonical component IDs
COMPONENT_IDS = (
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
)

# Accuracy threshold for triggering retraining (-10% means accuracy dropped 10%)
ACCURACY_DROP_THRESHOLD = -0.10


class RetrainingTrigger:
    """Monitor and trigger model retraining based on accuracy trends."""
    
    def __init__(self, accuracy_threshold: float = ACCURACY_DROP_THRESHOLD):
        """Initialize retraining trigger.
        
        Args:
            accuracy_threshold: Minimum acceptable accuracy delta (negative = drop)
        """
        self.accuracy_threshold = accuracy_threshold
        
    async def compute_accuracy_delta(
        self,
        session: AsyncSession,
        component: str,
        days_back: int = 21,
    ) -> Optional[Dict[str, Any]]:
        """Compute accuracy delta: last week vs 3-week average.
        
        Args:
            session: Database session
            component: Component ID (canonical)
            days_back: Days to look back (default 21 = 3 weeks)
            
        Returns:
            Dict with last_week_acc, prev_avg_acc, delta, samples_count
        """
        from predict.core.db.models.prediction_feedback import PredictionFeedback
        
        now = datetime.utcnow()
        last_week_start = now - timedelta(days=7)
        period_start = now - timedelta(days=days_back)
        
        # Convert to timestamps
        last_week_timestamp = last_week_start.timestamp()
        period_timestamp = period_start.timestamp()
        
        # Query last week's feedback (has actual outcome)
        last_week_result = await session.execute(
            select(PredictionFeedback).where(
                and_(
                    PredictionFeedback.component == component,
                    PredictionFeedback.feedback_date >= last_week_timestamp,
                    PredictionFeedback.actual_outcome.isnot(None),
                )
            )
        )
        last_week_feedback = last_week_result.scalars().all()
        
        # Query previous 2 weeks (for 3-week avg excluding last week)
        prev_weeks_result = await session.execute(
            select(PredictionFeedback).where(
                and_(
                    PredictionFeedback.component == component,
                    PredictionFeedback.feedback_date >= period_timestamp,
                    PredictionFeedback.feedback_date < last_week_timestamp,
                    PredictionFeedback.actual_outcome.isnot(None),
                )
            )
        )
        prev_weeks_feedback = prev_weeks_result.scalars().all()
        
        if not last_week_feedback or not prev_weeks_feedback:
            logger.warning(
                f"Insufficient feedback for {component}: "
                f"last_week={len(last_week_feedback)}, prev_weeks={len(prev_weeks_feedback)}"
            )
            return None
        
        # Calculate accuracies (any outcome that's not "unknown" counts as valid feedback)
        last_week_valid = sum(
            1 for f in last_week_feedback 
            if f.actual_outcome in ("confirmed_good", "confirmed_bad")
        )
        last_week_acc = last_week_valid / len(last_week_feedback) if last_week_feedback else 0
        
        prev_weeks_valid = sum(
            1 for f in prev_weeks_feedback 
            if f.actual_outcome in ("confirmed_good", "confirmed_bad")
        )
        prev_weeks_acc = prev_weeks_valid / len(prev_weeks_feedback) if prev_weeks_feedback else 0
        
        # Compute delta
        delta = last_week_acc - prev_weeks_acc
        
        return {
            "component": component,
            "last_week_accuracy": round(last_week_acc, 4),
            "previous_avg_accuracy": round(prev_weeks_acc, 4),
            "accuracy_delta": round(delta, 4),
            "last_week_samples": len(last_week_feedback),
            "previous_samples": len(prev_weeks_feedback),
            "needs_retraining": delta < self.accuracy_threshold,
        }
    
    async def check_all_components(
        self,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Check accuracy for all components.
        
        Args:
            session: Database session
            
        Returns:
            Results dict with per-component stats and trigger list
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "components_checked": [],
            "components_triggered": [],
            "insufficient_data": [],
            "accuracy_stats": {},
        }
        
        for component in COMPONENT_IDS:
            delta_info = await self.compute_accuracy_delta(session, component)
            
            if delta_info is None:
                results["insufficient_data"].append(component)
                continue
            
            results["components_checked"].append(component)
            results["accuracy_stats"][component] = delta_info
            
            if delta_info["needs_retraining"]:
                results["components_triggered"].append(component)
                logger.warning(
                    f"Retraining triggered for {component}: "
                    f"accuracy dropped {delta_info['accuracy_delta']:.1%}"
                )
        
        return results
    
    async def trigger_retraining(
        self,
        session: AsyncSession,
        component: str,
        model_type: str = "xgboost",
    ) -> Dict[str, Any]:
        """Trigger retraining for a specific component.
        
        Args:
            session: Database session
            component: Component ID
            model_type: Type of model to retrain (xgboost, survival, isolation_forest)
            
        Returns:
            Trigger result dict
        """
        # Enqueue retraining job directly (component-level, not vehicle-specific)
        pool = await _get_pool()
        arq_job = await pool.enqueue_job(
            "retrain_model",
            component=component,
            model_type=model_type,
        )
        job_id = arq_job.job_id
        
        logger.info(f"Enqueued retraining job for {component}: job_id={job_id}")
        
        return {
            "component": component,
            "model_type": model_type,
            "queue_job_id": job_id,
            "status": "queued",
        }


# ARQ Job Functions

async def weekly_retraining_check() -> Dict[str, Any]:
    """ARQ job: Weekly check for model retraining triggers.
    
    Checks accuracy delta for all components and triggers retraining
    for those with significant accuracy drops.
    
    Returns:
        Check results
    """
    trigger = RetrainingTrigger()
    
    async with get_session_maker()() as session:
        # Check all components
        results = await trigger.check_all_components(session)
        
        # Trigger retraining for components that need it
        for component in results["components_triggered"]:
            await trigger.trigger_retraining(session, component, model_type="xgboost")
        
        await session.commit()
    
    logger.info(
        f"Weekly retraining check complete: "
        f"checked={len(results['components_checked'])}, "
        f"triggered={len(results['components_triggered'])}"
    )
    
    return results


async def retrain_model(
    component: str,
    model_type: str,
) -> Dict[str, Any]:
    """ARQ job: Retrain a specific model.
    
    Args:
        component: Component ID to retrain
        model_type: Type of model (xgboost, survival, isolation_forest)
        
    Returns:
        Training results
    """
    logger.info(f"Starting retraining for {component} ({model_type})")
    started_at = datetime.utcnow()
    
    try:
        async with get_session_maker()() as session:
            # Retrain based on model type
            if model_type == "xgboost":
                from predict.core.ai.xgboost_predictor import XGBoostFailurePredictor
                
                predictor = XGBoostFailurePredictor()
                metrics = await predictor.train_from_db(session, min_samples=50)
                
                # Serialize new model
                model_path = f"/app/models/xgboost_{component}_{datetime.utcnow().strftime('%Y%m%d')}.joblib"
                paths = predictor.serialize(model_path)
                
                return {
                    "component": component,
                    "model_type": model_type,
                    "status": "completed",
                    "metrics": metrics,
                    "model_paths": paths,
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                }
                
            elif model_type == "survival":
                from predict.core.ai.survival_engine import SurvivalEngine
                
                engine = SurvivalEngine()
                metrics = await engine.train_from_db(session, min_failures=10)
                
                return {
                    "component": component,
                    "model_type": model_type,
                    "status": "completed",
                    "metrics": metrics,
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                }
                
            else:
                return {
                    "component": component,
                    "model_type": model_type,
                    "status": "failed",
                    "error": f"Unknown model type: {model_type}",
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                }
            
    except Exception as e:
        logger.exception(f"Retraining failed for {component}: {e}")
        
        return {
            "component": component,
            "model_type": model_type,
            "status": "failed",
            "error": str(e),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }


async def get_retraining_stats(days: int = 30) -> Dict[str, Any]:
    """ARQ job: Get retraining statistics.
    
    Note: Component-level retraining doesn't use TrainingJob table.
    Stats are tracked via ARQ job results or ComponentAccuracyStats.
    
    Args:
        days: Days to look back
        
    Returns:
        Statistics dict
    """
    from predict.core.db.models.prediction_feedback import ComponentAccuracyStats
    
    async with get_session_maker()() as session:
        since_timestamp = (datetime.utcnow() - timedelta(days=days)).timestamp()
        
        # Get component accuracy stats
        result = await session.execute(
            select(ComponentAccuracyStats).where(
                ComponentAccuracyStats.last_updated >= since_timestamp
            )
        )
        stats_records = result.scalars().all()
        
        stats = {
            "period_days": days,
            "components_tracked": len(stats_records),
            "by_component": {},
        }
        
        for record in stats_records:
            stats["by_component"][record.component] = {
                "mean_absolute_error": record.mean_absolute_error,
                "directional_accuracy": record.directional_accuracy,
                "sample_count": record.sample_count,
                "last_updated": record.last_updated,
            }
        
        return stats
