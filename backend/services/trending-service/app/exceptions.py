from shared.exceptions import AppException


class VideoNotFoundError(AppException):
    """Raised when a video ID does not exist."""

    def __init__(self, video_id: str) -> None:
        super().__init__(
            status_code=404,
            error_code="NOT_FOUND",
            message=f"Video '{video_id}' not found.",
        )
