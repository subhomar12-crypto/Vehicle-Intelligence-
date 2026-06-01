"""
Trip and driver behavior repository.
"""

from typing import Optional, List

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.trip import (
    Trip, TripEvent, DriverBehaviorSummary
)
from predict.core.db.repositories.base import BaseRepository


class TripRepository(BaseRepository[Trip]):
    """Repository for Trip entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, Trip)
    
    async def get_trips_for_profile(
        self,
        profile_id: int,
        limit: int = 50,
    ) -> List[Trip]:
        """Get trips for a vehicle profile."""
        stmt = (
            select(Trip)
            .where(Trip.profile_id == profile_id)
            .order_by(desc(Trip.start_time))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_active_trip(self, profile_id: int) -> Optional[Trip]:
        """Get currently active (ongoing) trip for a vehicle."""
        stmt = (
            select(Trip)
            .where(Trip.profile_id == profile_id)
            .where(Trip.end_time.is_(None))
            .order_by(desc(Trip.start_time))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_trips_in_range(
        self,
        profile_id: int,
        start_ts: float,
        end_ts: float,
    ) -> List[Trip]:
        """Get trips within a time range."""
        stmt = (
            select(Trip)
            .where(Trip.profile_id == profile_id)
            .where(
                and_(
                    Trip.start_time >= start_ts,
                    Trip.start_time <= end_ts,
                )
            )
            .order_by(Trip.start_time)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_trips_for_driver(
        self,
        driver_id: int,
        limit: int = 50,
    ) -> List[Trip]:
        """Get trips for a specific driver."""
        stmt = (
            select(Trip)
            .where(Trip.driver_id == driver_id)
            .order_by(desc(Trip.start_time))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def end_trip(
        self,
        trip_id: int,
        end_time: float,
        end_location: dict,
        total_distance_km: float,
    ) -> Optional[Trip]:
        """Mark a trip as ended."""
        trip = await self.get_by_id(trip_id)
        if trip:
            trip.end_time = end_time
            trip.end_location_lat = end_location.get('lat')
            trip.end_location_lon = end_location.get('lon')
            trip.total_distance_km = total_distance_km
            await self.session.flush()
        return trip


class TripEventRepository(BaseRepository[TripEvent]):
    """Repository for Trip Event entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, TripEvent)
    
    async def get_events_for_trip(self, trip_id: int) -> List[TripEvent]:
        """Get all events for a trip."""
        stmt = (
            select(TripEvent)
            .where(TripEvent.trip_id == trip_id)
            .order_by(TripEvent.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_events_by_type(
        self,
        trip_id: int,
        event_type: str,
    ) -> List[TripEvent]:
        """Get events of a specific type for a trip."""
        stmt = (
            select(TripEvent)
            .where(TripEvent.trip_id == trip_id)
            .where(TripEvent.event_type == event_type)
            .order_by(TripEvent.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_recent_events(
        self,
        profile_id: int,
        limit: int = 100,
    ) -> List[TripEvent]:
        """Get recent events for a vehicle."""
        stmt = (
            select(TripEvent)
            .where(TripEvent.profile_id == profile_id)
            .order_by(desc(TripEvent.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class DriverBehaviorRepository(BaseRepository[DriverBehaviorSummary]):
    """Repository for Driver Behavior Summary entities."""
    
    def __init__(self, session: AsyncSession):
        super().__init__(session, DriverBehaviorSummary)
    
    async def get_driver_summary(
        self,
        driver_id: int,
    ) -> Optional[DriverBehaviorSummary]:
        """Get behavior summary for a driver."""
        stmt = (
            select(DriverBehaviorSummary)
            .where(DriverBehaviorSummary.driver_id == driver_id)
            .order_by(desc(DriverBehaviorSummary.period_end))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_summaries_for_profile(
        self,
        profile_id: int,
        limit: int = 12,
    ) -> List[DriverBehaviorSummary]:
        """Get behavior summaries for a vehicle."""
        stmt = (
            select(DriverBehaviorSummary)
            .where(DriverBehaviorSummary.profile_id == profile_id)
            .order_by(desc(DriverBehaviorSummary.period_end))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_summary_for_period(
        self,
        driver_id: int,
        period_start: float,
        period_end: float,
    ) -> Optional[DriverBehaviorSummary]:
        """Get behavior summary for a specific period."""
        stmt = (
            select(DriverBehaviorSummary)
            .where(DriverBehaviorSummary.driver_id == driver_id)
            .where(DriverBehaviorSummary.period_start == period_start)
            .where(DriverBehaviorSummary.period_end == period_end)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
