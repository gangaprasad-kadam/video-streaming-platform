# Streaming Service — Complete Technical Reference

## 1. What Is This Service?

The **streaming-service** is a read-only HTTP service that serves HLS video content directly
to video players (browser, mobile, smart TV). It has two jobs:

1. **Serve HLS manifest files** (`.m3u8`) — the playlist file that tells the player what
   segments exist and in what order
2. **Serve HLS segment files** (`.ts`) — the actual video chunks (6 seconds each)

It does **NOT** upload, encode, or store videos. It reads files that the encoding-worker
placed on the shared media volume. It connects to the **same PostgreSQL database** as
video-service (read-only access) to check whether a video is actually `ready` before serving.

**Port:** `8003` (internal Docker network: `streaming-service:8003`)  
**Database:** PostgreSQL (`videoplatform` — same DB as video-service, read-only queries)  
**Cache:** Redis DB 2 (`redis://redis:6379/2`) — manifest content cache (5-min TTL)  
**Media:** Read-only access to shared Docker volume at `/media`  
**Framework:** FastAPI + SQLAlchemy (async) + asyncpg + aiofiles

---

## 2. Folder Structure

```
streaming-service/
├── app/
│   ├── main.py              ← FastAPI app factory, lifespan, error handlers
│   ├── config.py            ← Pydantic-Settings (reads .env)
│   ├── database.py          ← SQLAlchemy async engine (same DB as video-service)
│   ├── redis_client.py      ← Redis connection (DB 2, separate from video-service DB 1)
│   ├── models.py            ← Read-only Video model (subset of video-service model)
│   ├── exceptions.py        ← VideoNotReadyError (425), StreamNotFoundError (404)
│   │
│   └── stream/              ← Stream domain
│       ├── handler/
│       │   └── router.py    ← HTTP routes: manifest, segment, cache invalidation
│       ├── utils/
│       │   ├── service.py   ← Business logic: validate ready, read file, cache-aside
│       │   └── cache.py     ← Redis manifest cache helpers
│       └── dao/
│           └── repository.py← One query: get_ready_video (status=ready filter)
│
├── tests/
│   ├── conftest.py          ← fixtures: SQLite in-memory, mock Redis, tmp_path
│   └── test_stream.py       ← 4 tests
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

---

## 3. Three-Layer Architecture

```
HTTP Request
    │
    ▼
handler/router.py      ← Receives URL params, calls service, returns FileResponse or PlainTextResponse
    │
    ▼
utils/service.py       ← Business logic:
    │                     - check Redis cache
    │                     - validate video is "ready" (not uploading/processing/failed)
    │                     - read file from disk with aiofiles
    │                     - cache manifest content in Redis
    ├──► utils/cache.py ← Redis: get/set/delete manifest cache
    └──► dao/repository.py ← Single SQL query: SELECT WHERE id=X AND status='ready'
```

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@postgres:5432/videoplatform` | Same PostgreSQL as video-service |
| `REDIS_URL` | `redis://redis:6379/2` | Redis **DB 2** (manifest cache) |
| `MEDIA_ROOT` | `/media` | Shared media volume mount path |
| `MANIFEST_CACHE_TTL` | `300` | Manifest cache TTL in seconds (5 minutes) |
| `DEBUG` | `False` | SQLAlchemy query logging |

**Important:** `REDIS_URL` uses DB 2. This is separate from:
- DB 0: user-service sessions
- DB 1: video-service video metadata cache
- DB 2: streaming-service manifest cache ← this service
- DB 3: summarization-service summary cache

---

## 5. Database (Read-Only Model)

The streaming-service connects to the **same PostgreSQL database** as video-service.
It does NOT have its own Alembic migrations — it reads a table that video-service manages.

### Video Model (subset — read-only)

```python
class Video(Base):
    __tablename__ = "videos"   # Same table as video-service

    id: UUID
    title: str
    creator_id: UUID
    file_path: str
    hls_path: str | None      ← Path to /media/hls/{id}/index.m3u8
    thumbnail_path: str | None
    duration: float | None
    status: VideoStatus        ← Only serves if status == "ready"
    created_at: datetime
```

The model does not include `description`, `file_size_bytes`, `mime_type`, `updated_at` —
those fields are not needed for streaming.

### Why the same database?

