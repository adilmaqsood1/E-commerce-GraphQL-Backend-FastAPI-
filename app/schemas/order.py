"""Strawberry GraphQL types — Order, Cart, Payment."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import strawberry


@strawberry.type
class PaymentType:
    id: str
    status: str
    method: str
    amount: float
    currency: str
    transaction_id: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime


@strawberry.type
class ShippingAddressType:
    id: str
    label: str
    full_name: str
    phone: str
    line1: str
    line2: Optional[str]
    city: str
    state: str
    postal_code: str
    country: str


@strawberry.type
class OrderItemProductType:
    id: str
    name: str
    slug: str
    images: List["OrderItemImageType"]


@strawberry.type
class OrderItemImageType:
    url: str


@strawberry.type
class OrderItemType:
    id: str
    quantity: int
    unit_price: float
    total_price: float
    product_name: str
    variant_name: Optional[str]
    product: Optional[OrderItemProductType]


@strawberry.type
class OrderType:
    id: str
    order_number: str
    status: str
    subtotal: float
    discount_amount: float
    shipping_amount: float
    tax_amount: float
    total: float
    currency: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    delivered_at: Optional[datetime]

    items: List[OrderItemType]
    payment: Optional[PaymentType]
    shipping_address: Optional[ShippingAddressType]


@strawberry.type
class CartItemType:
    id: str
    quantity: int
    unit_price: float
    total_price: float
    product_id: str
    variant_id: Optional[str]
    created_at: datetime

    # Resolved lazily
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    variant_name: Optional[str] = None


@strawberry.type
class CartType:
    items: List[CartItemType]
    item_count: int
    subtotal: float


# ── Input types ───────────────────────────────────────────────────────────────
@strawberry.input
class AddToCartInput:
    product_id: str
    quantity: int = 1
    variant_id: Optional[str] = None


@strawberry.input
class UpdateCartItemInput:
    cart_item_id: str
    quantity: int


@strawberry.input
class CreateOrderInput:
    address_id: str
    payment_method: str  # "CARD", "PAYPAL", "COD"
    coupon_code: Optional[str] = None
    notes: Optional[str] = None


@strawberry.type
class OrderStatusUpdate:
    order_id: str
    status: str
    updated_at: datetime
