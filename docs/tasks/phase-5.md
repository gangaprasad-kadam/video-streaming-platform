# 📋 Phase 5 — Streaming Service Task File

> **Goal:** FastAPI microservice on port 8003 that serves HLS video files.
> Caches the `.m3u8` manifest in Redis (5-min TTL). Serves `.ts` segments directly
> from the shared Docker media volume with range-request support.

**Reference doc:** [`docs/phases/phase-5-streaming-service.md`](../phases/phase-5-streaming-service.md)
**Depends on:** Phase 1 ✅ (infra), Phase 4 ✅ (encoding-worker creates HLS files)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure | ⬜ |
| 2 | Write `requirements.txt` | ⬜ |
| 3 | Write `Dockerfile` | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/redis_client.py` | ⬜ |
| 6 | Write `app/exceptions.py` | ⬜ |
| 7 | Write `app/streaming/repository.py` | ⬜ |
| 8 | Write `app/streaming/service.py` | ⬜ |
| 9 | Write `app/streaming/router.py` | ⬜ |
| 10 | Write `app/main.py` | ⬜ |
| 11 | Add `streaming-service` to `docker-compose.yml` | ⬜ |
| 12 | Test manifest caching (unit) | ⬜ |
| 13 | Test streaming end-to-end | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Create Folder Structure

```bash
mkdir -p services/streaming-service/app/streaming \
         services/streaming-service/tests
touch services/streaming-service/app/__init__.py \
      services/streaming-service/app/streaming/__init__.py \
      services/streaming-service/tests/__init__.py
```

**Test / Verify:**
```bash
find services/streaming-service -type f | sort
```

**Acceptance criteria:**
- [ ] `app/streaming/` and `tests/` exist with `__init__.py`

---

### ✅ Task 2 — Write `requirements.txt`

**File:** `services/streaming-service/requirements.txt`

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
redis[asyncio]==5.0.3
aiofiles==23.2.1
pydantic-settings==2.2.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
fakeredis==2.21.3
```

**Note:** No `alembic` — this service reads from the DB but owns no tables.

**Test / Verify:**
```bash
pip install -r services/streaming-service/requirements.txt --dry-run 2>&1 | tail -3
```

**Acceptance criteria:**
- [ ] All packages listed, no alembic

---

### ✅ Task 3 — Write `Dockerfile`

**File:** `services/streaming-service/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
```

**Note:** No `alembic upgrade head` — this service does not own any DB tables.

**Acceptance criteria:**
- [ ] Dockerfile exists
- [ ] No alembic in CMD
- [ ] Port is `8003`

---

### ✅ Task 4 — Write `app/config.py`

**File:** `services/streaming-service/app/config.py`

**Settings:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_*` | 5 PG vars | — |
| `redis_host` | `REDIS_HOST` | `redis` |
| `redis_port` | `REDIS_PORT` | `6379` |
| `media_root` | `MEDIA_ROOT` | `/media` |
| `manifest_ttl` | `MANIFEST_TTL` | `300` |

**Test / Verify:**
```bash
cd services/streaming-service
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
python -c "
from app.config import settings
assert settings.manifest_ttl == 300
assert settings.media_root == '/media'
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] `manifest_ttl` defaults to `300` seconds
- [ ] `media_root` defaults to `/media`
- [ ] Test exits 0

---

### ✅ Task 5 — Write `app/redis_client.py`

**Same pattern as user-service** — async Redis connection with lifecycle functions.

**Expose:** `connect_redis()`, `close_redis()`, `get_redis()` (async generator)

**Test / Verify:**
```bash
cd services/streaming-service
python -c "
from app.redis_client import get_redis, connect_redis, close_redis
import inspect
assert inspect.isasyncgenfunction(get_redis)
print('Redis client OK')
"
```

**Acceptance criteria:**
- [ ] `get_redis` is async generator, test exits 0

---

### ✅ Task 6 — Write `app/exceptions.py`

**File:** `services/streaming-service/app/exceptions.py`

**Two service-specific exceptions:**

```python
from shared.exceptions import AppException, NotFoundError

class StreamNotReadyError(AppException):
    """Video exists but HLS encoding is not complete."""
    def __init__(self, video_id: str):
        super().__init__(
            status_code=404,
            error_code="STREAM_NOT_READY",
            message=f"Video '{video_id}' is still processing"
        )

class SegmentNotFoundError(AppException):
    """Requested .ts segment file does not exist on disk."""
    def __init__(self, segment: str):
        super().__init__(
            status_code=404,
            error_code="SEGMENT_NOT_FOUND",
            message=f"Segment '{segment}' not found"
        )
```

