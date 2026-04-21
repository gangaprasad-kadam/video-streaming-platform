# Heatmap Aggregator — Complete Testing Guide

## Overview

The **heatmap-aggregator** is a **Kafka consumer service** — it has no public HTTP API except
a health check. Testing it means:

1. Verifying it starts and connects to Kafka
2. Publishing events to Kafka and confirming the service processes them
3. Checking Redis and MongoDB to verify scores were written correctly

**Base URL (health only):** `http://localhost:8007`

> **No Postman requests needed for the main functionality.** The primary test is: publish
> an event → check Redis → check MongoDB.

---

## Step 1: Start the Services

```bash
cd /path/to/project

docker compose up -d redis kafka zookeeper mongo heatmap-aggregator

# Wait 15 seconds, then verify health:
curl http://localhost:8007/health
```

**Expected:**
```json
{"status": "ok", "service": "heatmap-aggregator"}
```

Check the logs to confirm the Kafka consumer started:
```bash
docker compose logs heatmap-aggregator
```

Expected log lines:
```
INFO  Heatmap consumer started — listening on 'viewer-interaction-events'
```

If you see this, the service is consuming from Kafka.

---

## Health Check (Postman / curl)

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8007/health` |
| Body | None |
| Auth | None |

**Expected (200):**
```json
{
  "status": "ok",
  "service": "heatmap-aggregator"
}
```

---

## Test 1: Publish a Single Event and Verify

### Step A — Publish via Kafka CLI

Open a terminal and run:

```bash
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic viewer-interaction-events
```

Type this JSON on **one line**, press Enter, then **Ctrl+C**:

```json
{"userId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "videoId": "YOUR_REAL_VIDEO_ID", "action": "PLAY", "videoTs": 0.0, "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc", "sessionId": "sess-001", "timestamp": "2024-01-15T10:00:00"}
```

> Use `YOUR_REAL_VIDEO_ID` — a UUID from your video upload tests.

### Step B — Verify the Log

```bash
docker compose logs heatmap-aggregator
```

Expected:
```
INFO  Recorded PLAY (w=1) for video=YOUR_REAL_VIDEO_ID bucket=0s
```

**Why bucket=0?** `videoTs=0.0` maps to the 0–5 second bucket (bucket 0).

### Step C — Check Redis

```bash
docker compose exec redis redis-cli

SELECT 6   # heatmap-aggregator uses Redis DB 6

# Check total key (permanent)
GET "heatmap:YOUR_REAL_VIDEO_ID:total:0"
# Expected: "1"   (PLAY weight = 1)

# Check live key (5-min TTL)
GET "heatmap:YOUR_REAL_VIDEO_ID:live:0"
# Expected: "1"

# Check TTL (should be ~300 seconds)
TTL "heatmap:YOUR_REAL_VIDEO_ID:live:0"
# Expected: a number between 1 and 300

exit
```

### Step D — Check MongoDB

```bash
docker compose exec mongo mongosh --host localhost --port 27017
```

Inside the MongoDB shell:
```javascript
use heatmaps

db.heatmap_buckets.find({videoId: "YOUR_REAL_VIDEO_ID"}).pretty()
```

Expected output:
```json
{
  "videoId": "YOUR_REAL_VIDEO_ID",
  "bucket": 0,
  "score": 1,
  "last_updated": "2024-01-15T10:00:00.000000+00:00"
}
```

Exit: `exit`

---

## Test 2: REWIND Event — Bucket Mapping (videoTs = 142.5)

### Publish
```bash
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic viewer-interaction-events
```

```json
{"userId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "videoId": "YOUR_REAL_VIDEO_ID", "action": "REWIND", "videoTs": 142.5, "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc", "sessionId": "sess-001", "timestamp": "2024-01-15T10:00:00"}
```

### Expected Log
```
INFO  Recorded REWIND (w=3) for video=YOUR_REAL_VIDEO_ID bucket=140s
```

**Why bucket=140?** `int(142.5 // 5) * 5 = int(28.5) * 5 = 28 * 5 = 140`

### Verify Redis
```bash
docker compose exec redis redis-cli

SELECT 6

GET "heatmap:YOUR_REAL_VIDEO_ID:total:140"
# Expected: "3"  (REWIND weight = 3)

GET "heatmap:YOUR_REAL_VIDEO_ID:live:140"
# Expected: "3"

exit
```

### Verify MongoDB
```bash
docker compose exec mongo mongosh --host localhost --port 27017
```

```javascript
use heatmaps
db.heatmap_buckets.find({videoId: "YOUR_REAL_VIDEO_ID", bucket: 140}).pretty()
```

Expected:
```json
{
  "videoId": "YOUR_REAL_VIDEO_ID",
  "bucket": 140,
  "score": 3,
  "last_updated": "..."
}
```

---

## Test 3: Multiple Events — Score Accumulation

### Publish 3 more REWIND events at the same timestamp

```bash
docker compose exec kafka kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic viewer-interaction-events
```

Paste each on a new line (press Enter after each):
```json
{"userId": "user-2", "videoId": "YOUR_REAL_VIDEO_ID", "action": "REWIND", "videoTs": 142.5, "creatorId": "cc", "sessionId": "s2", "timestamp": "2024-01-15T10:01:00"}
{"userId": "user-3", "videoId": "YOUR_REAL_VIDEO_ID", "action": "REWIND", "videoTs": 143.9, "creatorId": "cc", "sessionId": "s3", "timestamp": "2024-01-15T10:02:00"}
{"userId": "user-4", "videoId": "YOUR_REAL_VIDEO_ID", "action": "REWIND", "videoTs": 144.9, "creatorId": "cc", "sessionId": "s4", "timestamp": "2024-01-15T10:03:00"}
```

**Note:** `videoTs=143.9` and `videoTs=144.9` both map to bucket 140 (they're in the 140–145 range).

Press **Ctrl+C** when done.

### Verify Accumulated Score in Redis

```bash
docker compose exec redis redis-cli

SELECT 6

GET "heatmap:YOUR_REAL_VIDEO_ID:total:140"
# Expected: "12"  (4 REWIND events × weight 3 = 12)

exit
```

### Verify MongoDB

```javascript
use heatmaps
db.heatmap_buckets.findOne({videoId: "YOUR_REAL_VIDEO_ID", bucket: 140})
// Expected: score: 12
```

MongoDB used `$inc` — each event increments the existing document without overwriting it.

---

## Test 4: SKIP Event — Negative Score

### Publish
```json
{"userId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "videoId": "YOUR_REAL_VIDEO_ID", "action": "SKIP", "videoTs": 30.0, "creatorId": "cc", "sessionId": "sess-001", "timestamp": "2024-01-15T10:00:00"}
```

### Expected Log
```
INFO  Recorded SKIP (w=-1) for video=YOUR_REAL_VIDEO_ID bucket=30s
```

### Verify Redis
```bash
GET "heatmap:YOUR_REAL_VIDEO_ID:total:30"
# Expected: "-1"  (SKIP weight = -1)
```

The score can go negative — this correctly reduces the visual heatmap spike for skipped segments.

---

## Test 5: WATCH_COMPLETE at End of Video

### Publish
```json
{"userId": "ffffffff-ffff-ffff-ffff-ffffffffffff", "videoId": "YOUR_REAL_VIDEO_ID", "action": "WATCH_COMPLETE", "videoTs": 119.0, "creatorId": "cc", "sessionId": "sess-001", "timestamp": "2024-01-15T10:02:00"}
```

### Expected Log
```
INFO  Recorded WATCH_COMPLETE (w=2) for video=YOUR_REAL_VIDEO_ID bucket=115s
```

**Why bucket=115?** `int(119.0 // 5) * 5 = 23 * 5 = 115`

---

## Test 6: Unknown Action — Silently Skipped

### Publish
```json
{"userId": "user-x", "videoId": "vid-x", "action": "UNKNOWN_ACTION", "videoTs": 5.0, "creatorId": "", "sessionId": "", "timestamp": "2024-01-15T10:00:00"}
```

### Expected Log
```
WARNING Unknown action 'UNKNOWN_ACTION' — skipping
```

No Redis keys or MongoDB documents are created. Check:
```bash
SELECT 6
KEYS "heatmap:vid-x:*"
# Expected: (empty list)
```

---

## Test 7: Live Key Expiry (5-Minute Window)

The `live` keys automatically expire after 300 seconds (5 minutes).
You can verify this by checking the TTL:

```bash
docker compose exec redis redis-cli

SELECT 6

TTL "heatmap:YOUR_REAL_VIDEO_ID:live:0"
# Returns remaining seconds (e.g. 250)
```

After the TTL drops to 0, the key is gone. The `total` key remains permanently:
```bash
TTL "heatmap:YOUR_REAL_VIDEO_ID:total:0"
# Returns -1  (-1 means no TTL — permanent)
```

---

## Test 8: Full Pipeline Verification

Start the full stack and send an event through the HTTP endpoint (event-ingestion):

```bash
docker compose up -d
```

Send via Postman or curl:
```bash
curl -X POST http://localhost:8006/events/interaction \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "videoId": "YOUR_REAL_VIDEO_ID",
    "action": "REWIND",
    "videoTs": 60.0,
    "creatorId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "sessionId": "test"
  }'
```

Expected: `202 Accepted`

Then check the aggregator logs and Redis bucket 60:
```bash
docker compose logs heatmap-aggregator --tail=5

docker compose exec redis redis-cli -n 6 GET "heatmap:YOUR_REAL_VIDEO_ID:total:60"
# Expected: "3"  (REWIND weight = 3)
```

---

## See All Heatmap Data in Redis

```bash
docker compose exec redis redis-cli

SELECT 6

# List all keys for a video
KEYS "heatmap:YOUR_REAL_VIDEO_ID:*"

# List all total keys
KEYS "heatmap:*:total:*"

# List all active live keys (only buckets with recent activity)
KEYS "heatmap:*:live:*"

exit
```

---

## See All Heatmap Data in MongoDB

```bash
docker compose exec mongo mongosh --host localhost --port 27017
```

```javascript
use heatmaps

// See all buckets for a video, sorted by position
db.heatmap_buckets
  .find({videoId: "YOUR_REAL_VIDEO_ID"})
  .sort({bucket: 1})
  .pretty()

// Top 5 most-engaged segments (sorted by score desc)
db.heatmap_buckets
  .find({videoId: "YOUR_REAL_VIDEO_ID"})
  .sort({score: -1})
  .limit(5)
  .pretty()

// Count total buckets recorded
db.heatmap_buckets.countDocuments({videoId: "YOUR_REAL_VIDEO_ID"})

exit
```

---

## Bucket Reference Table

| `videoTs` | Bucket | Redis Key suffix | Label |
|---|---|---|---|
| 0.0 – 4.9 | 0 | `:total:0` / `:live:0` | `0:00–0:05` |
| 5.0 – 9.9 | 5 | `:total:5` / `:live:5` | `0:05–0:10` |
| 10.0 – 14.9 | 10 | `:total:10` / `:live:10` | `0:10–0:15` |
| 60.0 – 64.9 | 60 | `:total:60` / `:live:60` | `1:00–1:05` |
| 140.0 – 144.9 | 140 | `:total:140` / `:live:140` | `2:20–2:25` |
| 145.0 – 149.9 | 145 | `:total:145` / `:live:145` | `2:25–2:30` |

---

## Action Weight Reference

| Action | Weight | Effect on Heatmap |
|---|---|---|
| `REWIND` | +3 | Strongest signal — segment was replayed |
| `WATCH_COMPLETE` | +2 | Video held attention to the end |
| `SEEK` | +2 | User navigated here intentionally |
| `PAUSE` | +1 | Mild interest |
| `PLAY` | +1 | Basic engagement |
| `SKIP` | -1 | User skipped this segment |

---

## Test Summary

| Test | Method | What to Check |
|---|---|---|
| 1 | Health check | `GET /health` → 200 |
| 2 | PLAY at bucket 0 | Redis total:0=1, live:0=1, MongoDB bucket=0 score=1 |
| 3 | REWIND at 142.5 | Redis total:140=3, bucket=140 in MongoDB |
| 4 | Multiple events accumulate | Redis total:140=12 after 4 REWINDs |
| 5 | SKIP negative score | Redis total:30=-1 |
| 6 | WATCH_COMPLETE | Redis total:115=2 |
| 7 | Unknown action skipped | No Redis keys created, WARNING log |
| 8 | Live key TTL | `live:*` keys expire in ~300s, `total:*` never expire |
| 9 | Full pipeline | event-ingestion → Kafka → aggregator → Redis + MongoDB |
