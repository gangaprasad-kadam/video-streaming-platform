# Summarization Service — Complete Technical Reference

## 1. What Is This Service?

The **summarization-service** is the AI-powered component of the platform. It uses two
machine learning models to automatically process videos:

1. **OpenAI Whisper** — Speech-to-text transcription. Converts audio to full text transcript
   plus timestamped segments with confidence scores.
2. **DistilBART (sshleifer/distilbart-cnn-12-6)** — Text summarization. Condenses the
   transcript into a short paragraph summary.

It runs in **dual-mode** — simultaneously:
- A **Kafka consumer** (background asyncio task) that auto-processes videos as they finish encoding
- A **FastAPI HTTP server** that serves pre-computed summaries on demand

**Port:** `8004` (internal Docker network: `summarization-service:8004`)  
**Database:** PostgreSQL (`videoplatform` — `video_summaries` table, its own migration)  
**Cache:** Redis DB 3 (`redis://redis:6379/3`) — summary cache (1-hour TTL)  
**Kafka:** Consumes `video.processed` topic (published by encoding-worker)  
**Framework:** FastAPI + asyncio background task + SQLAlchemy + aiokafka + openai-whisper + transformers

---

## 2. Folder Structure

```
summarization-service/
├── app/
│   ├── main.py              ← FastAPI app factory + lifespan (starts Kafka consumer as background task)
│   ├── config.py            ← Pydantic-Settings (reads .env)
│   ├── database.py          ← SQLAlchemy async engine + get_db()
│   ├── redis_client.py      ← Redis connection (DB 3)
│   ├── models.py            ← VideoSummary ORM model
│   ├── exceptions.py        ← SummaryNotFoundError, TranscriptionError
│   │
│   └── summary/             ← Summary domain
│       ├── handler/
│       │   ├── consumer.py  ← Kafka consumer loop (runs as asyncio background task)
│       │   └── router.py    ← HTTP route: GET /summary/{video_id}
│       ├── utils/
│       │   ├── service.py   ← Business logic: get_summary (cache-aside) + process_video (pipeline)
│       │   ├── whisper_utils.py ← Audio extraction (ffmpeg) + Whisper transcription + key moments
│       │   ├── bart_utils.py    ← BART summarization
│       │   ├── cache.py     ← Redis cache helpers (get/set/invalidate)
│       │   └── schemas.py   ← SummaryResponse + KeyMoment Pydantic models
│       └── dao/
│           └── repository.py← PostgreSQL CRUD for video_summaries table
│
├── migrations/
│   └── versions/
│       └── 0001_create_video_summaries_table.py
├── tests/
│   ├── conftest.py          ← fixtures: SQLite, mock Redis, Kafka consumer patched to no-op
│   └── test_summary.py      ← 4 tests
├── Dockerfile               ← Pre-downloads Whisper + BART models at build time
├── alembic.ini
├── requirements.txt
└── pytest.ini
```

---

## 3. Three-Layer Architecture

```
Two entry points:

1. HTTP (FastAPI):
   GET /summary/{video_id}
       │
       ▼
   handler/router.py    ← Routes only
       │
       ▼
   utils/service.get_summary()  ← Cache-aside: Redis → PostgreSQL → 404
       ├──► utils/cache.py     ← Redis: get/set/invalidate
       └──► dao/repository.py  ← SELECT from video_summaries

2. Kafka (background task in lifespan):
   video.processed event arrives
       │
       ▼
   handler/consumer.py    ← Receives Kafka message, calls service
       │
       ▼
   utils/service.process_video()  ← Full AI pipeline
       ├──► utils/whisper_utils.py  ← ffmpeg + Whisper
       ├──► utils/bart_utils.py     ← BART summarization
       ├──► dao/repository.py       ← INSERT into video_summaries
       └──► utils/cache.py          ← Prime Redis cache after insert
```

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@postgres:5432/videoplatform` | PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/3` | Redis **DB 3** (summary cache) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker |
| `KAFKA_GROUP_ID` | `summarization-service` | Consumer group for offset tracking |
| `KAFKA_TOPIC_CONSUME` | `video.processed` | Topic published by encoding-worker |
| `WHISPER_MODEL` | `base` | Whisper model size (tiny/base/small/medium/large) |
| `BART_MODEL` | `sshleifer/distilbart-cnn-12-6` | HuggingFace model identifier |
| `SUMMARY_CACHE_TTL` | `3600` | Summary cache TTL in seconds (1 hour) |
| `DEBUG` | `False` | SQLAlchemy query logging |

