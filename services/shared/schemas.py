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
    """Standard success envelope. All 2xx responses use this."""

    data: T
    message: str = "success"

    model_config = {"arbitrary_types_allowed": True}


class ErrorResponse(BaseModel):
    """Standard error envelope. All 4xx/5xx responses use this."""

    error: str           # machine-readable code e.g. "VIDEO_NOT_FOUND"
    message: str         # human-readable explanation
    detail: Optional[Any] = None  # extra debug info (stack trace, field errors, etc.)


class PagedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    data: List[T]
    total: int           # total items matching the query (before pagination)
    page: int            # current page number (1-indexed)
    page_size: int       # items per page
