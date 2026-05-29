from __future__ import annotations

from pydantic import BaseModel


class BucketItem(BaseModel):
    """A single 5-second heatmap bucket."""
    bucket: int       # start second of the window (e.g. 140 → 140–144s)
    score: int        # cumulative weighted engagement score
    label: str        # human-readable label e.g. "2:20–2:25"


class HeatmapResponse(BaseModel):
    video_id: str
    bucket_size: int  # always 5
    total_buckets: int
    buckets: list[BucketItem]


class HighlightsResponse(BaseModel):
    video_id: str
    highlights: list[BucketItem]  # top N most-engaging segments


def make_label(bucket: int, bucket_size: int) -> str:
    """Convert a bucket start second into a MM:SS–MM:SS string."""
    def fmt(s: int) -> str:
        return f"{s // 60}:{s % 60:02d}"
    return f"{fmt(bucket)}–{fmt(bucket + bucket_size)}"
