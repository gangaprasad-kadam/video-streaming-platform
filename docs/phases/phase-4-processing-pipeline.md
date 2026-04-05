# Phase 4 — Video Processing Pipeline

## Goal
Two Kafka consumer workers that trigger automatically when a video is uploaded. The **Encoding Worker** transcodes the raw video to HLS format. The **Thumbnail Worker** extracts a frame as a JPEG thumbnail. Both use `ffmpeg` under the hood and publish a `video.processed` event on completion.

---

## Services

| Service | Consumes | Produces | Tool |
|---|---|---|---|
| `encoding-worker` | `video.uploaded` | `video.processed` | ffmpeg (HLS) |
| `thumbnail-worker` | `video.uploaded` | (updates DB only) | ffmpeg (frame extract) |

Both are **Kafka consumer services** — they have no HTTP API. They run as long-lived processes consuming from Kafka.

---

## Folder Structure

```
services/encoding-worker/
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
└── app/
    ├── main.py              ← Kafka consumer runner loop (no FastAPI)
    ├── config.py
    ├── database.py
    ├── kafka_consumer.py    ← Consumes: video.uploaded
    ├── kafka_producer.py    ← Publishes: video.processed
    ├── models.py            ← [L3] Video model (status + hls_path updates)
    ├── exceptions.py
    └── encoding/
        ├── __init__.py
        ├── service.py       ← [L2] encode_video() — ffmpeg 360p/720p/1080p HLS
        └── repository.py    ← [L3] update_status(), update_hls_path()

services/thumbnail-worker/
├── Dockerfile
├── requirements.txt
└── app/
    ├── main.py              ← Kafka consumer runner loop (no FastAPI)
    ├── config.py
    ├── database.py
    ├── kafka_consumer.py    ← Consumes: video.uploaded
    ├── models.py            ← [L3] Video model (thumbnail_path update)
    ├── exceptions.py
    └── thumbnail/
        ├── __init__.py
        ├── service.py       ← [L2] extract_thumbnail() — ffmpeg frame at 5s
        └── repository.py    ← [L3] update_thumbnail_path()
```

---

## Encoding Worker

### What It Does

```
1. Consume video.uploaded event
2. Update video status → "processing"
3. Run ffmpeg to transcode video to HLS
4. Output: /media/hls/{videoId}/index.m3u8 + .ts segments
5. Update video record: hls_path, duration, status → "ready"
6. Publish video.processed Kafka event
```

### ffmpeg HLS Command

```bash
ffmpeg -i /media/uploads/{videoId}.mp4 \
  -codec: copy \
  -start_number 0 \
  -hls_time 10 \
  -hls_list_size 0 \
  -hls_segment_filename "/media/hls/{videoId}/segment_%03d.ts" \
  -f hls \
  /media/hls/{videoId}/index.m3u8
```

This creates 10-second segments for adaptive streaming.

### ffprobe Duration Calculation

After encoding, the worker reads the video duration using `ffprobe`:

```bash
ffprobe -v error -show_entries format=duration -of json input.mp4
```

```python
import subprocess, json

def get_duration(input_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", input_path],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])
```

### consumer.py (encoding)

```python
from aiokafka import AIOKafkaConsumer
import asyncio, subprocess, json

async def consume():
    consumer = AIOKafkaConsumer(
        "video.uploaded",
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id="encoding-worker-group",
        value_deserializer=lambda v: json.loads(v.decode()),
        key_deserializer=lambda k: k.decode() if k else None   # ← partition key: videoId
    )
    await consumer.start()
    async for msg in consumer:
        event = msg.value
        await process_video(event)
```

> **Partition key:** producers set `key=videoId.encode()` (see Shared Patterns §6) so all events for the same video land on the same partition, ensuring ordered processing.

async def process_video(event: dict):
    video_id = event["videoId"]
    input_path = event["filePath"]

    # Idempotency check — skip if already processed (handles Kafka redelivery)
    video = await repo.get_video(video_id)
    if video.status in ("ready", "failed"):
        return  # already processed — skip silently

    await update_status(video_id, "processing")
    try:
        encode_to_hls(video_id, input_path)    # blocking ffmpeg call
        duration = get_duration(input_path)
        await update_video(video_id, duration, f"/media/hls/{video_id}/index.m3u8")
        await update_status(video_id, "ready")
        await publish_processed_event(video_id)
    except Exception as e:
        await update_status(video_id, "failed")
        raise e
