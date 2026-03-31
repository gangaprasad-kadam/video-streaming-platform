# 📋 Phase 4 — Processing Pipeline Task File

> **Goal:** Two Kafka consumer workers. The **encoding-worker** transcodes uploaded videos
> to HLS format using ffmpeg. The **thumbnail-worker** extracts a JPEG frame.
> Both run headless (no HTTP port), consuming `video.uploaded` events in parallel.

**Reference doc:** [`docs/phases/phase-4-processing-pipeline.md`](../phases/phase-4-processing-pipeline.md)
**Depends on:** Phase 1 ✅ (Kafka topics), Phase 3 ✅ (video-service publishes `video.uploaded`)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

### Encoding Worker

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure for encoding-worker | ⬜ |
| 2 | Write `requirements.txt` (encoding-worker) | ⬜ |
| 3 | Write `Dockerfile` (encoding-worker) | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/repository.py` (DB queries) | ⬜ |
| 6 | Write `app/logger.py` (MongoDB logger) | ⬜ |
| 7 | Write `app/encoder.py` (ffmpeg + ffprobe) | ⬜ |
| 8 | Write `app/consumer.py` (Kafka consumer loop) | ⬜ |
| 9 | Write `app/main.py` | ⬜ |
| 10 | Add encoding-worker to `docker-compose.yml` | ⬜ |
| 11 | Test encoding-worker end-to-end | ⬜ |

### Thumbnail Worker

| # | Task | Status |
|---|---|---|
| 12 | Create folder structure for thumbnail-worker | ⬜ |
| 13 | Write `requirements.txt` (thumbnail-worker) | ⬜ |
| 14 | Write `Dockerfile` (thumbnail-worker) | ⬜ |
| 15 | Write `app/config.py` | ⬜ |
| 16 | Write `app/repository.py` | ⬜ |
| 17 | Write `app/logger.py` | ⬜ |
| 18 | Write `app/thumbnailer.py` (ffmpeg frame extract) | ⬜ |
| 19 | Write `app/consumer.py` | ⬜ |
| 20 | Write `app/main.py` | ⬜ |
| 21 | Add thumbnail-worker to `docker-compose.yml` | ⬜ |
| 22 | Test thumbnail-worker end-to-end | ⬜ |

---

## Task Details

---

## 🔧 Encoding Worker

---

### ✅ Task 1 — Create Folder Structure (encoding-worker)

```bash
mkdir -p services/encoding-worker/app
touch services/encoding-worker/app/__init__.py
```

**Test / Verify:**
```bash
find services/encoding-worker -type f | sort
```

**Acceptance criteria:**
- [ ] `services/encoding-worker/app/__init__.py` exists

---

### ✅ Task 2 — Write `requirements.txt` (encoding-worker)

**File:** `services/encoding-worker/requirements.txt`

```
aiokafka==0.10.0
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.28
pydantic-settings==2.2.1
motor==3.3.2
```

**Note:** `ffmpeg` is installed via `apt-get` in the Dockerfile — not in requirements.txt.

**Test / Verify:**
```bash
pip install -r services/encoding-worker/requirements.txt --dry-run 2>&1 | tail -3
```

**Acceptance criteria:**
- [ ] All 5 packages listed, `motor` included for MongoDB logging

---

### ✅ Task 3 — Write `Dockerfile` (encoding-worker)

**File:** `services/encoding-worker/Dockerfile`

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python", "-m", "app.main"]
```

**Key:** `ffmpeg` installed via `apt-get`, not pip.
**No `alembic upgrade head`** — this service does not own any DB tables.

**Test / Verify:**
```bash
docker build -t encoding-worker-test services/encoding-worker/
docker run --rm encoding-worker-test ffmpeg -version 2>&1 | head -1
# Should print: ffmpeg version ...
```

**Acceptance criteria:**
- [ ] Docker build exits 0
- [ ] `ffmpeg -version` works inside the container

---

### ✅ Task 4 — Write `app/config.py` (encoding-worker)

**File:** `services/encoding-worker/app/config.py`

**Settings:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_*` | 5 PG vars | — |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `mongo_host` | `MONGO_HOST` | `mongodb` |
| `mongo_port` | `MONGO_PORT` | `27017` |
| `mongo_user` | `MONGO_USER` | — |
| `mongo_password` | `MONGO_PASSWORD` | — |
| `media_root` | `MEDIA_ROOT` | `/media` |

**Test / Verify:**
```bash
cd services/encoding-worker
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
MONGO_USER=admin MONGO_PASSWORD=secret \
python -c "
from app.config import settings
assert settings.media_root == '/media'
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] All vars mapped, test exits 0

