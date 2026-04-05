# Phase 5 — Streaming Service

## Goal
A FastAPI microservice that serves HLS video segments to the browser's video player. It reads from the shared Docker media volume and caches the HLS manifest in Redis to avoid repeated disk reads for popular videos.

---

## Service Details

| Property | Value |
|---|---|
| Service name | `streaming-service` |
| Port | `8003` |
| Framework | FastAPI (Python) |
| Storage | Docker volume (`/media/hls/`) |
| Cache | Redis (`stream:manifest:{videoId}`, TTL: 5min) |

---

## Folder Structure

```
services/streaming-service/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py
    ├── config.py
    ├── redis_client.py
    ├── exceptions.py
    └── streaming/
        ├── __init__.py
        ├── router.py        ← [L1] GET /stream/{videoId}/manifest.m3u8
        │                         GET /stream/{videoId}/{segment}.ts
        ├── schemas.py       ← [L1] ManifestResponse, SegmentHeaders
        ├── service.py       ← [L2] get_manifest(), get_segment(), validate_ready()
        ├── repository.py    ← [L3] queries videos table for hls_path / status
        └── cache.py         ← [L3] get_cached_manifest(), cache_manifest()
```

---

## API Endpoints

```
GET /stream/:videoId/index.m3u8
  Response : HLS manifest file (text/x-mpegurl)
  Cache    : Redis key stream:manifest:{videoId}, TTL 5min
  Error 404: video not processed yet (hls_path not set)

GET /stream/:videoId/:segment
  Example  : /stream/uuid/segment_001.ts
  Response : video/MP2T (binary stream)
  Cache    : none (segments are served directly from disk)
  Headers  : Accept-Ranges: bytes (supports range requests)
```

### Why cache only the manifest?
- The `.m3u8` manifest is small (< 1KB) but fetched frequently as the player re-requests it to check for new segments.
- `.ts` segment files are large binaries — caching them in Redis would be wasteful. They're served directly from the Docker volume.

---

## HLS Streaming Flow

```
Browser (hls.js player)        Streaming Service         Redis      Disk (media volume)
       │                              │                     │               │
       │── GET /stream/vid/index.m3u8 ▶                     │               │
       │                              │── GET manifest ─────▶               │
       │                              │◀── (cache miss)                     │
       │                              │── Read from disk ───│───────────────▶
       │                              │◀── manifest content                 │
       │                              │── SET manifest ─────▶ (TTL: 5min)  │
       │◀── 200 manifest ─────────────│                     │               │
       │                              │                     │               │
       │ (player parses manifest,     │                     │               │
       │  requests .ts segments)      │                     │               │
       │                              │                     │               │
       │── GET /stream/vid/seg_000.ts ▶                     │               │
       │                              │── Read file ────────│───────────────▶
       │◀── 200 binary ───────────────│                     │               │
       │ (repeat for each segment)    │                     │               │
```

---

## Database Lookup

Before reading the manifest from disk, `repository.py` queries PostgreSQL to validate that the video exists and its status is `ready`. This prevents serving stale paths if a video is re-encoded.

```python
# streaming/repository.py

async def get_video_hls_path(video_id: str) -> str | None:
    """Returns hls_path if video status is 'ready', else None."""
    result = await db.execute(
        select(Video.hls_path)
        .where(Video.id == video_id, Video.status == "ready")
    )
    row = result.scalar_one_or_none()
    return row   # None → video not ready or not found
```

The service layer calls this before falling back to disk:

```python
async def get_manifest(video_id: str) -> str:
    hls_path = await repo.get_video_hls_path(video_id)
    if hls_path is None:
        raise NotFoundError("stream", video_id)
    # … cache lookup / disk read follows
```

---

## Manifest Caching (Redis)

```python
# streaming/service.py

MANIFEST_TTL = 300  # 5 minutes

async def get_manifest(video_id: str) -> str:
    cache_key = f"stream:manifest:{video_id}"

    # 1. Try cache first (sync-style Redis read)
    cached = await redis.get(cache_key)
    if cached:
        return cached.decode()

    # 2. Cache miss — read from disk
    manifest_path = f"/media/hls/{video_id}/index.m3u8"
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="Stream not ready")

    with open(manifest_path, "r") as f:
        content = f.read()

    # 3. Store in cache
    await redis.setex(cache_key, MANIFEST_TTL, content)
    return content
```

---

## HTTP Response Headers

For `.ts` segments, include range-request support so browsers can seek efficiently:

```python
@router.get("/{video_id}/{segment}")
async def get_segment(video_id: str, segment: str):
    path = f"/media/hls/{video_id}/{segment}"
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(
        path,
        media_type="video/MP2T",
        headers={"Accept-Ranges": "bytes"}
    )
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| Redis manifest read | Async (await) | Non-blocking via redis[asyncio] |
| File read (manifest) | Sync (wrapped) | Small file, acceptable; or use aiofiles |
| File serve (.ts segment) | Sync via FileResponse | FastAPI's FileResponse handles streaming efficiently |
| Redis manifest write | Async (await) | Non-blocking |

---

## Error Codes

| Situation | Status | Error Code | Message |
|---|---|---|---|
| Video status not `ready` | `404` | `STREAM_NOT_READY` | `"Video is still processing"` |
| Segment file not on disk | `404` | `SEGMENT_NOT_FOUND` | `"Segment not found"` |

```python
# Example responses
{"error": "STREAM_NOT_READY",  "message": "Video is still processing"}
{"error": "SEGMENT_NOT_FOUND", "message": "Segment not found"}
```

---

## Cache Invalidation

If a video is re-encoded (e.g. quality upgrade), the cached manifest becomes stale. The encoding-worker (or an admin endpoint) must delete the Redis key:

```python
# streaming/repository.py

async def invalidate_manifest_cache(video_id: str) -> None:
    """DEL stream:manifest:{videoId} — call after re-encoding."""
    await redis.delete(f"stream:manifest:{video_id}")
```

The next manifest request will trigger a fresh DB lookup + disk read + re-cache.

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Video still processing | `404` — HLS path not yet set in DB |
| Manifest cache eviction | Next request triggers disk read + re-cache |
| Segment not found | `404` with clear error |
| Large video files | `FileResponse` streams in chunks, doesn't load into memory |

---

## References: Shared Patterns

- **§1 Layered Architecture** — `repository.py` for DB queries, `service.py` for business logic
- **§5 Standard Response Format** — `STREAM_NOT_READY`, `SEGMENT_NOT_FOUND` follow `{RESOURCE}_NOT_FOUND` convention
- **§7 MongoDB Error Logger** — `logger.py` using `ErrorLogger` from shared module
- **§8 Standard Service Folder Structure** — `repository.py`, `exceptions.py`, `logger.py` added to folder
