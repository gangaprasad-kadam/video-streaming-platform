from shared.exceptions import AuthError, ConflictError, NotFoundError


class EmailConflictError(ConflictError):
    """Raised when a registration attempt uses an already-registered email."""

    def __init__(self):
        super().__init__(message="Email already registered")


class UsernameConflictError(ConflictError):
    """Raised when a registration attempt uses an already-taken username."""

    def __init__(self):
        super().__init__(message="Username already taken")


class UserNotFoundError(NotFoundError):
    """Raised when a user cannot be found by ID or email."""

    def __init__(self):
        super().__init__(resource="user")


class InvalidCredentialsError(AuthError):
    """Raised when email/password do not match."""

    def __init__(self):
        super().__init__(message="Invalid email or password")