---

## 5. Dual-Mode Architecture (main.py)

This service is unique — it's **both** a Kafka consumer AND an HTTP server running simultaneously
in the same process. This is achieved through asyncio's cooperative concurrency:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await connect_redis()

    # Start Kafka consumer as a BACKGROUND asyncio task
    consumer_task = asyncio.create_task(run_consumer())
    logger.info("Kafka consumer task started")

    yield  # FastAPI is now serving HTTP requests

    # Shutdown: cancel the consumer task
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass

    await close_redis()
    await close_db()
```

**How this works:**

```
asyncio event loop
    │
    ├── [task 1] uvicorn HTTP server
    │     └── handles GET /summary/{id} requests
    │
    └── [task 2] run_consumer() (background)
          └── Kafka consumer loop
                └── processes video.processed events
```

Both tasks run on the **same event loop**. They interleave using `await` — when the consumer
is waiting for Kafka, the HTTP server handles requests. When an AI model runs (CPU-heavy),
it runs in a thread executor (see section 9) so it doesn't block the event loop.

---

## 6. Database Schema (models.py + Migration)

### Table: `video_summaries`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, auto-generated | Row identifier |
| `video_id` | UUID | UNIQUE, NOT NULL | Reference to video (no FK — decoupled) |
| `transcript` | TEXT | NOT NULL | Full Whisper transcription |
| `summary` | TEXT | NOT NULL | BART-generated summary paragraph |
| `key_moments` | JSONB (PostgreSQL) / JSON (SQLite for tests) | NOT NULL, DEFAULT [] | Array of `{timestamp, label}` objects |
| `created_at` | TIMESTAMPTZ | DEFAULT now() | Processing timestamp |
| `updated_at` | TIMESTAMPTZ | DEFAULT now(), ON UPDATE | Last update |

**`key_moments` JSON structure:**
```json
[
  {"timestamp": 5.0, "label": "Introduction to the topic"},
  {"timestamp": 42.5, "label": "Main demonstration begins"},
  {"timestamp": 118.0, "label": "Summary and conclusions"}
]
```

**Unique constraint on `video_id`:** One row per video. Ensures idempotency — trying to process
the same video twice will find the existing record and skip.

**Indexes:** `idx_summaries_video_id` on `video_id` — fast lookup by video UUID.

**JSONB vs JSON:** The migration uses PostgreSQL `JSONB` (binary JSON, queryable, indexed).
The SQLAlchemy model uses `JSON` (for SQLite test compatibility). In production PostgreSQL,
JSONB is used.

---

## 7. Kafka Consumer (handler/consumer.py)

### Consumer Setup

```python
consumer = AIOKafkaConsumer(
    "video.processed",
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    group_id="summarization-service",
    value_deserializer=lambda v: json.loads(v.decode()),
    auto_offset_reset="earliest",
    enable_auto_commit=True,
)
```

**Listens to `video.processed`** — the event published by encoding-worker after successful HLS
transcoding. This is important: summarization only happens for successfully encoded videos.

**Shutdown handling:** The consumer loop handles `asyncio.CancelledError`:
```python
try:
    async for msg in consumer:
        await _handle_event(msg.value)
except asyncio.CancelledError:
    logger.info("Consumer cancelled — shutting down")
finally:
    await consumer.stop()
```

When `main.py` calls `consumer_task.cancel()`, this exception is raised at the next `await`
inside the consumer loop, triggering graceful cleanup.

### Event Handler

```python
async def _handle_event(event: dict) -> None:
    video_id = event.get("videoId")
    hls_path = event.get("hlsPath")   ← Uses HLS path (not filePath!)

    async with AsyncSessionFactory() as db:
        redis = get_redis()
        await process_video(db, redis, video_id, hls_path)
