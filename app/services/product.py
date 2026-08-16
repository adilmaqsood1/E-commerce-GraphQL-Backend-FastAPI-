"""Product service — CRUD, listing with filters/pagination, full-text search."""

from __future__ import annotations

import base64
import hashlib
import json
from typing import List, Optional

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import redis.asyncio as aioredis

from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.core.permissions import Role
from app.models.product import (
    Category,
    Brand,
    Product,
    ProductImage,
    ProductInventory,
    ProductVariant,
)
from app.models.user import User, UserProductInteraction
from app.schemas.product import (
    CreateProductInput,
    ProductFilterInput,
    ProductSortField,
    UpdateProductInput,
)


def _slug(name: str) -> str:
    import re
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    return s


class ProductService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis

    async def get_by_id(self, product_id: str, track_user_id: Optional[str] = None) -> Product:
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.variants),
                selectinload(Product.inventory),
                selectinload(Product.reviews),
                selectinload(Product.category),
                selectinload(Product.brand),
            )
            .where(Product.id == product_id, Product.is_active == True)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError(f"Product '{product_id}' not found")

        # Track view interaction for AI recommendations
        if track_user_id:
            await self._track_interaction(track_user_id, product_id, "view", weight=1.0)

        return product

    async def get_by_slug(self, slug: str) -> Product:
        result = await self.db.execute(
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.variants),
                selectinload(Product.inventory),
                selectinload(Product.reviews),
                selectinload(Product.category),
                selectinload(Product.brand),
            )
            .where(Product.slug == slug, Product.is_active == True)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError(f"Product with slug '{slug}' not found")
        return product

    async def list_products(
        self,
        filters: Optional[ProductFilterInput] = None,
        sort: Optional[ProductSortField] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> tuple[List[Product], int, bool]:
        """
        Returns (products, total_count, has_next_page).
        Uses cursor-based pagination.
        """
        # Build cache key
        cache_key = self._build_cache_key(filters, sort, first, after)
        cached = await self.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            # Re-fetch from DB using cached IDs for ORM objects
            ids = data["ids"]
            if not ids:
                return [], data["total"], False
            result = await self.db.execute(
                select(Product)
                .options(selectinload(Product.images), selectinload(Product.category))
                .where(Product.id.in_(ids))
            )
            products = {p.id: p for p in result.scalars().all()}
            ordered = [products[i] for i in ids if i in products]
            return ordered, data["total"], data["has_next"]

        query = select(Product).where(Product.is_active == True)

        # Apply filters
        if filters:
            if filters.category_id:
                query = query.where(Product.category_id == filters.category_id)
            if filters.brand_id:
                query = query.where(Product.brand_id == filters.brand_id)
            if filters.min_price is not None:
                query = query.where(Product.price >= filters.min_price)
            if filters.max_price is not None:
                query = query.where(Product.price <= filters.max_price)
            if filters.is_featured is not None:
                query = query.where(Product.is_featured == filters.is_featured)
            if filters.in_stock:
                query = query.join(ProductInventory).where(
                    ProductInventory.quantity > ProductInventory.reserved
                )
            if filters.search:
                # Full-text search via tsvector
                query = query.where(
                    Product.search_vector.op("@@")(
                        func.plainto_tsquery("english", filters.search)
                    )
                )

        # Count total (before pagination)
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        # Cursor offset
        offset = 0
        if after:
            try:
                decoded = base64.b64decode(after.encode()).decode()
                offset = int(decoded.replace("cursor:", ""))
            except Exception:
                offset = 0

        # Apply sort
        if sort == ProductSortField.PRICE_ASC:
            query = query.order_by(Product.price.asc())
        elif sort == ProductSortField.PRICE_DESC:
            query = query.order_by(Product.price.desc())
        elif sort == ProductSortField.RATING:
            query = query.order_by(Product.average_rating.desc())
        elif sort == ProductSortField.POPULARITY:
            query = query.order_by(Product.sold_count.desc())
        else:  # NEWEST (default)
            query = query.order_by(Product.created_at.desc())

        query = (
            query.options(selectinload(Product.images), selectinload(Product.category))
            .offset(offset)
            .limit(first + 1)
        )

        result = await self.db.execute(query)
        products = result.scalars().all()

        has_next = len(products) > first
        products = products[:first]

        # Cache for 5 minutes
        await self.redis.setex(
            cache_key,
            300,
            json.dumps(
                {"ids": [p.id for p in products], "total": total, "has_next": has_next}
            ),
        )

        return list(products), total, has_next

    async def create_product(self, data: CreateProductInput, seller: User) -> Product:
        if Role(seller.role) not in (Role.SELLER, Role.ADMIN):
            raise ForbiddenError("Only sellers and admins can create products")

        # Check unique SKU
        existing = await self.db.execute(
            select(Product).where(Product.sku == data.sku)
        )
        if existing.scalar_one_or_none():
            raise ValidationError(f"SKU '{data.sku}' already exists")

        slug = _slug(data.name)
        # Ensure slug uniqueness
        slug_check = await self.db.execute(
            select(Product).where(Product.slug == slug)
        )
        if slug_check.scalar_one_or_none():
            import uuid
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"

        product = Product(
            name=data.name,
            slug=slug,
            description=data.description,
            short_description=data.short_description,
            sku=data.sku,
            price=data.price,
            compare_at_price=data.compare_at_price,
            category_id=data.category_id,
            brand_id=data.brand_id,
            seller_id=seller.id,
            tags=data.tags,
        )
        self.db.add(product)
        await self.db.flush()

        # Create inventory record
        inventory = ProductInventory(
            product_id=product.id,
            quantity=data.initial_stock or 0,
        )
        self.db.add(inventory)
        await self.db.flush()

        return product

    async def update_product(
        self, product_id: str, data: UpdateProductInput, seller: User
    ) -> Product:
        product = await self._get_owned_product(product_id, seller)

        if data.name is not None:
            product.name = data.name
        if data.description is not None:
            product.description = data.description
        if data.price is not None:
            product.price = data.price
        if data.is_active is not None:
            product.is_active = data.is_active
        if data.is_featured is not None:
            product.is_featured = data.is_featured
        if data.tags is not None:
            product.tags = data.tags

        await self.db.flush()
        # Invalidate cache
        await self.redis.delete(f"product:{product_id}")
        return product

    async def delete_product(self, product_id: str, seller: User) -> bool:
        product = await self._get_owned_product(product_id, seller)
        product.is_active = False
        await self.db.flush()
        await self.redis.delete(f"product:{product_id}")
        return True

    async def _get_owned_product(self, product_id: str, seller: User) -> Product:
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundError(f"Product '{product_id}' not found")
        if Role(seller.role) != Role.ADMIN and product.seller_id != seller.id:
            raise ForbiddenError("You don't own this product")
        return product

    async def _track_interaction(
        self, user_id: str, product_id: str, interaction_type: str, weight: float
    ) -> None:
        interaction = UserProductInteraction(
            user_id=user_id,
            product_id=product_id,
            interaction_type=interaction_type,
            weight=weight,
        )
        self.db.add(interaction)
        # Don't await flush — let it commit with the main transaction

    def _build_cache_key(self, filters, sort, first, after) -> str:
        key_data = json.dumps(
            {
                "filters": filters.__dict__ if filters else {},
                "sort": sort.value if sort else None,
                "first": first,
                "after": after,
            },
            sort_keys=True,
        )
        hash_ = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"products:{hash_}"
