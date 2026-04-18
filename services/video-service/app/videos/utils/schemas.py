from typing import Literal

from pydantic import BaseModel


class VideoResponse(BaseModel):
    id: str
    title: str
    description: str | None
    status: str
    creator_id: str
    file_path: str
    hls_path: str | None
    thumbnail_path: str | None
    duration: float | None
    file_size_bytes: int | None
    mime_type: str | None
    created_at: str

    model_config = {"from_attributes": True}


class VideoUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class VideoStatusResponse(BaseModel):
    id: str
    status: str


class InternalStatusUpdateRequest(BaseModel):
    status: Literal["uploading", "processing", "ready", "failed"]
    hls_path: str | None = None
    thumbnail_path: str | None = None
    duration: float | None = None
