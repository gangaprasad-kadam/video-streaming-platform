# Summarization Service — Complete API Testing Guide (Postman)

## Overview

The **summarization-service** has only ONE public API endpoint: `GET /summary/{videoId}`.
Everything else is automatic — it listens to Kafka and processes videos in the background.

This guide shows how to:
1. Manually insert a summary record (to test the GET endpoint without real AI models)
2. Verify the full AI pipeline (if you have GPU/sufficient RAM)

**Base URL:** `http://localhost:8004`

---

## Step 1: Start the Services

```bash
docker compose up -d postgres redis kafka zookeeper summarization-service

# Verify:
curl http://localhost:8004/health
```

> ⚠️ The summarization-service Docker image is large (~2GB with Whisper + BART).
> First build takes 5-10 minutes. Subsequent starts are instant.

---

## API Test 1: Health Check

```
GET http://localhost:8004/health
```

**Expected (200):**
```json
{"status": "ok", "service": "summarization-service"}
```

---

## API Test 2: Get Summary — Not Found

```
GET http://localhost:8004/summary/00000000-0000-0000-0000-000000000000
```

**Expected (404):**
```json
{
  "error": "SUMMARY_NOT_FOUND",
  "message": "Summary for video '00000000-...' not found — processing may still be in progress",
  "detail": null
}
```

The message says "processing may still be in progress" — a 404 doesn't mean the video
doesn't exist, just that no summary has been generated yet.

---

## API Test 3: Get Summary — Cache Hit

### Setup: Seed Redis cache manually

```bash
docker compose exec redis redis-cli

SELECT 3
SET "summary:test-video-uuid" '{"video_id":"test-video-uuid","transcript":"This is a test transcript about software engineering.","summary":"A video about software engineering practices.","key_moments":[{"timestamp":5.0,"label":"Introduction to the topic"},{"timestamp":42.5,"label":"Main demonstration"}],"created_at":"2024-01-15T10:40:00"}'

exit
```

### Request
```
GET http://localhost:8004/summary/test-video-uuid
```

**Expected (200):**
```json
{
  "data": {
    "video_id": "test-video-uuid",
    "transcript": "This is a test transcript about software engineering.",
    "summary": "A video about software engineering practices.",
    "key_moments": [
      {"timestamp": 5.0, "label": "Introduction to the topic"},
      {"timestamp": 42.5, "label": "Main demonstration"}
    ],
    "created_at": "2024-01-15T10:40:00"
  }
}
```

This came from **Redis** — no DB query. Response is instant.

---

## API Test 4: Get Summary — From Database

### Setup: Insert a summary record directly in PostgreSQL

```bash
docker compose exec postgres psql -U postgres -d videoplatform

INSERT INTO video_summaries (
  video_id,
  transcript,
  summary,
  key_moments
) VALUES (
  'dddddddd-dddd-dddd-dddd-dddddddddddd',
  'Welcome to this tutorial. Today we will learn about Python async programming. First, let us understand coroutines. Then we will look at asyncio event loop. Finally, we will build a real application.',
  'This tutorial covers Python async programming, including coroutines, the asyncio event loop, and building real async applications.',
  '[{"timestamp": 0.0, "label": "Welcome to this tutorial"}, {"timestamp": 15.5, "label": "Understanding coroutines"}, {"timestamp": 45.0, "label": "Building a real application"}]'
);

\q
```

### Request
```
GET http://localhost:8004/summary/dddddddd-dddd-dddd-dddd-dddddddddddd
```

**Expected (200):**
```json
{
  "data": {
    "video_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "transcript": "Welcome to this tutorial. Today we will learn about Python async programming...",
    "summary": "This tutorial covers Python async programming, including coroutines...",
    "key_moments": [
      {"timestamp": 0.0, "label": "Welcome to this tutorial"},
      {"timestamp": 15.5, "label": "Understanding coroutines"},
      {"timestamp": 45.0, "label": "Building a real application"}
    ],
    "created_at": "2024-01-15T10:40:00"
  }
}
```

First request: from **PostgreSQL** (cache miss).

### Verify Cache Was Primed
```bash
docker compose exec redis redis-cli
SELECT 3
GET "summary:dddddddd-dddd-dddd-dddd-dddddddddddd"
exit
```

Should return the JSON string. Second GET request will serve from cache.

---

## API Test 5: Test the Full AI Pipeline (Optional — Requires Real Video)

This test actually runs Whisper + BART. Requires:
- A video that has been encoded to HLS (encoding-worker ran)
- The summarization-service has enough RAM (~1.5GB for base Whisper + DistilBART)

### How It Works (Automatic)

1. Upload a video → `POST http://localhost:8002/videos/upload`
2. Encoding-worker processes it → publishes `video.processed` to Kafka
3. Summarization-service consumer receives `video.processed`
4. Runs AI pipeline (takes 1-5 minutes depending on video length)
5. Stores result in `video_summaries` table
6. `GET /summary/{video_id}` returns the result

### Monitor Progress via Logs

```bash
# Watch the summarization-service logs
docker compose logs -f summarization-service
```

You'll see output like:
```
[2024-01-15 10:40:00] [INFO] Consumer started — listening on 'video.processed'
[2024-01-15 10:40:30] [INFO] [{video_id}] Processing for AI summarization
[2024-01-15 10:40:31] [INFO] [{video_id}] Extracting audio from /media/hls/{id}/index.m3u8
[2024-01-15 10:40:32] [INFO] Loading Whisper model: base
[2024-01-15 10:41:30] [INFO] [{video_id}] Running BART summarization
[2024-01-15 10:41:45] [INFO] [{video_id}] Summarization complete
```

### Check Result
```
GET http://localhost:8004/summary/{video_id}
```

---

## Understanding the Response Fields

| Field | Description |
|---|---|
| `video_id` | UUID of the video this summary belongs to |
| `transcript` | Full speech-to-text from Whisper (can be very long) |
| `summary` | Short summary paragraph from BART (30-150 words) |
| `key_moments` | Array of up to 10 timestamps with labels from Whisper segments |
| `created_at` | When the summary was generated |

**`key_moments` explained:**  
Whisper segments the audio into chunks with start/end times and confidence scores.
The service filters segments where:
- `no_speech_prob < 0.4` (confident speech detected)
- `len(text) > 15` (not just "[applause]" or one word)

Then picks up to 10 timestamps — these become "key moments" for video navigation.

---

## Test Summary

| # | Method | URL | Expected |
|---|---|---|---|
| 1 | GET | `/health` | 200 |
| 2 | GET | `/summary/{unknown-id}` | 404 SUMMARY_NOT_FOUND |
| 3 | GET | `/summary/{id}` (Redis seeded) | 200 from cache |
| 4 | GET | `/summary/{id}` (DB seeded) | 200 from DB, cache primed |
| 5 | GET | `/summary/{id}` (after step 4) | 200 from cache |
| 6 | GET | `/summary/{id}` (AI pipeline) | 200 real AI output |

---

## Verify Database Directly

```bash
docker compose exec postgres psql -U postgres -d videoplatform

-- See all summaries
SELECT video_id, LENGTH(transcript) as transcript_length,
       LENGTH(summary) as summary_length,
       jsonb_array_length(key_moments::jsonb) as num_key_moments,
       created_at
FROM video_summaries;

-- See key moments for a specific video
SELECT key_moments FROM video_summaries
WHERE video_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd';

\q
```
