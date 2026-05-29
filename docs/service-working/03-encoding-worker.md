# Encoding Worker — Complete Technical Reference

## 1. What Is This Service?

The **encoding-worker** is a background processing service (not an HTTP server). Its job is:
1. **Listen** to the `video.uploaded` Kafka topic
2. **Transcode** the uploaded raw video file to HLS format using `ffmpeg`
3. **Notify** the video-service about the new status via HTTP
4. **Publish** a `video.processed` Kafka event (for the summarization-service to consume)
5. **Log** every step to MongoDB for observability

It runs as a pure asyncio process — there is no FastAPI, no HTTP server, no web framework.
It is a long-running Kafka consumer loop that starts once and processes events indefinitely.

**Type:** Kafka Consumer Worker (no HTTP server)  
**Consumes:** `video.uploaded` topic  
**Produces:** `video.processed` topic  
**DB:** MongoDB (`platform` database, `processing_logs` collection) — for event logging only  
**Media:** Reads/writes the shared Docker volume at `/media`

---

## 2. Folder Structure

```
encoding-worker/
├── app/
│   ├── main.py              ← Entry point: asyncio.run(main()), signal handlers
│   ├── config.py            ← Pydantic-Settings (reads .env)
│   │
│   └── encoding/            ← Encoding domain
│       ├── handler/
│       │   └── consumer.py  ← Kafka consumer loop + event dispatch
│       ├── utils/
│       │   ├── ffmpeg.py    ← ffmpeg/ffprobe subprocess wrappers
│       │   ├── http_client.py ← PATCH /internal/videos/{id}/status caller
│       │   └── kafka_producer.py ← Publishes video.processed events
│       └── dao/
│           └── mongo_dao.py ← MongoDB logging (processing_logs collection)
│
├── Dockerfile
└── requirements.txt
```

---

## 3. Three-Layer Architecture (adapted for a worker)

```
Kafka Message Arrives
    │
    ▼
handler/consumer.py     ← Receives Kafka message, deserializes JSON, dispatches
    │                      Does NOT do business logic itself
    ▼
(utils layer)           ← All processing logic split across utilities:
    ├── utils/ffmpeg.py           ← Transcode video (subprocess calls)
    ├── utils/http_client.py      ← Tell video-service about status changes
    └── utils/kafka_producer.py   ← Notify downstream services
    │
    ▼
dao/mongo_dao.py        ← Log processing events to MongoDB (no logic, just writes)
```

In a worker (no HTTP), the "handler" layer is the Kafka consumer entry point, and the "dao" layer
handles persistence (MongoDB logs), just like HTTP services use PostgreSQL in their dao layers.

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker |
| `KAFKA_GROUP_ID` | `encoding-worker` | Consumer group (enables offset tracking) |
| `KAFKA_TOPIC_CONSUME` | `video.uploaded` | Topic to listen on |
| `KAFKA_TOPIC_PRODUCE` | `video.processed` | Topic to publish to after encoding |
| `VIDEO_SERVICE_URL` | `http://video-service:8002` | Base URL for status update calls |
| `MEDIA_ROOT` | `/media` | Shared media volume mount path |
| `MONGO_URL` | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGO_DB` | `platform` | MongoDB database name |

---

## 5. Entry Point (main.py)

The main function is the process entry point. It:
1. Sets up structured logging
2. Gets the asyncio event loop
3. Creates an `asyncio.Event` to signal shutdown
4. Registers OS signal handlers for `SIGINT` (Ctrl+C) and `SIGTERM` (Docker stop)
5. Calls `run_consumer(stop_event)` — blocks until shutdown

```python
async def main() -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        stop_event.set()  # tells consumer loop to stop after current message

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    await run_consumer(stop_event)

if __name__ == "__main__":
    asyncio.run(main())
