# 📋 Phase 6 — AI Summarization Service Task File

> **Goal:** FastAPI service (port 8004) that also runs a background Kafka consumer.
> Consumes `video.processed` events → extracts audio (ffmpeg) → transcribes (Whisper) →
> summarizes (BART) → extracts key timestamps → stores in PostgreSQL + Redis cache.
> Exposes `GET /summary/:videoId`.

**Reference doc:** [`docs/phases/phase-6-ai-summarization.md`](../phases/phase-6-ai-summarization.md)
**Depends on:** Phase 1 ✅ (infra), Phase 4 ✅ (encoding-worker publishes `video.processed`)
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Create folder structure | ⬜ |
| 2 | Write `requirements.txt` | ⬜ |
| 3 | Write `Dockerfile` (with model pre-download) | ⬜ |
| 4 | Write `app/config.py` | ⬜ |
| 5 | Write `app/database.py` | ⬜ |
| 6 | Write `app/redis_client.py` | ⬜ |
| 7 | Write `app/exceptions.py` | ⬜ |
| 8 | Write `app/models.py` (VideoSummary) | ⬜ |
| 9 | Set up Alembic + create `video_summaries` migration | ⬜ |
| 10 | Write `app/pipeline/audio.py` | ⬜ |
| 11 | Write `app/pipeline/transcribe.py` | ⬜ |
| 12 | Write `app/pipeline/summarize.py` | ⬜ |
| 13 | Write `app/pipeline/timestamps.py` | ⬜ |
| 14 | Write `app/api/repository.py` | ⬜ |
| 15 | Write `app/api/cache.py` | ⬜ |
| 16 | Write `app/api/router.py` | ⬜ |
| 17 | Write `app/consumer.py` | ⬜ |
| 18 | Write `app/main.py` | ⬜ |
| 19 | Add to `docker-compose.yml` | ⬜ |
| 20 | Write `tests/test_summarization.py` + run | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Create Folder Structure

```bash
mkdir -p services/summarization-service/app/pipeline \
         services/summarization-service/app/api \
         services/summarization-service/tests
touch services/summarization-service/app/__init__.py \
      services/summarization-service/app/pipeline/__init__.py \
      services/summarization-service/app/api/__init__.py \
      services/summarization-service/tests/__init__.py
```

**Test / Verify:**
```bash
find services/summarization-service -type f | sort
```

**Acceptance criteria:**
- [ ] `app/pipeline/`, `app/api/`, `tests/` exist with `__init__.py`

---

### ✅ Task 2 — Write `requirements.txt`

**File:** `services/summarization-service/requirements.txt`

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.28
asyncpg==0.29.0
aiokafka==0.10.0
redis[asyncio]==5.0.3
openai-whisper==20231117
transformers==4.39.3
torch==2.2.2
pydantic-settings==2.2.1
alembic==1.13.1
motor==3.3.2
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0
fakeredis==2.21.3
```

**⚠️ Note:** `torch` is large (~2GB). Docker build time will be significant.

**Test / Verify:**
```bash
pip install -r services/summarization-service/requirements.txt --dry-run 2>&1 | grep -E "Would install|ERROR" | head -5
```

**Acceptance criteria:**
- [ ] All packages listed
- [ ] `openai-whisper`, `transformers`, `torch` all included

---

### ✅ Task 3 — Write `Dockerfile`

**File:** `services/summarization-service/Dockerfile`

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download models at build time (avoids cold start delay)
RUN python -c "import whisper; whisper.load_model('base')"
RUN python -c "from transformers import pipeline; pipeline('summarization', model='facebook/bart-large-cnn')"
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8004"]
```

**Key points:**
- `ffmpeg` installed for audio extraction
- Models downloaded during build (not at runtime)
- Alembic runs before uvicorn

**Test / Verify (will take ~5 min first time due to model downloads):**
```bash
docker build -t summarization-service-test services/summarization-service/
# Should exit 0 — models downloaded into image
```

