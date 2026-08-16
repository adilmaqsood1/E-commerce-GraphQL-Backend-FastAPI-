"""Tests — Authentication."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import gql


REGISTER_MUTATION = """
mutation Register($input: RegisterInput!) {
  register(input: $input) {
    accessToken
    refreshToken
    tokenType
  }
}
"""

LOGIN_MUTATION = """
mutation Login($input: LoginInput!) {
  login(input: $input) {
    accessToken
    refreshToken
  }
}
"""

REFRESH_MUTATION = """
mutation Refresh($refreshToken: String!) {
  refreshToken(refreshToken: $refreshToken) {
    accessToken
    refreshToken
  }
}
"""

ME_QUERY = """
query {
  me {
    id
    email
    fullName
    role
  }
}
"""


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    result = await gql(
        client,
        REGISTER_MUTATION,
        {"input": {"email": "test@example.com", "password": "secret123", "fullName": "Test User"}},
    )
    assert "errors" not in result
    data = result["data"]["register"]
    assert data["accessToken"]
    assert data["refreshToken"]
    assert data["tokenType"] == "Bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    payload = {"input": {"email": "dup@example.com", "password": "secret123", "fullName": "Dup User"}}
    await gql(client, REGISTER_MUTATION, payload)
    result = await gql(client, REGISTER_MUTATION, payload)
    assert "errors" in result


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Register first
    await gql(
        client, REGISTER_MUTATION,
        {"input": {"email": "login_test@example.com", "password": "mypassword", "fullName": "Login User"}},
    )
    result = await gql(
        client, LOGIN_MUTATION,
        {"input": {"email": "login_test@example.com", "password": "mypassword"}},
    )
    assert "errors" not in result
    assert result["data"]["login"]["accessToken"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    result = await gql(
        client, LOGIN_MUTATION,
        {"input": {"email": "login_test@example.com", "password": "wrongpassword"}},
    )
    assert "errors" in result


@pytest.mark.asyncio
async def test_me_query_authenticated(client: AsyncClient):
    # Register and get token
    reg = await gql(
        client, REGISTER_MUTATION,
        {"input": {"email": "me_test@example.com", "password": "mypassword", "fullName": "Me User"}},
    )
    token = reg["data"]["register"]["accessToken"]
    result = await gql(client, ME_QUERY, token=token)
    assert "errors" not in result
    assert result["data"]["me"]["email"] == "me_test@example.com"


@pytest.mark.asyncio
async def test_me_query_unauthenticated(client: AsyncClient):
    result = await gql(client, ME_QUERY)
    # Should return null (not error) for unauthenticated
    assert result["data"]["me"] is None
