# Thumbnail Worker — Complete Technical Reference

## 1. What Is This Service?

The **thumbnail-worker** is a background Kafka consumer whose sole job is to:
1. **Listen** to the same `video.uploaded` topic as the encoding-worker
2. **Extract** a single JPEG frame from the video at the 5-second mark using `ffmpeg`
3. **Save** the thumbnail to the shared media volume at `/media/thumbnails/{video-id}.jpg`
4. **Notify** the video-service about the new `thumbnail_path` via HTTP
5. **Log** each step to MongoDB

It runs **in parallel** with the encoding-worker — both consume the same `video.uploaded` event
simultaneously, each in their own consumer group. This means encoding and thumbnail generation
happen at the same time.

**Type:** Kafka Consumer Worker (no HTTP server)  
**Consumes:** `video.uploaded` topic  
**Produces:** Nothing (no Kafka output)  
**DB:** MongoDB (`platform` database, `processing_logs` collection) — logging only  
**Media:** Reads original upload, writes thumbnail to `/media/thumbnails/`

---

## 2. Folder Structure

```
thumbnail-worker/
├── app/
│   ├── main.py              ← Entry point: asyncio.run(main()), signal handlers
│   ├── config.py            ← Pydantic-Settings (reads .env)
│   │
│   └── thumbnail/           ← Thumbnail domain
│       ├── handler/
│       │   └── consumer.py  ← Kafka consumer loop + event dispatch
│       ├── utils/
│       │   ├── ffmpeg.py    ← ffmpeg frame extraction subprocess wrapper
│       │   └── http_client.py ← PATCH /internal/videos/{id}/status caller
│       └── dao/
│           └── mongo_dao.py ← MongoDB logging (same collection as encoding-worker)
│
├── Dockerfile
└── requirements.txt
```

> **Structural note:** The thumbnail-worker has the same directory layout as the encoding-worker
> (`handler/`, `utils/`, `dao/`) — this is the three-layer architecture applied to workers.
> The main difference from the encoding-worker is: no `kafka_producer.py` (no downstream events).

---

## 3. Three-Layer Architecture (adapted for a worker)

```
Kafka Message Arrives
    │
    ▼
handler/consumer.py    ← Entry point. Deserializes message, calls utils.
    │
    ├──► utils/ffmpeg.py      ← Runs ffmpeg as subprocess to extract frame
    ├──► utils/http_client.py ← PATCH video-service with thumbnail_path
    │
    ▼
dao/mongo_dao.py       ← Logs events to MongoDB (no logic, just writes)
```

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker |
| `KAFKA_GROUP_ID` | `thumbnail-worker` | **Different group from encoding-worker** |
| `KAFKA_TOPIC_CONSUME` | `video.uploaded` | Same topic as encoding-worker |
| `VIDEO_SERVICE_URL` | `http://video-service:8002` | Base URL for status update calls |
| `MEDIA_ROOT` | `/media` | Shared media volume mount path |
| `MONGO_URL` | `mongodb://mongo:27017` | MongoDB connection string |
| `MONGO_DB` | `platform` | MongoDB database name |

**Key config difference from encoding-worker:** No `KAFKA_TOPIC_PRODUCE` — this worker
does not publish any Kafka events.

---

## 5. Entry Point (main.py)

Identical pattern to encoding-worker:

```python
async def main() -> None:
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown() -> None:
        stop_event.set()  # signal consumer to stop after current message

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown)

    await run_consumer(stop_event)

if __name__ == "__main__":
    asyncio.run(main())
```

Graceful shutdown on SIGTERM (Docker stop) — finishes the current message before stopping.

---

## 6. Kafka Consumer (handler/consumer.py)

### Consumer Setup

```python
consumer = AIOKafkaConsumer(
    "video.uploaded",
    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
    group_id="thumbnail-worker",       ← Different group = independent offset tracking
    value_deserializer=lambda v: json.loads(v.decode()),
    auto_offset_reset="earliest",
    enable_auto_commit=True,
)
```

**Why the same topic as encoding-worker works:**

Kafka uses **consumer groups** to track offsets independently. Each group maintains its own
"read position" (offset) in each partition. So:

```
Kafka Topic: "video.uploaded"
├── Partition 0: [Event-A, Event-B, Event-C]
│
├── Consumer Group "encoding-worker":
│   └── offset=2 (has processed A, B; C is next)
│
└── Consumer Group "thumbnail-worker":
    └── offset=1 (has processed A; B is next)
```

Both groups get **every message** — they don't share or compete. This is a Kafka "fan-out" pattern.

### Event Handler (`_handle_event`)

```python
async def _handle_event(event: dict) -> None:
    video_id = event["videoId"]
    file_path = event["filePath"]

    await log_processing_event(video_id, "thumbnail_started", {"file_path": file_path})

    try:
        # Extract frame at 5 seconds
        thumbnail_path = await extract_thumbnail(video_id, file_path)

        # Update video-service with the thumbnail path
        await update_video_thumbnail(video_id, thumbnail_path)

        await log_processing_event(video_id, "thumbnail_completed",
                                   {"thumbnail_path": thumbnail_path})

    except Exception as exc:
        # Non-fatal: log but don't mark video as "failed"
        await log_processing_event(video_id, "thumbnail_failed", {"error": str(exc)})
```

