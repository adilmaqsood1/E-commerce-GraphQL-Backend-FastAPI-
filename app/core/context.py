from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from fastapi import Request
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.core.security import decode_access_token

if TYPE_CHECKING:
    import redis.asyncio as aioredis

    from app.dataloaders.category_loader import CategoryLoader
    from app.dataloaders.product_loader import ProductLoader
    from app.dataloaders.user_loader import UserLoader
    from app.models.user import User


@dataclass
class GraphQLContext:
    """Injected into every GraphQL resolver via `info.context`."""

    request: Request
    db: AsyncSession
    redis: "aioredis.Redis"
    current_user: Optional["User"] = None

    # DataLoaders (lazy-initialised per request)
    _category_loader: Optional["CategoryLoader"] = field(default=None, repr=False)
    _user_loader: Optional["UserLoader"] = field(default=None, repr=False)
    _product_loader: Optional["ProductLoader"] = field(default=None, repr=False)

    @property
    def category_loader(self) -> "CategoryLoader":
        if self._category_loader is None:
            from app.dataloaders.category_loader import CategoryLoader

            self._category_loader = CategoryLoader(db=self.db)
        return self._category_loader

    @property
    def user_loader(self) -> "UserLoader":
        if self._user_loader is None:
            from app.dataloaders.user_loader import UserLoader

            self._user_loader = UserLoader(db=self.db)
        return self._user_loader

    @property
    def product_loader(self) -> "ProductLoader":
        if self._product_loader is None:
            from app.dataloaders.product_loader import ProductLoader

            self._product_loader = ProductLoader(db=self.db)
        return self._product_loader


async def get_context(request: Request, db: AsyncSession) -> GraphQLContext:
    """
    Build the GraphQL context from the incoming HTTP request.
    Extracts and validates JWT from the Authorization header.
    """
    redis = await get_redis()
    current_user = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            if user_id:
                # Check if the token's jti is blacklisted
                jti = payload.get("jti", "")
                blacklisted = await redis.get(f"blacklist:{jti}")
                if not blacklisted:
                    from app.models.user import User
                    from sqlalchemy import select

                    result = await db.execute(
                        select(User).where(User.id == user_id, User.is_active == True)
                    )
                    current_user = result.scalar_one_or_none()
        except (JWTError, Exception):
            pass  # Unauthenticated — resolvers enforce access control

    return GraphQLContext(
        request=request,
        db=db,
        redis=redis,
        current_user=current_user,
    )
