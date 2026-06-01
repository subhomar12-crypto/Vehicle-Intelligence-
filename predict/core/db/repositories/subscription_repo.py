"""
Subscription, geofence, and fleet invite repository.
"""

from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.subscription import (
    FleetInvite, Geofence, TierUpgradeRequest
)
from predict.core.db.repositories.base import BaseRepository


class GeofenceRepository(BaseRepository[Geofence]):
    """Repository for Geofence entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Geofence)
    
    async def get_active_geofences(self, profile_id: int) -> List[Geofence]:
        """Get active geofences for a vehicle."""
        stmt = (
            select(Geofence)
            .where(Geofence.profile_id == profile_id)
            .where(Geofence.is_active == True)
            .order_by(desc(Geofence.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_geofence_by_name(
        self,
        profile_id: int,
        name: str,
    ) -> Optional[Geofence]:
        """Get geofence by name for a vehicle."""
        stmt = (
            select(Geofence)
            .where(Geofence.profile_id == profile_id)
            .where(Geofence.name == name)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_geofences_by_type(
        self,
        profile_id: int,
        geofence_type: str,
    ) -> List[Geofence]:
        """Get geofences by type (allowed/restricted)."""
        stmt = (
            select(Geofence)
            .where(Geofence.profile_id == profile_id)
            .where(Geofence.geofence_type == geofence_type)
            .where(Geofence.is_active == True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class FleetInviteRepository(BaseRepository[FleetInvite]):
    """Repository for Fleet Invite entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, FleetInvite)
    
    async def get_invite_by_code(self, code: str) -> Optional[FleetInvite]:
        """Get invite by its code."""
        stmt = select(FleetInvite).where(FleetInvite.invite_code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_pending_invites(self, user_id: int) -> List[FleetInvite]:
        """Get pending invites for a user."""
        import time
        stmt = (
            select(FleetInvite)
            .where(FleetInvite.invited_user_id == user_id)
            .where(FleetInvite.status == 'pending')
            .where(FleetInvite.expires_at > time.time())
            .order_by(desc(FleetInvite.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_sent_invites(
        self,
        fleet_owner_id: int,
        limit: int = 50,
    ) -> List[FleetInvite]:
        """Get invites sent by a fleet owner."""
        stmt = (
            select(FleetInvite)
            .where(FleetInvite.fleet_owner_id == fleet_owner_id)
            .order_by(desc(FleetInvite.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_accepted(self, invite_id: int) -> None:
        """Mark an invite as accepted."""
        import time
        invite = await self.get_by_id(invite_id)
        if invite:
            invite.status = 'accepted'
            invite.responded_at = time.time()
            await self.session.flush()
    
    async def mark_declined(self, invite_id: int) -> None:
        """Mark an invite as declined."""
        import time
        invite = await self.get_by_id(invite_id)
        if invite:
            invite.status = 'declined'
            invite.responded_at = time.time()
            await self.session.flush()


class TierUpgradeRepository(BaseRepository[TierUpgradeRequest]):
    """Repository for Tier Upgrade Request entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, TierUpgradeRequest)
    
    async def get_pending_upgrades(self) -> List[TierUpgradeRequest]:
        """Get all pending tier upgrade requests."""
        stmt = (
            select(TierUpgradeRequest)
            .where(TierUpgradeRequest.status == 'pending')
            .order_by(desc(TierUpgradeRequest.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_upgrades_for_user(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[TierUpgradeRequest]:
        """Get upgrade history for a user."""
        stmt = (
            select(TierUpgradeRequest)
            .where(TierUpgradeRequest.user_id == user_id)
            .order_by(desc(TierUpgradeRequest.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def approve_upgrade(self, request_id: int, admin_id: int) -> None:
        """Approve a tier upgrade request."""
        import time
        request = await self.get_by_id(request_id)
        if request:
            request.status = 'approved'
            request.processed_at = time.time()
            request.processed_by = admin_id
            await self.session.flush()
    
    async def reject_upgrade(
        self,
        request_id: int,
        admin_id: int,
        reason: str,
    ) -> None:
        """Reject a tier upgrade request."""
        import time
        request = await self.get_by_id(request_id)
        if request:
            request.status = 'rejected'
            request.processed_at = time.time()
            request.processed_by = admin_id
            request.rejection_reason = reason
            await self.session.flush()
