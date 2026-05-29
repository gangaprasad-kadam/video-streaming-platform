from pydantic import BaseModel


class KeyMoment(BaseModel):
    """A single notable moment within a video.

    Attributes:
        timestamp: Start time of the moment in seconds.
        label: Short text label describing the moment (max 120 chars).
    """

    timestamp: float
    label: str


class SummaryResponse(BaseModel):
    """API response payload for a video summary.

    Attributes:
        video_id: UUID string of the summarized video.
        transcript: Full text transcript of the video's audio.
        summary: AI-generated condensed summary.
        key_moments: List of notable moments with timestamps.
        created_at: ISO 8601 timestamp when the summary was created.
    """

    video_id: str
    transcript: str
    summary: str
    key_moments: list[KeyMoment]
    created_at: str

    model_config = {"from_attributes": True}
