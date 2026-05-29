from shared.exceptions import NotFoundError


class SummaryNotFoundError(NotFoundError):
    """Raised when no summary record exists for the requested video."""

    def __init__(self, video_id: str = ""):
        """Initialise with the video ID whose summary is missing.

        Args:
            video_id: UUID string of the video without a summary.
        """
        super().__init__(resource="summary")
        self.message = f"Summary for video '{video_id}' not found — processing may still be in progress"


class TranscriptionError(Exception):
    """Raised when Whisper fails to transcribe a video's audio."""

    def __init__(self, message: str = "Failed to transcribe audio"):
        """Initialise with an optional error description.

        Args:
            message: Human-readable description of the transcription failure.
        """
        super().__init__(message)
        self.message = message
