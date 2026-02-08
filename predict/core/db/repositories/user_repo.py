"""
User and API key repository.
"""

from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from predict.core.db.models.user import User, ApiKey
from predict.core.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        stmt = (
            select(User)
            .where(User.status == "active")
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class ApiKeyRepository(BaseRepository[ApiKey]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ApiKey)

    async def get_by_key_hash(self, key_hash: str) -> Optional[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_key_id(self, key_id: str) -> Optional[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.key_id == key_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_keys_for_user(self, user_id: int) -> List[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id, ApiKey.status == "active")
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