```

**Why `hlsPath` not `filePath`?**

The `video.processed` event from encoding-worker contains `hlsPath` (the `.m3u8` manifest path)
but NOT `filePath` (original upload). This is intentional — ffmpeg can extract audio directly
from the HLS manifest, reading all segments transparently.

---

## 8. AI Processing Pipeline (utils/service.py → process_video)

```python
async def process_video(db, redis, video_id, hls_path) -> None:
    # 1. Idempotency check
    existing = await repo.get_by_video_id(db, video_id)
    if existing:
        return  # Already processed — skip

    try:
        # 2. Extract audio from HLS
        audio_path = await extract_audio(video_id, hls_path)

        # 3. Transcribe with Whisper
        whisper_result = await transcribe(audio_path, "base")
        transcript = whisper_result["text"].strip()
        segments = whisper_result["segments"]

        # 4. Extract key moments from segments
        key_moments = extract_key_moments(segments)

        # 5. Summarize with BART
        summary_text = await summarize(transcript, "sshleifer/distilbart-cnn-12-6")

        # 6. Store in PostgreSQL
        await repo.create_summary(db, video_id, transcript, summary_text, key_moments)

        # 7. Prime Redis cache immediately
        record = await repo.get_by_video_id(db, video_id)
        await cache_summary(redis, video_id, SummaryResponse(...).model_dump())

    finally:
        cleanup_audio(audio_path)  # Delete /tmp/audio_{id}.wav
```

**Idempotency:** If the consumer re-processes an event (e.g. after crash + restart),
`get_by_video_id()` returns the existing record and the function returns early.
No duplicate records are created.

---

## 9. Audio Extraction — ffmpeg (utils/whisper_utils.py)

### What "Audio Extraction" Means

Whisper needs a WAV audio file as input. The HLS video files are `.ts` (MPEG-TS containers with
both video and audio streams). We use ffmpeg to:
1. Open the HLS manifest (ffmpeg reads all segments automatically)
2. Extract only the audio stream (`-vn` = no video)
3. Convert to 16kHz mono WAV (Whisper's required format)

### The ffmpeg Command

```bash
ffmpeg -y \
  -i /media/hls/{video-uuid}/index.m3u8 \
  -vn \                    ← Skip video stream, audio only
  -acodec pcm_s16le \      ← Raw PCM 16-bit little-endian (uncompressed WAV)
  -ar 16000 \              ← Sample rate: 16kHz (Whisper's native rate)
  -ac 1 \                  ← Mono channel (Whisper doesn't need stereo)
  /tmp/audio_{video-uuid}.wav
```

**Why 16kHz mono?** Whisper was trained on 16kHz audio. Converting to this rate gives the
best transcription accuracy. Stereo adds no information for speech recognition.

**Output:** `/tmp/audio_{video-uuid}.wav` — temporary file, deleted after transcription.

---

## 10. Whisper Transcription (utils/whisper_utils.py)

### What Is Whisper?

OpenAI Whisper is an open-source speech-to-text model. The `base` model (~142MB) has good
accuracy for English and reasonable performance on modern hardware.

**Model sizes (trade-off between speed and accuracy):**
| Model | Size | Speed | Accuracy |
|---|---|---|---|
| `tiny` | 39MB | Fastest | Lowest |
| `base` | 142MB | Fast | Good (used here) |
| `small` | 244MB | Medium | Better |
| `medium` | 769MB | Slow | Very good |
| `large` | 1.5GB | Slowest | Best |

### Lazy Loading (Singleton Pattern)

```python
_model = None

def _load_model(model_name: str):
    global _model
    if _model is None:
        _model = whisper.load_model(model_name)  # Only loaded ONCE
    return _model
```

The model is loaded on first use, not at startup. After first load, subsequent calls
reuse the same in-memory model object. Loading takes ~5 seconds and uses ~300MB RAM.

### Thread Executor (Non-Blocking)

```python
async def transcribe(audio_path: str, model_name: str) -> dict:
    loop = asyncio.get_event_loop()

    def _run():
        model = _load_model(model_name)
        return model.transcribe(audio_path)

    result = await loop.run_in_executor(None, _run)
    return result
```

**Why `run_in_executor`?**

`model.transcribe()` is a **CPU-intensive synchronous** operation (it loads and processes audio,
runs neural network inference). If called directly in the async code, it would **block the event
loop** for several seconds — during which no HTTP requests would be served.

`run_in_executor(None, fn)` runs `fn` in Python's default thread pool. The event loop stays
responsive: other async tasks (HTTP requests, Kafka messages) continue running while Whisper
processes in a background thread.

### Whisper Output Structure

```python
whisper_result = {
    "text": "Welcome to this video about Python programming. Today we will cover...",
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 5.2,
            "text": "Welcome to this video about Python programming.",
            "no_speech_prob": 0.02,   ← Low = confident speech detected
        },
        {
            "id": 1,
            "start": 5.2,
            "end": 10.8,
            "text": "[Music]",
            "no_speech_prob": 0.95,   ← High = likely silence or music, not speech
        },
        ...
    ]
}
```

### Key Moments Extraction

```python
def extract_key_moments(segments: list) -> list[dict]:
    key_moments = []
    for seg in segments:
        text = seg.get("text", "").strip()
        no_speech_prob = seg.get("no_speech_prob", 1.0)

        # Filter: confident speech AND meaningful length
        if no_speech_prob < 0.4 and len(text) > 15:
            key_moments.append({
                "timestamp": round(float(seg["start"]), 1),
                "label": text[:120],  # Truncate to 120 chars
            })

    return key_moments[:10]  # Maximum 10 key moments
