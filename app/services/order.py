"""Order service — create, cancel, update status."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import List, Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ForbiddenError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from app.core.permissions import Role
from app.core.redis import CacheKeys
from app.models.cart import CartItem
from app.models.order import Order, OrderItem, OrderStatus, OrderStatusHistory, Payment
from app.models.product import Product, ProductInventory, ProductVariant
from app.models.user import User, UserProductInteraction
from app.schemas.order import CreateOrderInput


def _order_number() -> str:
    import random, string
    return "ORD-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))


class OrderService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis

    async def create_order(self, user: User, data: CreateOrderInput) -> Order:
        """Convert cart to order with atomic stock decrement."""
        # Load cart
        cart_result = await self.db.execute(
            select(CartItem)
            .options(
                selectinload(CartItem.product).selectinload(Product.inventory),
                selectinload(CartItem.variant),
            )
            .where(CartItem.user_id == user.id)
        )
        cart_items = cart_result.scalars().all()

        if not cart_items:
            raise ValidationError("Cart is empty")

        # Validate address
        from app.models.user import Address
        addr_result = await self.db.execute(
            select(Address).where(
                Address.id == data.address_id, Address.user_id == user.id
            )
        )
        address = addr_result.scalar_one_or_none()
        if not address:
            raise NotFoundError("Shipping address not found")

        # Apply coupon
        discount_amount = Decimal("0")
        coupon_id = None
        if data.coupon_code:
            from app.services.coupon import CouponService
            coupon_svc = CouponService(self.db)
            coupon = await coupon_svc.validate_coupon(data.coupon_code, user.id)
            coupon_id = coupon.id
            subtotal = sum(
                Decimal(str(ci.unit_price)) * ci.quantity for ci in cart_items
            )
            discount_amount = coupon_svc.calculate_discount(coupon, subtotal)

        # Build order items and decrement stock atomically
        order_items_data = []
        subtotal = Decimal("0")

        for ci in cart_items:
            product = ci.product
            variant = ci.variant

            if variant:
                if variant.stock < ci.quantity:
                    raise InsufficientStockError(product.name, ci.quantity, variant.stock)
                variant.stock -= ci.quantity
            else:
                inv = product.inventory
                if not inv or inv.available < ci.quantity:
                    available = inv.available if inv else 0
                    raise InsufficientStockError(product.name, ci.quantity, available)
                inv.quantity -= ci.quantity

            item_total = Decimal(str(ci.unit_price)) * ci.quantity
            subtotal += item_total

            order_items_data.append(
                OrderItem(
                    product_id=product.id,
                    variant_id=variant.id if variant else None,
                    quantity=ci.quantity,
                    unit_price=ci.unit_price,
                    total_price=item_total,
                    product_name=product.name,
                    variant_name=variant.name if variant else None,
                )
            )

            # Track purchase interaction for AI
            interaction = UserProductInteraction(
                user_id=user.id,
                product_id=product.id,
                interaction_type="purchase",
                weight=5.0,
            )
            self.db.add(interaction)

            # Update sold count
            product.sold_count += ci.quantity

        shipping_amount = Decimal("5.99")  # Simplified
        tax_rate = Decimal("0.08")
        taxable = subtotal - discount_amount
        tax_amount = (taxable * tax_rate).quantize(Decimal("0.01"))
        total = taxable + shipping_amount + tax_amount

        order = Order(
            order_number=_order_number(),
            customer_id=user.id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_amount=shipping_amount,
            tax_amount=tax_amount,
            total=total,
            coupon_id=coupon_id,
            shipping_address_id=address.id,
            notes=data.notes,
        )
        self.db.add(order)
        await self.db.flush()

        # Add order items
        for item in order_items_data:
            item.order_id = order.id
            self.db.add(item)

        # Create payment record
        payment = Payment(
            order_id=order.id,
            method=data.payment_method,
            amount=total,
            status="PAID" if data.payment_method == "COD" else "PENDING",
        )
        self.db.add(payment)

        # Record initial status
        history = OrderStatusHistory(
            order_id=order.id,
            status=OrderStatus.PENDING,
            note="Order placed",
            changed_by_id=user.id,
        )
        self.db.add(history)

        # Clear cart
        for ci in cart_items:
            await self.db.delete(ci)

        await self.db.flush()

        # Increment coupon usage
        if coupon_id:
            from app.models.coupon import Coupon
            coupon_obj = await self.db.get(Coupon, coupon_id)
            if coupon_obj:
                coupon_obj.usage_count += 1

        # Publish status update for subscription
        await self.redis.publish(
            CacheKeys.order_status_channel(order.id),
            f"{OrderStatus.PENDING}",
        )

        return order

    async def update_order_status(
        self, order_id: str, new_status: str, user: User, note: Optional[str] = None
    ) -> Order:
        order = await self._get_order(order_id)
        if Role(user.role) not in (Role.SELLER, Role.ADMIN):
            raise ForbiddenError("Only sellers and admins can update order status")

        order.status = new_status
        if new_status == OrderStatus.DELIVERED:
            order.delivered_at = datetime.now(UTC)

        history = OrderStatusHistory(
            order_id=order.id,
            status=new_status,
            note=note,
            changed_by_id=user.id,
        )
        self.db.add(history)
        await self.db.flush()

        # Publish for WebSocket subscription
        await self.redis.publish(
            CacheKeys.order_status_channel(order.id), new_status
        )

        return order

    async def cancel_order(self, order_id: str, user: User) -> Order:
        order = await self._get_order(order_id)
        if order.customer_id != user.id and Role(user.role) != Role.ADMIN:
            raise ForbiddenError("You can only cancel your own orders")
        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            raise ValidationError(f"Cannot cancel order in '{order.status}' status")

        return await self.update_order_status(
            order_id, OrderStatus.CANCELLED, user, note="Cancelled by customer"
        )

    async def get_user_orders(self, user_id: str) -> List[Order]:
        result = await self.db.execute(
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.payment),
                selectinload(Order.shipping_address),
            )
            .where(Order.customer_id == user_id)
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()

    async def _get_order(self, order_id: str) -> Order:
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError(f"Order '{order_id}' not found")
        return order