```

**Graceful shutdown:** When Docker sends `SIGTERM`, `stop_event` is set. The consumer finishes
processing the current message, then exits cleanly. No messages are dropped or left mid-processing.

---

## 6. Kafka Consumer (handler/consumer.py)

### Consumer Setup

```python
consumer = AIOKafkaConsumer(
    "video.uploaded",
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    group_id="encoding-worker",
    value_deserializer=lambda v: json.loads(v.decode()),
    auto_offset_reset="earliest",   # start from beginning if no prior offset
    enable_auto_commit=True,        # auto-commit offsets after processing
)
```

**Key settings explained:**
- `group_id="encoding-worker"` — Kafka tracks this group's offset. If the worker restarts,
  it resumes from where it left off (doesn't re-process already-handled events)
- `auto_offset_reset="earliest"` — If starting fresh (no prior offset in Kafka), consume
  all events from the beginning of the topic
- `enable_auto_commit=True` — Kafka automatically marks messages as processed after they're
  yielded by the consumer loop (simple but sufficient for this use case)

### Consumer Loop

```python
async for msg in consumer:
    if stop_event.is_set():
        break
    await _handle_event(msg.value)
```

Each message is processed **synchronously in sequence** — the next message is not read until the
current one finishes. This ensures ordering and prevents overloading ffmpeg.

### Event Handler (`_handle_event`)

```python
async def _handle_event(event: dict) -> None:
    video_id = event["videoId"]
    file_path = event["filePath"]

    # 1. Mark as "processing"
    await update_video_status(video_id, status="processing")
    await log_processing_event(video_id, "encoding_started", {"file_path": file_path})

    try:
        # 2. Transcode (heavy operation, takes seconds to minutes)
        result = await transcode_to_hls(video_id, file_path)

        # 3. Mark as "ready" with HLS path + duration
        await update_video_status(video_id, status="ready",
                                  hls_path=result["hls_path"],
                                  duration=result["duration"])
        await log_processing_event(video_id, "encoding_completed", result)

        # 4. Publish video.processed event (for summarization-service)
        await publish_processed(video_id, result["hls_path"], result["duration"])

    except Exception as exc:
        # 5. On any failure: mark as "failed"
        await update_video_status(video_id, status="failed")
        await log_processing_event(video_id, "encoding_failed", {"error": str(exc)})
```

---

## 7. ffmpeg Transcoding (utils/ffmpeg.py)

### What Is HLS?

**HLS (HTTP Live Streaming)** is Apple's adaptive streaming protocol. Instead of serving a single
large video file, the video is split into small 6-second `.ts` (transport stream) segments.
A `.m3u8` manifest file lists all segments in order. The video player requests the manifest,
then fetches segments sequentially.

**Benefits:**
- Seekable without downloading the whole file
- Works with standard HTTP servers (no special streaming server needed)
- Adaptive bitrate possible (multiple quality levels)

### ffprobe — Get Duration

Before transcoding, the worker extracts the video's duration:

```bash
ffprobe -v quiet -print_format json -show_format {input_path}
```

Returns JSON like:
```json
{ "format": { "duration": "125.5", "size": "...", ... } }
```

This runs as an async subprocess via `asyncio.create_subprocess_exec`.

### ffmpeg — Transcode to HLS

```bash
ffmpeg -y \
  -i /media/uploads/video-uuid.mp4 \
  -codec: copy \           ← Copy streams (no re-encoding, very fast)
  -start_number 0 \
  -hls_time 6 \            ← 6-second segments
  -hls_list_size 0 \       ← Include ALL segments in manifest (not rolling window)
  -f hls \
  /media/hls/video-uuid/index.m3u8
```

**Output structure:**
```
/media/hls/{video-uuid}/
├── index.m3u8      ← master manifest listing all segments
├── index000.ts     ← segment 0 (seconds 0–6)
├── index001.ts     ← segment 1 (seconds 6–12)
├── index002.ts     ← segment 2 (seconds 12–18)
└── ...
```

**`-codec: copy`** means the video and audio streams are **not re-encoded** — just remuxed
(repackaged) into HLS container. This is extremely fast (seconds, not minutes) but requires
the source codec (H.264) to be compatible. A production implementation would add quality
transcoding (`-vcodec libx264 -acodec aac`).

### Subprocess Execution

Both ffmpeg and ffprobe run via `asyncio.create_subprocess_exec`:

```python
proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, stderr = await proc.communicate()

