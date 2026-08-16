"""Tests — Products."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import gql

PRODUCTS_QUERY = """
query Products($first: Int) {
  products(first: $first) {
    totalCount
    edges {
      cursor
      node {
        id
        name
        price
        slug
      }
    }
    pageInfo {
      hasNextPage
      hasPreviousPage
      startCursor
      endCursor
    }
  }
}
"""

PRODUCT_QUERY = """
query Product($id: String!) {
  product(id: $id) {
    id
    name
    price
    category {
      name
    }
    variants {
      id
      name
      price
    }
    images {
      url
    }
  }
}
"""

CREATE_PRODUCT_MUTATION = """
mutation CreateProduct($input: CreateProductInput!) {
  createProduct(input: $input) {
    id
    name
    sku
    price
  }
}
"""

REGISTER_MUTATION = """
mutation Register($input: RegisterInput!) {
  register(input: $input) {
    accessToken
  }
}
"""


@pytest.mark.asyncio
async def test_products_list_empty(client: AsyncClient):
    result = await gql(client, PRODUCTS_QUERY, {"first": 10})
    assert "errors" not in result
    data = result["data"]["products"]
    assert "totalCount" in data
    assert "edges" in data


@pytest.mark.asyncio
async def test_products_pagination_fields(client: AsyncClient):
    result = await gql(client, PRODUCTS_QUERY, {"first": 5})
    assert "errors" not in result
    page_info = result["data"]["products"]["pageInfo"]
    assert "hasNextPage" in page_info
    assert "hasPreviousPage" in page_info


@pytest.mark.asyncio
async def test_create_product_unauthenticated(client: AsyncClient):
    """Unauthenticated users should not be able to create products."""
    result = await gql(
        client,
        CREATE_PRODUCT_MUTATION,
        {
            "input": {
                "name": "Test Product",
                "sku": "SKU-001",
                "price": 29.99,
            }
        },
    )
    # Should error with auth requirement
    assert "errors" in result
