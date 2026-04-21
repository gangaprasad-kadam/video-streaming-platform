from __future__ import annotations

from pydantic import BaseModel


class InteractionEvent(BaseModel):
    """Viewer interaction event consumed from Kafka."""

    userId: str
    videoId: str
    action: str  # PLAY | WATCH_COMPLETE | REWIND | SEEK | PAUSE | SKIP
    videoTs: float = 0.0
    creatorId: str = ""
    sessionId: str = ""
    timestamp: str = ""


# Score weight assigned to each action type.
# Positive = engagement signal, negative = disengagement signal.
ACTION_WEIGHTS: dict[str, int] = {
    "REWIND": 3,         # strongest re-engagement signal
    "WATCH_COMPLETE": 2, # user watched to the end
    "SEEK": 2,           # intentional navigation to this segment
    "PAUSE": 1,          # mild interest
    "PLAY": 1,           # basic play
    "SKIP": -1,          # disengagement signal
}
