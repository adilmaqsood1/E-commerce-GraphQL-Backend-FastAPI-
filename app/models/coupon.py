"""SQLAlchemy ORM model — Coupon."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class DiscountType:
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"
    FREE_SHIPPING = "FREE_SHIPPING"


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    discount_type: Mapped[str] = mapped_column(String(20), nullable=False)  # PERCENTAGE, FIXED
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    minimum_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    maximum_discount_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    per_user_limit: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def is_valid(self) -> bool:
        now = datetime.now(UTC)
        if not self.is_active:
            return False
        if self.usage_limit and self.usage_count >= self.usage_limit:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True

    def __repr__(self) -> str:
        return f"<Coupon {self.code}>"
