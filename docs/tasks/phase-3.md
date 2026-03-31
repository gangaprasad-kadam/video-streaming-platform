# 📋 Phase 3 — Video Service Task File

> **Goal:** FastAPI microservice on port 8002 that handles video uploads, stores metadata in
> PostgreSQL, saves files to a shared Docker volume, and publishes a `video.uploaded`
> Kafka event to trigger downstream workers.

**Reference doc:** [`docs/phases/phase-3-video-service.md`](../phases/phase-3-video-service.md)
**Depends on:** Phase 1 ✅ (infra), Phase 2 ✅ (user-service for `creator_id` FK)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure for video-service | ⬜ |
| 2 | Write `requirements.txt` | ⬜ |
| 3 | Write `Dockerfile` | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/database.py` | ⬜ |
| 6 | Write `app/kafka_producer.py` | ⬜ |
| 7 | Write `app/models.py` (Video SQLAlchemy model) | ⬜ |
| 8 | Set up Alembic + create `videos` table migration | ⬜ |
| 9 | Write `app/exceptions.py` | ⬜ |
| 10 | Write `app/videos/schemas.py` | ⬜ |
| 11 | Write `app/videos/repository.py` | ⬜ |
| 12 | Write `app/videos/cache.py` | ⬜ |
| 13 | Write `app/videos/service.py` | ⬜ |
| 14 | Write `app/videos/router.py` | ⬜ |
| 15 | Write `app/main.py` | ⬜ |
| 16 | Add `video-service` + `media_volume` to `docker-compose.yml` | ⬜ |
| 17 | Write `tests/conftest.py` | ⬜ |
| 18 | Write `tests/test_videos.py` + run | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Create Folder Structure

**Commands:**
```bash
mkdir -p services/video-service/app/videos \
         services/video-service/tests
touch services/video-service/app/__init__.py \
      services/video-service/app/videos/__init__.py \
      services/video-service/tests/__init__.py
```

**Test / Verify:**
```bash
find services/video-service -type f | sort
```

**Acceptance criteria:**
- [ ] `app/`, `app/videos/`, `tests/` exist with `__init__.py` files

---

### ✅ Task 2 — Write `requirements.txt`

**File:** `services/video-service/requirements.txt`

**Content:**
```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
aiokafka==0.10.0
aiofiles==23.2.1
python-multipart==0.0.9
pydantic-settings==2.2.1
pydantic[email]==2.6.4
alembic==1.13.1
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
fakeredis==2.21.3
```

**Test / Verify:**
```bash
pip install -r services/video-service/requirements.txt --dry-run 2>&1 | tail -3
```

**Acceptance criteria:**
- [ ] All packages listed
- [ ] `python-multipart` included (required for file upload)
- [ ] `aiokafka` included (required for Kafka producer)

---

### ✅ Task 3 — Write `Dockerfile`

**File:** `services/video-service/Dockerfile`

**Content:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8002"]
```

**Acceptance criteria:**
- [ ] Dockerfile exists
- [ ] CMD runs `alembic upgrade head` before `uvicorn`
- [ ] Port is `8002`

---

### ✅ Task 4 — Write `app/config.py`

**File:** `services/video-service/app/config.py`

**Settings to expose:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_*` | all 5 PG vars | — |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `media_root` | `MEDIA_ROOT` | `/media` |

**`POSTGRES_URL` property:** `postgresql+asyncpg://{user}:{pass}@{host}:{port}/{db}`

**Test / Verify:**
```bash
cd services/video-service
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
python -c "
from app.config import settings
assert 'asyncpg' in settings.POSTGRES_URL
assert settings.media_root == '/media'
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] All env vars mapped
- [ ] `POSTGRES_URL` property returns correct URL
- [ ] `media_root` defaults to `/media`

---

### ✅ Task 5 — Write `app/database.py`

**What:** Identical pattern to user-service — async SQLAlchemy engine + sessionmaker + `Base` + lifecycle functions.

**File:** `services/video-service/app/database.py`

**Expose:** `engine`, `AsyncSessionLocal`, `Base`, `connect_db()`, `close_db()`

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.database import Base, connect_db, close_db
import inspect
assert inspect.iscoroutinefunction(connect_db)
print('Database module OK')
"
```

