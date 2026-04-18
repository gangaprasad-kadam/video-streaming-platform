from shared.exceptions import ForbiddenError, NotFoundError


class VideoNotReadyError(NotFoundError):
    """Raised when a video exists but is not yet ready for streaming."""

    def __init__(self, video_id: str = ""):
        super().__init__(resource="video")
        self.error_code = "VIDEO_NOT_READY"
        self.status_code = 425  # Too Early
        self.message = f"Video '{video_id}' is not ready for streaming yet"


class StreamNotFoundError(NotFoundError):
    """Raised when the HLS manifest or segment file cannot be found on disk."""

    def __init__(self, path: str = ""):
        super().__init__(resource="stream")
        self.message = f"Stream file not found: {path}"
