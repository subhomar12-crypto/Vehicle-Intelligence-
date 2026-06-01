"""
Data export service with float timestamps.

Handles exporting user data in various formats.
"""

import logging
import time
import json
from typing import Dict, Any, Optional
from pathlib import Path

from sqlalchemy import select

from predict.core.config import get_config

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for exporting user data.
    
    Handles GDPR/CCPA data export requests.
    """
    
    def __init__(self):
        self.config = get_config()
        self.exports_dir = self.config.EXPORTS_DIR
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("ExportService initialized")
    
    async def export_user_data(
        self,
        user_id: int,
        session,
    ) -> Dict[str, Any]:
        """
        Export all data for a user.
        
        Args:
            user_id: User to export
            session: Database session
        
        Returns:
            Export result with file path
        """
        start_time = time.perf_counter()
        export_timestamp = time.time()
        
        # Collect user data
        export_data = {
            "export_metadata": {
                "user_id": user_id,
                "exported_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(export_timestamp)
                ),
                "exported_at_unix": export_timestamp,
                "version": "1.0",
            },
            "user_profile": await self._get_user_profile(user_id, session),
            "vehicles": await self._get_vehicle_data(user_id, session),
            "predictions": await self._get_prediction_data(user_id, session),
            "dtcs": await self._get_dtc_data(user_id, session),
        }
        
        # Write to file
        filename = f"export_user_{user_id}_{int(export_timestamp)}.json"
        filepath = self.exports_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(f"User {user_id} data exported to {filepath} in {elapsed_ms:.2f}ms")
        
        return {
            "status": "completed",
            "user_id": user_id,
            "filename": filename,
            "filepath": str(filepath),
            "file_size_bytes": filepath.stat().st_size,
            "processing_time_ms": elapsed_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": export_timestamp,
        }
    
    async def _get_user_profile(self, user_id: int, session) -> Dict[str, Any]:
        """Get user profile data."""
        from predict.core.db.models.user import User

        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return {}
        
        return {
            "id": user.id,
            "email": user.email,
            "tier": getattr(user, 'tier', 'free'),
            "created_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(user.created_at)
            ) if user.created_at else None,
            "created_at_unix": user.created_at,
        }
    
    async def _get_vehicle_data(self, user_id: int, session) -> list:
        """Get vehicle data for user."""
        from predict.core.db.models.vehicle import VehicleProfile

        stmt = select(VehicleProfile).where(VehicleProfile.owner_id == user_id)
        result = await session.execute(stmt)
        vehicles = result.scalars().all()
        
        return [
            {
                "id": v.id,
                "vin": v.vin,
                "make": v.make,
                "model": v.model,
                "year": v.year,
                "created_at_unix": v.created_at,
            }
            for v in vehicles
        ]
    
    async def _get_prediction_data(self, user_id: int, session) -> list:
        """Get prediction data for user's vehicles."""
        # This would join through vehicles
        return []
    
    async def _get_dtc_data(self, user_id: int, session) -> list:
        """Get DTC data for user's vehicles."""
        return []
    
    async def schedule_export(
        self,
        user_id: int,
        session,
    ) -> Dict[str, Any]:
        """Schedule a data export for async processing."""
        request_time = time.time()
        request_id = f"EXP-{int(request_time)}-{user_id}"
        
        # In real implementation, this would queue a background job
        logger.info(f"Scheduled export {request_id} for user {user_id}")
        
        return {
            "request_id": request_id,
            "user_id": user_id,
            "status": "scheduled",
            "estimated_completion": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(request_time + 3600)
            ),
            "estimated_completion_unix": request_time + 3600,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": request_time,
        }
