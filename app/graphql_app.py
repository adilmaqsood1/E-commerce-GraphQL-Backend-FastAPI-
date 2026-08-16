from __future__ import annotations

from typing import Any, Optional

import strawberry
from fastapi import Depends, Request
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.resolvers.mutation import Mutation
from app.resolvers.query import Query
from app.resolvers.subscription import Subscription
from app.core.context import GraphQLContext, get_context
from app.core.database import get_db


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    config=StrawberryConfig(auto_camel_case=True),
)


async def get_graphql_context(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GraphQLContext:
    """
    HTTP context getter — FastAPI Depends handles DB session lifecycle.
    Strawberry calls this per request; the session is committed/closed
    by FastAPI's dependency injection after the response is sent.
    """
    return await get_context(request, db)


async def get_ws_context(
    ws: Any,
    connection_params: Optional[dict] = None,
) -> GraphQLContext:
    """
    WebSocket context getter for subscriptions.
    Opens its own DB session for the lifetime of the WS connection.
    """
    from app.core.database import AsyncSessionLocal
    from app.core.redis import get_redis
    from app.core.context import GraphQLContext

    db = AsyncSessionLocal()
    redis = await get_redis()
    return GraphQLContext(request=ws, db=db, redis=redis)


graphql_router = GraphQLRouter(
    schema=schema,
    context_getter=get_graphql_context,
    graphql_ide="graphiql",  # Enable GraphiQL playground at /graphql
    subscription_protocols=["graphql-ws", "graphql-transport-ws"],
)