This is a deliberate architectural choice — the streaming-service does not call video-service
over HTTP to check video status. Instead, it reads directly from the shared PostgreSQL database.

**Pros:** No inter-service HTTP latency, no coupling to video-service's HTTP API  
**Cons:** Tight DB coupling — streaming-service must know the schema

This pattern is acceptable here because both services are in the same data domain (videos).

---

## 6. API Endpoints

### Health Check

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service liveness check |

---

### Public Streaming Endpoints (`/stream`)

#### GET `/stream/{video_id}/index.m3u8`

Serves the HLS master manifest file.

**Auth Required:** No (streaming is public)

**Success Response — 200 OK:**
```
Content-Type: application/vnd.apple.mpegurl

#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:0
#EXTINF:6.000000,
index000.ts
#EXTINF:6.000000,
index001.ts
#EXTINF:5.500000,
index002.ts
#EXT-X-ENDLIST
```

Returns raw text (not JSON). Content-Type tells the player it's an HLS manifest.

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 425 | `VIDEO_NOT_READY` | Video exists but status is not "ready" (still processing) |
| 404 | `NOT_FOUND` | Video UUID not in DB, or `hls_path` not set, or file not on disk |

**Cache behavior:**
- Checks Redis `stream:manifest:{videoId}` (TTL 300s)
- HIT: return cached string directly (no DB, no file I/O)
- MISS: query DB → read `.m3u8` file from disk → cache in Redis → return

**Internal Flow:**
```
GET /stream/{video_id}/index.m3u8
    → router.py → stream_service.get_manifest(db, redis, video_id)
        1. get_cached_manifest(redis, video_id) → HIT: return cached string
        2. repo.get_ready_video(db, video_id)
             SELECT * FROM videos WHERE id=X AND status='ready'
             → None → raise VideoNotReadyError (425)
        3. check video.hls_path is not None → else StreamNotFoundError
        4. check os.path.isfile(video.hls_path) → else StreamNotFoundError
        5. async with aiofiles.open(hls_path, "r") as f: content = await f.read()
        6. cache_manifest(redis, video_id, content)  ← store for 5min
    ← PlainTextResponse(content, media_type="application/vnd.apple.mpegurl")
```

---

#### GET `/stream/{video_id}/{segment}`

Serves an individual HLS segment file (`.ts` transport stream).

**Auth Required:** No

**URL parameter examples:**
- `GET /stream/uuid/index000.ts`
- `GET /stream/uuid/index001.ts`
- `GET /stream/uuid/index002.ts`

**Success Response — 200 OK (or 206 Partial Content for range requests):**
```
Content-Type: video/MP2T
Accept-Ranges: bytes
Content-Range: bytes 0-65535/131072   (only for range requests)
[binary TS data]
```

**Key feature — HTTP Range requests:**  
`FileResponse` from Starlette/FastAPI natively supports HTTP Range requests.
When a video player seeks to a position, it sends `Range: bytes=N-M` in the header.
The streaming-service responds with only the requested bytes (HTTP 206 Partial Content),
enabling efficient seeking without re-downloading the whole segment.

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 425 | `VIDEO_NOT_READY` | Video not ready |
| 404 | `NOT_FOUND` | Segment file not found on disk |

**Internal Flow:**
```
GET /stream/{video_id}/index002.ts
    → router.py → stream_service.get_segment_path(db, video_id, "index002.ts")
        1. repo.get_ready_video(db, video_id) → None → 425
        2. check video.hls_path is not None
        3. hls_dir = os.path.dirname(video.hls_path)
             e.g. /media/hls/uuid/
        4. segment_path = /media/hls/uuid/index002.ts
        5. check os.path.isfile(segment_path) → else 404
    ← FileResponse(segment_path, media_type="video/MP2T", headers={"Accept-Ranges": "bytes"})
```

**Why segments are NOT cached in Redis:**  
Segments are binary files up to several MB each. Caching them in Redis would consume huge
amounts of memory. Only the tiny manifest text is cached.

---

### Internal Endpoints (`/stream/internal`)

#### DELETE `/stream/internal/{video_id}/cache`

Invalidates the cached manifest for a video. Called after re-encoding.

**Auth Required:** No (internal network only — not exposed via nginx)

**Success Response — 200 OK:**
```json
{ "message": "Cache invalidated for video {video_id}" }
```

