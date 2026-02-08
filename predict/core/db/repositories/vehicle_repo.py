"""
Vehicle profile and data repository.
"""

from typing import Optional, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.vehicle import VehicleProfile, VehicleData, ServiceRecord
from predict.core.db.repositories.base import BaseRepository


class VehicleProfileRepository(BaseRepository[VehicleProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, VehicleProfile)

    async def get_by_plate(self, plate: str) -> Optional[VehicleProfile]:
        stmt = select(VehicleProfile).where(VehicleProfile.license_plate == plate)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_vin(self, vin: str) -> Optional[VehicleProfile]:
        stmt = select(VehicleProfile).where(VehicleProfile.vin == vin)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class VehicleDataRepository(BaseRepository[VehicleData]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, VehicleData)

    async def get_latest(self, profile_id: int, limit: int = 50) -> List[VehicleData]:
        stmt = (
            select(VehicleData)
            .where(VehicleData.profile_id == profile_id)
            .order_by(desc(VehicleData.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_history(
        self, profile_id: int, start_ts: float, end_ts: float
    ) -> List[VehicleData]:
        stmt = (
            select(VehicleData)
            .where(
                VehicleData.profile_id == profile_id,
                VehicleData.timestamp >= start_ts,
                VehicleData.timestamp <= end_ts,
            )
            .order_by(VehicleData.timestamp)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ServiceRecordRepository(BaseRepository[ServiceRecord]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ServiceRecord)

    async def get_for_profile(self, profile_id: int) -> List[ServiceRecord]:
        stmt = (
            select(ServiceRecord)
            .where(ServiceRecord.profile_id == profile_id)
            .order_by(desc(ServiceRecord.service_date))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
