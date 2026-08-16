from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

import strawberry

from app.schemas.review import ReviewType


@strawberry.type
class CategoryType:
    id: str
    name: str
    slug: str
    description: Optional[str]
    image_url: Optional[str]
    parent_id: Optional[str]
    is_active: bool
    created_at: datetime


@strawberry.type
class BrandType:
    id: str
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    website: Optional[str]
    is_active: bool
    created_at: datetime


@strawberry.type
class ProductImageType:
    id: str
    url: str
    alt_text: Optional[str]
    position: int
    is_primary: bool


@strawberry.type
class ProductVariantType:
    id: str
    name: str
    sku: str
    price: float
    stock: int
    attributes: Optional[str]
    image_url: Optional[str]
    is_active: bool


@strawberry.type
class InventoryType:
    id: str
    quantity: int
    reserved: int
    available: int
    low_stock_threshold: int
    is_low_stock: bool
    updated_at: datetime


@strawberry.type
class ProductType:
    id: str
    name: str
    slug: str
    description: Optional[str]
    short_description: Optional[str]
    sku: str
    price: float
    compare_at_price: Optional[float]
    is_active: bool
    is_featured: bool
    average_rating: float
    review_count: int
    sold_count: int
    tags: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Resolved relationships
    category: Optional[CategoryType]
    brand: Optional[BrandType]
    images: List[ProductImageType]
    variants: List[ProductVariantType]
    inventory: Optional[InventoryType]
    reviews: List[ReviewType]


@strawberry.type
class RecommendedProductType:
    """Product with an AI recommendation score."""
    product: ProductType
    score: float
    reason: str  # "collaborative", "content_based", "popularity"


# ── Input types ───────────────────────────────────────────────────────────────
@strawberry.input
class ProductFilterInput:
    category_id: Optional[str] = None
    brand_id: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    in_stock: Optional[bool] = None
    is_featured: Optional[bool] = None
    search: Optional[str] = None

@strawberry.enum
class ProductSortField(enum.Enum):
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING = "rating"
    NEWEST = "newest"
    POPULARITY = "popularity"


@strawberry.input
class CreateProductInput:
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    sku: str
    price: float
    compare_at_price: Optional[float] = None
    category_id: Optional[str] = None
    brand_id: Optional[str] = None
    tags: Optional[str] = None
    initial_stock: Optional[int] = 0


@strawberry.input
class UpdateProductInput:
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    tags: Optional[str] = None
