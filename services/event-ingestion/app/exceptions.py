from shared.exceptions import RateLimitError


class TooManyRequestsError(RateLimitError):
    def __init__(self, user_id: str):
        super().__init__(
            message=f"Too many events from user {user_id}. Limit: 60 per minute.",
        )
