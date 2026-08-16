"""Shared Strawberry GraphQL types: pagination, connections, errors."""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

import strawberry

T = TypeVar("T")


@strawberry.type
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]


@strawberry.type
class Edge(Generic[T]):
    cursor: str
    node: T


@strawberry.type
class Connection(Generic[T]):
    """Relay-style cursor pagination connection."""
    edges: List[Edge[T]]
    page_info: PageInfo
    total_count: int


@strawberry.input
class PaginationInput:
    first: Optional[int] = 20
    after: Optional[str] = None
    last: Optional[int] = None
    before: Optional[str] = None


@strawberry.type
class MutationSuccess:
    success: bool = True
    message: str = "Operation completed successfully"


@strawberry.type
class AuthPayload:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


def encode_cursor(value: str) -> str:
    import base64
    return base64.b64encode(f"cursor:{value}".encode()).decode()


def decode_cursor(cursor: str) -> str:
    import base64
    decoded = base64.b64decode(cursor.encode()).decode()
    return decoded.replace("cursor:", "", 1)
