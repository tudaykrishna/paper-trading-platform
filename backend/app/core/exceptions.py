"""Domain exceptions mapped to HTTP responses in ``app.main``."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class AuthError(AppError):
    status_code = 401
    code = "auth_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class InsufficientFundsError(AppError):
    status_code = 422
    code = "insufficient_funds"


class MarketClosedError(AppError):
    status_code = 422
    code = "market_closed"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
