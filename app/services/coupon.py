"""Coupon service — validate, calculate discount."""

from __future__ import annotations

from decimal import Decimal
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.coupon import Coupon, DiscountType
from app.models.order import Order


class CouponService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_coupon(self, code: str, user_id: str) -> Coupon:
        result = await self.db.execute(
            select(Coupon).where(Coupon.code == code.upper())
        )
        coupon = result.scalar_one_or_none()
        if not coupon:
            raise NotFoundError(f"Coupon '{code}' not found")
        if not coupon.is_valid:
            raise ValidationError(f"Coupon '{code}' is invalid or expired")

        # Check per-user usage
        user_usage_result = await self.db.execute(
            select(Order).where(
                Order.coupon_id == coupon.id,
                Order.customer_id == user_id,
            )
        )
        user_usage = len(user_usage_result.scalars().all())
        if user_usage >= coupon.per_user_limit:
            raise ValidationError(f"You have already used coupon '{code}' {coupon.per_user_limit} time(s)")

        return coupon

    def calculate_discount(self, coupon: Coupon, subtotal: Decimal) -> Decimal:
        if coupon.minimum_order_amount and subtotal < coupon.minimum_order_amount:
            raise ValidationError(
                f"Minimum order amount for this coupon is {coupon.minimum_order_amount}"
            )

        if coupon.discount_type == DiscountType.PERCENTAGE:
            discount = (subtotal * coupon.discount_value / 100).quantize(Decimal("0.01"))
            if coupon.maximum_discount_amount:
                discount = min(discount, coupon.maximum_discount_amount)
        elif coupon.discount_type == DiscountType.FIXED:
            discount = min(coupon.discount_value, subtotal)
        elif coupon.discount_type == DiscountType.FREE_SHIPPING:
            discount = Decimal("0")  # Handled in shipping calculation
        else:
            discount = Decimal("0")

        return discount