**Important design difference from encoding-worker:**  
A thumbnail failure does **NOT** mark the video as `failed`. Thumbnail is supplementary —
the video can still be streamed without a thumbnail. The error is logged to MongoDB but
the video lifecycle continues normally.

---

## 7. ffmpeg Thumbnail Extraction (utils/ffmpeg.py)

### What "Thumbnail" Means Here

A thumbnail is a single JPEG image frame captured from the video — the visual preview shown
before someone plays a video. It's extracted at **5 seconds** into the video (configurable).

### The ffmpeg Command

```bash
ffmpeg -y \
  -ss 00:00:05 \          ← Seek to 5 seconds BEFORE opening file (fast seek)
  -i /media/uploads/uuid.mp4 \
  -vframes 1 \            ← Extract exactly 1 frame
  -q:v 2 \                ← JPEG quality scale (2=high quality, 1-31 range)
  /media/thumbnails/uuid.jpg
```

**`-ss` before `-i`:** Placing `-ss` (seek) BEFORE `-i` (input) uses "fast seek" — ffmpeg
seeks using keyframes and doesn't decode all preceding frames. Much faster for long videos.

**`-vframes 1`:** Only decode and output one video frame.

**`-q:v 2`:** JPEG quality factor. Lower number = higher quality. `2` is near-maximum quality.

**`-y`:** Overwrite output without prompting (needed for non-interactive subprocess).

### Output Location

```
/media/thumbnails/{video-uuid}.jpg
```

Example: `/media/thumbnails/550e8400-e29b-41d4-a716-446655440000.jpg`

### Async Subprocess Execution

```python
proc = await asyncio.create_subprocess_exec(
    *cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
_, stderr = await proc.communicate()

if proc.returncode != 0:
    raise RuntimeError(f"ffmpeg failed (exit {proc.returncode}): {stderr.decode()}")
```

Same asyncio subprocess pattern as encoding-worker — non-blocking, event loop stays responsive.

---

## 8. HTTP Client — Status Update (utils/http_client.py)

After creating the thumbnail, calls video-service to update `thumbnail_path`:

```python
async def update_video_thumbnail(video_id: str, thumbnail_path: str) -> None:
    url = f"{VIDEO_SERVICE_URL}/internal/videos/{video_id}/status"
    payload = {
        "status": "processing",          ← Hint status (will be ignored for terminal videos)
        "thumbnail_path": thumbnail_path, ← This is what actually matters
    }
    async with httpx.AsyncClient() as client:
        resp = await client.patch(url, json=payload, timeout=15.0)
        resp.raise_for_status()
```

**Why `"status": "processing"` in the payload?**

The video-service's `update_status` function has this logic:
```python
if video.status.value in ("ready", "failed"):
    # Terminal state — DON'T change status, but DO update metadata fields
    if any(v is not None for v in (hls_path, thumbnail_path, duration)):
        video = await repo.update_video_fields(db, video, thumbnail_path=thumbnail_path)
    return _to_response(video)  # status unchanged!
```

So even if we send `"status": "processing"`, video-service ignores the status change for
terminal-state videos and only updates `thumbnail_path`. This is safe because:
- If thumbnail finishes BEFORE encoding: video is still `uploading` → `processing` status
  is set (fine, encoding will override it soon)
- If thumbnail finishes AFTER encoding: video is `ready` → status unchanged, only `thumbnail_path` updated ✅
- If thumbnail finishes AFTER failure: video is `failed` → status unchanged, `thumbnail_path` updated ✅

---

## 9. MongoDB Logging (dao/mongo_dao.py)

Same implementation as encoding-worker, writing to the **same collection** (`platform.processing_logs`):

```json
{
  "videoId": "550e8400-...",
  "event": "thumbnail_started",
  "details": { "file_path": "/media/uploads/uuid.mp4" },
  "worker": "thumbnail-worker",
  "timestamp": "2024-01-15T10:30:00+00:00"
}
```

**Events logged:**

| Event | When | Details |
|---|---|---|
| `thumbnail_started` | Consumer receives message | `{"file_path": "..."}` |
| `thumbnail_completed` | ffmpeg succeeds | `{"thumbnail_path": "/media/thumbnails/uuid.jpg"}` |
| `thumbnail_failed` | ffmpeg or HTTP fails | `{"error": "..."}` |

All workers share the `processing_logs` collection — you can query the full processing
history for a video by filtering `db.processing_logs.find({"videoId": "..."})`.

---

## 10. Parallel Processing — Thumbnail vs. Encoding

Both workers consume `video.uploaded` simultaneously with different consumer groups:

