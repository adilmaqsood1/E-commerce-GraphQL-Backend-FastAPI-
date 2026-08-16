from __future__ import annotations

import enum
from functools import wraps
from typing import Any, Callable

import strawberry
from strawberry.types import Info

from app.core.exceptions import ForbiddenError, UnauthorizedError


class Role(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    SELLER = "SELLER"
    ADMIN = "ADMIN"


# ── Permission sets ───────────────────────────────────────────────────────────
CUSTOMER_PERMISSIONS = frozenset(
    [
        "view_products",
        "manage_cart",
        "create_orders",
        "view_own_orders",
        "manage_wishlist",
        "create_reviews",
        "view_own_profile",
    ]
)

SELLER_PERMISSIONS = frozenset(
    CUSTOMER_PERMISSIONS
    | {
        "manage_products",
        "manage_inventory",
        "view_seller_orders",
    }
)

ADMIN_PERMISSIONS = frozenset(
    SELLER_PERMISSIONS
    | {
        "manage_users",
        "manage_sellers",
        "manage_all_products",
        "view_analytics",
        "manage_coupons",
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.CUSTOMER: CUSTOMER_PERMISSIONS,
    Role.SELLER: SELLER_PERMISSIONS,
    Role.ADMIN: ADMIN_PERMISSIONS,
}


def has_permission(role: Role, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def has_role(role: Role, required: Role | list[Role]) -> bool:
    if isinstance(required, list):
        return role in required
    return role == required


# ── Strawberry resolver decorators ────────────────────────────────────────────
def login_required(func: Callable) -> Callable:
    """Ensure the caller is authenticated."""

    @wraps(func)
    async def wrapper(*args: Any, info: Info, **kwargs: Any) -> Any:
        if info.context.current_user is None:
            raise UnauthorizedError("Authentication required")
        return await func(*args, info=info, **kwargs)

    return wrapper


def role_required(*roles: Role) -> Callable:
    """Ensure the caller has one of the specified roles."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, info: Info, **kwargs: Any) -> Any:
            user = info.context.current_user
            if user is None:
                raise UnauthorizedError("Authentication required")
            if Role(user.role) not in roles:
                raise ForbiddenError(
                    f"This action requires one of: {[r.value for r in roles]}"
                )
            return await func(*args, info=info, **kwargs)

        return wrapper

    return decorator


def permission_required(permission: str) -> Callable:
    """Ensure the caller has a specific permission."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, info: Info, **kwargs: Any) -> Any:
            user = info.context.current_user
            if user is None:
                raise UnauthorizedError("Authentication required")
            if not has_permission(Role(user.role), permission):
                raise ForbiddenError(f"Missing permission: {permission}")
            return await func(*args, info=info, **kwargs)

        return wrapper

    return decorator