---

### ✅ Task 5 — Write `app/repository.py` (encoding-worker)

**File:** `services/encoding-worker/app/repository.py`

**What:** DB queries to read and update video records. No business logic.

**Functions:**

| Function | SQL | Notes |
|---|---|---|
| `get_video(engine, video_id)` | `SELECT * FROM videos WHERE id=...` | Returns row dict or None |
| `update_video_processing(engine, video_id, hls_path, duration)` | `UPDATE videos SET hls_path=..., duration=..., status='processing'` | — |
| `update_video_ready(engine, video_id, hls_path, duration)` | `UPDATE videos SET hls_path=..., duration=..., status='ready'` | — |
| `update_video_failed(engine, video_id)` | `UPDATE videos SET status='failed'` | — |

**Note:** This service uses raw SQLAlchemy Core (not ORM sessions from video-service) — import `text()` from sqlalchemy.

**Test / Verify:**
```bash
cd services/encoding-worker
python -c "
from app.repository import get_video, update_video_processing, update_video_ready, update_video_failed
import inspect
for fn in [get_video, update_video_processing, update_video_ready, update_video_failed]:
    assert inspect.iscoroutinefunction(fn)
print('Repository signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 4 functions are `async def`
- [ ] Test command exits 0

---

### ✅ Task 6 — Write `app/logger.py` (encoding-worker)

**File:** `services/encoding-worker/app/logger.py`

**What:** MongoDB logger that records a `processing_logs` document at job start and end.

**Document schema:**
```python
{
    "videoId":      str,
    "workerType":   "encoding",
    "status":       "started" | "completed" | "failed",
    "inputPath":    str,
    "outputPath":   str | None,
    "durationMs":   int | None,      # wall-clock ms
    "errorMessage": str | None,
    "ffmpegCommand": str,
    "startedAt":    datetime,
    "completedAt":  datetime | None,
}
```

**Expose:**

| Function | Action |
|---|---|
| `log_started(video_id, input_path, ffmpeg_cmd)` | Insert doc with status=started |
| `log_completed(video_id, output_path, duration_ms)` | Update doc status=completed |
| `log_failed(video_id, error_message)` | Update doc status=failed |

**Motor connection uses `settings.MONGO_*`.**

**Test / Verify:**
```bash
cd services/encoding-worker
python -c "
from app.logger import log_started, log_completed, log_failed
import inspect
for fn in [log_started, log_completed, log_failed]:
    assert inspect.iscoroutinefunction(fn)
