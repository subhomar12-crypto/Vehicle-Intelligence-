"""
Guardian service for parental monitoring features.

Handles:
- Guardian-driver relationships
- Real-time location sharing
- Speed/geofence alerts
- Remote vehicle commands
"""

import logging
import math
import time
from typing import Optional, Dict, Any, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.guardian import Guardian, GuardianCommand, VehicleGuardian
from predict.core.db.models.vehicle import TelemetryRecord
from predict.core.db.models.subscription import Geofence
from predict.core.db.repositories.guardian_repo import GuardianRepository
from predict.core.db.repositories.vehicle_repo import VehicleProfileRepository
from predict.core.services.fcm_service import FCMService

logger = logging.getLogger(__name__)


class GuardianService:
    """Business logic for Guardian parental monitoring."""
    
    def __init__(self):
        self.fcm = FCMService()
    
    async def create_guardian_link(
        self,
        guardian_user_id: int,
        driver_user_id: int,
        vehicle_profile_id: int,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Create a guardian-driver monitoring link.
        
        Args:
            guardian_user_id: The parent/guardian user ID
            driver_user_id: The driver being monitored
            vehicle_profile_id: Vehicle to monitor
            session: Database session
        
        Returns:
            Created link details
        """
        repo = GuardianRepository(session)
        
        # Check if guardian exists
        guardian = await repo.get_by_guardian_id(str(guardian_user_id))
        if not guardian:
            # Create guardian record
            guardian = Guardian(
                user_id=guardian_user_id,
                created_at=time.time(),
                updated_at=time.time(),
            )
            session.add(guardian)
            await session.flush()
        
        # Create vehicle-guardian link
        link = VehicleGuardian(
            guardian_id=guardian.id,
            vehicle_id=vehicle_profile_id,
            driver_id=driver_user_id,
            is_active=True,
            created_at=time.time(),
            updated_at=time.time(),
        )
        session.add(link)
        await session.flush()
        
        logger.info(f"Guardian link created: {guardian_user_id} -> {driver_user_id}")
        
        return {
            "guardian_id": guardian.id,
            "driver_id": driver_user_id,
            "vehicle_id": vehicle_profile_id,
            "status": "active",
            "link_id": link.id,
        }
    
    async def get_driver_location(
        self,
        guardian_user_id: int,
        driver_user_id: int,
        session: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Get real-time location for a monitored driver.
        
        Args:
            guardian_user_id: Guardian requesting location
            driver_user_id: Driver to locate
            session: Database session
        
        Returns:
            Location data or None
        """
        # Check authorization
        repo = GuardianRepository(session)
        has_access = await self._check_guardian_access(
            guardian_user_id, driver_user_id, session
        )
        
        if not has_access:
            logger.warning(f"Unauthorized location request: {guardian_user_id} -> {driver_user_id}")
            return None
        
        # Get latest telemetry record with location
        stmt = (
            select(TelemetryRecord)
            .where(TelemetryRecord.device_id == str(driver_user_id))
            .order_by(desc(TelemetryRecord.ts))
            .limit(1)
        )
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        
        if not record:
            return None
        
        return {
            "latitude": record.latitude,
            "longitude": record.longitude,
            "altitude": record.altitude,
            "accuracy": getattr(record, 'accuracy', None),
            "speed": record.gps_speed,
            "heading": record.heading,
            "timestamp": record.ts,
        }
    
    async def send_command(
        self,
        guardian_user_id: int,
        driver_user_id: int,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        session: AsyncSession = None,
    ) -> bool:
        """
        Send a command to a driver's device.
        
        Args:
            guardian_user_id: Guardian sending command
            driver_user_id: Driver to receive command
            command: Command type (lock, unlock, horn, lights)
            params: Optional command parameters
            session: Database session
        
        Returns:
            True if command queued successfully
        """
        # Check authorization
        has_access = await self._check_guardian_access(
            guardian_user_id, driver_user_id, session
        )
        
        if not has_access:
            logger.warning(f"Unauthorized command: {guardian_user_id} -> {driver_user_id}")
            return False
        
        # Valid commands
        valid_commands = ["lock", "unlock", "horn", "lights", "location_request"]
        if command not in valid_commands:
            logger.error(f"Invalid guardian command: {command}")
            return False
        
        # Send via FCM
        success = await self.fcm.send_push(
            token="",  # TODO: Get driver's FCM token
            title="Guardian Command",
            body=f"Command received: {command}",
            data={
                "type": "guardian_command",
                "command": command,
                "params": str(params or {}),
                "guardian_id": str(guardian_user_id),
            },
            channel_id="guardian_commands",
        )
        
        # Log command
        if session:
            cmd = GuardianCommand(
                guardian_id=guardian_user_id,
                driver_id=driver_user_id,
                command=command,
                params=str(params or {}),
                status="sent" if success else "failed",
                created_at=time.time(),
            )
            session.add(cmd)
        
        logger.info(f"Guardian command sent: {command} -> driver {driver_user_id}")
        return success
    
    async def get_alerts(
        self,
        guardian_user_id: int,
        limit: int = 50,
        session: AsyncSession = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent alerts for a guardian.
        
        Args:
            guardian_user_id: Guardian to get alerts for
            limit: Maximum number of alerts
            session: Database session
        
        Returns:
            List of alert dictionaries
        """
        if not session:
            return []

        stmt = (
            select(Alert)
            .where(Alert.guardian_id == guardian_user_id)
            .order_by(desc(Alert.created_at))
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        alerts = result.scalars().all()
        
        return [
            {
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "title": a.title,
                "message": a.message,
                "vehicle_id": a.vehicle_id,
                "timestamp": a.created_at,
                "is_read": a.is_read,
            }
            for a in alerts
        ]
    
    async def create_geofence(
        self,
        guardian_user_id: int,
        vehicle_profile_id: int,
        name: str,
        latitude: float,
        longitude: float,
        radius_m: float,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """
        Create a geofence for a vehicle.
        
        Args:
            guardian_user_id: Guardian creating geofence
            vehicle_profile_id: Vehicle to monitor
            name: Geofence name
            latitude: Center latitude
            longitude: Center longitude
            radius_m: Radius in meters
            session: Database session
        
        Returns:
            Created geofence details
        """
        geofence = Geofence(
            guardian_id=guardian_user_id,
            vehicle_id=vehicle_profile_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            is_active=True,
            created_at=time.time(),
            updated_at=time.time(),
        )
        
        session.add(geofence)
        await session.flush()
        
        logger.info(f"Geofence created: {name} for vehicle {vehicle_profile_id}")
        
        return {
            "id": geofence.id,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "radius_m": radius_m,
        }
    
    async def check_geofence_violations(
        self,
        vehicle_id: int,
        latitude: float,
        longitude: float,
        session: AsyncSession,
    ) -> List[Dict[str, Any]]:
        """
        Check if vehicle has left any geofences.
        
        Args:
            vehicle_id: Vehicle to check
            latitude: Current latitude
            longitude: Current longitude
            session: Database session
        
        Returns:
            List of violated geofences
        """
        from predict.core.db.models.subscription import Geofence

        stmt = (
            select(Geofence)
            .where(Geofence.vehicle_id == vehicle_id)
            .where(Geofence.is_active == True)
        )
        
        result = await session.execute(stmt)
        geofences = result.scalars().all()
        
        violations = []
        
        for geofence in geofences:
            distance = self._calculate_distance(
                latitude, longitude,
                geofence.latitude, geofence.longitude
            )
            
            if distance > geofence.radius_m:
                violations.append({
                    "geofence_id": geofence.id,
                    "name": geofence.name,
                    "distance_m": distance,
                    "radius_m": geofence.radius_m,
                })
        
        return violations
    
    def _calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float,
    ) -> float:
        """Calculate distance between two coordinates in meters (Haversine formula)."""
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    async def _check_guardian_access(
        self,
        guardian_user_id: int,
        driver_user_id: int,
        session: AsyncSession,
    ) -> bool:
        """Check if guardian has access to monitor driver."""
        stmt = (
            select(VehicleGuardian)
            .where(VehicleGuardian.guardian_id == guardian_user_id)
            .where(VehicleGuardian.driver_id == driver_user_id)
            .where(VehicleGuardian.is_active == True)
        )
        
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None
