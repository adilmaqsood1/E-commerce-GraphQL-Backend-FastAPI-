"""GraphQL Query resolvers."""

from __future__ import annotations

from typing import List, Optional

import strawberry
from strawberry.types import Info

from app.core.context import GraphQLContext
from app.core.exceptions import UnauthorizedError
from app.core.permissions import login_required
from app.schemas.common import Connection, Edge, PageInfo, encode_cursor
from app.schemas.product import (
    BrandType,
    CategoryType,
    ProductFilterInput,
    ProductSortField,
    ProductType,
    RecommendedProductType,
)
from app.schemas.order import CartType, CartItemType, OrderType
from app.schemas.user import MeType, AddressType
from app.schemas.review import ReviewType


def _product_to_type(p) -> ProductType:
    from app.schemas.product import ProductImageType, ProductVariantType, InventoryType
    return ProductType(
        id=p.id,
        name=p.name,
        slug=p.slug,
        description=p.description,
        short_description=p.short_description,
        sku=p.sku,
        price=float(p.price),
        compare_at_price=float(p.compare_at_price) if p.compare_at_price else None,
        is_active=p.is_active,
        is_featured=p.is_featured,
        average_rating=p.average_rating,
        review_count=p.review_count,
        sold_count=p.sold_count,
        tags=p.tags,
        created_at=p.created_at,
        updated_at=p.updated_at,
        category=CategoryType(
            id=p.category.id,
            name=p.category.name,
            slug=p.category.slug,
            description=p.category.description,
            image_url=p.category.image_url,
            parent_id=p.category.parent_id,
            is_active=p.category.is_active,
            created_at=p.category.created_at,
        ) if p.category else None,
        brand=BrandType(
            id=p.brand.id,
            name=p.brand.name,
            slug=p.brand.slug,
            description=p.brand.description,
            logo_url=p.brand.logo_url,
            website=p.brand.website,
            is_active=p.brand.is_active,
            created_at=p.brand.created_at,
        ) if p.brand else None,
        images=[
            ProductImageType(
                id=img.id,
                url=img.url,
                alt_text=img.alt_text,
                position=img.position,
                is_primary=img.is_primary,
            )
            for img in p.images
        ],
        variants=[
            ProductVariantType(
                id=v.id,
                name=v.name,
                sku=v.sku,
                price=float(v.price),
                stock=v.stock,
                attributes=v.attributes,
                image_url=v.image_url,
                is_active=v.is_active,
            )
            for v in p.variants
        ],
        inventory=InventoryType(
            id=p.inventory.id,
            quantity=p.inventory.quantity,
            reserved=p.inventory.reserved,
            available=p.inventory.available,
            low_stock_threshold=p.inventory.low_stock_threshold,
            is_low_stock=p.inventory.is_low_stock,
            updated_at=p.inventory.updated_at,
        ) if p.inventory else None,
        reviews=[
            ReviewType(
                id=r.id,
                product_id=r.product_id,
                rating=r.rating,
                title=r.title,
                comment=r.comment,
                is_verified_purchase=r.is_verified_purchase,
                helpful_count=r.helpful_count,
                created_at=r.created_at,
            )
            for r in p.reviews
        ],
    )