**Acceptance criteria:**
- [ ] Build exits 0
- [ ] Whisper model pre-downloaded
- [ ] BART model pre-downloaded
- [ ] `ffmpeg` available

---

### ✅ Task 4 — Write `app/config.py`

**Settings:**

| Setting | Env var | Default |
|---|---|---|
| `postgres_*` | 5 PG vars | — |
| `redis_*` | 2 Redis vars | — |
| `kafka_bootstrap_servers` | `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` |
| `mongo_*` | 4 Mongo vars | — |
| `media_root` | `MEDIA_ROOT` | `/media` |
| `whisper_model` | `WHISPER_MODEL` | `base` |
| `hf_model` | `HF_MODEL` | `facebook/bart-large-cnn` |
| `summary_ttl` | `SUMMARY_TTL` | `3600` |

**Test / Verify:**
```bash
cd services/summarization-service
POSTGRES_USER=admin POSTGRES_PASSWORD=secret POSTGRES_DB=videoplatform \
MONGO_USER=admin MONGO_PASSWORD=secret \
python -c "
from app.config import settings
assert settings.whisper_model == 'base'
assert settings.summary_ttl == 3600
print('Config OK')
"
```

**Acceptance criteria:**
- [ ] `whisper_model` and `hf_model` configurable via env vars
- [ ] `summary_ttl` defaults to `3600`
- [ ] Test exits 0

---

### ✅ Task 5 — Write `app/database.py`

Same async SQLAlchemy pattern as previous services.

**Expose:** `engine`, `AsyncSessionLocal`, `Base`, `connect_db()`, `close_db()`

**Test / Verify:**
```bash
cd services/summarization-service
python -c "from app.database import Base, connect_db; import inspect; assert inspect.iscoroutinefunction(connect_db); print('DB OK')"
```

**Acceptance criteria:**
- [ ] All 5 symbols importable, test exits 0

---

### ✅ Task 6 — Write `app/redis_client.py`

Same pattern as streaming-service.

**Expose:** `connect_redis()`, `close_redis()`, `get_redis()`

**Test / Verify:**
```bash
cd services/summarization-service
python -c "from app.redis_client import get_redis; import inspect; assert inspect.isasyncgenfunction(get_redis); print('Redis OK')"
```

**Acceptance criteria:**
- [ ] `get_redis` is async generator, test exits 0

---

### ✅ Task 7 — Write `app/exceptions.py`

**Two service-specific exceptions:**

```python
from shared.exceptions import AppException

class SummaryNotFoundError(AppException):
    def __init__(self, video_id: str):
        super().__init__(404, "SUMMARY_NOT_FOUND",
                         f"Summary for video '{video_id}' not yet generated")

class ModelUnavailableError(AppException):
    def __init__(self):
        super().__init__(503, "MODEL_UNAVAILABLE",
                         "AI model is not loaded")
```

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.exceptions import SummaryNotFoundError, ModelUnavailableError
e1 = SummaryNotFoundError('abc')
assert e1.status_code == 404
e2 = ModelUnavailableError()
assert e2.status_code == 503
print('Exceptions OK')
"
```

**Acceptance criteria:**
- [ ] `SummaryNotFoundError` → 404, `SUMMARY_NOT_FOUND`
- [ ] `ModelUnavailableError` → 503, `MODEL_UNAVAILABLE`
- [ ] Test exits 0

---

### ✅ Task 8 — Write `app/models.py`

**File:** `services/summarization-service/app/models.py`

**`VideoSummary` model columns:**

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK |
| `video_id` | `UUID` | UNIQUE, FK → `videos.id` |
| `transcript` | `Text` | nullable (Whisper output) |
| `summary` | `Text` | NOT NULL (BART output) |
| `key_moments` | `JSON` | `[{timestamp, label}]` |
| `whisper_model` | `String(20)` | default `'base'` |
| `processing_ms` | `Integer` | wall-clock time in ms |
| `created_at` | `DateTime` | default `now()` |

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.models import VideoSummary
cols = {c.name for c in VideoSummary.__table__.columns}
required = {'id','video_id','transcript','summary','key_moments','whisper_model','processing_ms','created_at'}
assert required == cols, f'Missing: {required - cols}'
print('VideoSummary model OK')
"
```

