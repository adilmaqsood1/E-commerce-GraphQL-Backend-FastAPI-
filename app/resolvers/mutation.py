"""GraphQL Mutation resolvers."""

from __future__ import annotations

from typing import Optional

import strawberry
from strawberry.types import Info

from app.core.context import GraphQLContext
from app.core.exceptions import UnauthorizedError
from app.schemas.common import AuthPayload, MutationSuccess
from app.schemas.order import (
    AddToCartInput,
    CartItemType,
    CreateOrderInput,
    OrderType,
    UpdateCartItemInput,
)
from app.schemas.product import CreateProductInput, ProductType, UpdateProductInput
from app.schemas.review import CreateReviewInput, ReviewType
from app.schemas.user import AddressInput, AddressType, LoginInput, RegisterInput


@strawberry.type
class Mutation:
    # ── Auth Mutations ─────────────────────────────────────────────────────────
    @strawberry.mutation(description="Register a new user account")
    async def register(
        self, info: Info[GraphQLContext, None], input: RegisterInput
    ) -> AuthPayload:
        from app.services.auth import AuthService
        ctx = info.context
        svc = AuthService(ctx.db, ctx.redis)
        return await svc.register(input)

    @strawberry.mutation(description="Login with email and password")
    async def login(
        self, info: Info[GraphQLContext, None], input: LoginInput
    ) -> AuthPayload:
        from app.services.auth import AuthService
        ctx = info.context
        svc = AuthService(ctx.db, ctx.redis)
        return await svc.login(input)

    @strawberry.mutation(description="Refresh access token using refresh token")
    async def refresh_token(
        self, info: Info[GraphQLContext, None], refresh_token: str
    ) -> AuthPayload:
        from app.services.auth import AuthService
        ctx = info.context
        svc = AuthService(ctx.db, ctx.redis)
        return await svc.refresh(refresh_token)

    @strawberry.mutation(description="Logout and invalidate refresh token")
    async def logout(
        self, info: Info[GraphQLContext, None], refresh_token: str
    ) -> MutationSuccess:
        from app.services.auth import AuthService
        ctx = info.context
        svc = AuthService(ctx.db, ctx.redis)
        await svc.logout(refresh_token)
        return MutationSuccess(message="Logged out successfully")

    # ── Cart Mutations ─────────────────────────────────────────────────────────
    @strawberry.mutation(description="Add a product to the shopping cart")
    async def add_to_cart(
        self, info: Info[GraphQLContext, None], input: AddToCartInput
    ) -> CartItemType:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.cart import CartService
        svc = CartService(ctx.db)
        item = await svc.add_to_cart(ctx.current_user.id, input)
        return CartItemType(
            id=item.id, quantity=item.quantity,
            unit_price=float(item.unit_price), total_price=float(item.total_price),
            product_id=item.product_id, variant_id=item.variant_id,
            created_at=item.created_at,
        )

    @strawberry.mutation(description="Update cart item quantity")
    async def update_cart_item(
        self, info: Info[GraphQLContext, None], input: UpdateCartItemInput
    ) -> CartItemType:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.cart import CartService
        svc = CartService(ctx.db)
        item = await svc.update_cart_item(ctx.current_user.id, input)
        return CartItemType(
            id=item.id, quantity=item.quantity,
            unit_price=float(item.unit_price), total_price=float(item.total_price),
            product_id=item.product_id, variant_id=item.variant_id,
            created_at=item.created_at,
        )

    @strawberry.mutation(description="Remove a specific item from cart")
    async def remove_from_cart(
        self, info: Info[GraphQLContext, None], cart_item_id: str
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.cart import CartService
        svc = CartService(ctx.db)
        await svc.remove_from_cart(ctx.current_user.id, cart_item_id)
        return MutationSuccess(message="Item removed from cart")

    @strawberry.mutation(description="Clear all items from cart")
    async def clear_cart(self, info: Info[GraphQLContext, None]) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.cart import CartService
        svc = CartService(ctx.db)
        await svc.clear_cart(ctx.current_user.id)
        return MutationSuccess(message="Cart cleared")

    # ── Wishlist Mutations ─────────────────────────────────────────────────────
    @strawberry.mutation(description="Add product to wishlist")
    async def add_to_wishlist(
        self, info: Info[GraphQLContext, None], product_id: str
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from sqlalchemy import select
        from app.models.cart import WishlistItem
        from app.models.user import UserProductInteraction
        existing = await ctx.db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == ctx.current_user.id,
                WishlistItem.product_id == product_id,
            )
        )
        if not existing.scalar_one_or_none():
            item = WishlistItem(user_id=ctx.current_user.id, product_id=product_id)
            ctx.db.add(item)
            interaction = UserProductInteraction(
                user_id=ctx.current_user.id, product_id=product_id,
                interaction_type="wishlist", weight=2.0,
            )
            ctx.db.add(interaction)
        return MutationSuccess(message="Added to wishlist")

    @strawberry.mutation(description="Remove product from wishlist")
    async def remove_from_wishlist(
        self, info: Info[GraphQLContext, None], product_id: str
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from sqlalchemy import select
        from app.models.cart import WishlistItem
        result = await ctx.db.execute(
            select(WishlistItem).where(
                WishlistItem.user_id == ctx.current_user.id,
                WishlistItem.product_id == product_id,
            )
        )
        item = result.scalar_one_or_none()
        if item:
            await ctx.db.delete(item)
        return MutationSuccess(message="Removed from wishlist")

    # ── Order Mutations ────────────────────────────────────────────────────────
    @strawberry.mutation(description="Create an order from cart")
    async def create_order(
        self, info: Info[GraphQLContext, None], input: CreateOrderInput
    ) -> OrderType:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.order import OrderService
        from app.resolvers.query import Query
        svc = OrderService(ctx.db, ctx.redis)
        order = await svc.create_order(ctx.current_user, input)
        # Trigger background email job
        from app.workers.email import send_order_confirmation_task
        await ctx.redis.rpush(
            "arq:queue",
            str({"task": "send_order_confirmation", "order_id": order.id, "user_id": ctx.current_user.id}),
        )
        return OrderType(
            id=order.id, order_number=order.order_number, status=order.status,
            subtotal=float(order.subtotal), discount_amount=float(order.discount_amount),
            shipping_amount=float(order.shipping_amount), tax_amount=float(order.tax_amount),
            total=float(order.total), currency=order.currency, notes=order.notes,
            created_at=order.created_at, updated_at=order.updated_at, delivered_at=order.delivered_at,
            items=[], payment=None, shipping_address=None,
        )

    @strawberry.mutation(description="Cancel an order")
    async def cancel_order(
        self, info: Info[GraphQLContext, None], order_id: str
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.order import OrderService
        svc = OrderService(ctx.db, ctx.redis)
        await svc.cancel_order(order_id, ctx.current_user)
        return MutationSuccess(message="Order cancelled")

    @strawberry.mutation(description="Update order status (Seller/Admin only)")
    async def update_order_status(
        self,
        info: Info[GraphQLContext, None],
        order_id: str,
        status: str,
        note: Optional[str] = None,
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.order import OrderService
        svc = OrderService(ctx.db, ctx.redis)
        await svc.update_order_status(order_id, status, ctx.current_user, note)
        return MutationSuccess(message=f"Order status updated to {status}")

    # ── Product Mutations (Seller/Admin) ───────────────────────────────────────
    @strawberry.mutation(description="Create a new product (Seller/Admin only)")
    async def create_product(
        self, info: Info[GraphQLContext, None], input: CreateProductInput
    ) -> ProductType:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.product import ProductService
        from app.resolvers.query import _product_to_type
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        from app.models.product import Product
        svc = ProductService(ctx.db, ctx.redis)
        product = await svc.create_product(input, ctx.current_user)
        result = await ctx.db.execute(
            select(Product)
            .options(
                selectinload(Product.images),
                selectinload(Product.variants),
                selectinload(Product.inventory),
                selectinload(Product.reviews),
                selectinload(Product.category),
                selectinload(Product.brand),
            )
            .where(Product.id == product.id)
        )
        p = result.scalar_one()
        return _product_to_type(p)

    @strawberry.mutation(description="Update a product (Seller/Admin only)")
    async def update_product(
        self,
        info: Info[GraphQLContext, None],
        product_id: str,
        input: UpdateProductInput,
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.product import ProductService
        svc = ProductService(ctx.db, ctx.redis)
        await svc.update_product(product_id, input, ctx.current_user)
        return MutationSuccess(message="Product updated")

    # ── Review Mutations ───────────────────────────────────────────────────────
    @strawberry.mutation(description="Submit a product review")
    async def create_review(
        self, info: Info[GraphQLContext, None], input: CreateReviewInput
    ) -> ReviewType:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.core.exceptions import ValidationError
        if not (1 <= input.rating <= 5):
            raise ValidationError("Rating must be between 1 and 5")

        from sqlalchemy import select
        from app.models.review import Review
        from app.models.order import Order, OrderItem
        from app.models.user import UserProductInteraction

        # Check if verified purchase
        purchase_check = await ctx.db.execute(
            select(OrderItem).join(Order).where(
                Order.customer_id == ctx.current_user.id,
                OrderItem.product_id == input.product_id,
            )
        )
        is_verified = purchase_check.scalar_one_or_none() is not None

        review = Review(
            product_id=input.product_id,
            user_id=ctx.current_user.id,
            order_id=input.order_id,
            rating=input.rating,
            title=input.title,
            comment=input.comment,
            is_verified_purchase=is_verified,
        )
        ctx.db.add(review)

        # Track review interaction for AI
        interaction = UserProductInteraction(
            user_id=ctx.current_user.id, product_id=input.product_id,
            interaction_type="review", weight=3.0,
        )
        ctx.db.add(interaction)

        # Update product aggregate stats
        from sqlalchemy import func
        from app.models.product import Product
        avg_result = await ctx.db.execute(
            select(func.avg(Review.rating), func.count(Review.id))
            .where(Review.product_id == input.product_id, Review.is_approved == True)
        )
        avg, count = avg_result.one()
        product_result = await ctx.db.execute(select(Product).where(Product.id == input.product_id))
        prod = product_result.scalar_one_or_none()
        if prod:
            prod.average_rating = float(avg or 0)
            prod.review_count = count or 0

        await ctx.db.flush()
        return ReviewType(
            id=review.id, product_id=review.product_id, rating=review.rating,
            title=review.title, comment=review.comment,
            is_verified_purchase=review.is_verified_purchase,
            helpful_count=review.helpful_count, created_at=review.created_at,
            user_name=ctx.current_user.full_name,
        )

    # ── Address Mutations ──────────────────────────────────────────────────────
    @strawberry.mutation(description="Add a shipping address")
    async def add_address(
        self, info: Info[GraphQLContext, None], input: AddressInput
    ) -> AddressType:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.models.user import Address
        address = Address(
            user_id=ctx.current_user.id, label=input.label, full_name=input.full_name,
            phone=input.phone, line1=input.line1, line2=input.line2,
            city=input.city, state=input.state, postal_code=input.postal_code,
            country=input.country, is_default=input.is_default or False,
        )
        ctx.db.add(address)
        await ctx.db.flush()
        return AddressType(
            id=address.id, label=address.label, full_name=address.full_name,
            phone=address.phone, line1=address.line1, line2=address.line2,
            city=address.city, state=address.state, postal_code=address.postal_code,
            country=address.country, is_default=address.is_default,
            created_at=address.created_at,
        )

    # ── Coupon Mutations ───────────────────────────────────────────────────────
    @strawberry.mutation(description="Validate a coupon code")
    async def validate_coupon(
        self, info: Info[GraphQLContext, None], code: str
    ) -> MutationSuccess:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.coupon import CouponService
        svc = CouponService(ctx.db)
        coupon = await svc.validate_coupon(code, ctx.current_user.id)
        return MutationSuccess(
            message=f"Coupon '{coupon.code}' is valid — {coupon.discount_type} discount of {coupon.discount_value}"
        )