```
video.uploaded event (videoId=X, filePath=/media/uploads/X.mp4)
    │
    ├──── encoding-worker (group: encoding-worker) ─────────►
    │         1. status → processing
    │         2. ffmpeg transcode (seconds to minutes)
    │         3. status → ready + hls_path + duration
    │         4. publish video.processed
    │
    └──── thumbnail-worker (group: thumbnail-worker) ──────►
              1. ffmpeg extract frame at 5s (< 1 second)
              2. PATCH thumbnail_path (terminal-state safe)
```

**Timing implications:**

Thumbnail extraction is almost instant (< 1 second). HLS transcoding takes longer.

**Likely scenario:**
```
T+0s:    Both workers receive the event
T+0.5s:  thumbnail-worker: frame extracted, PATCH thumbnail_path
         → video is still "uploading" → status becomes "processing", thumbnail set
T+30s:   encoding-worker: transcoding done, PATCH status=ready, hls_path, duration
         → video is now "ready" with all three fields filled
```

**Edge case scenario (fast transcoding):**
```
T+0s:    Both workers receive the event
T+1s:    encoding-worker: transcode done, status=ready
T+2s:    thumbnail-worker: frame extracted, PATCH thumbnail_path
         → video is "ready" (terminal) → status NOT changed, only thumbnail_path updated ✅
```

The terminal-state fix in video-service ensures this edge case is handled correctly.

---

## 11. Error Handling

| Error | Cause | Action |
|---|---|---|
| Malformed event | Missing `videoId` or `filePath` | Log warning, skip message |
| ffmpeg non-zero exit | Video at 5s is corrupted, codec error | Log to MongoDB, continue (video not marked failed) |
| HTTP timeout (15s) | video-service unreachable | Exception logged to MongoDB, processing continues |
| MongoDB write failure | MongoDB down | Warning log only, processing continues |

**No video status is set to "failed"** — thumbnail failure is always silent from the video
lifecycle perspective. This is a deliberate design choice: thumbnails are cosmetic.

---

## 12. Comparison: thumbnail-worker vs. encoding-worker

| Aspect | encoding-worker | thumbnail-worker |
|---|---|---|
| Kafka group | `encoding-worker` | `thumbnail-worker` |
| Output | HLS files + video.processed event | Single JPEG file |
| Kafka produce | Yes (`video.processed`) | No |
| Processing time | Seconds to minutes | < 1 second |
| Failure impact | Video marked `failed` | Silent (video still works) |
| Status changes | `processing` → `ready`/`failed` | Only `thumbnail_path` field |
| Media writes | `/media/hls/{id}/` (many files) | `/media/thumbnails/{id}.jpg` (one file) |

---

## 13. Docker Configuration

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["python3", "-m", "app.main"]
```

Identical to encoding-worker Dockerfile. Both need `ffmpeg` installed.

docker-compose configuration:
- `media_data:/media` mounted (read original upload, write thumbnail)
- No shared/ mount (doesn't use shared module)
- Depends on Kafka and MongoDB

---

## 14. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `aiokafka` | 0.10.0 | Async Kafka consumer |
| `httpx` | 0.27.0 | Async HTTP client (PATCH video-service) |
| `motor` | 3.3.2 | Async MongoDB driver |
| `pydantic-settings` | 2.2.1 | Config from environment |

**Identical library set to encoding-worker** — minus Kafka producer (aiokafka still needed for consumer).

---

## 15. Full Flow Diagram

```
VIDEO-SERVICE         Kafka            THUMBNAIL-WORKER        VIDEO-SERVICE       MongoDB
     │                  │                    │                      │                │
     │── publish ───────►│                    │                      │                │
     │  "video.uploaded" │                    │                      │                │
     │  {videoId,        │                    │                      │                │
     │   filePath}       │                    │                      │                │
     │                  │─── deliver ────────►│                      │                │
     │                  │                    │── log thumbnail_started ───────────────►│
     │                  │                    │                      │                │
     │                  │                    │─── ffmpeg -ss 00:00:05 ────────────────►
     │                  │                    │    -i /media/uploads/uuid.mp4          │
     │                  │                    │    -vframes 1                          │
     │                  │                    │    -q:v 2                              │
     │                  │                    │    /media/thumbnails/uuid.jpg          │
     │                  │                    │                      │                │
     │                  │                    │── PATCH /internal/videos/{id}/status ──►
     │                  │                    │   {status:"processing",               │
     │                  │                    │    thumbnail_path:"...jpg"}            │
     │                  │                    │                      │                │
     │                  │                    │   [video-service logic]               │
     │                  │                    │   if terminal: only update thumb_path │
     │                  │                    │   else: set status+thumb_path         │
     │                  │                    │                      │                │
     │                  │                    │── log thumbnail_completed ─────────────►│
     │                  │                    │                      │                │
     │                  │                    │   [on error]         │                │
     │                  │                    │── log thumbnail_failed ────────────────►│
     │                  │                    │   (no status change) │                │
```