```

**Filtering logic:**
- `no_speech_prob < 0.4` — the model is confident there IS speech (not music/silence)
- `len(text) > 15` — exclude short segments like "[applause]" or single words
- Max 10 moments — practical limit for the UI
- `text[:120]` — truncate long segments to label length

---

## 11. BART Summarization (utils/bart_utils.py)

### What Is BART?

BART (Bidirectional and Auto-Regressive Transformer) is a Facebook AI text-to-text model
originally designed for text summarization. We use **DistilBART** — a smaller, faster version
distilled from the full BART model.

**Why DistilBART over BART-large?**
| Model | Size | Generation speed | Quality |
|---|---|---|---|
| `sshleifer/distilbart-cnn-12-6` | ~306MB | Fast | Good |
| `facebook/bart-large-cnn` | ~1.6GB | Slow | Better |

For a platform feature (not a research paper), DistilBART quality is sufficient.

### Lazy Loading + Thread Executor

Same pattern as Whisper:

```python
_summarizer = None

def _load_summarizer(model_name: str):
    global _summarizer
    if _summarizer is None:
        _summarizer = pipeline("summarization", model=model_name)
    return _summarizer

async def summarize(text: str, model_name: str) -> str:
    truncated = text[:1000]  # BART has token limit

    loop = asyncio.get_event_loop()
    def _run():
        summarizer = _load_summarizer(model_name)
        result = summarizer(truncated, max_length=150, min_length=30, do_sample=False)
        return result[0]["summary_text"]

    return await loop.run_in_executor(None, _run)
```

**`max_length=150, min_length=30`:** Summary is between 30 and 150 tokens (~20–120 words).  
**`do_sample=False`:** Use greedy/beam search (deterministic). Sampling = random, less consistent.  
**`text[:1000]`:** BART's token limit is ~1024 tokens. We truncate input to ~1000 characters
as a safe approximation (English averages ~5 chars/token).

---

## 12. Redis Cache Design (utils/cache.py)

| Key | Value | TTL |
|---|---|---|
| `summary:{videoId}` | JSON-serialized SummaryResponse dict | 3600s (1 hour) |

```python
async def get_cached_summary(redis, video_id):
    raw = await redis.get(f"summary:{video_id}")
    return json.loads(raw) if raw else None

async def cache_summary(redis, video_id, data):
    await redis.set(f"summary:{video_id}", json.dumps(data), ex=3600)