**Acceptance criteria:**
- [ ] All 8 columns present
- [ ] `video_id` is UNIQUE
- [ ] `key_moments` is JSON type
- [ ] Test exits 0

---

### ✅ Task 9 — Set Up Alembic + Create Migration

```bash
cd services/summarization-service
alembic init alembic
# Edit alembic.ini + alembic/env.py (same pattern as user-service)
alembic revision --autogenerate -m "create_video_summaries_table"
```

**Test / Verify:**
```bash
alembic upgrade head
docker compose exec postgres psql -U admin -d videoplatform -c "\d video_summaries"
```

**Acceptance criteria:**
- [ ] `alembic upgrade head` exits 0
- [ ] `video_summaries` table exists with all 8 columns
- [ ] `idx_summaries_video_id` index created

---

### ✅ Task 10 — Write `app/pipeline/audio.py`

**File:** `services/summarization-service/app/pipeline/audio.py`

**What:** Extract audio from HLS video using ffmpeg → 16kHz mono WAV (required by Whisper).

**ffmpeg command:**
```bash
ffmpeg -i /media/hls/{videoId}/index.m3u8 \
  -vn -acodec pcm_s16le -ar 16000 -ac 1 \
  /tmp/{videoId}.wav
```

**Function:**
```python
async def extract_audio(video_id: str, hls_path: str) -> str:
    """Returns path to extracted .wav file."""
    # Run ffmpeg in executor (blocking)
    # Output: /tmp/{video_id}.wav
    # Raises RuntimeError if ffmpeg fails
```

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.pipeline.audio import extract_audio
import inspect
assert inspect.iscoroutinefunction(extract_audio)
print('Audio pipeline signature OK')
"
```

**Acceptance criteria:**
- [ ] `extract_audio` is `async def` using `run_in_executor`
- [ ] Outputs to `/tmp/{video_id}.wav`
- [ ] Raises `RuntimeError` on ffmpeg failure
- [ ] Test exits 0

---

### ✅ Task 11 — Write `app/pipeline/transcribe.py`

**File:** `services/summarization-service/app/pipeline/transcribe.py`

**What:** Load Whisper model once at module level. Expose a `transcribe()` function.

```python
import whisper
from app.config import settings

_model = None   # loaded lazily on first call

def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(settings.whisper_model)
    return _model

