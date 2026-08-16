"""Strawberry GraphQL types — User, Address."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import strawberry

from app.core.permissions import Role


@strawberry.type
class AddressType:
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
    is_default: bool
    created_at: datetime


@strawberry.type
class UserType:
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    addresses: List[AddressType]


@strawberry.type
class MeType:
    """Current authenticated user — includes sensitive fields."""
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    addresses: List[AddressType]


@strawberry.input
class RegisterInput:
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None


@strawberry.input
class LoginInput:
    email: str
    password: str


@strawberry.input
class UpdateProfileInput:
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None


@strawberry.input
class AddressInput:
    label: Optional[str] = "Home"
    full_name: str
    phone: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    is_default: Optional[bool] = False
