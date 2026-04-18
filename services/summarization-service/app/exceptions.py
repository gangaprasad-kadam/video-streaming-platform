from shared.exceptions import NotFoundError


class SummaryNotFoundError(NotFoundError):
    def __init__(self, video_id: str = ""):
        super().__init__(resource="summary")
        self.message = f"Summary for video '{video_id}' not found — processing may still be in progress"


class TranscriptionError(Exception):
    def __init__(self, message: str = "Failed to transcribe audio"):
        super().__init__(message)
        self.message = message
