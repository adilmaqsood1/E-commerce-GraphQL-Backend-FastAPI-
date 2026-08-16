"""Cart service — add, remove, update, clear."""

from __future__ import annotations

from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError, InsufficientStockError
from app.models.cart import CartItem
from app.models.product import Product, ProductVariant
from app.models.user import UserProductInteraction
from app.schemas.order import AddToCartInput, UpdateCartItemInput


class CartService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_cart(self, user_id: str) -> List[CartItem]:
        result = await self.db.execute(
            select(CartItem)
            .options(
                selectinload(CartItem.product).selectinload(Product.images),
                selectinload(CartItem.variant),
            )
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.created_at.desc())
        )
        return result.scalars().all()

    async def add_to_cart(self, user_id: str, data: AddToCartInput) -> CartItem:
        if data.quantity < 1:
            raise ValidationError("Quantity must be at least 1")

        # Fetch product
        product_result = await self.db.execute(
            select(Product).where(Product.id == data.product_id, Product.is_active == True)
        )
        product = product_result.scalar_one_or_none()
        if not product:
            raise NotFoundError(f"Product '{data.product_id}' not found")

        # Determine price and check stock
        if data.variant_id:
            variant_result = await self.db.execute(
                select(ProductVariant).where(
                    ProductVariant.id == data.variant_id,
                    ProductVariant.product_id == data.product_id,
                )
            )
            variant = variant_result.scalar_one_or_none()
            if not variant:
                raise NotFoundError("Product variant not found")
            if variant.stock < data.quantity:
                raise InsufficientStockError(
                    product.name, data.quantity, variant.stock
                )
            unit_price = Decimal(str(variant.price))
        else:
            unit_price = Decimal(str(product.price))

        # Check if item already in cart — update quantity
        existing_result = await self.db.execute(
            select(CartItem).where(
                CartItem.user_id == user_id,
                CartItem.product_id == data.product_id,
                CartItem.variant_id == data.variant_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            existing.quantity += data.quantity
            existing.unit_price = unit_price
            await self.db.flush()
            return existing

        cart_item = CartItem(
            user_id=user_id,
            product_id=data.product_id,
            variant_id=data.variant_id,
            quantity=data.quantity,
            unit_price=unit_price,
        )
        self.db.add(cart_item)

        # Track wishlist/add-to-cart interaction for AI
        interaction = UserProductInteraction(
            user_id=user_id,
            product_id=data.product_id,
            interaction_type="cart",
            weight=2.0,
        )
        self.db.add(interaction)

        await self.db.flush()
        return cart_item

    async def update_cart_item(
        self, user_id: str, data: UpdateCartItemInput
    ) -> CartItem:
        result = await self.db.execute(
            select(CartItem).where(
                CartItem.id == data.cart_item_id, CartItem.user_id == user_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError("Cart item not found")

        if data.quantity < 1:
            raise ValidationError("Quantity must be at least 1")

        item.quantity = data.quantity
        await self.db.flush()
        return item

    async def remove_from_cart(self, user_id: str, cart_item_id: str) -> bool:
        result = await self.db.execute(
            select(CartItem).where(
                CartItem.id == cart_item_id, CartItem.user_id == user_id
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError("Cart item not found")
        await self.db.delete(item)
        await self.db.flush()
        return True

    async def clear_cart(self, user_id: str) -> bool:
        result = await self.db.execute(
            select(CartItem).where(CartItem.user_id == user_id)
        )
        items = result.scalars().all()
        for item in items:
            await self.db.delete(item)
        await self.db.flush()
        return True
