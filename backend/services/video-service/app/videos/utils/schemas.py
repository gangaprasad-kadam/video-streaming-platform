from typing import Literal

from pydantic import BaseModel


class VideoResponse(BaseModel):
    """Full representation of a video returned to API clients."""

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
    """Request body for PATCH /videos/{id}.

    All fields are optional; omitted fields are left unchanged.
    """

    title: str | None = None
    description: str | None = None


class VideoStatusResponse(BaseModel):
    """Lightweight status-only response used by the polling endpoint."""

    id: str
    status: str


class StreamInfoResponse(BaseModel):
    """Minimal video info needed by streaming-service to locate HLS files."""

    id: str
    status: str
    hls_path: str | None

    model_config = {"from_attributes": True}


class InternalStatusUpdateRequest(BaseModel):
    """Request body for the internal PATCH /internal/videos/{id}/status endpoint.

    Used by encoding and thumbnail workers to advance the video lifecycle.
    """

    status: Literal["uploading", "processing", "ready", "failed"]
    hls_path: str | None = None
    thumbnail_path: str | None = None
    duration: float | None = None