```

---

## Thumbnail Worker

### What It Does

```
1. Consume video.uploaded event
2. Run ffmpeg to extract frame at t=5s as JPEG
3. Output: /media/thumbnails/{videoId}.jpg
4. Update video record: thumbnail_path
```

### ffmpeg Thumbnail Command

```bash
ffmpeg -i /media/uploads/{videoId}.mp4 \
  -ss 00:00:05 \
  -vframes 1 \
  /media/thumbnails/{videoId}.jpg
```

The two workers consume the **same Kafka topic** (`video.uploaded`) in **different consumer groups** so they run independently and in parallel.

---

## Kafka Consumer Groups

```
Topic: video.uploaded
  ├── Consumer group: encoding-worker-group   (encoding-worker)
  └── Consumer group: thumbnail-worker-group  (thumbnail-worker)

Both groups get every message independently → parallel processing
```

---

## Kafka Event: `video.processed`

Published by encoding-worker after successful HLS encoding:

```json
{
  "videoId":       "uuid",
  "creatorId":     "uuid",
  "hlsPath":       "/media/hls/uuid/index.m3u8",
  "thumbnailPath": "/media/thumbnails/uuid.jpg",
  "duration":      542.3,
  "processedAt":   "2026-03-31T12:05:00Z"
}
```

Consumed by:
- Summarization Service (Phase 6)

---

## MongoDB Logging

Both workers write a `processing_logs` document to MongoDB at the start and end of each job (see DB Design §3.1):

```javascript
// Collection: processing_logs
{
  _id:          ObjectId,
  videoId:      "uuid-string",
  workerType:   "encoding" | "thumbnail",
  status:       "started" | "completed" | "failed",
  inputPath:    "/media/uploads/uuid.mp4",
  outputPath:   "/media/hls/uuid/index.m3u8",   // null for thumbnail → "/media/thumbnails/uuid.jpg"
  durationMs:   45230,                            // wall-clock processing time
  errorMessage: null,                             // populated on failure
  ffmpegCommand: "ffmpeg -i ...",                 // full command for debugging
  startedAt:    ISODate("2026-03-31T12:00:00Z"),
  completedAt:  ISODate("2026-03-31T12:00:45Z")
}
```

`logger.py` (per-worker instance of the shared `ErrorLogger`) inserts these documents via the Motor async driver.

---

## Error Handling & Retry

```
If ffmpeg fails:
  - Video status set to "failed"
  - Error logged to MongoDB (audit log)
  - No retry (manual re-upload required)
  - Future: dead-letter queue on Kafka

If worker crashes mid-processing:
  - Kafka offset NOT committed until processing complete
  - On restart, message is redelivered (at-least-once semantics)
  - Idempotency: check video status before processing
    (skip if already "ready" or "processing")
```

---

## Processing Flow Diagram

```
  video.uploaded Kafka topic
         │
  ┌──────┴────────────────────────┐
  │                               │
  ▼                               ▼
Encoding Worker              Thumbnail Worker
(group: encoding-worker-group) (group: thumbnail-worker-group)
  │                               │
  │ ffmpeg → HLS                  │ ffmpeg → JPEG
  │                               │
  ▼                               ▼
/media/hls/{id}/            /media/thumbnails/{id}.jpg
index.m3u8 + .ts
  │
  │ UPDATE videos SET
  │   hls_path, duration, status='ready'
  ▼
video.processed Kafka topic
  │
  ▼
Summarization Service (Phase 6)
```

---

## Dockerfile (encoding-worker)

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python", "-m", "app.main"]
```

## requirements.txt

```
aiokafka==0.10.0
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.28
pydantic-settings==2.2.1
motor==3.3.2        ← MongoDB async driver (for error logging)
```

---

## Async vs Sync

| Operation | Type | Reason |
|---|---|---|
| Kafka message consume | Async loop | Non-blocking consumer via aiokafka |
| ffmpeg execution | Sync (subprocess) | ffmpeg is a blocking CLI tool; runs in executor thread |
| PostgreSQL status update | Async (await) | Non-blocking |
| Kafka event publish | Async (await) | Non-blocking |
| File I/O (read/write) | Sync (aiofiles) | Volume I/O, wrapped in thread executor |

---

## References: Shared Patterns

- **§1 Layered Architecture** — `repository.py` for all DB queries
- **§6 Kafka Partition Key Strategy** — `key=videoId.encode()` on every producer send
- **§7 MongoDB Error Logger** — `logger.py` using `ErrorLogger` from shared module
- **§8 Standard Service Folder Structure** — `repository.py`, `exceptions.py`, `logger.py` in both workers
- **§10 Idempotency in Kafka Consumers** — check `video.status` before processing
