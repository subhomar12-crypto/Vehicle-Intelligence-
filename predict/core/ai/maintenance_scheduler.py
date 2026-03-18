"""Maintenance scheduler — auto-generate maintenance calendar entries from survival predictions.

Uses survival analysis predictions to schedule maintenance activities.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.ai.survival_engine import SurvivalEngine, COMPONENT_IDS

logger = logging.getLogger(__name__)


class MaintenanceScheduler:
    """Schedule maintenance based on survival predictions."""
    
    def __init__(self, survival_engine: Optional[SurvivalEngine] = None):
        """Initialize scheduler.
        
        Args:
            survival_engine: SurvivalEngine instance (creates new if None)
        """
        self.survival_engine = survival_engine or SurvivalEngine()
        
    async def schedule_for_vehicle(
        self,
        session: AsyncSession,
        profile_id: int,
        current_ages: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Generate maintenance schedule for a vehicle.
        
        Args:
            session: Database session
            profile_id: Vehicle profile ID
            current_ages: Dict mapping component -> current age in days
            
        Returns:
            Schedule dict with maintenance items
        """
        if not self.survival_engine.is_trained:
            # Try to load or train
            try:
                self.survival_engine.load("/app/models/survival")
            except:
                logger.warning("Survival engine not trained, using synthetic data")
                self.survival_engine.train_from_synthetic(n_samples=500)
        
        # Get survival predictions
        predictions = self.survival_engine.predict_all_components(current_ages)
        
        schedule = {
            "profile_id": profile_id,
            "generated_at": datetime.utcnow().isoformat(),
            "maintenance_items": [],
        }
        
        for component, pred in predictions.items():
            remaining_life = pred.get("mean_remaining_life_days")
            
            if remaining_life is None:
                continue
            
            # Calculate due date
            due_date = datetime.utcnow() + timedelta(days=remaining_life)
            
            # Determine priority based on remaining life
            if remaining_life <= 30:
                priority = "critical"
            elif remaining_life <= 90:
                priority = "high"
            elif remaining_life <= 180:
                priority = "medium"
            else:
                priority = "low"
            
            # Calculate survival probability at due date
            survival_curve = pred.get("survival_curve")
            survival_prob = None
            if survival_curve:
                # Find probability at remaining_life
                timeline = survival_curve.get("timeline_days", [])
                probs = survival_curve.get("survival_probability", [])
                for t, p in zip(timeline, probs):
                    if t >= remaining_life:
                        survival_prob = p
                        break
            
            item = {
                "component": component,
                "due_date": due_date.isoformat(),
                "due_in_days": remaining_life,
                "priority": priority,
                "current_age_days": pred.get("current_age_days", 0),
                "survival_probability": survival_prob,
                "estimated_cost": self._estimate_cost(component),
            }
            
            schedule["maintenance_items"].append(item)
        
        # Sort by due date
        schedule["maintenance_items"].sort(key=lambda x: x["due_in_days"])
        
        return schedule
    
    def _estimate_cost(self, component: str) -> Dict[str, float]:
        """Estimate maintenance cost for a component.
        
        Args:
            component: Component ID
            
        Returns:
            Cost dict with parts and labor
        """
        # Base costs per component (QAR)
        base_costs = {
            "engine_oil": {"parts": 150, "labor": 50},
            "coolant_system": {"parts": 200, "labor": 100},
            "battery": {"parts": 400, "labor": 30},
            "brakes": {"parts": 600, "labor": 150},
            "transmission_fluid": {"parts": 300, "labor": 100},
            "spark_plugs": {"parts": 200, "labor": 80},
            "catalytic_converter": {"parts": 1500, "labor": 200},
            "o2_sensors": {"parts": 400, "labor": 100},
            "air_filter": {"parts": 80, "labor": 20},
            "fuel_system": {"parts": 500, "labor": 150},
        }
        
        costs = base_costs.get(component, {"parts": 300, "labor": 100})
        costs["total"] = costs["parts"] + costs["labor"]
        
        return costs
    
    async def get_upcoming_maintenance(
        self,
        session: AsyncSession,
        profile_id: int,
        days_ahead: int = 90,
    ) -> List[Dict[str, Any]]:
        """Get upcoming maintenance within specified days.
        
        Args:
            session: Database session
            profile_id: Vehicle profile ID
            days_ahead: Days to look ahead
            
        Returns:
            List of maintenance items due within days_ahead
        """
        schedule = await self.schedule_for_vehicle(session, profile_id)
        
        upcoming = [
            item for item in schedule["maintenance_items"]
            if item["due_in_days"] <= days_ahead
        ]
        
        return upcoming
    
    async def get_maintenance_summary(
        self,
        session: AsyncSession,
        profile_id: int,
    ) -> Dict[str, Any]:
        """Get maintenance summary for dashboard.
        
        Args:
            session: Database session
            profile_id: Vehicle profile ID
            
        Returns:
            Summary dict
        """
        schedule = await self.schedule_for_vehicle(session, profile_id)
        
        items = schedule["maintenance_items"]
        
        critical_count = sum(1 for item in items if item["priority"] == "critical")
        high_count = sum(1 for item in items if item["priority"] == "high")
        medium_count = sum(1 for item in items if item["priority"] == "medium")
        low_count = sum(1 for item in items if item["priority"] == "low")
        
        total_cost = sum(item["estimated_cost"]["total"] for item in items)
        
        # Next maintenance due
        next_item = items[0] if items else None
        
        return {
            "profile_id": profile_id,
            "total_items": len(items),
            "by_priority": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
            },
            "estimated_total_cost": total_cost,
            "next_maintenance": next_item,
            "generated_at": schedule["generated_at"],
        }


async def generate_maintenance_schedule(profile_id: int) -> Dict[str, Any]:
    """ARQ job: Generate maintenance schedule for a vehicle.
    
    Args:
        profile_id: Vehicle profile ID
        
    Returns:
        Schedule dict
    """
    from predict.core.db.session import get_session_maker
    
    scheduler = MaintenanceScheduler()
    
    async with get_session_maker()() as session:
        schedule = await scheduler.schedule_for_vehicle(session, profile_id)
        
        logger.info(f"Generated maintenance schedule for vehicle {profile_id}")
        
        return schedule


async def get_vehicle_maintenance_summary(profile_id: int) -> Dict[str, Any]:
    """ARQ job: Get maintenance summary for dashboard.
    
    Args:
        profile_id: Vehicle profile ID
        
    Returns:
        Summary dict
    """
    from predict.core.db.session import get_session_maker
    
    scheduler = MaintenanceScheduler()
    
    async with get_session_maker()() as session:
        summary = await scheduler.get_maintenance_summary(session, profile_id)
        
        return summary
