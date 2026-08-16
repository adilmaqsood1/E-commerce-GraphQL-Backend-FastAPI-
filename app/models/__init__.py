"""Central import for all ORM models — ensures Alembic sees all tables."""

from app.models.cart import CartItem, WishlistItem
from app.models.coupon import Coupon
from app.models.order import Order, OrderItem, OrderStatusHistory, Payment
from app.models.product import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductInventory,
    ProductVariant,
)
from app.models.review import Review
from app.models.user import Address, User, UserProductInteraction

__all__ = [
    "User",
    "Address",
    "UserProductInteraction",
    "Category",
    "Brand",
    "Product",
    "ProductImage",
    "ProductVariant",
    "ProductInventory",
    "Order",
    "OrderItem",
    "Payment",
    "OrderStatusHistory",
    "CartItem",
    "WishlistItem",
    "Review",
    "Coupon",
]