**Use case:** If a video is re-encoded with different settings, the old manifest in Redis
needs to be cleared so the next GET serves the new manifest.

---

## 7. HLS Playback — How It Actually Works

When a browser loads the video player (e.g. hls.js):

```
BROWSER (hls.js)                    NGINX              STREAMING-SERVICE        DISK (/media)
    │                                  │                      │                    │
    │── GET /stream/{id}/index.m3u8 ──►│──────────────────────►│                    │
    │                                  │         check Redis cache (miss)           │
    │                                  │         query DB: ready? Yes              │
    │                                  │         read /media/hls/{id}/index.m3u8 ──►│
    │                                  │         cache in Redis                    │
    │◄─── #EXTM3U\n#EXTINF... ─────────┤◄──────────────────────┤                    │
    │                                  │                      │                    │
    │    [player parses manifest,       │                      │                    │
    │     sees 3 segments]              │                      │                    │
    │                                  │                      │                    │
    │── GET /stream/{id}/index000.ts ──►│──────────────────────►│                    │
    │                                  │         get_segment_path()                 │
    │                                  │         FileResponse(/media/hls/{id}/000) ►│
    │◄─── [6s of video data] ──────────┤◄──────────────────────┤                    │
    │  [plays first 6 seconds]         │                      │                    │
    │                                  │                      │                    │
    │── GET /stream/{id}/index001.ts ──►│──────────────────────►│                    │
    │◄─── [next 6s] ───────────────────┤◄──────────────────────┤                    │
    │   [user seeks to 60s]            │                      │                    │
    │── GET /stream/{id}/index010.ts   │                      │                    │
    │   Range: bytes=0-131072 ─────────►│──────────────────────►│                    │
    │◄─── 206 Partial Content ─────────┤                      │ (FileResponse handles range)
```

The player fetches segments one at a time, ahead of playback position. Seeking jumps to
a specific segment number (`index010.ts` = seconds 60–66).

---

## 8. Redis Cache Design (utils/cache.py)

| Key | Value | TTL |
|---|---|---|
| `stream:manifest:{videoId}` | `.m3u8` file content as plain text string | 300s (5 min) |

```python
_KEY_PREFIX = "stream:manifest:"

async def get_cached_manifest(redis, video_id):
    return await redis.get(f"stream:manifest:{video_id}")

async def cache_manifest(redis, video_id, content):
    await redis.set(f"stream:manifest:{video_id}", content, ex=300)

async def invalidate_manifest_cache(redis, video_id):
    await redis.delete(f"stream:manifest:{video_id}")
```

**Why cache the manifest?**

The manifest is a small text file (~100 bytes) that the player fetches EVERY time the page loads.
Without cache, every page load = DB query + disk read. With cache, most requests return from Redis
in <1ms without touching the disk or database.

**Why 5-minute TTL?**

