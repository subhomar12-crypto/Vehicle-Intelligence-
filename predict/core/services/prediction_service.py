"""
Prediction service for vehicle health and failure predictions.

Handles:
- Running AI predictions on vehicle data
- Managing prediction history
- Prediction quota enforcement per tier
"""

import logging
import time
from typing import Optional, Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.ai.unified_ai_module import UnifiedAI
from predict.core.db.repositories.prediction_repo import PredictionRepository
from predict.core.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class PredictionService:
    """Vehicle prediction business logic."""
    
    def __init__(self):
        self.ai = None  # Lazy initialization
    
    def _ensure_ai(self):
        """Lazy initialize AI module."""
        if self.ai is None:
            self.ai = UnifiedAI()
    
    async def run_prediction(
        self,
        user_id: int,
        vehicle_profile_id: int,
        obd_data: Dict[str, Any],
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Run a vehicle health prediction.
        
        Args:
            user_id: User requesting prediction
            vehicle_profile_id: Vehicle to analyze
            obd_data: OBD sensor data
            session: Database session
        
        Returns:
            Prediction results
        """
        self._ensure_ai()
        
        # Check quota
        quota = await self.check_prediction_quota(user_id, session)
        if quota["remaining"] <= 0:
            return {
                "error": "quota_exceeded",
                "message": "Prediction quota exceeded for your tier",
                "reset_date": quota.get("reset_date"),
            }
        
        try:
            # Run AI analysis
            result = await self.ai.analyze_vehicle_health(
                vehicle_id=vehicle_profile_id,
                obd_data=obd_data.get("records", []),
            )

            # Store prediction in database
            await self._store_prediction(
                user_id=user_id,
                vehicle_id=vehicle_profile_id,
                result=result,
                session=session,
            )
            
            # Increment usage counter
            await self._increment_usage(user_id, session)
            
            return result
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {
                "error": "prediction_failed",
                "message": str(e),
            }
    
    async def get_vehicle_prediction(
        self,
        vehicle_id: int,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Get AI prediction for a vehicle using recent data.
        
        Args:
            vehicle_id: Vehicle ID
            session: Database session
        
        Returns:
            AI analysis results
        """
        self._ensure_ai()
        
        # Fetch recent vehicle data
        from predict.core.db.repositories.vehicle_repo import VehicleDataRepository
        vehicle_repo = VehicleDataRepository(session)
        
        recent_data = await vehicle_repo.get_latest(vehicle_id, limit=200)
        
        if not recent_data:
            return {"error": "No vehicle data available", "vehicle_id": vehicle_id}
        
        # Convert DB records to OBD dict format
        obd_records = self._records_to_obd_dict(recent_data)
        
        # Run AI analysis
        result = await self.ai.analyze_vehicle_health(
            vehicle_id=vehicle_id,
            obd_data=obd_records,
        )
        
        return result
    
    async def get_component_risk(
        self,
        vehicle_id: int,
        component: str,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Get risk assessment for a specific component.
        
        Args:
            vehicle_id: Vehicle ID
            component: Component name (engine, transmission, battery, etc.)
            session: Database session
        
        Returns:
            Component risk assessment
        """
        # Get full prediction
        prediction = await self.get_vehicle_prediction(vehicle_id, session)
        
        if "error" in prediction:
            return prediction
        
        # Extract component-specific data
        subsystems = prediction.get("subsystem_scores", {})
        component_data = subsystems.get(component, {})
        
        return {
            "vehicle_id": vehicle_id,
            "component": component,
            "health_score": component_data.get("score", 0),
            "status": component_data.get("status", "unknown"),
            "risk_level": prediction.get("risk_level", "unknown"),
        }
    
    async def get_prediction_history(
        self,
        user_id: int,
        vehicle_profile_id: int,
        limit: int = 20,
        session: AsyncSession = None,
    ) -> List[Dict[str, Any]]:
        """
        Get prediction history for a vehicle.
        
        Args:
            user_id: User ID
            vehicle_profile_id: Vehicle ID
            limit: Maximum number of records
            session: Database session
        
        Returns:
            List of prediction records
        """
        if not session:
            return []
        
        repo = PredictionRepository(session)
        predictions = await repo.get_prediction_history(vehicle_profile_id, limit)
        
        return [
            {
                "id": p.id,
                "component": p.component,
                "risk_score": p.failure_probability,
                "confidence": p.confidence_score,
                "created_at": p.created_at,
                "is_active": p.status == "active",
            }
            for p in predictions
        ]
    
    async def check_prediction_quota(
        self,
        user_id: int,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Check remaining prediction quota for user's tier.
        
        Args:
            user_id: User ID
            session: Database session
        
        Returns:
            Quota details
        """
        # Get user's tier
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(user_id)
        
        if not user:
            return {"remaining": 0, "limit": 0, "reset_date": None}
        
        # Tier limits
        tier_limits = {
            "free": 10,
            "pro": 100,
            "premium": 1000,
            "enterprise": 10000,
        }
        
        limit = tier_limits.get(user.tier, 10)
        
        # Count usage in current period
        from predict.core.db.models.prediction import Prediction

        # Current month start (calculate from epoch without datetime)
        now = time.time()
        gm = time.gmtime(now)
        month_start = time.mktime(time.strptime(f"{gm.tm_year}-{gm.tm_mon:02d}-01", "%Y-%m-%d"))
        
        stmt = (
            select(func.count(Prediction.id))
            .where(Prediction.user_id == user_id)
            .where(Prediction.created_at >= month_start)
        )
        
        result = await session.execute(stmt)
        used = result.scalar() or 0
        
        return {
            "remaining": max(0, limit - used),
            "limit": limit,
            "used": used,
            "reset_date": month_start + 30 * 86400,  # Approximate next month
            "tier": user.tier,
        }
    
    async def log_prediction(
        self,
        vehicle_id: int,
        prediction_data: Dict[str, Any],
        session: AsyncSession,
    ) -> bool:
        """
        Log a prediction to the audit log.
        
        Args:
            vehicle_id: Vehicle ID
            prediction_data: Prediction results
            session: Database session
        
        Returns:
            True if logged successfully
        """
        try:
            from predict.core.db.models.hindsight import PredictionAuditLog
            
            log = PredictionAuditLog(
                vehicle_id=vehicle_id,
                component=prediction_data.get("component", "general"),
                risk_score=prediction_data.get("risk_score", 0.0),
                raw_risk_score=prediction_data.get("raw_risk_score", 0.0),
                confidence=prediction_data.get("confidence", 0.0),
                models_used=str(prediction_data.get("models_used", [])),
                model_predictions=str(prediction_data.get("model_predictions", {})),
                abstained=prediction_data.get("abstained", False),
                abstention_reason=prediction_data.get("abstention_reason"),
                created_at=time.time(),
            )
            
            session.add(log)
            return True
            
        except Exception as e:
            logger.error(f"Failed to log prediction: {e}")
            return False
    
    def _records_to_obd_dict(self, records: List[Any]) -> List[Dict[str, Any]]:
        """Convert DB records to OBD dict format."""
        result = []
        for r in records:
            result.append({
                "timestamp": r.timestamp,
                "rpm": r.rpm,
                "speed": r.speed,
                "coolant_temp": r.coolant_temp,
                "battery_voltage": r.battery_voltage,
                "engine_load": r.engine_load,
                "maf": getattr(r, 'maf_rate', None),
                "throttle_position": getattr(r, 'throttle_pos', None),
                "intake_temp": r.intake_temp,
            })
        return result
    
    async def _store_prediction(
        self,
        user_id: int,
        vehicle_id: int,
        result: Dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Store prediction in database."""
        try:
            from predict.core.db.models.prediction import Prediction
            
            pred = Prediction(
                prediction_id=f"pred_{int(time.time())}_{vehicle_id}",
                profile_id=vehicle_id,
                component=result.get("component", "general"),
                failure_probability=result.get("risk_score", 0.0),
                confidence_score=result.get("confidence", 0.0),
                severity=result.get("risk_level", "unknown"),
                status="active",
                created_at=time.time(),
                updated_at=time.time(),
            )
            
            session.add(pred)
            
        except Exception as e:
            logger.error(f"Failed to store prediction: {e}")
    
    async def _increment_usage(self, user_id: int, session: AsyncSession) -> None:
        """Increment prediction usage counter."""
        # TODO: Implement usage counter increment
        pass
