"""Authentication service — register, login, refresh, logout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Optional

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.core.exceptions import (
    ConflictError,
    UnauthorizedError,
    ValidationError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.core.config import settings
from app.models.user import User
from app.schemas.common import AuthPayload
from app.schemas.user import RegisterInput, LoginInput


class AuthService:
    def __init__(self, db: AsyncSession, redis: aioredis.Redis):
        self.db = db
        self.redis = redis

    async def register(self, data: RegisterInput) -> AuthPayload:
        """Register a new user and return tokens."""
        # Check for existing user
        existing = await self.db.execute(
            select(User).where(User.email == data.email.lower())
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Email '{data.email}' is already registered")

        if len(data.password) < 8:
            raise ValidationError("Password must be at least 8 characters")

        user = User(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
        )
        self.db.add(user)
        await self.db.flush()  # Get user.id without committing

        return await self._generate_tokens(user)

    async def login(self, data: LoginInput) -> AuthPayload:
        """Authenticate user credentials and return tokens."""
        result = await self.db.execute(
            select(User).where(User.email == data.email.lower())
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password")

        if not user.is_active:
            raise UnauthorizedError("Account is disabled")

        return await self._generate_tokens(user)

    async def refresh(self, refresh_token: str) -> AuthPayload:
        """Rotate refresh token and issue new access token."""
        try:
            payload = decode_refresh_token(refresh_token)
        except JWTError:
            raise UnauthorizedError("Invalid or expired refresh token")

        jti = payload.get("jti", "")
        if await self.redis.get(f"blacklist:{jti}"):
            raise UnauthorizedError("Refresh token has been revoked")

        user_id = payload.get("sub")
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise UnauthorizedError("User not found or inactive")

        # Blacklist old refresh token
        exp = payload.get("exp", 0)
        ttl = max(0, exp - int(datetime.now(UTC).timestamp()))
        if ttl > 0:
            await self.redis.setex(f"blacklist:{jti}", ttl, "1")

        return await self._generate_tokens(user)

    async def logout(self, refresh_token: str) -> bool:
        """Blacklist the refresh token."""
        try:
            payload = decode_refresh_token(refresh_token)
            jti = payload.get("jti", "")
            exp = payload.get("exp", 0)
            ttl = max(0, exp - int(datetime.now(UTC).timestamp()))
            if ttl > 0:
                await self.redis.setex(f"blacklist:{jti}", ttl, "1")
        except JWTError:
            pass  # Already invalid — that's fine
        return True

    async def _generate_tokens(self, user: User) -> AuthPayload:
        access_token = create_access_token(
            subject=user.id, role=user.role
        )
        refresh_token, _ = create_refresh_token(subject=user.id)
        return AuthPayload(
            access_token=access_token,
            refresh_token=refresh_token,
        )
