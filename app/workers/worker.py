"""ARQ Worker settings — registers all background tasks."""

from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.email import (
    send_order_confirmation,
    send_shipping_notification,
    send_welcome_email,
)


async def startup(ctx: dict) -> None:
    """Called when ARQ worker starts."""
    import redis.asyncio as aioredis
    ctx["redis"] = aioredis.from_url(settings.redis_url, decode_responses=True)
    print("ARQ Worker started")


async def shutdown(ctx: dict) -> None:
    """Called when ARQ worker shuts down."""
    await ctx["redis"].aclose()
    print("ARQ Worker shut down")


class WorkerSettings:
    functions = [
        send_order_confirmation,
        send_shipping_notification,
        send_welcome_email,
    ]

    redis_settings = RedisSettings.from_dsn(settings.redis_url)

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 10
    job_timeout = 300  # seconds
    keep_result = 3600  # keep job result for 1 hour
