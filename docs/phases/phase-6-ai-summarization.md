# Phase 6 — AI Summarization Service

## Goal
A Kafka consumer service that listens for `video.processed` events, extracts audio from the HLS video, transcribes it using **OpenAI Whisper**, summarizes it using **HuggingFace BART**, generates key timestamps, and stores the results in PostgreSQL + Redis cache.

---

## Service Details

| Property | Value |
|---|---|
| Service name | `summarization-service` |
| Port | `8004` |
| Framework | FastAPI (HTTP) + Kafka consumer (background) |
| Database | PostgreSQL (`video_summaries` table) |
| Cache | Redis (`summary:{videoId}`, TTL: 1h) |
| AI Models | Whisper (`base`) + `facebook/bart-large-cnn` |

---

## Folder Structure

```
services/summarization-service/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py             ← FastAPI app + background Kafka consumer
    ├── config.py
    ├── database.py
    ├── redis_client.py
    ├── exceptions.py       ← service-specific exceptions
    ├── logger.py           ← MongoDB ErrorLogger instance
    ├── consumer.py         ← Kafka consumer loop
    ├── pipeline/
    │   ├── audio.py        ← extract audio with ffmpeg
    │   ├── transcribe.py   ← Whisper transcription
    │   ├── summarize.py    ← BART summarization
    │   └── timestamps.py   ← key moment extraction
    └── api/
        ├── router.py       ← GET /summary/:videoId
        ├── repository.py   ← PostgreSQL queries for video_summaries
        └── cache.py        ← Redis get/set for summary:{videoId}
```

---

## AI Pipeline

```
video.processed event received
         │
         ▼
┌─────────────────────────┐
│  1. Extract Audio       │  ffmpeg: .m3u8 → .wav (16kHz mono)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  2. Transcribe (Whisper)│  whisper.transcribe(audio_path)
│     → transcript text   │  → returns { text, segments: [{start, end, text}] }
│     → word timestamps   │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  3. Summarize (BART)    │  pipeline("summarization")(transcript_text)
│     → summary text      │  → returns { summary_text }
│     max_length=150 tokens│
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  4. Extract Key Moments │  Find segments with highest density of
│     → timestamps list   │  information (longest segments, repeated terms)
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  5. Store Results       │  PostgreSQL + Redis cache
└─────────────────────────┘
```

---

## Code: Transcription

```python
# pipeline/transcribe.py
import whisper

model = whisper.load_model("base")   # loaded once at startup

def transcribe(audio_path: str) -> dict:
    result = model.transcribe(audio_path)
    return {
        "text": result["text"],
        "segments": [
            {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
            for seg in result["segments"]
        ]
    }
```

---

## Code: Summarization

```python
# pipeline/summarize.py
from transformers import pipeline

summarizer = pipeline(
    "summarization",
    model="facebook/bart-large-cnn",
    device=-1   # CPU; set to 0 for GPU
)

def summarize(text: str) -> str:
    # BART has a 1024-token limit per input — split long transcripts into chunks.
    # chunk_text() splits on sentence boundaries to avoid cutting mid-sentence.
    chunks = chunk_text(text, max_tokens=1024)
    summaries = [
        summarizer(chunk, max_length=150, min_length=30, do_sample=False)[0]["summary_text"]
        for chunk in chunks
    ]
    return " ".join(summaries)
```

---

## Code: Key Timestamp Extraction

```python
# pipeline/timestamps.py

def extract_key_moments(segments: list[dict], top_n: int = 5) -> list[dict]:
    # Score segments by word count (proxy for information density)
    scored = [
        {"start": seg["start"], "end": seg["end"],
         "text": seg["text"], "score": len(seg["text"].split())}
        for seg in segments
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [
        {"timestamp": s["start"], "label": s["text"][:60]}
        for s in scored[:top_n]
    ]
```

---

## PostgreSQL Schema

```sql
CREATE TABLE video_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id        UUID UNIQUE NOT NULL REFERENCES videos(id),
    transcript      TEXT,
    summary         TEXT NOT NULL,
    key_moments     JSONB,   -- [{ "timestamp": 42.0, "label": "..." }]
    whisper_model   VARCHAR(20) DEFAULT 'base',
    processing_ms   INTEGER,           -- how long it took
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_summaries_video_id ON video_summaries(video_id);
```

---

## Redis Cache

```
Key   : summary:{videoId}
Value : JSON { summary, key_moments, transcript }
TTL   : 3600 seconds (1 hour)
```

---

## Cache Layer (`api/cache.py`)

```python
# api/cache.py
import json

SUMMARY_TTL = 3600  # 1 hour

async def get_summary(video_id: str) -> dict | None:
    """Check Redis first; returns None on miss."""
    cached = await redis.get(f"summary:{video_id}")
    return json.loads(cached) if cached else None

async def set_summary(video_id: str, data: dict) -> None:
    """Cache summary with 1-hour TTL."""
    await redis.setex(f"summary:{video_id}", SUMMARY_TTL, json.dumps(data))
```

The service layer calls `get_summary()` first; on a miss it queries PostgreSQL via `repository.py` then calls `set_summary()` to populate the cache.

---

## API Endpoint

```
GET /summary/:videoId
  Response 200:
  {
    "videoId": "uuid",
    "summary": "This video explains...",
    "keyMoments": [
      { "timestamp": 42.0, "label": "Introduction to recursion" },
      { "timestamp": 180.5, "label": "Live coding demo" }
    ],
    "transcriptAvailable": true
  }

  Cache: Check Redis first (TTL 1h), fallback to PostgreSQL
  Error 404: {"error": "SUMMARY_NOT_FOUND", "message": "Summary not yet generated"}
  Error 503: {"error": "MODEL_UNAVAILABLE",  "message": "Whisper/BART model not loaded"}
```

---

## Kafka Consumer

```python
# consumer.py
async def consume():
    consumer = AIOKafkaConsumer(
        "video.processed",
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="summarization-service-group",
        value_deserializer=lambda v: json.loads(v.decode())
    )
    await consumer.start()
    async for msg in consumer:
        event = msg.value
        # Run CPU-heavy pipeline in thread executor
        await asyncio.get_event_loop().run_in_executor(
            None, run_pipeline, event
        )
```

> ⚠️ Whisper and BART are CPU-heavy. They run in a thread executor to avoid blocking the async event loop.

---

## Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Pre-download models at build time (avoids cold start)
RUN python -c "import whisper; whisper.load_model('base')"
RUN python -c "from transformers import pipeline; pipeline('summarization', model='facebook/bart-large-cnn')"
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| Kafka consume | Async loop | Non-blocking via aiokafka |
| Whisper transcription | Sync in executor | CPU-bound; must not block event loop |
| BART summarization | Sync in executor | CPU-bound; must not block event loop |
| Redis cache read/write | Async (await) | Non-blocking |
| PostgreSQL insert | Async (await) | Non-blocking |
| GET /summary/:id | Sync read (Redis first) | Fast Redis lookup, fallback to DB |

---

## References: Shared Patterns

- **§1 Layered Architecture** — `api/repository.py` for DB queries, `api/cache.py` for Redis operations
- **§5 Standard Response Format** — `SUMMARY_NOT_FOUND` (404), `MODEL_UNAVAILABLE` (503) follow standard error code conventions
- **§7 MongoDB Error Logger** — `logger.py` using `ErrorLogger` from shared module
- **§8 Standard Service Folder Structure** — `repository.py`, `cache.py`, `exceptions.py`, `logger.py` added
- **§10 Idempotency in Kafka Consumers** — check if summary already exists before running the AI pipeline