if proc.returncode != 0:
    raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {stderr.decode()}")
```

`await proc.communicate()` waits for the subprocess to finish **without blocking the event loop**
(asyncio handles this with OS-level I/O multiplexing).

---

## 8. HTTP Client — Status Updates (utils/http_client.py)

After each processing step, the worker calls the video-service's internal API to update status:

```python
async def update_video_status(video_id, status, hls_path=None, thumbnail_path=None, duration=None):
    url = f"{VIDEO_SERVICE_URL}/internal/videos/{video_id}/status"
    payload = {"status": status}
    if hls_path:   payload["hls_path"] = hls_path
    if duration:   payload["duration"] = duration

    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json=payload, timeout=15.0)
        resp.raise_for_status()
```

**Uses `httpx.AsyncClient`** — async HTTP client, doesn't block the event loop.
**`timeout=15.0`** — if video-service doesn't respond in 15 seconds, raises an exception
(caught by the try/except in `_handle_event`, marks video as "failed").

**Calls made during encoding:**

| Step | API Call | Payload |
|---|---|---|
| Start encoding | `PATCH /internal/videos/{id}/status` | `{"status": "processing"}` |
| Encoding success | `PATCH /internal/videos/{id}/status` | `{"status": "ready", "hls_path": "...", "duration": 125.5}` |
| Encoding failure | `PATCH /internal/videos/{id}/status` | `{"status": "failed"}` |

---

## 9. Kafka Producer — Downstream Notification (utils/kafka_producer.py)

After successful encoding, publishes to `video.processed`:

```python
await _producer.send_and_wait(
    "video.processed",
    key=video_id.encode(),
    value={
        "videoId": "550e8400-...",
        "hlsPath": "/media/hls/uuid/index.m3u8",
        "duration": 125.5,
        "processedAt": "2024-01-15T10:35:00+00:00"
    }
)
```

**Important:** The `video.processed` event does **NOT include `filePath`** (the original upload
path). Downstream consumers (summarization-service) use `hlsPath` to extract audio via ffmpeg.

**Who consumes `video.processed`:**
- `summarization-service` — extracts audio from HLS → Whisper transcription → BART summary

---

## 10. MongoDB Logging (dao/mongo_dao.py)

Every processing step is logged to MongoDB for observability and debugging:

```python
async def log_processing_event(video_id: str, event: str, details: dict) -> None:
    await collection.insert_one({
        "videoId": video_id,
        "event": event,
        "details": details,
        "worker": "encoding-worker",
        "timestamp": "2024-01-15T10:30:00+00:00"
    })
