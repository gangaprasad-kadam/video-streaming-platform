from shared.exceptions import ForbiddenError, NotFoundError


class VideoNotFoundError(NotFoundError):
    def __init__(self, video_id: str = ""):
        msg = f"Video with id '{video_id}' not found" if video_id else "Video not found"
        super().__init__(resource="video")
        self.message = msg


class VideoForbiddenError(ForbiddenError):
    def __init__(self):
        super().__init__(message="Access denied")


class StorageError(Exception):
    """Raised when the file cannot be saved to the media volume."""
    def __init__(self, message: str = "Failed to save file to storage"):
        super().__init__(message)
        self.message = message
