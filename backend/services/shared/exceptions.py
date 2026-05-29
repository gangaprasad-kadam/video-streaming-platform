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
    """Base exception for all application errors.

    All service-specific exceptions extend this class and override
    ``status_code`` and ``error_code`` as needed.

    Attributes:
        status_code: HTTP status code returned to the client.
        error_code: Machine-readable error identifier (e.g. ``"INTERNAL_ERROR"``).
        message: Human-readable description of what went wrong.
        detail: Optional extra context (field errors, stack info, etc.).
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred", detail=None):
        """Initialise the exception with an optional message and detail payload.

        Args:
            message: Human-readable error description sent to the client.
            detail: Optional extra data attached to the error response (e.g.
                validation field errors or a downstream error message).
        """
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppException):
    """Raised when a requested resource does not exist.

    Automatically builds ``error_code`` from the resource name, e.g.
    ``NotFoundError("video")`` sets ``error_code = "VIDEO_NOT_FOUND"``.

    Attributes:
        status_code: Always ``404``.
        error_code: ``"{RESOURCE}_NOT_FOUND"`` derived from the resource arg.
    """

    status_code = 404

    def __init__(self, resource: str = "resource", detail=None):
        """Set ``error_code`` from the resource name and build a readable message.

        Args:
            resource: Singular name of the missing resource (e.g. ``"video"``).
                Used to construct both ``error_code`` and the error message.
            detail: Optional extra context forwarded to the error response.
        """
        # e.g. NotFoundError("video") → error_code = "VIDEO_NOT_FOUND"
        self.error_code = f"{resource.upper()}_NOT_FOUND"
        super().__init__(message=f"{resource.capitalize()} not found", detail=detail)


class AuthError(AppException):
    """Raised when authentication is missing or the session has expired.

    Attributes:
        status_code: Always ``401``.
        error_code: Always ``"UNAUTHORIZED"``.
    """

    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, message: str = "Authentication required", detail=None):
        """Create an authentication error with an optional custom message.

        Args:
            message: Human-readable reason for the 401 response.
            detail: Optional extra context forwarded to the error response.
        """
        super().__init__(message=message, detail=detail)


class ForbiddenError(AppException):
    """Raised when a user is authenticated but not allowed to perform an action.

    Attributes:
        status_code: Always ``403``.
        error_code: Always ``"FORBIDDEN"``.
    """

    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, message: str = "You do not have permission to perform this action", detail=None):
        """Create a forbidden error with an optional custom message.

        Args:
            message: Human-readable reason the action is denied.
            detail: Optional extra context forwarded to the error response.
        """
        super().__init__(message=message, detail=detail)


class ConflictError(AppException):
    """Raised on duplicate resource creation (e.g. a duplicate email or username).

    Attributes:
        status_code: Always ``409``.
        error_code: Always ``"CONFLICT"``.
    """

    status_code = 409
    error_code = "CONFLICT"

    def __init__(self, message: str = "Resource already exists", detail=None):
        """Create a conflict error with an optional custom message.

        Args:
            message: Human-readable reason for the conflict.
            detail: Optional extra context forwarded to the error response.
        """
        super().__init__(message=message, detail=detail)


class RateLimitError(AppException):
    """Raised when a client exceeds the allowed request rate.

    Attributes:
        status_code: Always ``429``.
        error_code: Always ``"RATE_LIMIT_EXCEEDED"``.
    """

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Too many requests. Please slow down.", detail=None):
        """Create a rate-limit error with an optional custom message.

        Args:
            message: Human-readable message asking the client to back off.
            detail: Optional extra context (e.g. retry-after seconds).
        """
        super().__init__(message=message, detail=detail)


class ServiceUnavailableError(AppException):
    """Raised when a required dependency (AI model, queue, etc.) is not ready.

    Attributes:
        status_code: Always ``503``.
        error_code: Always ``"SERVICE_UNAVAILABLE"``.
    """

    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"

    def __init__(self, message: str = "Service temporarily unavailable", detail=None):
        """Create a service-unavailable error with an optional custom message.

        Args:
            message: Human-readable reason the service cannot fulfil the request.
            detail: Optional extra context (e.g. which dependency is down).
        """
        super().__init__(message=message, detail=detail)
