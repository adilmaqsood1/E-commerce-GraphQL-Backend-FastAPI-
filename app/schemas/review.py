"""Strawberry GraphQL types — Review."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import strawberry


@strawberry.type
class ReviewType:
    id: str
    product_id: str
    rating: int
    title: Optional[str]
    comment: Optional[str]
    is_verified_purchase: bool
    helpful_count: int
    created_at: datetime

    # Resolved by DataLoader
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None


@strawberry.input
class CreateReviewInput:
    product_id: str
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    order_id: Optional[str] = None