```

**Why 1-hour TTL?** Summaries don't change (the video is static). But after 1 hour, the cache
refreshes from PostgreSQL (which is always up to date). Longer TTL = fewer DB queries.

**Cache priming:** After saving to PostgreSQL, `process_video()` immediately calls `cache_summary()`
to pre-populate Redis. This means the very first GET request for a newly processed video will
be a **cache hit** (no DB query on first access).

---

## 13. HTTP API Endpoint

### GET `/health`

Standard health check. Returns `{"status": "ok", "service": "summarization-service"}`.

---

### GET `/summary/{video_id}`

Returns the AI-generated summary for a video.

**Auth Required:** No (public endpoint)

**Success Response — 200 OK:**
```json
{
  "data": {
    "video_id": "550e8400-e29b-41d4-a716-446655440000",
    "transcript": "Welcome to this video about Python programming. Today we will cover FastAPI, SQLAlchemy, and async patterns...",
    "summary": "This video covers Python web development using FastAPI and SQLAlchemy. It demonstrates async patterns and database integration techniques.",
    "key_moments": [
      {"timestamp": 5.0, "label": "Introduction to FastAPI"},
      {"timestamp": 42.5, "label": "SQLAlchemy async session setup"},
      {"timestamp": 118.0, "label": "Demo: running the full application"}
    ],
    "created_at": "2024-01-15T10:40:00"
  }
}
```

**Error Responses:**
| Status | Error Code | Cause |
|---|---|---|
| 404 | `SUMMARY_NOT_FOUND` | Video hasn't been processed yet, or Whisper failed |

**Note on 404:** A 404 doesn't mean the video doesn't exist — it means the summary hasn't
been generated yet. The error message says: "processing may still be in progress."

**Internal Flow:**
```
GET /summary/{video_id}
    → router.py → summary_service.get_summary(db, redis, video_id)
        1. get_cached_summary(redis, video_id) → HIT: return SummaryResponse immediately
        2. repo.get_by_video_id(db, video_id) → None → raise SummaryNotFoundError (404)
        3. Build SummaryResponse from DB record
        4. cache_summary(redis, video_id, response.model_dump())
    ← SuccessResponse[SummaryResponse]
```

---

## 14. Exceptions (exceptions.py)

```python
class SummaryNotFoundError(NotFoundError):
    error_code = "SUMMARY_NOT_FOUND"
    status_code = 404
    message = "Summary for video '{video_id}' not found — processing may still be in progress"

class TranscriptionError(Exception):
    """Raised when Whisper fails to transcribe."""
    message = "Failed to transcribe audio"
```

`SummaryNotFoundError` uses a custom `error_code` (`SUMMARY_NOT_FOUND`) so clients can
distinguish it from generic 404s.

---

## 15. Docker Configuration

```dockerfile
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download AI models at BUILD TIME (not at runtime)
RUN python3 -c "import whisper; whisper.load_model('base')"
RUN python3 -c "from transformers import pipeline; pipeline('summarization', model='sshleifer/distilbart-cnn-12-6')"

