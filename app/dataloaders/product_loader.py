"""DataLoader for Product — batches N product fetches into 1 query."""

from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.dataloader import DataLoader

from app.models.product import Product


async def load_products(keys: List[str], db: AsyncSession) -> List[Product | None]:
    result = await db.execute(select(Product).where(Product.id.in_(keys)))
    products = result.scalars().all()
    product_map = {p.id: p for p in products}
    return [product_map.get(key) for key in keys]


class ProductLoader(DataLoader[str, Product | None]):
    def __init__(self, db: AsyncSession):
        super().__init__(load_fn=lambda keys: load_products(keys, db))