**Test / Verify:**
```bash
cd services/streaming-service
python -c "
from app.exceptions import StreamNotReadyError, SegmentNotFoundError
e1 = StreamNotReadyError('abc')
assert e1.status_code == 404
assert e1.error_code == 'STREAM_NOT_READY'
e2 = SegmentNotFoundError('segment_000.ts')
assert e2.status_code == 404
assert e2.error_code == 'SEGMENT_NOT_FOUND'
print('Exceptions OK')
"
```

**Acceptance criteria:**
- [ ] Both exceptions importable
- [ ] Correct status codes and error codes
- [ ] Test exits 0

---

### ✅ Task 7 — Write `app/streaming/repository.py`

**File:** `services/streaming-service/app/streaming/repository.py`

**What:** Query PostgreSQL to validate video is ready and get its HLS path.

**Functions:**

| Function | SQL | Returns |
|---|---|---|
| `get_video_hls_path(db, video_id)` | `SELECT hls_path FROM videos WHERE id=:id AND status='ready'` | `str \| None` |

**Also: cache invalidation helper:**

| Function | Redis op |
|---|---|
| `invalidate_manifest_cache(redis, video_id)` | `DEL stream:manifest:{videoId}` |

**Test / Verify:**
```bash
cd services/streaming-service
python -c "
from app.streaming.repository import get_video_hls_path, invalidate_manifest_cache
import inspect
assert inspect.iscoroutinefunction(get_video_hls_path)
assert inspect.iscoroutinefunction(invalidate_manifest_cache)
print('Repository signatures OK')
"
```

**Acceptance criteria:**
- [ ] `get_video_hls_path` only returns a path if video status is `ready`
- [ ] Returns `None` if video not found OR status is not `ready`
- [ ] Both functions `async def`, test exits 0

---

### ✅ Task 8 — Write `app/streaming/service.py`

**File:** `services/streaming-service/app/streaming/service.py`

**Functions:**

| Function | Logic |
|---|---|
| `get_manifest(db, redis, video_id)` | 1. DB check → `StreamNotReadyError` if not ready. 2. Try Redis cache (`stream:manifest:{vid}`). 3. On miss: read manifest from disk. 4. Set cache `SETEX` with `manifest_ttl`. 5. Return manifest string. |
| `get_segment_path(video_id, segment)` | Build path `/media/hls/{vid}/{segment}`. Validate filename (only `.ts` allowed). Return path if file exists, else raise `SegmentNotFoundError`. |

**Segment filename validation:**
```python
import re
def _validate_segment_name(segment: str) -> bool:
    # Only allow: segment_NNN.ts — prevent path traversal
    return bool(re.match(r'^segment_\d{3}\.ts$', segment))
```

**Manifest read (use `aiofiles` for async I/O):**
```python
import aiofiles
async with aiofiles.open(manifest_path, 'r') as f:
    content = await f.read()
```

**Test / Verify:**
```bash
cd services/streaming-service
python -c "
from app.streaming.service import get_manifest, get_segment_path
import inspect
assert inspect.iscoroutinefunction(get_manifest)
assert inspect.iscoroutinefunction(get_segment_path)
print('Service signatures OK')
"
```

**Acceptance criteria:**
- [ ] `get_manifest` checks DB first — raises `StreamNotReadyError` if not ready
- [ ] `get_manifest` checks Redis cache before disk
- [ ] `get_manifest` uses `aiofiles` for non-blocking disk read
- [ ] `get_segment_path` validates filename (blocks path traversal)
- [ ] `get_segment_path` raises `SegmentNotFoundError` if file missing
- [ ] Both `async def`, test exits 0

---

### ✅ Task 9 — Write `app/streaming/router.py`

**File:** `services/streaming-service/app/streaming/router.py`

**Endpoints:**

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/stream/{video_id}/index.m3u8` | None | `text/x-mpegurl` manifest string |
| `GET` | `/stream/{video_id}/{segment}` | None | `FileResponse` with `video/MP2T` + `Accept-Ranges: bytes` |

**Manifest response:**
```python
from fastapi.responses import PlainTextResponse

@router.get("/{video_id}/index.m3u8")
async def get_manifest(video_id: str, ...):
    content = await service.get_manifest(db, redis, video_id)
    return PlainTextResponse(content, media_type="text/x-mpegurl")
```

**Segment response:**
```python
from fastapi.responses import FileResponse

@router.get("/{video_id}/{segment}")
async def get_segment(video_id: str, segment: str):
    path = await service.get_segment_path(video_id, segment)
    return FileResponse(
        path,
        media_type="video/MP2T",
        headers={"Accept-Ranges": "bytes"}
    )
