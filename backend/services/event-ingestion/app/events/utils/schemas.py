from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


VALID_ACTIONS = Literal["PLAY", "WATCH_COMPLETE", "REWIND", "SEEK", "PAUSE", "SKIP"]


class InteractionEventRequest(BaseModel):
    """Incoming viewer interaction event from the client."""

    userId: str = Field(..., min_length=1)
    videoId: str = Field(..., min_length=1)
    action: VALID_ACTIONS
    videoTs: float = Field(default=0.0, ge=0)
    creatorId: str = ""
    sessionId: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class InteractionEventAccepted(BaseModel):
    """Response returned after a successfully queued event."""

    accepted: bool = True
    action: str
    videoId: str