COPY alembic.ini .
COPY migrations/ ./migrations/
COPY app/ ./app/

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8004"]
```

**Key point: models pre-downloaded at build time.**

Without this, the first time `model.transcribe()` or `pipeline()` is called, HuggingFace
would download ~300–450MB of model weights from the internet. This would:
- Fail in environments without internet access
- Add 60–120 seconds to first request latency
- Fail if the model registry is unavailable

By running `python3 -c "import whisper; whisper.load_model('base')"` during `docker build`,
the model weights are downloaded and baked into the Docker image layer. Container starts
instantly with models ready.

**Build time impact:** Image is ~2GB (base Python + torch + models). Build takes ~5 minutes.

---

## 16. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `sqlalchemy[asyncio]` | 2.0.28 | Async ORM |
| `asyncpg` | 0.29.0 | Async PostgreSQL driver |
| `redis[asyncio]` | 5.0.3 | Async Redis client |
| `aiokafka` | 0.10.0 | Async Kafka consumer |
| `openai-whisper` | 20231117 | Speech-to-text model (includes torch dependency) |
| `transformers` | 4.39.3 | HuggingFace model hub + pipeline API (BART) |
| `torch` | 2.2.2 | PyTorch — tensor operations for both models |
| `pydantic-settings` | 2.2.1 | Config from environment |
| `alembic` | 1.13.1 | Database migrations |

---

## 17. Testing

**The testing challenge:** Whisper and BART are huge models that can't run in unit tests
(too slow, require GPU/large RAM). Solution: mock them out entirely.

**Test strategy:**
- SQLite in-memory for DB
- AsyncMock for Redis (dict-backed)
- **Kafka consumer patched to a no-op** — the `asyncio.create_task(run_consumer())` in lifespan
  would try to connect to a real Kafka broker in tests. We patch it:
  ```python
  with patch("app.summary.handler.consumer.run_consumer", return_value=None):
      async with AsyncClient(...) as ac:
          yield ac, store
  ```
- AI model calls are NOT called in tests (no test for `process_video` pipeline —
  that would require a real Whisper model)

**Test coverage (4 tests):**

| Test | What is tested |
|---|---|
| `test_health` | Health endpoint returns 200 |
| `test_get_summary_not_found` | Unknown video UUID → 404 with `SUMMARY_NOT_FOUND` |
| `test_get_summary_from_db` | (placeholder — covered by cache test) |
| `test_get_summary_from_cache` | Pre-seed Redis → GET returns cached data without DB |

**Run tests:**
```bash
cd backend/summarization-service
python -m pytest tests/ -q
# Expected: 4 passed
```

---

## 18. Full End-to-End Flow — Video Upload to Summary Available

```
USER             NGINX          VIDEO-SERVICE    KAFKA    ENCODING-WORKER    SUMMARIZATION-SERVICE    POSTGRES    REDIS
  │               │                │               │             │                   │                   │          │
  │ POST /videos/upload            │               │             │                   │                   │          │
  │──────────────►│──────────────►│               │             │                   │                   │          │
  │               │               │── publish ────►│             │                   │                   │          │
  │               │               │  video.uploaded│             │                   │                   │          │
  │◄── 201 ───────┤               │               │             │                   │                   │          │
  │                               │               │             │                   │                   │          │
  │                               │               │─ deliver ───►│                   │                   │          │
  │                               │               │             │── ffmpeg transcode │                   │          │
  │                               │               │             │   → /media/hls/X/ │                   │          │
  │                               │               │             │                   │                   │          │
  │                               │               │             │── publish ────────────────────────────►│          │
  │                               │               │             │  video.processed   │                   │          │
  │                               │               │             │  {videoId, hlsPath}│                   │          │
  │                               │               │             │                   │                   │          │
  │                               │               │             │                   │── ffmpeg extract audio       │
  │                               │               │             │                   │   /tmp/audio_X.wav│          │
  │                               │               │             │                   │                   │          │
  │                               │               │             │                   │── Whisper.transcribe()       │
  │                               │               │             │                   │   (in thread exec)│          │
  │                               │               │             │                   │                   │          │
  │                               │               │             │                   │── BART.summarize()│          │
  │                               │               │             │                   │   (in thread exec)│          │
  │                               │               │             │                   │                   │          │
  │                               │               │             │                   │── INSERT video_summaries ───►│
  │                               │               │             │                   │── cache_summary ────────────────────►│
  │                               │               │             │                   │── delete /tmp/audio_X.wav    │          │
  │                               │               │             │                   │                   │          │
  │ GET /summary/{video_id}        │               │             │                   │                   │          │
  │──────────────►│────────────────────────────────────────────────────────────────►│                   │          │
  │               │               │               │             │                   │── get_cached ─────────────────────────►│
  │               │               │               │             │                   │   (HIT from cache priming)│  │
  │◄── 200 {transcript, summary, key_moments} ─────────────────────────────────────┤                   │          │
```

---

## 19. Comparison: This Service vs. Other Workers

| Aspect | encoding-worker | thumbnail-worker | summarization-service |
|---|---|---|---|
| Type | Pure worker (no HTTP) | Pure worker (no HTTP) | Dual: HTTP + Kafka consumer |
| Entry point | `python3 -m app.main` | `python3 -m app.main` | uvicorn + background task |
| Kafka topic in | `video.uploaded` | `video.uploaded` | `video.processed` |
| Kafka topic out | `video.processed` | None | None |
| Persistence | MongoDB (logs) | MongoDB (logs) | PostgreSQL (`video_summaries`) |
| AI models | None | None | Whisper + BART (~450MB) |
| Processing time | Seconds (ffmpeg) | < 1 second | Minutes (AI inference) |
| Thread executor | No | No | Yes (both models) |
| Shutdown | asyncio.Event + signals | asyncio.Event + signals | asyncio.CancelledError |
