"""DataLoader for User — batches N user fetches into 1 query."""

from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.dataloader import DataLoader

from app.models.user import User


async def load_users(keys: List[str], db: AsyncSession) -> List[User | None]:
    result = await db.execute(select(User).where(User.id.in_(keys)))
    users = result.scalars().all()
    user_map = {u.id: u for u in users}
    return [user_map.get(key) for key in keys]


class UserLoader(DataLoader[str, User | None]):
    def __init__(self, db: AsyncSession):
        super().__init__(load_fn=lambda keys: load_users(keys, db))
