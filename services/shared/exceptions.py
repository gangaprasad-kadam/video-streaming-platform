"""
Shared exception hierarchy.

Every service imports from here. Service-specific exceptions extend AppException
and override error_code / status_code as needed.

Standard error codes:
    UNAUTHORIZED         401  — no/expired session
    FORBIDDEN            403  — authenticated but not allowed
    {RESOURCE}_NOT_FOUND 404  — entity missing
    CONFLICT             409  — duplicate (email, etc.)
    VALIDATION_ERROR     422  — Pydantic validation failure
    RATE_LIMIT_EXCEEDED  429  — too many requests
    SERVICE_UNAVAILABLE  503  — model/dep not ready
"""

from __future__ import annotations


class AppException(Exception):
    """Base exception for all application errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred", detail=None):
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    status_code = 404

    def __init__(self, resource: str = "resource", detail=None):
        # e.g. NotFoundError("video") → error_code = "VIDEO_NOT_FOUND"
        self.error_code = f"{resource.upper()}_NOT_FOUND"
        super().__init__(message=f"{resource.capitalize()} not found", detail=detail)


class AuthError(AppException):
    """Raised when authentication is missing or session is expired."""

    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, message: str = "Authentication required", detail=None):
        super().__init__(message=message, detail=detail)


class ForbiddenError(AppException):
    """Raised when a user is authenticated but not allowed to perform an action."""

    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, message: str = "You do not have permission to perform this action", detail=None):
        super().__init__(message=message, detail=detail)


class ConflictError(AppException):
    """Raised on duplicate resource creation (e.g., duplicate email)."""

    status_code = 409
    error_code = "CONFLICT"

    def __init__(self, message: str = "Resource already exists", detail=None):
        super().__init__(message=message, detail=detail)


class RateLimitError(AppException):
    """Raised when a client exceeds the allowed request rate."""

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Too many requests. Please slow down.", detail=None):
        super().__init__(message=message, detail=detail)


class ServiceUnavailableError(AppException):
    """Raised when a dependency (AI model, queue, etc.) is not ready."""

    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"

    def __init__(self, message: str = "Service temporarily unavailable", detail=None):
        super().__init__(message=message, detail=detail)
