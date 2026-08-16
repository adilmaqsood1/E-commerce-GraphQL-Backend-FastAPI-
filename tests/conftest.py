"""Pytest fixtures — async DB, Redis, test app, and GraphQL client."""

from __future__ import annotations

from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # noqa: F401 - ensure all ORM models are registered on Base.metadata
from app.core.database import AsyncSessionLocal, Base, engine
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def gql(client: AsyncClient, query: str, variables: dict = None, token: str = None):
    """Helper to send a GraphQL request."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )
    return response.json()

