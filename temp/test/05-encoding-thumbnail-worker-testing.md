# Encoding Worker — Testing Guide

## Overview

The **encoding-worker** is NOT an HTTP service — it has no API endpoints.
You test it by publishing a Kafka message and watching the side effects.

**What to verify:**
- HLS files appear in `/media/hls/{videoId}/`
- `videos` table gets `status=ready`, `hls_path`, `duration` set
- `video.processed` Kafka event is published

---

## Step 1: Start Required Services

```bash
docker compose up -d postgres redis kafka zookeeper encoding-worker
```

---

## Step 2: Insert a Test Video Record

```bash
docker compose exec postgres psql -U postgres -d videoplatform

INSERT INTO videos (id, title, creator_id, file_path, status)
VALUES (
  'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
  'Encoding Test Video',
  'ffffffff-ffff-ffff-ffff-ffffffffffff',
  '/media/uploads/test.mp4',
  'uploading'
);

\q
```

---

## Step 3: Place a Real MP4 File

```bash
# Copy any MP4 into the container
docker compose cp /path/to/your/video.mp4 encoding-worker:/media/uploads/test.mp4

# OR create a minimal test MP4 with ffmpeg if installed locally:
ffmpeg -f lavfi -i testsrc=duration=10:size=320x240:rate=25 \
       -f lavfi -i sine=frequency=440:duration=10 \
       -c:v libx264 -c:a aac /tmp/test.mp4

docker compose cp /tmp/test.mp4 encoding-worker:/media/uploads/test.mp4
```

---

## Step 4: Publish a `video.uploaded` Kafka Event

```bash
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic video.uploaded
```

Type this JSON (one line), then press Enter, then Ctrl+C:
```json
{"videoId": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee", "filePath": "/media/uploads/test.mp4", "creatorId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "uploadedAt": "2024-01-15T10:00:00"}
```

---

## Step 5: Watch Encoding Logs

```bash
docker compose logs -f encoding-worker
```

Expected output:
```
[INFO] Starting video encoding worker
[INFO] Consumer connected — listening on 'video.uploaded'
[INFO] [eeeeeeee-...] Received video.uploaded event
[INFO] [eeeeeeee-...] Starting HLS encoding
[INFO] [eeeeeeee-...] ffprobe extracted duration: 10.0s
[INFO] [eeeeeeee-...] ffmpeg complete — /media/hls/eeeeeeee-.../index.m3u8
[INFO] [eeeeeeee-...] Published video.processed event
```

---

## Step 6: Verify Side Effects

### Check HLS files created:
```bash
docker compose exec encoding-worker ls /media/hls/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee/
# Expected: index.m3u8  index000.ts  index001.ts  ...
```

### Check DB updated:
```bash
docker compose exec postgres psql -U postgres -d videoplatform

SELECT id, status, hls_path, duration FROM videos
WHERE id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee';

-- Expected:
-- status   = 'ready'
-- hls_path = '/media/hls/eeeeeeee-.../index.m3u8'
-- duration = 10.0
\q
```

### Check `video.processed` was published:
```bash
docker compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic video.processed \
  --from-beginning \
  --max-messages 1
```

Expected message:
```json
{
  "videoId": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
  "hlsPath": "/media/hls/eeeeeeee-.../index.m3u8",
  "duration": 10.0,
  "processedAt": "2024-01-15T10:00:30"
}
```

---

## Thumbnail Worker — Testing Guide

The **thumbnail-worker** also has no HTTP API. It reads the same `video.uploaded` topic
(different consumer group) and extracts a JPEG frame.

```bash
docker compose up -d thumbnail-worker
```

Repeat Steps 2–4 above with the same Kafka message (thumbnail-worker gets every message too).

### Verify:
```bash
# Thumbnail file exists:
docker compose exec thumbnail-worker ls /media/thumbnails/

# DB has thumbnail_path:
docker compose exec postgres psql -U postgres -d videoplatform
SELECT id, thumbnail_path FROM videos
WHERE id = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee';
\q
```

Expected: `/media/thumbnails/eeeeeeee-....jpg`

---

## Test Summary

| Check | How to verify |
|---|---|
| Encoding worker received message | `docker compose logs encoding-worker` |
| HLS files created | `ls /media/hls/{id}/` inside container |
| DB status = ready | `SELECT status FROM videos WHERE id=...` |
| video.processed published | `kafka-console-consumer.sh --topic video.processed` |
| Thumbnail created | `ls /media/thumbnails/` inside container |
| DB thumbnail_path set | `SELECT thumbnail_path FROM videos WHERE id=...` |