```

**Events logged:**

| Event Name | When | Details |
|---|---|---|
| `encoding_started` | Consumer receives message | `{"file_path": "/media/uploads/uuid.mp4"}` |
| `encoding_completed` | ffmpeg finishes successfully | `{"hls_path": "...", "duration": 125.5}` |
| `encoding_failed` | ffmpeg or HTTP call fails | `{"error": "ffmpeg failed: ..."}` |

**MongoDB collection:** `platform.processing_logs`  
**Driver:** `Motor` (async MongoDB driver for Python, built on top of PyMongo)

**Fault tolerance:** MongoDB logging failures are **non-fatal** — they're wrapped in try/except
with a warning log. A MongoDB outage will not stop video processing.

---

## 11. Kafka Topics Overview

| Topic | Direction | Schema |
|---|---|---|
| `video.uploaded` | **Consumed** | `{videoId, creatorId, filePath, mimeType, title, uploadedAt}` |
| `video.processed` | **Produced** | `{videoId, hlsPath, duration, processedAt}` |

---

## 12. Full Processing Flow

```
video-service               Kafka              encoding-worker         video-service        Kafka
     │                        │                      │                      │               │
     │── publish ─────────────►│                      │                      │               │
     │  "video.uploaded"       │                      │                      │               │
     │  {videoId, filePath}    │                      │                      │               │
     │                        │── deliver ───────────►│                      │               │
     │                        │                      │─ PATCH status=processing ─────────────►│
     │                        │                      │                      │               │
     │                        │                      │─── ffprobe {filePath} ────────────────►
     │                        │                      │   (get duration)      │               │
     │                        │                      │                      │               │
     │                        │                      │─── ffmpeg transcode ─────────────────►
     │                        │                      │   (6s HLS segments)   │               │
     │                        │                      │   output: /media/hls/{id}/index.m3u8  │
     │                        │                      │                      │               │
     │                        │                      │─ PATCH status=ready, hls_path, duration►
     │                        │                      │                      │               │
     │                        │                      │─ MongoDB log: encoding_completed      │
     │                        │                      │                      │               │
     │                        │                      │── publish ───────────────────────────►│
     │                        │                      │  "video.processed"   │               │
     │                        │                      │  {videoId, hlsPath,  │               │
     │                        │                      │   duration}          │               │
     │                        │                      │                      │               │
     │                        │                      │  [if any error]       │               │
     │                        │                      │─ PATCH status=failed ─────────────────►│
     │                        │                      │─ MongoDB log: encoding_failed         │
```

---

## 13. Error Handling

| Error Type | Cause | Action |
|---|---|---|
| Malformed Kafka event | Missing `videoId` or `filePath` | Log warning, skip message |
| ffmpeg non-zero exit | Invalid file, codec error | Mark video "failed", log to MongoDB |
| ffprobe failure | Can't read file metadata | `duration = None`, continue transcoding |
| HTTP timeout (15s) | video-service unreachable | Exception propagates, video marked "failed" |
| MongoDB write failure | MongoDB down | Warning log only, processing continues |

---

## 14. Docker Configuration

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python3", "-m", "app.main"]
```

**Key points:**
- Installs `ffmpeg` package from apt — includes both `ffmpeg` and `ffprobe` binaries
- No uvicorn, no web server — just `python3 -m app.main`
- docker-compose mounts `media_data:/media` (read-write — worker writes HLS output)
- docker-compose mounts `./backend/shared:/app/shared:ro`

---

## 15. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `aiokafka` | 0.10.0 | Async Kafka consumer + producer |
| `httpx` | 0.27.0 | Async HTTP client (PATCH video-service) |
| `motor` | 3.3.2 | Async MongoDB driver |
| `pydantic-settings` | 2.2.1 | Config from environment variables |

**No FastAPI, no SQLAlchemy, no uvicorn** — this is a pure async Python process.

---

## 16. Consumer Group Semantics

**Why consumer groups matter:**

If you run two encoding-worker instances:
```
Kafka partition 0: [video-A, video-C]
Kafka partition 1: [video-B, video-D]

encoding-worker-1 gets partition 0 → processes video-A, video-C
encoding-worker-2 gets partition 1 → processes video-B, video-D
```

Each video is processed by **exactly one** worker. This enables horizontal scaling:
add more encoding-worker containers, Kafka distributes the work automatically.

**Offset tracking:** Kafka stores the "last processed offset" per group. If the worker crashes
mid-message and restarts, it will re-process the last message (at-least-once delivery).
The `_handle_event` function is idempotent for failed videos (re-calling `status=failed` is safe).

---

## 17. Why MongoDB for Logs (not PostgreSQL)?

| Concern | MongoDB | PostgreSQL |
|---|---|---|
| Schema | Flexible — each log entry can have different `details` shape | Requires schema migration for new fields |
| Write pattern | Append-only, no updates | Same |
| Query pattern | Range queries by videoId/timestamp | Same |
| Operational overhead | Separate service, separate from app DB | Would require mixing concerns in app DB |

MongoDB's document model is ideal for **structured-but-variable event logs** where the `details`
field can be `{"file_path": "..."}` for one event and `{"error": "..."}` for another.

This is the only MongoDB usage in the platform. All other persistence uses PostgreSQL.