def transcribe(audio_path: str) -> dict:
    """Returns { text: str, segments: [{start, end, text}] }"""
    result = get_model().transcribe(audio_path)
    return {
        "text": result["text"],
        "segments": [
            {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
            for seg in result["segments"]
        ]
    }
```

**Note:** `transcribe()` is sync (blocking) — the caller must wrap it in `run_in_executor`.

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.pipeline.transcribe import transcribe, get_model
import inspect
# Function should be sync (caller runs it in executor)
assert not inspect.iscoroutinefunction(transcribe)
print('Transcribe module OK')
"
```

**Acceptance criteria:**
- [ ] `transcribe()` is **sync** (not async)
- [ ] Returns dict with `text` and `segments`
- [ ] Model loaded lazily (not at import time)
- [ ] Test exits 0

---

### ✅ Task 12 — Write `app/pipeline/summarize.py`

**File:** `services/summarization-service/app/pipeline/summarize.py`

**What:** Load BART pipeline once. Handle long transcripts by chunking.

```python
from transformers import pipeline as hf_pipeline

_summarizer = None

def get_summarizer():
    global _summarizer
    if _summarizer is None:
        _summarizer = hf_pipeline("summarization",
                                   model="facebook/bart-large-cnn",
                                   device=-1)   # CPU
    return _summarizer

def chunk_text(text: str, max_tokens: int = 1024) -> list[str]:
    """Split long text into chunks at sentence boundaries."""
    sentences = text.split('. ')
    chunks, current, count = [], [], 0
    for sent in sentences:
        word_count = len(sent.split())
        if count + word_count > max_tokens:
            chunks.append('. '.join(current))
            current, count = [sent], word_count
        else:
            current.append(sent)
            count += word_count
    if current:
        chunks.append('. '.join(current))
    return chunks

def summarize(text: str) -> str:
    """Returns summary string. Handles texts longer than BART's 1024-token limit."""
    chunks = chunk_text(text)
    summaries = [
        get_summarizer()(chunk, max_length=150, min_length=30, do_sample=False)[0]["summary_text"]
        for chunk in chunks
    ]
    return " ".join(summaries)
```

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.pipeline.summarize import chunk_text
chunks = chunk_text('word ' * 3000)
assert len(chunks) > 1, 'Should split long text into multiple chunks'
for c in chunks:
    assert len(c.split()) <= 1024
print('Summarize chunking OK')
"
```

**Acceptance criteria:**
- [ ] `summarize()` is **sync** (caller wraps in executor)
- [ ] `chunk_text()` correctly splits long text at sentence boundaries
- [ ] Each chunk ≤ 1024 words
- [ ] Model loaded lazily
- [ ] Test exits 0

---

### ✅ Task 13 — Write `app/pipeline/timestamps.py`

**File:** `services/summarization-service/app/pipeline/timestamps.py`

**What:** Select top N most information-dense segments from Whisper output.

```python
def extract_key_moments(segments: list[dict], top_n: int = 5) -> list[dict]:
    """
    Score each segment by word count (proxy for information density).
    Returns top_n segments sorted by score descending.
    """
    scored = [
        {
            "start": seg["start"],
            "end":   seg["end"],
            "text":  seg["text"],
            "score": len(seg["text"].split())
        }
        for seg in segments
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [
        {"timestamp": round(s["start"], 1), "label": s["text"][:60].strip()}
        for s in scored[:top_n]
    ]
```

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.pipeline.timestamps import extract_key_moments
segs = [
    {'start': 0.0, 'end': 5.0, 'text': 'hello'},
    {'start': 5.0, 'end': 10.0, 'text': 'this is a much longer segment with many words in it'},
    {'start': 10.0, 'end': 15.0, 'text': 'short'},
]
result = extract_key_moments(segs, top_n=2)
assert result[0]['timestamp'] == 5.0, 'Longest segment should be first'
assert len(result) == 2
print('Key moments extraction OK')
"
```

**Acceptance criteria:**
- [ ] Returns at most `top_n` moments
- [ ] Sorted by information density (word count) descending
- [ ] `timestamp` is the segment start time (rounded to 1 decimal)
- [ ] `label` truncated to 60 chars
- [ ] Test exits 0

---

### ✅ Task 14 — Write `app/api/repository.py`

**File:** `services/summarization-service/app/api/repository.py`

**Functions:**

| Function | SQL | Returns |
|---|---|---|
| `get_summary_by_video_id(db, video_id)` | `SELECT * FROM video_summaries WHERE video_id=...` | `VideoSummary \| None` |
| `create_summary(db, video_id, transcript, summary, key_moments, whisper_model, processing_ms)` | `INSERT INTO video_summaries ...` | `VideoSummary` |
| `summary_exists(db, video_id)` | `SELECT 1 FROM video_summaries WHERE video_id=...` | `bool` |

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.api.repository import get_summary_by_video_id, create_summary, summary_exists
import inspect
for fn in [get_summary_by_video_id, create_summary, summary_exists]:
    assert inspect.iscoroutinefunction(fn)
print('API repository OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions `async def`
- [ ] `summary_exists` returns bool (for idempotency check)
- [ ] Test exits 0

---

### ✅ Task 15 — Write `app/api/cache.py`

**File:** `services/summarization-service/app/api/cache.py`

**Functions:**

| Function | Redis op | TTL |
|---|---|---|
| `get_summary_cache(redis, video_id)` | `GET summary:{vid}` → JSON decode | — |
| `set_summary_cache(redis, video_id, data)` | `SETEX summary:{vid} 3600 JSON` | 3600s |
| `invalidate_summary_cache(redis, video_id)` | `DEL summary:{vid}` | — |

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.api.cache import get_summary_cache, set_summary_cache, invalidate_summary_cache
import inspect
for fn in [get_summary_cache, set_summary_cache, invalidate_summary_cache]:
    assert inspect.iscoroutinefunction(fn)
print('API cache OK')
"
```

**Acceptance criteria:**
- [ ] All 3 functions `async def`
- [ ] Uses `summary:` key prefix
- [ ] TTL is 3600
- [ ] Test exits 0

---

### ✅ Task 16 — Write `app/api/router.py`

**File:** `services/summarization-service/app/api/router.py`

**Endpoint:**

| Method | Path | Auth | Response |
|---|---|---|---|
| `GET` | `/summary/{video_id}` | None | 200 `SummaryResponse` |

**Response schema:**
```python
class SummaryResponse(BaseModel):
    video_id: str
    summary: str
    key_moments: list[dict]   # [{timestamp, label}]
    transcript_available: bool
```

**Service logic:**
1. Check Redis cache → return if hit
2. Query PostgreSQL → raise `SummaryNotFoundError` if None
3. Set Redis cache
4. Return response

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.api.router import router
paths = {r.path for r in router.routes}
assert '/summary/{video_id}' in paths
print('API router OK')
"
```

**Acceptance criteria:**
- [ ] Route `/summary/{video_id}` defined
- [ ] Returns 404 `SUMMARY_NOT_FOUND` if not yet generated
- [ ] Redis cache checked first
- [ ] Test exits 0

---

### ✅ Task 17 — Write `app/consumer.py`

**File:** `services/summarization-service/app/consumer.py`

**Consumer group:** `summarization-service-group`

**Processing flow per `video.processed` event:**
```
1. video_id = event["videoId"]
2. IDEMPOTENCY: summary_exists(db, video_id) → return if True
3. start_time = time.time()
4. audio_path = await extract_audio(video_id, event["hlsPath"])
5. In executor (blocking):
     a. result = transcribe(audio_path)
     b. summary_text = summarize(result["text"])
     c. key_moments = extract_key_moments(result["segments"])
6. processing_ms = int((time.time() - start_time) * 1000)
7. create_summary(db, video_id, ..., processing_ms)
8. set_summary_cache(redis, video_id, {...})
9. Clean up: os.remove(audio_path)  ← remove temp WAV
```

**On exception:**
- Log error to MongoDB
- Continue consuming (do not crash)

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.consumer import consume
import inspect
assert inspect.iscoroutinefunction(consume)
print('Consumer signature OK')
"
```

**Acceptance criteria:**
- [ ] Consumer group is `summarization-service-group`
- [ ] **Idempotency**: skips if summary already exists
- [ ] AI pipeline (Whisper + BART) run in **thread executor** (not on async loop)
- [ ] Temp WAV file cleaned up after processing
- [ ] Test exits 0

---

### ✅ Task 18 — Write `app/main.py`

**What:** FastAPI app with lifespan hooks that starts the Kafka consumer as a background task.

**Lifespan startup:**
1. `connect_db()`
2. `connect_redis()`
3. Start `consume()` as `asyncio.create_task()` (background)

**Lifespan shutdown:**
1. Cancel consumer task
2. `close_redis()`
3. `close_db()`

**Include router:**
```python
app.include_router(summary_router, prefix="/summary", tags=["summary"])
```

**Test / Verify:**
```bash
cd services/summarization-service
python -c "
from app.main import app
paths = {r.path for r in app.routes}
assert '/summary/{video_id}' in paths
print('main.py OK')
"
```

**Acceptance criteria:**
- [ ] Kafka consumer runs as background `asyncio.Task`
- [ ] API server and consumer run concurrently in same process
- [ ] App starts without import errors
- [ ] Test exits 0

---

### ✅ Task 19 — Add to `docker-compose.yml`

```yaml
summarization-service:
  build: ./services/summarization-service
  ports:
    - "8004:8004"
  environment:
    POSTGRES_USER: ${POSTGRES_USER}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB}
    POSTGRES_HOST: ${POSTGRES_HOST}
    POSTGRES_PORT: ${POSTGRES_PORT}
    REDIS_HOST: ${REDIS_HOST}
    REDIS_PORT: ${REDIS_PORT}
    KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS}
    MONGO_USER: ${MONGO_USER}
    MONGO_PASSWORD: ${MONGO_PASSWORD}
    MONGO_HOST: ${MONGO_HOST}
    MONGO_PORT: ${MONGO_PORT}
    MEDIA_ROOT: /media
    WHISPER_MODEL: ${WHISPER_MODEL}
    HF_MODEL: ${HF_MODEL}
  volumes:
    - ./services/shared:/app/shared:ro
    - media_volume:/media
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    kafka:
      condition: service_healthy
```

**Test / Verify:**
```bash
docker compose config --quiet
docker compose build summarization-service   # ~5-10min first time
docker compose up -d summarization-service
sleep 10
curl -f http://localhost:8004/docs
docker compose logs summarization-service | tail -15
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] Build exits 0 (models downloaded)
- [ ] `GET http://localhost:8004/docs` returns 200
- [ ] Logs show both API server started AND Kafka consumer started

