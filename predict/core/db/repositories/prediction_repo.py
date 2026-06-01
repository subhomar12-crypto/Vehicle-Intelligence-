"""
Prediction and ML training data repository.
"""

from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.prediction import (
    Prediction, MLTrainingLabel, MLAggregatedFeature
)
from predict.core.db.repositories.base import BaseRepository


class PredictionRepository(BaseRepository[Prediction]):
    """Repository for Prediction entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Prediction)
    
    async def get_active_predictions(self, profile_id: int) -> List[Prediction]:
        """Get active predictions for a vehicle."""
        stmt = (
            select(Prediction)
            .where(Prediction.profile_id == profile_id)
            .where(Prediction.status == "active")
            .order_by(desc(Prediction.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_prediction_history(
        self,
        profile_id: int,
        limit: int = 100,
    ) -> List[Prediction]:
        """Get prediction history for a vehicle."""
        stmt = (
            select(Prediction)
            .where(Prediction.profile_id == profile_id)
            .order_by(desc(Prediction.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_component(
        self,
        profile_id: int,
        component: str,
    ) -> List[Prediction]:
        """Get predictions for a specific component."""
        stmt = (
            select(Prediction)
            .where(Prediction.profile_id == profile_id)
            .where(Prediction.component == component)
            .order_by(desc(Prediction.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_latest_for_component(
        self,
        profile_id: int,
        component: str,
    ) -> Optional[Prediction]:
        """Get latest prediction for a component."""
        stmt = (
            select(Prediction)
            .where(Prediction.profile_id == profile_id)
            .where(Prediction.component == component)
            .order_by(desc(Prediction.created_at))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def deactivate_old_predictions(
        self,
        profile_id: int,
        component: str,
    ) -> None:
        """Deactivate old predictions when new one is created."""
        stmt = (
            select(Prediction)
            .where(Prediction.profile_id == profile_id)
            .where(Prediction.component == component)
            .where(Prediction.status == "active")
        )
        result = await self.session.execute(stmt)
        predictions = result.scalars().all()

        for pred in predictions:
            pred.status = "resolved"
        
        await self.session.flush()


class MLTrainingLabelRepository(BaseRepository[MLTrainingLabel]):
    """Repository for ML Training Label entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, MLTrainingLabel)
    
    async def create_training_label(
        self,
        prediction_id: int,
        actual_outcome: str,
        label_data: Optional[dict] = None,
    ) -> MLTrainingLabel:
        """Create a training label for a prediction."""
        import time
        
        label = await self.create(
            prediction_id=prediction_id,
            actual_outcome=actual_outcome,
            label_data=label_data or {},
            created_at=time.time(),
        )
        return label
    
    async def get_unlabeled(self, limit: int = 100) -> List[MLTrainingLabel]:
        """Get training labels awaiting verification."""
        stmt = (
            select(MLTrainingLabel)
            .where(MLTrainingLabel.actual_outcome.is_(None))
            .order_by(desc(MLTrainingLabel.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_labels_for_prediction(
        self,
        prediction_id: int,
    ) -> List[MLTrainingLabel]:
        """Get training labels for a prediction."""
        stmt = (
            select(MLTrainingLabel)
            .where(MLTrainingLabel.prediction_id == prediction_id)
            .order_by(desc(MLTrainingLabel.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_recent_labels(
        self,
        limit: int = 100,
    ) -> List[MLTrainingLabel]:
        """Get recent training labels."""
        stmt = (
            select(MLTrainingLabel)
            .order_by(desc(MLTrainingLabel.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class MLFeatureRepository(BaseRepository[MLAggregatedFeature]):
    """Repository for ML Aggregated Feature entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, MLAggregatedFeature)
    
    async def get_features_for_profile(
        self,
        profile_id: int,
        feature_type: str,
        limit: int = 100,
    ) -> List[MLAggregatedFeature]:
        """Get aggregated features for a vehicle."""
        stmt = (
            select(MLAggregatedFeature)
            .where(MLAggregatedFeature.profile_id == profile_id)
            .where(MLAggregatedFeature.feature_type == feature_type)
            .order_by(desc(MLAggregatedFeature.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_latest_features(
        self,
        profile_id: int,
        feature_type: str,
    ) -> Optional[MLAggregatedFeature]:
        """Get latest aggregated features for a vehicle."""
        stmt = (
            select(MLAggregatedFeature)
            .where(MLAggregatedFeature.profile_id == profile_id)
            .where(MLAggregatedFeature.feature_type == feature_type)
            .order_by(desc(MLAggregatedFeature.timestamp))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
