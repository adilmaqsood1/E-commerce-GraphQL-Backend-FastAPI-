"""DataLoader for Category — batches N category fetches into 1 query."""

from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.dataloader import DataLoader

from app.models.product import Category


async def load_categories(
    keys: List[str], db: AsyncSession
) -> List[Category | None]:
    """Batch-load categories by their IDs."""
    result = await db.execute(
        select(Category).where(Category.id.in_(keys))
    )
    categories = result.scalars().all()
    category_map = {c.id: c for c in categories}
    return [category_map.get(key) for key in keys]


class CategoryLoader(DataLoader[str, Category | None]):
    def __init__(self, db: AsyncSession):
        super().__init__(load_fn=lambda keys: load_categories(keys, db))
