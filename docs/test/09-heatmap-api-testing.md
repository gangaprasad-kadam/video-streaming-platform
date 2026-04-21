# Heatmap API — Complete API Testing Guide (Postman)

## Overview

The **heatmap-api** exposes three read-only endpoints that let you visualise viewer engagement
data on a video's progress bar.

**Base URL:** `http://localhost:8008`  
**Swagger UI:** `http://localhost:8008/docs`

> ⚠️ **Prerequisites:** You need heatmap data in MongoDB and Redis before these endpoints return
> meaningful results. Complete the heatmap-aggregator tests first (or follow Step 2 below to
> seed data manually).

---

## Step 1: Start the Services

```bash
cd /path/to/project

docker compose up -d redis mongo heatmap-aggregator heatmap-api

# Wait 10 seconds, then verify:
curl http://localhost:8008/health
```

**Expected:**
```json
{"status": "ok", "service": "heatmap-api"}
```

Check logs:
```bash
docker compose logs heatmap-api
```

---

## Step 2: Seed Heatmap Data

Before testing the API, you need some data. Choose one of these approaches:

### Approach A — Use the Full Pipeline (Recommended)

Start event-ingestion and send several events through it:
```bash
docker compose up -d kafka zookeeper event-ingestion trending-service

# Send multiple events via curl
curl -X POST http://localhost:8006/events/interaction \
  -H "Content-Type: application/json" \
  -d '{"userId":"u1","videoId":"YOUR_REAL_VIDEO_ID","action":"PLAY","videoTs":0.0,"creatorId":"cc","sessionId":"s1"}'

curl -X POST http://localhost:8006/events/interaction \
  -H "Content-Type: application/json" \
  -d '{"userId":"u2","videoId":"YOUR_REAL_VIDEO_ID","action":"REWIND","videoTs":142.5,"creatorId":"cc","sessionId":"s2"}'

curl -X POST http://localhost:8006/events/interaction \
  -H "Content-Type: application/json" \
  -d '{"userId":"u3","videoId":"YOUR_REAL_VIDEO_ID","action":"REWIND","videoTs":143.1,"creatorId":"cc","sessionId":"s3"}'

curl -X POST http://localhost:8006/events/interaction \
  -H "Content-Type: application/json" \
  -d '{"userId":"u4","videoId":"YOUR_REAL_VIDEO_ID","action":"WATCH_COMPLETE","videoTs":180.0,"creatorId":"cc","sessionId":"s4"}'
```

Wait 3-5 seconds for heatmap-aggregator to process them.

### Approach B — Seed MongoDB Directly

```bash
docker compose exec mongo mongosh --host localhost --port 27017
```

```javascript
use heatmaps

db.heatmap_buckets.insertMany([
  { videoId: "YOUR_REAL_VIDEO_ID", bucket: 0,   score: 2,  last_updated: "2024-01-15T10:00:00Z" },
  { videoId: "YOUR_REAL_VIDEO_ID", bucket: 5,   score: 8,  last_updated: "2024-01-15T10:00:00Z" },
  { videoId: "YOUR_REAL_VIDEO_ID", bucket: 60,  score: 15, last_updated: "2024-01-15T10:00:00Z" },
  { videoId: "YOUR_REAL_VIDEO_ID", bucket: 140, score: 47, last_updated: "2024-01-15T10:00:00Z" },
  { videoId: "YOUR_REAL_VIDEO_ID", bucket: 175, score: 5,  last_updated: "2024-01-15T10:00:00Z" }
])

exit
```

---

## Step 3: Postman Setup

1. Open **Postman**
2. Click **New** → **Collection** → Name it `Heatmap API Tests`
3. For each test below, click **New Request** inside this collection

All endpoints are `GET` — no request body required.

---

## API Test 1: Health Check

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8008/health` |
| Body | None |
| Auth | None |

### Expected Response
**Status: 200 OK**
```json
{
  "status": "ok",
  "service": "heatmap-api"
}
```

---

## API Test 2: Get All-Time Heatmap

### Purpose
Returns all engagement buckets for a video from MongoDB, sorted by position.
This is the **full historical heatmap** — all data since the video was first interacted with.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID` |
| Body | None |
| Auth | None |