print('Logger signatures OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions are `async def`
- [ ] Collection name is `processing_logs`
- [ ] Uses Motor async driver (not pymongo)
- [ ] Test command exits 0

---

### ✅ Task 7 — Write `app/encoder.py`

**File:** `services/encoding-worker/app/encoder.py`

**What:** Wraps ffmpeg/ffprobe CLI calls. Runs them in a thread executor (blocking → async).

**Functions:**

| Function | Command | Notes |
|---|---|---|
| `encode_to_hls(video_id, input_path)` | `ffmpeg -i input -codec: copy -hls_time 10 -hls_list_size 0 -hls_segment_filename /media/hls/{vid}/segment_%03d.ts -f hls /media/hls/{vid}/index.m3u8` | Creates `/media/hls/{vid}/` dir first |
| `get_duration(input_path)` | `ffprobe -v error -show_entries format=duration -of json input` | Returns `float` seconds |
| `build_ffmpeg_command(video_id, input_path)` | — | Returns the ffmpeg command string (for logging) |

**Must run in executor (blocking ops):**
```python
import asyncio, subprocess
async def encode_to_hls(video_id: str, input_path: str) -> str:
    loop = asyncio.get_event_loop()
    output_dir = f"{settings.media_root}/hls/{video_id}"
    os.makedirs(output_dir, exist_ok=True)
    await loop.run_in_executor(None, _run_ffmpeg, video_id, input_path, output_dir)
    return f"{output_dir}/index.m3u8"

def _run_ffmpeg(video_id, input_path, output_dir):
    cmd = [...]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")
```

**Test / Verify:**
```bash
cd services/encoding-worker
python -c "
from app.encoder import encode_to_hls, get_duration, build_ffmpeg_command
import inspect
assert inspect.iscoroutinefunction(encode_to_hls)
assert inspect.iscoroutinefunction(get_duration)
cmd = build_ffmpeg_command('test-id', '/media/uploads/test-id.mp4')
assert 'ffmpeg' in cmd
print('Encoder OK')
"
```

**Acceptance criteria:**
- [ ] `encode_to_hls` is `async def` and uses `run_in_executor`
- [ ] `get_duration` is `async def` and parses ffprobe JSON output
- [ ] `build_ffmpeg_command` returns a string containing `ffmpeg`
- [ ] Raises `RuntimeError` if ffmpeg exit code != 0
- [ ] Test command exits 0

---

### ✅ Task 8 — Write `app/consumer.py` (encoding-worker)

**File:** `services/encoding-worker/app/consumer.py`

**What:** Main Kafka consumer loop. Connects, subscribes to `video.uploaded`, processes each message.

**Consumer group:** `encoding-worker-group`

**Processing flow per message:**
```
1. event = msg.value  (dict decoded from JSON)
2. video_id = event["videoId"]
3. IDEMPOTENCY: get_video(engine, video_id)
   → if status in ("ready", "failed"): return  ← skip silently
4. update_video_processing(engine, video_id, ...)
5. log_started(...)
6. start_time = time.time()
7. hls_path = await encode_to_hls(video_id, input_path)
8. duration = await get_duration(input_path)
9. update_video_ready(engine, video_id, hls_path, duration)
10. await publish_processed_event(video_id, ...)
11. log_completed(...)
```

**On exception:**
```
update_video_failed(engine, video_id)
log_failed(...)
# do NOT re-raise — let consumer continue to next message
```

**Kafka processed event payload:**
```json
{
  "videoId":     "uuid",
  "creatorId":   "uuid",
  "hlsPath":     "/media/hls/uuid/index.m3u8",
  "duration":    542.3,
  "processedAt": "ISO timestamp"
}
```

**Test / Verify:**
```bash
cd services/encoding-worker
python -c "
from app.consumer import consume
import inspect
assert inspect.iscoroutinefunction(consume)
print('Consumer function signature OK')
"
```

**Acceptance criteria:**
- [ ] `consume()` is `async def`
- [ ] Idempotency check — skips if video already `ready` or `failed`
- [ ] On ffmpeg failure: updates status to `failed`, logs error, continues consuming
- [ ] Publishes `video.processed` with correct payload after success
- [ ] Test command exits 0

---

### ✅ Task 9 — Write `app/main.py` (encoding-worker)

**File:** `services/encoding-worker/app/main.py`

**What:** Entry point. Initialises DB engine + starts consumer loop.

```python
import asyncio
from app.consumer import consume

async def main():
    # No lifespan hooks needed — engine created in consumer, no HTTP server
    await consume()

if __name__ == "__main__":
    asyncio.run(main())
```

**Test / Verify:**
```bash
cd services/encoding-worker
python -c "import app.main; print('main.py importable OK')"
```

**Acceptance criteria:**
- [ ] `app.main` importable
- [ ] `asyncio.run(main())` starts the consumer loop

---

### ✅ Task 10 — Add Encoding Worker to `docker-compose.yml`

```yaml
encoding-worker:
  build: ./services/encoding-worker
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    MONGO_USER: ${MONGO_USER}
    MONGO_PASSWORD: ${MONGO_PASSWORD}
    MONGO_HOST: ${MONGO_HOST}
    MONGO_PORT: ${MONGO_PORT}
    MEDIA_ROOT: /media
  volumes:
    - ./services/shared:/app/shared:ro
    - media_volume:/media
  depends_on:
    kafka:
      condition: service_healthy
    postgres:
      condition: service_healthy
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build encoding-worker
docker compose up -d encoding-worker
sleep 5
docker compose logs encoding-worker | tail -10
# Should show: "Consumer started. Waiting for messages..."
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] Container starts without `Exit` state
- [ ] Logs show consumer is running (not crashing)

---

### ✅ Task 11 — Test Encoding Worker End-to-End

**What:** Upload a real (small) video via video-service and observe encoding-worker output.

**Steps:**
```bash
# 1. Get a small test video (or create a synthetic one)
ffmpeg -f lavfi -i testsrc=duration=10:size=320x240:rate=25 /tmp/test.mp4

# 2. Register + login (get session cookie)
curl -c cookies.txt -X POST http://localhost:8001/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"password123"}'

curl -c cookies.txt -b cookies.txt -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# 3. Upload video
curl -b cookies.txt -X POST http://localhost:8002/videos/upload \
  -F "file=@/tmp/test.mp4" \
  -F "title=Test Video" \
  -F "description=E2E test"
# Save the returned video ID

# 4. Wait ~15 seconds, then check status
curl http://localhost:8002/videos/{VIDEO_ID}/status
# Expected: { "data": { "status": "ready" } }

# 5. Check HLS files were created
docker compose exec encoding-worker ls /media/hls/{VIDEO_ID}/
# Expected: index.m3u8, segment_000.ts, segment_001.ts ...
```

**Test / Verify MongoDB log:**
```bash
docker compose exec mongodb mongosh --eval "
  db.getSiblingDB('videoplatform').processing_logs.find({workerType:'encoding'}).pretty()
" --quiet
```

**Acceptance criteria:**
- [ ] Video status transitions: `uploading` → `processing` → `ready`
- [ ] `/media/hls/{videoId}/index.m3u8` exists
- [ ] `/media/hls/{videoId}/segment_*.ts` files exist
- [ ] MongoDB `processing_logs` has a `completed` document for this video
- [ ] `video.processed` Kafka event published (verify via `kafka-console-consumer`)

---

## 🖼️ Thumbnail Worker

---

### ✅ Task 12 — Create Folder Structure (thumbnail-worker)

```bash
mkdir -p services/thumbnail-worker/app
touch services/thumbnail-worker/app/__init__.py
```

**Acceptance criteria:**
- [ ] `services/thumbnail-worker/app/__init__.py` exists

---

### ✅ Task 13 — Write `requirements.txt` (thumbnail-worker)

**File:** `services/thumbnail-worker/requirements.txt`

```
aiokafka==0.10.0
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.28
pydantic-settings==2.2.1
motor==3.3.2
```

**Acceptance criteria:**
- [ ] Identical set to encoding-worker requirements

---

### ✅ Task 14 — Write `Dockerfile` (thumbnail-worker)

**File:** `services/thumbnail-worker/Dockerfile`

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python", "-m", "app.main"]
```

**Test / Verify:**
```bash
docker build -t thumbnail-worker-test services/thumbnail-worker/
docker run --rm thumbnail-worker-test ffmpeg -version 2>&1 | head -1
```

**Acceptance criteria:**
- [ ] Build exits 0
- [ ] `ffmpeg` available in container

---

### ✅ Task 15 — Write `app/config.py` (thumbnail-worker)

**Same as encoding-worker config** — same env vars, same `POSTGRES_URL` property.

**Test / Verify:**
```bash
cd services/thumbnail-worker
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
MONGO_USER=admin MONGO_PASSWORD=secret \
python -c "from app.config import settings; print('Config OK')"
```

**Acceptance criteria:**
- [ ] Config importable, all vars mapped

---

### ✅ Task 16 — Write `app/repository.py` (thumbnail-worker)

**File:** `services/thumbnail-worker/app/repository.py`

**Functions:**

| Function | SQL |
|---|---|
| `get_video(engine, video_id)` | `SELECT * FROM videos WHERE id=...` |
| `update_thumbnail_path(engine, video_id, thumbnail_path)` | `UPDATE videos SET thumbnail_path=... WHERE id=...` |

**Test / Verify:**
```bash
cd services/thumbnail-worker
python -c "
from app.repository import get_video, update_thumbnail_path
import inspect
for fn in [get_video, update_thumbnail_path]:
    assert inspect.iscoroutinefunction(fn)
print('Repository OK')
"
```

**Acceptance criteria:**
- [ ] Both functions are `async def`, test exits 0

---

### ✅ Task 17 — Write `app/logger.py` (thumbnail-worker)

**Same as encoding-worker logger** — same MongoDB schema, same 3 functions.
Only difference: `"workerType": "thumbnail"`.

**Test / Verify:**
```bash
cd services/thumbnail-worker
python -c "
from app.logger import log_started, log_completed, log_failed
import inspect
for fn in [log_started, log_completed, log_failed]:
    assert inspect.iscoroutinefunction(fn)
print('Logger OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions `async def`, `workerType` is `"thumbnail"`, test exits 0

---

### ✅ Task 18 — Write `app/thumbnailer.py`

**File:** `services/thumbnail-worker/app/thumbnailer.py`

**What:** Runs ffmpeg to extract a single frame at t=5s as JPEG.

**ffmpeg command:**
```bash
ffmpeg -i /media/uploads/{videoId}.mp4 -ss 00:00:05 -vframes 1 /media/thumbnails/{videoId}.jpg
```

**Function:**
```python
async def extract_thumbnail(video_id: str, input_path: str) -> str:
    # Creates /media/thumbnails/ dir if needed
    # Runs ffmpeg in executor (blocking)
    # Returns output path: /media/thumbnails/{video_id}.jpg
```

**Test / Verify:**
```bash
cd services/thumbnail-worker
python -c "
from app.thumbnailer import extract_thumbnail
import inspect
assert inspect.iscoroutinefunction(extract_thumbnail)
print('Thumbnailer signature OK')
"
```

**Acceptance criteria:**
- [ ] `extract_thumbnail` is `async def` using `run_in_executor`
- [ ] Raises `RuntimeError` if ffmpeg exit code != 0
- [ ] Returns path string `/media/thumbnails/{video_id}.jpg`
- [ ] Test command exits 0

---

### ✅ Task 19 — Write `app/consumer.py` (thumbnail-worker)

**File:** `services/thumbnail-worker/app/consumer.py`

**Consumer group:** `thumbnail-worker-group`

**Processing flow per message:**
```
1. video_id = event["videoId"]
2. IDEMPOTENCY: get_video(engine, video_id)
   → if thumbnail_path is not None: return  ← already done
3. log_started(...)
4. thumbnail_path = await extract_thumbnail(video_id, input_path)
5. update_thumbnail_path(engine, video_id, thumbnail_path)
6. log_completed(...)
```

**On exception:**
```
log_failed(...)
# continue — do NOT crash the consumer
```

**Note:** Thumbnail worker does NOT publish any Kafka event — it only updates the DB.

**Test / Verify:**
```bash
cd services/thumbnail-worker
python -c "
from app.consumer import consume
import inspect
assert inspect.iscoroutinefunction(consume)
print('Consumer signature OK')
"
```

**Acceptance criteria:**
- [ ] `consume()` is `async def`
- [ ] Consumer group is `thumbnail-worker-group` (different from encoding-worker)
- [ ] Idempotency: skip if `thumbnail_path` already set
- [ ] Does NOT publish any Kafka event
- [ ] Test command exits 0

---

### ✅ Task 20 — Write `app/main.py` (thumbnail-worker)

Same pattern as encoding-worker:

```python
import asyncio
from app.consumer import consume

async def main():
    await consume()

if __name__ == "__main__":
    asyncio.run(main())
```

**Acceptance criteria:**
- [ ] `app.main` importable

---

### ✅ Task 21 — Add Thumbnail Worker to `docker-compose.yml`

```yaml
thumbnail-worker:
  build: ./services/thumbnail-worker
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    MONGO_USER: ${MONGO_USER}
    MONGO_PASSWORD: ${MONGO_PASSWORD}
    MONGO_HOST: ${MONGO_HOST}
    MONGO_PORT: ${MONGO_PORT}
    MEDIA_ROOT: /media
  volumes:
    - ./services/shared:/app/shared:ro
    - media_volume:/media
  depends_on:
    kafka:
      condition: service_healthy
    postgres:
      condition: service_healthy
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build thumbnail-worker
docker compose up -d thumbnail-worker
sleep 5
docker compose logs thumbnail-worker | tail -10
```

**Acceptance criteria:**
- [ ] Container starts without `Exit` state
- [ ] Logs show consumer is running

---

### ✅ Task 22 — Test Thumbnail Worker End-to-End

**Steps:** Use the same test video and session from Task 11 (or repeat upload).

```bash
# After upload, wait ~10s then check thumbnail:
curl http://localhost:8002/videos/{VIDEO_ID}
# Response should include: "thumbnail_path": "/media/thumbnails/{VIDEO_ID}.jpg"

# Verify file exists on volume:
docker compose exec thumbnail-worker ls /media/thumbnails/
# Expected: {VIDEO_ID}.jpg
```

**Test / Verify MongoDB log:**
```bash
docker compose exec mongodb mongosh --eval "
  db.getSiblingDB('videoplatform').processing_logs.find({workerType:'thumbnail'}).pretty()
" --quiet
```

**Acceptance criteria:**
- [ ] `thumbnail_path` set in videos table (visible via `GET /videos/{id}`)
- [ ] `/media/thumbnails/{videoId}.jpg` exists and is a valid JPEG
- [ ] MongoDB `processing_logs` has a `completed` document with `workerType: thumbnail`

---

## Phase Complete Checklist

Before marking Phase 4 as ✅ done in `COPILOT.md`:

- [ ] All 22 tasks above are ✅ done
- [ ] Both workers start without crashes (`docker compose ps`)
- [ ] Upload a test video → status reaches `ready` within 30s
- [ ] `/media/hls/{videoId}/index.m3u8` exists
- [ ] `/media/thumbnails/{videoId}.jpg` exists
- [ ] `video.processed` Kafka event published by encoding-worker
- [ ] MongoDB `processing_logs` has entries for both `encoding` and `thumbnail` workers
- [ ] Both workers use separate consumer groups → both run in parallel