@strawberry.type
class Query:
    @strawberry.field(description="Fetch a single product by ID")
    async def product(self, info: Info[GraphQLContext, None], id: str) -> Optional[ProductType]:
        from app.services.product import ProductService
        ctx = info.context
        svc = ProductService(ctx.db, ctx.redis)
        user_id = ctx.current_user.id if ctx.current_user else None
        p = await svc.get_by_id(id, track_user_id=user_id)
        return _product_to_type(p)

    @strawberry.field(description="Fetch a product by slug")
    async def product_by_slug(self, info: Info[GraphQLContext, None], slug: str) -> Optional[ProductType]:
        from app.services.product import ProductService
        ctx = info.context
        svc = ProductService(ctx.db, ctx.redis)
        p = await svc.get_by_slug(slug)
        return _product_to_type(p)

    @strawberry.field(description="List products with filtering, sorting, and cursor pagination")
    async def products(
        self,
        info: Info[GraphQLContext, None],
        filters: Optional[ProductFilterInput] = None,
        sort: Optional[ProductSortField] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> Connection[ProductType]:
        from app.services.product import ProductService
        ctx = info.context
        svc = ProductService(ctx.db, ctx.redis)
        prods, total, has_next = await svc.list_products(filters, sort, first, after)

        edges = [
            Edge(cursor=encode_cursor(str(i)), node=_product_to_type(p))
            for i, p in enumerate(prods)
        ]

        return Connection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                has_previous_page=after is not None,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=total,
        )

    @strawberry.field(description="AI-powered product recommendations for current user")
    async def recommended_products(
        self,
        info: Info[GraphQLContext, None],
        limit: int = 10,
    ) -> List[RecommendedProductType]:
        from app.services.recommendation import RecommendationService
        from app.services.product import ProductService
        ctx = info.context
        user_id = ctx.current_user.id if ctx.current_user else "anonymous"

        svc = RecommendationService(ctx.db, ctx.redis)
        recs = await svc.get_recommendations(user_id, limit=limit)

        product_svc = ProductService(ctx.db, ctx.redis)
        results = []
        for rec in recs:
            try:
                p = await product_svc.get_by_id(rec.product_id)
                results.append(
                    RecommendedProductType(
                        product=_product_to_type(p),
                        score=rec.score,
                        reason=rec.reason,
                    )
                )
            except Exception:
                continue
        return results

    @strawberry.field(description="List all active categories")
    async def categories(self, info: Info[GraphQLContext, None]) -> List[CategoryType]:
        from sqlalchemy import select
        from app.models.product import Category
        result = await info.context.db.execute(
            select(Category).where(Category.is_active == True).order_by(Category.name)
        )
        cats = result.scalars().all()
        return [
            CategoryType(
                id=c.id, name=c.name, slug=c.slug, description=c.description,
                image_url=c.image_url, parent_id=c.parent_id,
                is_active=c.is_active, created_at=c.created_at,
            )
            for c in cats
        ]

    @strawberry.field(description="List all active brands")
    async def brands(self, info: Info[GraphQLContext, None]) -> List[BrandType]:
        from sqlalchemy import select
        from app.models.product import Brand
        result = await info.context.db.execute(
            select(Brand).where(Brand.is_active == True).order_by(Brand.name)
        )
        brands = result.scalars().all()
        return [
            BrandType(
                id=b.id, name=b.name, slug=b.slug, description=b.description,
                logo_url=b.logo_url, website=b.website,
                is_active=b.is_active, created_at=b.created_at,
            )
            for b in brands
        ]

    @strawberry.field(description="Get current authenticated user")
    async def me(self, info: Info[GraphQLContext, None]) -> Optional[MeType]:
        ctx = info.context
        user = ctx.current_user
        if not user:
            return None
        from sqlalchemy import select
        from app.models.user import User, Address
        from sqlalchemy.orm import selectinload
        result = await ctx.db.execute(
            select(User).options(selectinload(User.addresses)).where(User.id == user.id)
        )
        u = result.scalar_one_or_none()
        if not u:
            return None
        return MeType(
            id=u.id, email=u.email, full_name=u.full_name, role=u.role,
            phone=u.phone, avatar_url=u.avatar_url, is_active=u.is_active,
            is_verified=u.is_verified, created_at=u.created_at,
            addresses=[
                AddressType(
                    id=a.id, label=a.label, full_name=a.full_name, phone=a.phone,
                    line1=a.line1, line2=a.line2, city=a.city, state=a.state,
                    postal_code=a.postal_code, country=a.country,
                    is_default=a.is_default, created_at=a.created_at,
                )
                for a in u.addresses
            ],
        )

    @strawberry.field(description="Get current user's orders")
    async def my_orders(self, info: Info[GraphQLContext, None]) -> List[OrderType]:
        ctx = info.context
        if not ctx.current_user:
            raise UnauthorizedError()
        from app.services.order import OrderService
        from app.schemas.order import (
            OrderItemType, PaymentType, ShippingAddressType, OrderItemProductType, OrderItemImageType
        )
        svc = OrderService(ctx.db, ctx.redis)
        orders = await svc.get_user_orders(ctx.current_user.id)
        result = []
        for o in orders:
            result.append(OrderType(
                id=o.id, order_number=o.order_number, status=o.status,
                subtotal=float(o.subtotal), discount_amount=float(o.discount_amount),
                shipping_amount=float(o.shipping_amount), tax_amount=float(o.tax_amount),
                total=float(o.total), currency=o.currency, notes=o.notes,
                created_at=o.created_at, updated_at=o.updated_at, delivered_at=o.delivered_at,
                items=[
                    OrderItemType(
                        id=item.id, quantity=item.quantity,
                        unit_price=float(item.unit_price), total_price=float(item.total_price),
                        product_name=item.product_name, variant_name=item.variant_name,
                        product=OrderItemProductType(
                            id=item.product.id, name=item.product.name,
                            slug=item.product.slug,
                            images=[OrderItemImageType(url=img.url) for img in item.product.images],
                        ) if item.product else None,
                    )
                    for item in o.items
                ],
                payment=PaymentType(
                    id=o.payment.id, status=o.payment.status, method=o.payment.method,
                    amount=float(o.payment.amount), currency=o.payment.currency,
                    transaction_id=o.payment.transaction_id, paid_at=o.payment.paid_at,
                    created_at=o.payment.created_at,
                ) if o.payment else None,
                shipping_address=ShippingAddressType(
                    id=o.shipping_address.id, label=o.shipping_address.label,
                    full_name=o.shipping_address.full_name, phone=o.shipping_address.phone,
                    line1=o.shipping_address.line1, line2=o.shipping_address.line2,
                    city=o.shipping_address.city, state=o.shipping_address.state,
                    postal_code=o.shipping_address.postal_code, country=o.shipping_address.country,
                ) if o.shipping_address else None,
            ))
        return result

    @strawberry.field(description="Get current user's shopping cart")
    async def my_cart(self, info: Info[GraphQLContext, None]) -> Optional[CartType]:
        ctx = info.context
        if not ctx.current_user:
            return None
        from app.services.cart import CartService
        from app.schemas.order import CartItemType
        svc = CartService(ctx.db)
        items = await svc.get_cart(ctx.current_user.id)
        item_types = [
            CartItemType(
                id=i.id, quantity=i.quantity,
                unit_price=float(i.unit_price), total_price=float(i.total_price),
                product_id=i.product_id, variant_id=i.variant_id,
                created_at=i.created_at,
                product_name=i.product.name if i.product else None,
                product_image=i.product.images[0].url if i.product and i.product.images else None,
                variant_name=i.variant.name if i.variant else None,
            )
            for i in items
        ]
        subtotal = sum(float(i.total_price) for i in items)
        return CartType(items=item_types, item_count=len(items), subtotal=subtotal)
