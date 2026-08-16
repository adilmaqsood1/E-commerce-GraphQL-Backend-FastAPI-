from __future__ import annotations

from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

# ── Singleton pool ─────────────────────────────────────────────────────────────
_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis connection pool (singleton)."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool gracefully."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


# ── Cache helpers ──────────────────────────────────────────────────────────────
class CacheKeys:
    """Centralised cache key namespace."""

    @staticmethod
    def product(product_id: str) -> str:
        return f"product:{product_id}"

    @staticmethod
    def product_list(filters_hash: str) -> str:
        return f"products:{filters_hash}"

    @staticmethod
    def recommendations(user_id: str) -> str:
        return f"recommendations:{user_id}"

    @staticmethod
    def cart(user_id: str) -> str:
        return f"cart:{user_id}"

    @staticmethod
    def refresh_token_blacklist(jti: str) -> str:
        return f"blacklist:{jti}"

    @staticmethod
    def order_status_channel(order_id: str) -> str:
        return f"order_status:{order_id}"

    @staticmethod
    def inventory_channel(product_id: str) -> str:
        return f"inventory:{product_id}"
