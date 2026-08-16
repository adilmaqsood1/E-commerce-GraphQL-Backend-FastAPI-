from __future__ import annotations

import strawberry


@strawberry.type
class AppError(Exception):
    message: str
    code: str


class UnauthorizedError(Exception):
    def __init__(self, message: str = "Unauthorized"):
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    def __init__(self, message: str = "Forbidden"):
        self.message = message
        super().__init__(message)


class NotFoundError(Exception):
    def __init__(self, message: str = "Not found"):
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InsufficientStockError(Exception):
    def __init__(self, product_name: str, requested: int, available: int):
        self.message = (
            f"Insufficient stock for '{product_name}': "
            f"requested {requested}, available {available}"
        )
        super().__init__(self.message)
