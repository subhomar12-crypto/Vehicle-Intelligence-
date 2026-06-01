"""
Guardian repository for parental monitoring data access.
"""

from typing import Optional, List

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.guardian import (
    Guardian, VehicleGuardian, Alert, GuardianCommand
)
from predict.core.db.repositories.base import BaseRepository


class GuardianRepository(BaseRepository[Guardian]):
    """Repository for Guardian entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Guardian)
    
    async def get_by_guardian_id(self, guardian_id: str) -> Optional[Guardian]:
        """Get guardian by external guardian ID."""
        stmt = select(Guardian).where(Guardian.guardian_id == guardian_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_user_id(self, user_id: int) -> Optional[Guardian]:
        """Get guardian by user ID (looks up by primary key id)."""
        stmt = select(Guardian).where(Guardian.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_vehicles_for_guardian(self, guardian_id: str) -> List[VehicleGuardian]:
        """Get all vehicle-guardian relationships for a guardian."""
        guardian = await self.get_by_guardian_id(guardian_id)
        if not guardian:
            return []
        
        stmt = (
            select(VehicleGuardian)
            .where(VehicleGuardian.guardian_id == guardian.id)
            .where(VehicleGuardian.is_active == True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_guardians_for_vehicle(self, profile_id: int) -> List[VehicleGuardian]:
        """Get all guardian relationships for a vehicle."""
        stmt = (
            select(VehicleGuardian)
            .where(VehicleGuardian.profile_id == profile_id)
            .where(VehicleGuardian.is_active == True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AlertRepository(BaseRepository[Alert]):
    """Repository for Guardian Alert entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Alert)
    
    async def get_recent_alerts(
        self,
        profile_id: int,
        limit: int = 20,
    ) -> List[Alert]:
        """Get recent alerts for a vehicle profile."""
        stmt = (
            select(Alert)
            .where(Alert.profile_id == profile_id)
            .order_by(desc(Alert.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unread_alerts(self, profile_id: int) -> List[Alert]:
        """Get unread alerts for a vehicle profile."""
        stmt = (
            select(Alert)
            .where(Alert.profile_id == profile_id)
            .where(Alert.is_read == False)
            .order_by(desc(Alert.timestamp))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_as_read(self, alert_id: int) -> None:
        """Mark an alert as read."""
        alert = await self.get_by_id(alert_id)
        if alert:
            alert.is_read = True
            await self.session.flush()
    
    async def get_alerts_for_vehicle(
        self,
        profile_id: int,
        limit: int = 50,
    ) -> List[Alert]:
        """Get alerts for a specific vehicle."""
        stmt = (
            select(Alert)
            .where(Alert.profile_id == profile_id)
            .order_by(desc(Alert.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class GuardianCommandRepository(BaseRepository[GuardianCommand]):
    """Repository for Guardian Command entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, GuardianCommand)
    
    async def get_pending_commands(self, profile_id: int) -> List[GuardianCommand]:
        """Get pending commands for a vehicle."""
        stmt = (
            select(GuardianCommand)
            .where(GuardianCommand.profile_id == profile_id)
            .where(GuardianCommand.status == 'pending')
            .order_by(desc(GuardianCommand.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_executed(self, command_id: int) -> None:
        """Mark a command as executed."""
        import time
        command = await self.get_by_id(command_id)
        if command:
            command.status = 'executed'
            command.executed_at = time.time()
            await self.session.flush()
    
    async def mark_failed(self, command_id: int, error: str) -> None:
        """Mark a command as failed."""
        import time
        command = await self.get_by_id(command_id)
        if command:
            command.status = 'failed'
            command.error_message = error
            command.executed_at = time.time()
            await self.session.flush()
    
    async def get_command_history(
        self,
        profile_id: int,
        limit: int = 50,
    ) -> List[GuardianCommand]:
        """Get command history for a vehicle."""
        stmt = (
            select(GuardianCommand)
            .where(GuardianCommand.profile_id == profile_id)
            .order_by(desc(GuardianCommand.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