**Acceptance criteria:**
- [ ] All 5 symbols importable
- [ ] `connect_db` / `close_db` are async

---

### ✅ Task 6 — Write `app/kafka_producer.py`

**File:** `services/video-service/app/kafka_producer.py`

**What:** `AIOKafkaProducer` with lifecycle functions and a `publish()` helper.

**Expose:**

| Symbol | Type | Purpose |
|---|---|---|
| `start_producer()` | `async def` | Called in `main.py` lifespan startup |
| `stop_producer()` | `async def` | Called in `main.py` lifespan shutdown |
| `publish(topic, key, value)` | `async def` | Send JSON message, partition key = `key` |

**Key detail:** `value_serializer=lambda v: json.dumps(v).encode()`

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.kafka_producer import start_producer, stop_producer, publish
import inspect
for fn in [start_producer, stop_producer, publish]:
    assert inspect.iscoroutinefunction(fn), f'{fn.__name__} must be async'
print('Kafka producer module OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions are `async def`
- [ ] `publish` encodes key as bytes and value as JSON bytes
- [ ] Test command exits 0

---

### ✅ Task 7 — Write `app/models.py`

**File:** `services/video-service/app/models.py`

**What:** SQLAlchemy ORM model for `videos` table.

**Columns:**

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK, server_default `gen_random_uuid()` |
| `title` | `String(255)` | NOT NULL |
| `description` | `Text` | nullable |
| `creator_id` | `UUID` | NOT NULL, FK → `users.id` |
| `file_path` | `Text` | NOT NULL — path on media volume |
| `hls_path` | `Text` | nullable — set by encoding-worker (Phase 4) |
| `thumbnail_path` | `Text` | nullable — set by thumbnail-worker (Phase 4) |
| `duration` | `Numeric(10,2)` | nullable — set after encoding |
| `status` | `Enum('uploading','processing','ready','failed')` | NOT NULL, default `'uploading'` |
| `file_size_bytes` | `BigInteger` | nullable |
| `mime_type` | `String(50)` | nullable |
| `created_at` | `DateTime` | default `now()` |
| `updated_at` | `DateTime` | default `now()`, onupdate |

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.models import Video
cols = {c.name for c in Video.__table__.columns}
required = {'id','title','description','creator_id','file_path',
            'hls_path','thumbnail_path','duration','status',
            'file_size_bytes','mime_type','created_at','updated_at'}
missing = required - cols
assert not missing, f'Missing columns: {missing}'
print('Video model OK')
"
```

**Acceptance criteria:**
- [ ] All 13 columns present
- [ ] `status` is an Enum with 4 values
- [ ] `creator_id` has FK to `users.id`
- [ ] Test command exits 0

---

### ✅ Task 8 — Set Up Alembic + Create Migration

**Steps:**
```bash
cd services/video-service
alembic init alembic
# Edit alembic.ini + alembic/env.py (same pattern as user-service)
alembic revision --autogenerate -m "create_videos_table"
```

**The migration must:**
1. Create `video_status` ENUM type
2. Create `videos` table with all 13 columns
3. Create 3 indexes: `idx_videos_creator`, `idx_videos_status`, `idx_videos_created_at`

**Test / Verify (requires running postgres):**
```bash
alembic upgrade head
docker compose exec postgres psql -U admin -d videoplatform \
  -c "\d videos"
```

**Acceptance criteria:**
- [ ] `alembic upgrade head` exits 0
- [ ] `\d videos` shows all 13 columns
- [ ] `video_status` ENUM created
- [ ] All 3 indexes created

---

### ✅ Task 9 — Write `app/exceptions.py`

**File:** `services/video-service/app/exceptions.py`

**What:** Re-export shared exceptions.

```python
from shared.exceptions import (
    AppException, NotFoundError, AuthError,
    ForbiddenError, ConflictError, RateLimitError
)
```

**Test / Verify:**
```bash
cd services/video-service
python -c "from app.exceptions import NotFoundError, ForbiddenError; print('OK')"
```

**Acceptance criteria:**
- [ ] Importable, test exits 0

---

### ✅ Task 10 — Write `app/videos/schemas.py`

**File:** `services/video-service/app/videos/schemas.py`

**Schemas:**

| Schema | Fields | Notes |
|---|---|---|
| `UploadVideoRequest` | `title` (1–255), `description` (optional) | Form fields (not JSON — multipart) |
| `VideoResponse` | `id`, `title`, `description`, `status`, `creator_id`, `thumbnail_path`, `duration`, `created_at` | `from_attributes=True` |
| `VideoStatusResponse` | `id`, `status` | For `/videos/:id/status` |
| `PatchVideoRequest` | `title?`, `description?` | Both optional |

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.videos.schemas import UploadVideoRequest, VideoResponse, VideoStatusResponse, PatchVideoRequest
from pydantic import ValidationError
try:
    UploadVideoRequest(title='')
    assert False
except ValidationError:
    pass
print('Video schemas OK')
"
```

**Acceptance criteria:**
- [ ] All 4 schemas importable
- [ ] `title` min_length=1 enforced
- [ ] `VideoResponse` has `from_attributes=True`
- [ ] Test command exits 0

---

### ✅ Task 11 — Write `app/videos/repository.py`

**File:** `services/video-service/app/videos/repository.py`

**Functions:**

| Function | SQL | Returns |
|---|---|---|
| `create_video(db, data)` | `INSERT INTO videos ...` | `Video` |
| `get_video_by_id(db, video_id)` | `SELECT ... WHERE id=...` | `Video \| None` |
| `list_videos(db, page, limit, creator_id?)` | paginated `SELECT` | `(list[Video], total: int)` |
| `update_video(db, video_id, fields)` | `UPDATE ... SET ...` | `Video \| None` |
| `update_video_status(db, video_id, status)` | `UPDATE videos SET status=...` | `Video \| None` |

**Rules:**
- Only `async def` functions
- Only SQLAlchemy queries — no business logic

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.videos.repository import create_video, get_video_by_id, list_videos, update_video, update_video_status
import inspect
for fn in [create_video, get_video_by_id, list_videos, update_video, update_video_status]:
    assert inspect.iscoroutinefunction(fn)
print('Video repository signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 5 functions are `async def`
- [ ] Test command exits 0

---

### ✅ Task 12 — Write `app/videos/cache.py`

**File:** `services/video-service/app/videos/cache.py`

**What:** Redis cache for video metadata (cache-aside pattern).

**Functions:**

| Function | Redis op | Notes |
|---|---|---|
| `get_video_cache(redis, video_id)` | `GET video:{vid}` | Returns `dict \| None` |
| `set_video_cache(redis, video_id, data)` | `SET video:{vid} ... EX 300` | 5-minute TTL |
| `invalidate_video_cache(redis, video_id)` | `DEL video:{vid}` | Called on update |

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.videos.cache import get_video_cache, set_video_cache, invalidate_video_cache
import inspect
for fn in [get_video_cache, set_video_cache, invalidate_video_cache]:
    assert inspect.iscoroutinefunction(fn)
print('Video cache signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions are `async def`
- [ ] Keys use `video:` prefix
- [ ] TTL is 300 seconds (5 minutes)

---

### ✅ Task 13 — Write `app/videos/service.py`

**File:** `services/video-service/app/videos/service.py`

**Functions:**

| Function | Logic |
|---|---|
| `upload_video(db, redis, current_user_id, file, title, description)` | Save file to `/media/uploads/{video_id}.ext` → insert DB record (status=uploading) → publish `video.uploaded` Kafka event → return `Video` |
| `get_video(db, redis, video_id)` | Check cache → if miss fetch from DB → set cache → return `Video` |
| `list_videos(db, page, limit, creator_id?)` | Call repository, return paged result |
| `patch_video(db, redis, video_id, current_user_id, data)` | Fetch video → check `creator_id == current_user_id` else raise `ForbiddenError` → update → invalidate cache |
| `update_status(db, video_id, new_status)` | Idempotent: if status already `ready` or `failed`, skip. Else update. |

**Kafka event payload for `video.uploaded`:**
```json
{
  "videoId": "uuid",
  "creatorId": "uuid",
  "filePath": "/media/uploads/uuid.mp4",
  "mimeType": "video/mp4",
  "title": "My Video",
  "uploadedAt": "ISO timestamp"
}
```

**File save:**
```python
# Use aiofiles for non-blocking write
import aiofiles, os, uuid
video_id = str(uuid.uuid4())
ext = file.filename.rsplit('.', 1)[-1]
save_path = f"{settings.media_root}/uploads/{video_id}.{ext}"
os.makedirs(os.path.dirname(save_path), exist_ok=True)
async with aiofiles.open(save_path, 'wb') as f:
    content = await file.read()
    await f.write(content)
```

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.videos.service import upload_video, get_video, list_videos, patch_video, update_status
import inspect
for fn in [upload_video, get_video, list_videos, patch_video, update_status]:
    assert inspect.iscoroutinefunction(fn), f'{fn.__name__} must be async'
print('Video service signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 5 functions are `async def`
- [ ] `upload_video` saves file using `aiofiles` (non-blocking)
- [ ] `upload_video` publishes Kafka event with correct payload
- [ ] `patch_video` raises `ForbiddenError` when `creator_id != current_user_id`
- [ ] `update_status` is idempotent (skips if already `ready` or `failed`)
- [ ] Test command exits 0

---

### ✅ Task 14 — Write `app/videos/router.py`

**File:** `services/video-service/app/videos/router.py`

**Endpoints:**

| Method | Path | Auth | Success | Errors |
|---|---|---|---|---|
| `POST` | `/videos/upload` | Required | 201 `VideoResponse` | 401 |
| `GET` | `/videos/{video_id}` | Optional | 200 `VideoResponse` | 404 |
| `GET` | `/videos` | Optional | 200 `PagedResponse[VideoResponse]` | — |
| `PATCH` | `/videos/{video_id}` | Required (creator) | 200 `VideoResponse` | 401, 403, 404 |
| `GET` | `/videos/{video_id}/status` | Optional | 200 `VideoStatusResponse` | 404 |

**File upload uses `UploadFile` + `Form`:**
```python
@router.post("/upload", status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(None),
    current_user: str = Depends(get_current_user),
    ...
):
```

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.videos.router import router
paths = {r.path for r in router.routes}
assert '/videos/upload' in paths
assert '/videos/{video_id}' in paths
assert '/videos' in paths
assert '/videos/{video_id}/status' in paths
print('Video router routes OK')
"
```

**Acceptance criteria:**
- [ ] All 5 routes defined
- [ ] Upload uses `UploadFile` + `Form`
- [ ] Test command exits 0

---

### ✅ Task 15 — Write `app/main.py`

**File:** `services/video-service/app/main.py`

**What:** Same pattern as user-service: lifespan hooks + 3 exception handlers + router include.

**Lifespan startup:**
1. `connect_db()`
2. `start_producer()` (Kafka)

**Lifespan shutdown:**
1. `stop_producer()`
2. `close_db()`

**Note:** No Redis connection in this service — Redis is used in videos/cache.py but connected on demand via dependency.

**Test / Verify:**
```bash
cd services/video-service
python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/videos/upload' in paths
print('main.py OK')
"
```

**Acceptance criteria:**
- [ ] App starts without import errors
- [ ] Videos router mounted
- [ ] All 3 exception handlers registered
- [ ] Kafka producer started/stopped in lifespan

---

### ✅ Task 16 — Add to `docker-compose.yml` + `media_volume`

**What:** Add `video-service` container and shared `media_volume` to `docker-compose.yml`.

**Add service:**
```yaml
video-service:
  build: ./services/video-service
  ports:
    - "8002:8002"
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    MEDIA_ROOT: /media
  volumes:
    - ./services/shared:/app/shared:ro
    - media_volume:/media
  depends_on:
    postgres:
      condition: service_healthy
    kafka:
      condition: service_healthy
```

**Add named volume:**
```yaml
volumes:
  postgres_data:
  mongo_data:
  media_volume:     ← add this
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build video-service
docker compose up -d video-service
sleep 5
curl -f http://localhost:8002/docs
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] `media_volume` declared in volumes section
- [ ] `GET http://localhost:8002/docs` returns 200
- [ ] Service starts without crash

---

### ✅ Task 17 — Write `tests/conftest.py`

**File:** `services/video-service/tests/conftest.py`

**Fixtures:**

| Fixture | What it provides |
|---|---|
| `client` | `AsyncClient` on test app |
| `db` | In-process async DB session |
| `mock_kafka` | `AsyncMock` replacing `publish()` so tests don't need a live Kafka |
| `auth_headers` | Dict with pre-seeded session cookie for `test_user_id` |

**Key:** Mock Kafka with `unittest.mock.AsyncMock` — tests should verify the mock was called with correct arguments, not actually send to Kafka.

**Test / Verify:**
```bash
cd services/video-service
pytest tests/conftest.py --collect-only
```

**Acceptance criteria:**
- [ ] `pytest --collect-only` exits 0 with no errors
- [ ] `mock_kafka` fixture patches `app.kafka_producer.publish`
- [ ] `auth_headers` fixture provides valid session

---

### ✅ Task 18 — Write `tests/test_videos.py` and Run

**File:** `services/video-service/tests/test_videos.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_upload_success` | Auth + valid mp4 file | 201, `status=uploading`, `id` in response |
| `test_upload_requires_auth` | No session cookie | 401 UNAUTHORIZED |
| `test_upload_publishes_kafka_event` | Valid upload | `mock_kafka` called with `video.uploaded` topic |
| `test_get_video_by_id` | Valid ID | 200, correct data |
| `test_get_video_not_found` | Unknown ID | 404 VIDEO_NOT_FOUND |
| `test_list_videos_pagination` | page=1, limit=5 | 200, paginated response |
| `test_patch_video_as_creator` | Creator patching own video | 200, updated title |
| `test_patch_video_as_non_creator` | Different user | 403 FORBIDDEN |
| `test_status_transitions` | uploading → processing → ready | Status updates correctly, idempotent on `ready` |

**Run:**
```bash
cd services/video-service
pytest tests/test_videos.py -v
```

**Acceptance criteria:**
- [ ] All 9 tests pass ✅
- [ ] `pytest tests/test_videos.py -v` exits 0
- [ ] Kafka publish mock verified — test proves event is sent

---

### ✅ Final: Run Full Test Suite

```bash
cd services/video-service
pytest tests/ -v --tb=short
```

**Acceptance criteria:**
- [ ] All 9 tests passing, 0 failing

---

## Phase Complete Checklist

Before marking Phase 3 as ✅ done in `COPILOT.md`:

- [ ] All 18 tasks above are ✅ done
- [ ] `pytest tests/ -v` — 9 tests passing, 0 failing
- [ ] `GET http://localhost:8002/docs` reachable
- [ ] `POST /videos/upload` (with file + auth) returns 201 with `status: uploading`
- [ ] `video.uploaded` Kafka event verified via mock in tests
- [ ] Alembic migration ran — `videos` table exists with 13 columns
- [ ] `media_volume` declared in `docker-compose.yml`