```

**Test / Verify:**
```bash
cd services/streaming-service
python -c "
from app.streaming.router import router
paths = {r.path for r in router.routes}
assert '/stream/{video_id}/index.m3u8' in paths
assert '/stream/{video_id}/{segment}' in paths
print('Router routes OK')
"
```

**Acceptance criteria:**
- [ ] Both routes defined
- [ ] Manifest returns `Content-Type: text/x-mpegurl`
- [ ] Segment returns `Content-Type: video/MP2T` with `Accept-Ranges: bytes`
- [ ] Neither route requires auth (streaming is public)
- [ ] Test exits 0

---

### ✅ Task 10 — Write `app/main.py`

**File:** `services/streaming-service/app/main.py`

**Lifespan startup:** `connect_db()` + `connect_redis()`
**Lifespan shutdown:** `close_redis()` + `close_db()`

**3 exception handlers:** `AppException`, `RequestValidationError`, generic `Exception`

**Include router:**
```python
app.include_router(streaming_router, prefix="/stream", tags=["streaming"])
```

**Test / Verify:**
```bash
cd services/streaming-service
python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/stream/{video_id}/index.m3u8' in paths
print('main.py OK')
"
```

**Acceptance criteria:**
- [ ] App starts without import errors
- [ ] Streaming router mounted under `/stream`
- [ ] All 3 exception handlers registered

---

### ✅ Task 11 — Add to `docker-compose.yml`

```yaml
streaming-service:
  build: ./services/streaming-service
  ports:
    - "8003:8003"
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    MEDIA_ROOT: /media
    MANIFEST_TTL: 300
  volumes:
    - ./services/shared:/app/shared:ro
    - media_volume:/media
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build streaming-service
docker compose up -d streaming-service
sleep 5
curl -f http://localhost:8003/docs
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] `GET http://localhost:8003/docs` returns 200
- [ ] Service starts without crash

---

### ✅ Task 12 — Test Manifest Caching (Unit)

**File:** `services/streaming-service/tests/test_streaming.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_manifest_returns_404_if_not_ready` | Video status is `processing` | 404 `STREAM_NOT_READY` |
| `test_manifest_served_from_disk` | Video ready, no cache hit | 200, manifest content, Redis key set |
| `test_manifest_served_from_cache` | Second request | 200, Redis `GET` called (not disk) |
| `test_manifest_cache_ttl` | Cache key has TTL | TTL ≤ 300s |
| `test_segment_served` | Valid `.ts` filename + file exists | 200, `video/MP2T` |
| `test_segment_not_found` | File not on disk | 404 `SEGMENT_NOT_FOUND` |
| `test_segment_path_traversal_blocked` | `segment=../../etc/passwd` | 404 (blocked by validation) |

**Run:**
```bash
cd services/streaming-service
pytest tests/test_streaming.py -v
```

**Acceptance criteria:**
- [ ] All 7 tests pass ✅
- [ ] Path traversal test passes (security)
- [ ] Cache TTL verified in test

---

### ✅ Task 13 — Test Streaming End-to-End

**Prerequisites:** Phase 4 complete — a video with `status=ready` and HLS files on volume.

**Steps:**
```bash
# 1. Get the video ID from a previously processed video
VIDEO_ID="<uuid from Phase 4 E2E test>"

# 2. Fetch the manifest
curl -v http://localhost:8003/stream/${VIDEO_ID}/index.m3u8
# Expected: 200, Content-Type: text/x-mpegurl, manifest body like:
# #EXTM3U
# #EXT-X-VERSION:3
# ...

# 3. Fetch a segment
FIRST_SEGMENT=$(curl -s http://localhost:8003/stream/${VIDEO_ID}/index.m3u8 | grep '.ts' | head -1)
curl -I http://localhost:8003/stream/${VIDEO_ID}/${FIRST_SEGMENT}
# Expected: 200, Content-Type: video/MP2T, Accept-Ranges: bytes

# 4. Verify Redis caching
docker compose exec redis redis-cli GET "stream:manifest:${VIDEO_ID}"
# Expected: manifest content (not empty)

# 5. Verify cache TTL
docker compose exec redis redis-cli TTL "stream:manifest:${VIDEO_ID}"
# Expected: number between 1 and 300
```

**Acceptance criteria:**
- [ ] Manifest request returns 200 with valid HLS content
- [ ] Segment request returns 200 with `video/MP2T` content type
- [ ] `Accept-Ranges: bytes` header present on segment response
- [ ] Redis key `stream:manifest:{videoId}` set after first manifest request
- [ ] TTL on Redis key is ≤ 300

---

## Phase Complete Checklist

Before marking Phase 5 as ✅ done in `COPILOT.md`:

- [ ] All 13 tasks above are ✅ done
- [ ] All 7 unit tests passing
- [ ] `GET /stream/{videoId}/index.m3u8` returns valid HLS manifest
- [ ] `GET /stream/{videoId}/segment_000.ts` returns video data
- [ ] Redis manifest cache confirmed working (set on first request, TTL ≤ 300)
- [ ] Path traversal attack blocked (test passes)
- [ ] Service starts without crash (`docker compose ps`)