---

### ✅ Task 20 — Write `tests/test_summarization.py` and Run

**File:** `services/summarization-service/tests/test_summarization.py`

**Test cases:**

| Test | Scenario | Expected |
|---|---|---|
| `test_get_summary_from_cache` | Summary in Redis | 200, data from cache (DB not queried) |
| `test_get_summary_from_db` | Cache miss, summary in DB | 200, DB queried, Redis populated |
| `test_get_summary_not_found` | No summary yet | 404 SUMMARY_NOT_FOUND |
| `test_extract_key_moments` | 10 segments, top_n=3 | Returns 3 highest-scoring moments |
| `test_chunk_text_short` | Text < 1024 words | Returns 1 chunk |
| `test_chunk_text_long` | Text > 1024 words | Returns multiple chunks, each ≤ 1024 words |
| `test_consumer_idempotency` | Summary already exists | Pipeline NOT run again |

**Note:** Whisper and BART are **mocked** in tests — do not run real models in unit tests.

```python
# conftest.py — mock AI models
@pytest.fixture
def mock_transcribe(monkeypatch):
    monkeypatch.setattr("app.pipeline.transcribe.transcribe",
                        lambda path: {"text": "test transcript", "segments": []})

@pytest.fixture
def mock_summarize(monkeypatch):
    monkeypatch.setattr("app.pipeline.summarize.summarize",
                        lambda text: "test summary")
```

**Run:**
```bash
cd services/summarization-service
pytest tests/test_summarization.py -v
```

**Acceptance criteria:**
- [ ] All 7 tests pass ✅
- [ ] AI models mocked in tests (no actual Whisper/BART inference)
- [ ] Idempotency test passes
- [ ] `pytest -v` exits 0

---

## Phase Complete Checklist

Before marking Phase 6 as ✅ done in `COPILOT.md`:

- [ ] All 20 tasks above are ✅ done
- [ ] All 7 tests passing, 0 failing
- [ ] `GET http://localhost:8004/docs` reachable
- [ ] Upload test video → wait for processing → `GET /summary/{videoId}` returns summary
- [ ] `video_summaries` table exists in PostgreSQL with data
- [ ] Redis key `summary:{videoId}` set after first request
- [ ] Temp WAV files cleaned up (not accumulating in `/tmp`)
- [ ] AI pipeline runs in thread executor (confirmed in code review)
