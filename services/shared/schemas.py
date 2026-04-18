"""
Standard response envelopes used by every endpoint.

All service responses MUST use one of these wrappers.

Success:  SuccessResponse[T]   → { "data": {...}, "message": "success" }
Error:    ErrorResponse        → { "error": "CODE", "message": "...", "detail": null }
Paged:    PagedResponse[T]     → { "data": [...], "total": N, "page": N, "page_size": N }
"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success envelope returned by all 2xx endpoints.

    Attributes:
        data: The response payload. Type is determined by the generic parameter ``T``.
        message: Short status string, defaults to ``"success"``.
    """

    data: T
    message: str = "success"

    model_config = {"arbitrary_types_allowed": True}


class ErrorResponse(BaseModel):
    """Standard error envelope returned by all 4xx/5xx responses.

    Attributes:
        error: Machine-readable error code (e.g. ``"VIDEO_NOT_FOUND"``).
        message: Human-readable explanation of what went wrong.
        detail: Optional extra debug info such as field-level validation errors
            or a downstream error message. ``None`` in production-safe responses.
    """

    error: str           # machine-readable code e.g. "VIDEO_NOT_FOUND"
    message: str         # human-readable explanation
    detail: Optional[Any] = None  # extra debug info (stack trace, field errors, etc.)


class PagedResponse(BaseModel, Generic[T]):
    """Paginated list response for collection endpoints.

    Attributes:
        data: The current page of items. Type is determined by the generic
            parameter ``T``.
        total: Total number of items matching the query before pagination.
        page: Current page number (1-indexed).
        page_size: Maximum number of items returned per page.
    """

    data: List[T]
    total: int           # total items matching the query (before pagination)
    page: int            # current page number (1-indexed)
    page_size: int       # items per page
