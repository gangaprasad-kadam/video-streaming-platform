from pydantic import BaseModel


class KeyMoment(BaseModel):
    timestamp: float
    label: str


class SummaryResponse(BaseModel):
    video_id: str
    transcript: str
    summary: str
    key_moments: list[KeyMoment]
    created_at: str

    model_config = {"from_attributes": True}