Manifests are stable for a given video (segments don't change after encoding). 5 minutes is
a reasonable balance between freshness and cache efficiency. The explicit invalidation endpoint
allows immediate cache clearing when needed.

---

## 9. Exceptions (exceptions.py)

```python
class VideoNotReadyError(NotFoundError):
    """Raised when video exists but status != ready."""
    status_code = 425  # HTTP 425 Too Early
    error_code = "VIDEO_NOT_READY"
    message = "Video '{video_id}' is not ready for streaming yet"

class StreamNotFoundError(NotFoundError):
    """Raised when hls_path is None or file doesn't exist on disk."""
    status_code = 404
    error_code = "NOT_FOUND"
```

**Why HTTP 425 "Too Early"?**

HTTP 425 "Too Early" is the semantically correct response for "the resource exists but isn't
ready yet, try again later." It's better than 404 (implies resource doesn't exist) or 503
(implies server is down). A 425 response tells the client: "come back later."

---

## 10. DAO — Single Query (dao/repository.py)

The entire DAO layer for this service is one function:

```python
async def get_ready_video(db: AsyncSession, video_id: str) -> Video | None:
    result = await db.execute(
        select(Video).where(
            Video.id == uuid.UUID(video_id),
            Video.status == VideoStatus.ready,   ← BOTH conditions in one query
        )
    )
    return result.scalar_one_or_none()
```

**Why filter by status in the DB query (not in Python)?**

If we fetched the video first and then checked `video.status == "ready"` in Python,
we'd have two round trips for invalid states (fetch + check). By putting the `status='ready'`
filter in the WHERE clause, a single query returns `None` for any video that isn't ready —
no data transferred for non-ready videos.

---

## 11. Startup & Shutdown

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()    # ping PostgreSQL (same DB as video-service)
    await connect_redis() # create Redis DB 2 pool
    yield
    await close_redis()
    await close_db()
```

---

## 12. Docker Configuration

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
```

**docker-compose volume mounts:**
- `media_data:/media:ro` — **read-only** (streaming reads, never writes)
- `./backend/shared:/app/shared:ro` — shared module

**Depends on:** PostgreSQL, Redis (no Kafka, no MongoDB, no Python packages beyond stdlib)

---

## 13. nginx Routing

```nginx
location /stream {
    proxy_pass http://streaming-service:8003;
    proxy_set_header Host $host;
    proxy_buffering off;        ← Critical for streaming!
    proxy_read_timeout 300s;    ← Long timeout for large segment downloads
}
```

**`proxy_buffering off`** — Without this, nginx would buffer the entire `.ts` segment in memory
before sending it to the client. This defeats the purpose of streaming. With buffering off,
nginx passes data through in real-time as it arrives from the streaming-service.

---

## 14. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework + FileResponse + PlainTextResponse |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `sqlalchemy[asyncio]` | 2.0.28 | Async ORM (read-only queries) |
| `asyncpg` | 0.29.0 | Async PostgreSQL driver |
| `redis[asyncio]` | 5.0.3 | Async Redis client (manifest cache) |
| `aiofiles` | 23.2.1 | Async file reads (manifest content) |
| `pydantic-settings` | 2.2.1 | Config from environment |

No Kafka, no MongoDB — simple read-only serving service.

---

## 15. Testing

**Test strategy:**
- SQLite in-memory for DB (same Video model)
- AsyncMock for Redis (dict-backed)
- `tmp_path` pytest fixture for creating real `.m3u8` files
- No real file system needed for most tests (testing error cases mostly)

**Test coverage (4 tests):**

| Test | What is tested |
|---|---|
| `test_health` | Health endpoint returns 200 |
| `test_get_manifest_success` | Manifest endpoint with valid video + file |
| `test_get_manifest_not_found_returns_404` | Unknown video UUID → 404/425 |
| `test_invalidate_cache` | DELETE cache removes Redis key |

**Run tests:**
```bash
cd backend/streaming-service
python -m pytest tests/ -q
# Expected: 4 passed
```

---

## 16. Complete Request Lifecycle for HLS Playback

```
State in DB: Video X status="ready", hls_path="/media/hls/X/index.m3u8"
Files on disk: /media/hls/X/index.m3u8, index000.ts, index001.ts, index002.ts

Step 1: Player requests manifest
────────────────────────────────
GET /stream/X/index.m3u8
    → Redis check: "stream:manifest:X" → MISS (first request)
    → DB: SELECT WHERE id=X AND status='ready' → returns Video
    → disk: read /media/hls/X/index.m3u8 (async, non-blocking)
    → Redis: SET "stream:manifest:X" content EX 300
    ← 200 PlainTextResponse: "#EXTM3U\n#EXT-X-VERSION:3\n..."

Step 2: Second request within 5 minutes
────────────────────────────────────────
GET /stream/X/index.m3u8
    → Redis check: "stream:manifest:X" → HIT!
    ← 200 PlainTextResponse: (from cache, no DB or disk I/O)

Step 3: Player requests first segment
───────────────────────────────────────
GET /stream/X/index000.ts
    → DB: SELECT WHERE id=X AND status='ready' → returns Video
    → segment_path = dirname("/media/hls/X/index.m3u8") + "/index000.ts"
            = "/media/hls/X/index000.ts"
    → os.path.isfile(segment_path) → True
    ← FileResponse("/media/hls/X/index000.ts", media_type="video/MP2T")
       (Starlette handles Range requests internally)

Step 4: Player seeks (jumps to segment 10)
───────────────────────────────────────────
GET /stream/X/index010.ts  [Range: bytes=0-65535]
    → DB check (same as above)
    → segment_path = /media/hls/X/index010.ts
    ← 206 Partial Content (Starlette's FileResponse handles Range header)
```
