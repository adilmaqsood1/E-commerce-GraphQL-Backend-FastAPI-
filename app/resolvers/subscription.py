"""GraphQL Subscription resolvers — real-time order status via Redis pub/sub."""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import strawberry
from strawberry.types import Info

from app.core.context import GraphQLContext
from app.core.redis import CacheKeys
from app.schemas.order import OrderStatusUpdate
from datetime import datetime, UTC


@strawberry.type
class Subscription:
    @strawberry.subscription(
        description="Subscribe to real-time order status changes"
    )
    async def order_status_changed(
        self,
        info: Info[GraphQLContext, None],
        order_id: str,
    ) -> AsyncGenerator[OrderStatusUpdate, None]:
        """
        Listens on Redis pub/sub channel for order status updates.
        The order service publishes when status changes.
        """
        redis = info.context.redis
        channel = CacheKeys.order_status_channel(order_id)

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    new_status = message["data"]
                    yield OrderStatusUpdate(
                        order_id=order_id,
                        status=new_status,
                        updated_at=datetime.now(UTC),
                    )
                else:
                    await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    @strawberry.subscription(
        description="Subscribe to inventory level changes for a product"
    )
    async def inventory_updated(
        self,
        info: Info[GraphQLContext, None],
        product_id: str,
    ) -> AsyncGenerator[str, None]:
        """Yields the new available stock whenever it changes."""
        redis = info.context.redis
        channel = CacheKeys.inventory_channel(product_id)

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel)

        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    yield message["data"]
                else:
                    await asyncio.sleep(0.5)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
