"""
Domain and HTTP exception hierarchy.

Services raise AppException subclasses; the global handler in main.py
translates them into consistent JSON error responses.
"""

from typing import Any


class AppException(Exception):
    """Base application exception with HTTP status mapping."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppException):
    status_code = 404
    error_code = "not_found"


class ValidationError(AppException):
    status_code = 422
    error_code = "validation_error"


class DatabaseError(AppException):
    status_code = 503
    error_code = "database_error"


class VectorStoreError(AppException):
    status_code = 503
    error_code = "vector_store_error"


class LLMError(AppException):
    status_code = 502
    error_code = "llm_error"


class EmbeddingError(AppException):
    status_code = 503
    error_code = "embedding_error"