### Steps in Postman
1. New Request → `GET`
2. URL: `http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID`
3. Click **Send**

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "video_id": "YOUR_REAL_VIDEO_ID",
    "bucket_size": 5,
    "total_buckets": 5,
    "buckets": [
      { "bucket": 0,   "score": 2,  "label": "0:00–0:05" },
      { "bucket": 5,   "score": 8,  "label": "0:05–0:10" },
      { "bucket": 60,  "score": 15, "label": "1:00–1:05" },
      { "bucket": 140, "score": 47, "label": "2:20–2:25" },
      { "bucket": 175, "score": 5,  "label": "2:55–3:00" }
    ]
  }
}
```

**Reading the response:**
- `bucket` — start second of the 5-second window
- `score` — cumulative engagement score (higher = more replayed)
- `label` — human-readable time range for the progress bar tooltip
- `bucket_size` — always 5 (the width of each bucket in seconds)
- `total_buckets` — total number of distinct 5-second segments that have data

### What Happened Internally?
```
GET /heatmap/YOUR_REAL_VIDEO_ID
  → MongoDB: db.heatmap_buckets.find({videoId: ...}).sort({bucket: 1})
  → Build BucketItem list with labels
  → Wrap in SuccessResponse
```

---

## API Test 3: Get All-Time Heatmap — Not Found

### Purpose
Test what happens when a video has no interaction data.

### Request
```
GET http://localhost:8008/heatmap/00000000-0000-0000-0000-000000000000
```

### Expected Response
**Status: 404 Not Found**
```json
{
  "error": "NOT_FOUND",
  "message": "heatmap not found",
  "detail": null
}
```

> **Note:** A 404 here means the video has never received an interaction event — the video
> itself may exist in the database, but the heatmap has no data.

---

## API Test 4: Get Live Heatmap

### Purpose
Returns only the **last 5 minutes** of engagement data from Redis.
This powers a real-time "currently popular segments" overlay on the progress bar.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/live` |
| Body | None |
| Auth | None |

### Steps in Postman
1. New Request → `GET`
2. URL: `http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/live`
3. Click **Send**

### Expected Response (within 5 minutes of seeding)
**Status: 200 OK**
```json
{
  "data": {
    "video_id": "YOUR_REAL_VIDEO_ID",
    "bucket_size": 5,
    "total_buckets": 2,
    "buckets": [
      { "bucket": 0,   "score": 1, "label": "0:00–0:05" },
      { "bucket": 140, "score": 6, "label": "2:20–2:25" }
    ]
  }
}
```

**Scores may differ from the all-time endpoint** — the live view only counts interactions
from the last 5 minutes, while the all-time view accumulates forever.

### Expected Response (after 5 minutes of no activity)
**Status: 200 OK**
```json
{
  "data": {
    "video_id": "YOUR_REAL_VIDEO_ID",
    "bucket_size": 5,
    "total_buckets": 0,
    "buckets": []
  }
}
```

> **An empty live heatmap is NOT a 404.** Zero activity is valid — the video has no recent
> viewers. Only the all-time endpoint raises 404 for missing data.

### What Happened Internally?
```
GET /heatmap/YOUR_REAL_VIDEO_ID/live
  → Redis: KEYS "heatmap:YOUR_REAL_VIDEO_ID:live:*"
  → For each key: GET key → parse bucket from key name → build BucketItem
  → Returns buckets sorted by bucket index
```

### Verify Redis Live Keys
```bash
docker compose exec redis redis-cli

SELECT 6

KEYS "heatmap:YOUR_REAL_VIDEO_ID:live:*"
# Example output:
# "heatmap:YOUR_REAL_VIDEO_ID:live:0"
# "heatmap:YOUR_REAL_VIDEO_ID:live:140"

TTL "heatmap:YOUR_REAL_VIDEO_ID:live:0"
# Returns remaining seconds (0–300)

exit
```

---

## API Test 5: Get Live Heatmap — No Recent Activity

### Purpose
Confirm that an empty live heatmap returns 200 (not 404).

### How to Test
Either:
- Use a video ID that was never interacted with
- Or wait 5 minutes after the last event (live keys expire)

```
GET http://localhost:8008/heatmap/00000000-0000-0000-0000-000000000000/live
```

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "video_id": "00000000-0000-0000-0000-000000000000",
    "bucket_size": 5,
    "total_buckets": 0,
    "buckets": []
  }
}
```

---

## API Test 6: Get Highlights (Top 5 by Default)

### Purpose
Returns the top N most-replayed segments, sorted by score descending.
This powers a "Most Replayed" badge or chapters list.

### Request
| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights` |
| Body | None |
| Auth | None |

### Steps in Postman
1. New Request → `GET`
2. URL: `http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights`
3. Click **Send**

### Expected Response
**Status: 200 OK**
```json
{
  "data": {
    "video_id": "YOUR_REAL_VIDEO_ID",
    "highlights": [
      { "bucket": 140, "score": 47, "label": "2:20–2:25" },
      { "bucket": 60,  "score": 15, "label": "1:00–1:05" },
      { "bucket": 5,   "score": 8,  "label": "0:05–0:10" },
      { "bucket": 175, "score": 5,  "label": "2:55–3:00" },
      { "bucket": 0,   "score": 2,  "label": "0:00–0:05" }
    ]
  }
}
```

**Reading the response:**
- Results are sorted by `score` descending (highest engagement first)
- `highlights` list (not `buckets`) — this is the `HighlightsResponse` schema
- Default limit is 5 — shows the 5 most-engaging segments

---

## API Test 7: Get Highlights with Custom Limit

### Purpose
Test the `limit` query parameter.

### Requests to try

**Limit=3:**
```
GET http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights?limit=3
```
Expected: 200, 3 buckets (top 3 by score)

**Limit=1:**
```
GET http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights?limit=1
```
Expected: 200, 1 bucket (the single most-replayed segment)

**Limit=20 (max):**
```
GET http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights?limit=20
```
Expected: 200, up to 20 buckets (or fewer if video has less data)

**Limit=0 (invalid — below minimum):**
```
GET http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights?limit=0
```
Expected: **422 Validation Error**
```json
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid input",
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be greater than or equal to 1"
    }
  ]
}
```

**Limit=21 (invalid — above maximum):**
```
GET http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/highlights?limit=21
```
Expected: **422 Validation Error**

---

## API Test 8: Get Highlights — Not Found

### Purpose
Verify 404 when no data exists.

```
GET http://localhost:8008/heatmap/no-such-video/highlights
```

### Expected Response
**Status: 404 Not Found**
```json
{
  "error": "NOT_FOUND",
  "message": "heatmap not found",
  "detail": null
}
```

---

## Understanding the Label Format

Every `BucketItem` includes a `label` field formatted as `MM:SS–MM:SS`:

| `bucket` (seconds) | `label` |
|---|---|
| `0` | `0:00–0:05` |
| `5` | `0:05–0:10` |
| `60` | `1:00–1:05` |
| `140` | `2:20–2:25` |
| `175` | `2:55–3:00` |
| `3600` | `60:00–60:05` |

The label directly reflects the 5-second window the bucket covers.
The frontend can display this directly in the video progress bar tooltip.

---

## Difference Between All-Time and Live Endpoints

| Feature | `/heatmap/{id}` | `/heatmap/{id}/live` |
|---|---|---|
| Data source | MongoDB | Redis |
| Time window | All-time (never expires) | Last 5 minutes only |
| Empty response | 404 Not Found | 200 with empty buckets |
| Use case | Full engagement history | Real-time "hot now" overlay |
| After inactivity | Scores remain | Scores fade away (TTL=300s) |

---

## Test Summary

| # | Method | URL | Expected Status |
|---|---|---|---|
| 1 | GET | `/health` | 200 |
| 2 | GET | `/heatmap/{id}` (with data) | 200 ✅ All buckets |
| 3 | GET | `/heatmap/{id}` (no data) | 404 ❌ Not Found |
| 4 | GET | `/heatmap/{id}/live` (with recent data) | 200 ✅ Live buckets |
| 5 | GET | `/heatmap/{id}/live` (no recent data) | 200 ✅ Empty buckets |
| 6 | GET | `/heatmap/{id}/highlights` (default) | 200 ✅ Top 5 |
| 7 | GET | `/heatmap/{id}/highlights?limit=3` | 200 ✅ Top 3 |
| 8 | GET | `/heatmap/{id}/highlights?limit=0` | 422 ❌ Validation error |
| 9 | GET | `/heatmap/{id}/highlights?limit=21` | 422 ❌ Validation error |
| 10 | GET | `/heatmap/{id}/highlights` (no data) | 404 ❌ Not Found |

---

## Cross-Service Verification

After sending events and testing the API, verify data consistency across all three services:

```bash
# Redis: check live and total keys
docker compose exec redis redis-cli -n 6 KEYS "heatmap:YOUR_REAL_VIDEO_ID:*"

# MongoDB: check all buckets
docker compose exec mongo mongosh --host localhost --port 27017 \
  --eval "db = db.getSiblingDB('heatmaps'); printjson(db.heatmap_buckets.find({videoId:'YOUR_REAL_VIDEO_ID'}).sort({score:-1}).toArray())"

# API: confirm live matches Redis
curl http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID/live | python3 -m json.tool

# API: confirm all-time matches MongoDB
curl http://localhost:8008/heatmap/YOUR_REAL_VIDEO_ID | python3 -m json.tool
```

Scores in the API response should match what you see directly in Redis and MongoDB.

---

## Swagger UI (Alternative to Postman)

Visit `http://localhost:8008/docs` in your browser.

The heatmap API has no cookies or auth — all endpoints work perfectly in Swagger UI.
You can test all three endpoints interactively directly in the browser.
