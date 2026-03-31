# 📋 Phase 10 — Integration & Final Documentation Task File

> **Goal:** Wire all 13 services into the final `docker-compose.yml`, run the complete
> end-to-end smoke test verifying every flow from upload → encode → stream → heatmap,
> and finalize all documentation for project submission.

**Reference doc:** [`docs/phases/phase-10-integration.md`](../phases/phase-10-integration.md)
**Depends on:** All phases 1–9 ✅
**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Task List

| # | Task | Status |
|---|---|---|
| 1 | Finalize `docker-compose.yml` — all 13 services + infra | ⬜ |
| 2 | Verify all services start healthy | ⬜ |
| 3 | Run all unit test suites | ⬜ |
| 4 | E2E smoke test: Register + Login | ⬜ |
| 5 | E2E smoke test: Upload video + poll status to `ready` | ⬜ |
| 6 | E2E smoke test: Stream video (HLS manifest + segments) | ⬜ |
| 7 | E2E smoke test: AI summary available | ⬜ |
| 8 | E2E smoke test: Send interaction events + check heatmap | ⬜ |
| 9 | E2E smoke test: Trending updated | ⬜ |
| 10 | E2E smoke test: 401 on unauthenticated access | ⬜ |
| 11 | E2E smoke test: 403 non-creator heatmap access | ⬜ |
| 12 | E2E smoke test: Rate limit 429 on event ingestion | ⬜ |
| 13 | Verify all DB tables created and populated | ⬜ |
| 14 | Verify MongoDB processing logs written | ⬜ |
| 15 | Update `README.md` with full "How to Run" instructions | ⬜ |
| 16 | Final documentation review | ⬜ |
| 17 | Update `COPILOT.md` — mark all phases done | ⬜ |

---

## Task Details

---

### ✅ Task 1 — Finalize `docker-compose.yml`

**What:** Ensure the complete `docker-compose.yml` at project root contains all services,
correct environment variables, volume mounts, and healthcheck dependencies.

**Complete service list (16 containers):**

| Container | Type |
|---|---|
| `postgres` | Infrastructure |
| `mongodb` | Infrastructure |
| `redis` | Infrastructure |
| `zookeeper` | Infrastructure |
| `kafka` | Infrastructure |
| `kafka-setup` | Init (exits after topics created) |
| `nginx` | Gateway |
| `user-service` | FastAPI :8001 |
| `video-service` | FastAPI :8002 |
| `streaming-service` | FastAPI :8003 |
| `summarization-service` | FastAPI :8004 |
| `trending-service` | FastAPI :8005 |
| `event-ingestion` | FastAPI :8006 |
| `heatmap-api` | FastAPI :8007 |
| `encoding-worker` | Kafka consumer |
| `thumbnail-worker` | Kafka consumer |
| `heatmap-aggregator` | Kafka consumer |
| `frontend` | nginx:alpine :3000 |

**Named volumes required:** `postgres_data`, `mongo_data`, `media_volume`

**Key checks for each service:**
- All env vars from `.env` properly substituted
- `./services/shared:/app/shared:ro` volume mounted for all Python services
- `media_volume:/media` mounted for: video-service, encoding-worker, thumbnail-worker, streaming-service, summarization-service
- Correct `depends_on` with `condition: service_healthy` where needed

**Test / Verify:**
```bash
docker compose config --quiet
# Should exit 0 with no errors
docker compose config | grep -c "build:"
# Expected: 11 (one per custom-built service)
```

**Acceptance criteria:**
- [ ] `docker compose config` exits 0
- [ ] 16 service entries in docker-compose.yml
- [ ] `postgres_data`, `mongo_data`, `media_volume` all declared in `volumes:`
- [ ] All Python services have `./services/shared:/app/shared:ro` mount

---

### ✅ Task 2 — Verify All Services Start Healthy

**Commands:**
```bash
# Copy env file if not done
cp .env.example .env

# Build all images
docker compose build

# Start everything
docker compose up -d

# Wait for Kafka (slowest to start)
sleep 45

# Check status
docker compose ps
```

**Expected output from `docker compose ps`:**
- All services show `running` or `healthy`
- `kafka-setup` shows `Exit 0` (completed successfully)
- No service shows `Exit 1` or `Restarting`

**Test / Verify:**
```bash
# Check for any failures
docker compose ps --format json | python3 -c "
import json, sys
services = [json.loads(l) for l in sys.stdin if l.strip()]
failed = [s for s in services if s.get('State') not in ('running','exited') or
          (s.get('State') == 'exited' and s['Name'] != 'kafka-setup')]
if failed:
    print('FAILED:', [s['Name'] for s in failed])
    sys.exit(1)
print('All services healthy ✅')
"
```

**Acceptance criteria:**
- [ ] All 16 containers started
- [ ] `kafka-setup` exits 0 (topics created)
- [ ] Zero services in `Restarting` or `Exit 1` state
- [ ] All FastAPI services reachable: `curl -f http://localhost:8001/docs`

---

### ✅ Task 3 — Run All Unit Test Suites

**What:** Run the full test suite for every service that has tests.

```bash
# Run all service test suites
FAILED=0
for svc in user-service video-service event-ingestion heatmap-aggregator heatmap-api streaming-service summarization-service trending-service; do
  echo "━━━ Testing $svc ━━━"
  cd services/$svc
  if pytest tests/ -v --tb=short -q 2>&1 | tail -5; then
    echo "✅ $svc PASS"
  else
    echo "❌ $svc FAIL"
    FAILED=1
  fi
  cd ../..
done
echo "All tests done. Failures: $FAILED"
```

**Expected test counts:**

| Service | Tests |
|---|---|
| user-service | 11 |
| video-service | 9 |
| event-ingestion | 5 |
| heatmap-aggregator | 8 |
| heatmap-api | 5 |
| streaming-service | 7 |
| summarization-service | 7 |
| trending-service | 12 |
| **Total** | **64** |

**Test / Verify:**
```bash
# Quick summary
pytest services/*/tests/ --tb=line -q 2>&1 | tail -10
```

**Acceptance criteria:**
- [ ] All 64 unit tests pass ✅
- [ ] Zero failures
- [ ] Zero errors (import errors, fixture errors, etc.)

---

### ✅ Task 4 — E2E Smoke Test: Register + Login

```bash
# Register
curl -s -c cookies.txt -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"smokeuser","email":"smoke@test.com","password":"Smoke1234"}' | python3 -m json.tool

# Login
curl -s -c cookies.txt -b cookies.txt -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.com","password":"Smoke1234"}' | python3 -m json.tool

# Verify session cookie was set
grep session_id cookies.txt | head -1
```

**Acceptance criteria:**
- [ ] Register returns 201 with user object
- [ ] Login returns 200
- [ ] `session_id` cookie set in `cookies.txt`
- [ ] `GET /users/me` with cookie returns the logged-in user

---

### ✅ Task 5 — E2E Smoke Test: Upload Video + Poll to `ready`

```bash
# Create a small test video (10s synthetic)
ffmpeg -f lavfi -i testsrc=duration=10:size=320x240:rate=25 -y /tmp/smoke_test.mp4

# Upload
VIDEO_ID=$(curl -s -b cookies.txt -X POST http://localhost/videos/upload \
  -F "file=@/tmp/smoke_test.mp4" \
  -F "title=Smoke Test Video" \
  -F "description=Integration test" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))")
echo "Video ID: $VIDEO_ID"

# Poll status (max 2 min = 24 attempts × 5s)
for i in $(seq 1 24); do
  STATUS=$(curl -s http://localhost/videos/${VIDEO_ID}/status | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
  echo "  [${i}/24] Status: $STATUS"
  if [ "$STATUS" = "ready" ]; then echo "✅ Video ready!"; break; fi
  if [ "$STATUS" = "failed" ]; then echo "❌ Video failed!"; break; fi
  sleep 5
done
```

**Acceptance criteria:**
- [ ] Upload returns 201 with `status: uploading`
- [ ] Status transitions: `uploading` → `processing` → `ready` (within 2 minutes)
- [ ] HLS files exist: `docker compose exec encoding-worker ls /media/hls/${VIDEO_ID}/`
- [ ] Thumbnail exists: `docker compose exec thumbnail-worker ls /media/thumbnails/`

---

### ✅ Task 6 — E2E Smoke Test: Stream Video

```bash
# Fetch HLS manifest
curl -s http://localhost/stream/${VIDEO_ID}/index.m3u8 | head -10
# Expected: #EXTM3U header

# Fetch first segment
FIRST_SEG=$(curl -s http://localhost/stream/${VIDEO_ID}/index.m3u8 | grep '\.ts' | head -1)
echo "First segment: $FIRST_SEG"

curl -I http://localhost/stream/${VIDEO_ID}/${FIRST_SEG}
# Expected: HTTP/1.1 200, Content-Type: video/MP2T, Accept-Ranges: bytes

# Verify Redis cache
docker compose exec redis redis-cli GET "stream:manifest:${VIDEO_ID}" | head -3
# Expected: manifest content (not empty)
```

**Acceptance criteria:**
- [ ] Manifest starts with `#EXTM3U`
- [ ] First segment returns 200 with `video/MP2T` content type
- [ ] `Accept-Ranges: bytes` header present
- [ ] Redis cache key set after first manifest request

---

### ✅ Task 7 — E2E Smoke Test: AI Summary Available

```bash
# Wait for summarization to complete (may take 2-5 min on CPU)
for i in $(seq 1 30); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/summary/${VIDEO_ID})
  echo "  [${i}/30] HTTP $HTTP"
  if [ "$HTTP" = "200" ]; then
    curl -s http://localhost/summary/${VIDEO_ID} | python3 -m json.tool
    echo "✅ Summary available!"
    break
  fi
  sleep 10
done
```

**Acceptance criteria:**
- [ ] `GET /summary/{videoId}` returns 200 within 10 minutes
- [ ] Response contains `summary` text and `key_moments` array
- [ ] `video_summaries` table has a row: `docker compose exec postgres psql -U admin -d videoplatform -c "SELECT video_id, whisper_model, processing_ms FROM video_summaries;"`

---

### ✅ Task 8 — E2E Smoke Test: Interaction Events + Heatmap

```bash
# Send multiple REWIND events at ts=142.5 to trigger viral detection
for i in $(seq 1 10); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" -b cookies.txt \
    -X POST http://localhost/events/interaction \
    -H "Content-Type: application/json" \
    -d "{\"videoId\":\"${VIDEO_ID}\",\"eventType\":\"REWIND\",\"videoTs\":142.5,\"clientTime\":$(date +%s)}")
  echo "Event $i: HTTP $HTTP"
  sleep 0.5
done

# Wait for aggregator to process
sleep 5

# Check Redis counters
docker compose exec redis redis-cli HGETALL "heatmap:${VIDEO_ID}:total:28"
# Expected: REWIND 10

# Fetch heatmap (creator only)
curl -s -b cookies.txt http://localhost/heatmap/${VIDEO_ID} | python3 -m json.tool

# Fetch highlights
curl -s -b cookies.txt http://localhost/heatmap/${VIDEO_ID}/highlights | python3 -m json.tool
```

**Acceptance criteria:**
- [ ] All 10 events return 202 immediately
- [ ] Redis key `heatmap:{vid}:total:28 REWIND = 10`
- [ ] `GET /heatmap/{vid}` returns segments with counts
- [ ] Segment 28 appears in highlights (highest rewind count)

---

### ✅ Task 9 — E2E Smoke Test: Trending Updated

```bash
curl -s http://localhost/trending | python3 -m json.tool
# Expected: list including the uploaded video with score > 0
```

**Acceptance criteria:**
- [ ] Trending list returns at least 1 item
- [ ] Uploaded video appears with `score > 0` (from REWIND events)
- [ ] Redis key `trending:videos` has entries:
  ```bash
  docker compose exec redis redis-cli ZREVRANGE trending:videos 0 4 WITHSCORES
  ```

---

### ✅ Task 10 — E2E Smoke Test: 401 Unauthenticated

```bash
# Test without cookies
curl -s http://localhost/users/me | python3 -m json.tool
# Expected: { "error": "UNAUTHORIZED", "message": "..." }

curl -s http://localhost/videos/upload \
  -X POST -F "file=@/tmp/smoke_test.mp4" -F "title=test" | python3 -m json.tool
# Expected: 401

curl -s http://localhost/heatmap/${VIDEO_ID} | python3 -m json.tool
# Expected: 401
```

**Acceptance criteria:**
- [ ] `GET /users/me` without cookie → 401 `UNAUTHORIZED`
- [ ] `POST /videos/upload` without cookie → 401
- [ ] `GET /heatmap/{id}` without cookie → 401

---

### ✅ Task 11 — E2E Smoke Test: 403 Non-Creator Access

```bash
# Register and login as viewer (second user)
curl -s -c cookies_viewer.txt -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"viewer1","email":"viewer1@test.com","password":"Viewer1234"}'

curl -s -c cookies_viewer.txt -b cookies_viewer.txt -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer1@test.com","password":"Viewer1234"}'

# Attempt to access creator's heatmap as viewer
curl -s -b cookies_viewer.txt http://localhost/heatmap/${VIDEO_ID} | python3 -m json.tool
# Expected: { "error": "FORBIDDEN", "message": "Access denied" }

# Attempt to patch creator's video as viewer
curl -s -b cookies_viewer.txt -X PATCH http://localhost/videos/${VIDEO_ID} \
  -H "Content-Type: application/json" \
  -d '{"title":"Hacked"}' | python3 -m json.tool
# Expected: 403
```

**Acceptance criteria:**
- [ ] Non-creator heatmap access → 403 `FORBIDDEN`
- [ ] Non-creator video patch → 403 `FORBIDDEN`
- [ ] Video creator can still access normally

---

### ✅ Task 12 — E2E Smoke Test: Rate Limit 429

```bash
# Send 101+ events rapidly to trigger rate limit
for i in $(seq 1 105); do
  curl -s -o /dev/null -w "$i: %{http_code}\n" -b cookies.txt \
    -X POST http://localhost/events/interaction \
    -H "Content-Type: application/json" \
    -d "{\"videoId\":\"${VIDEO_ID}\",\"eventType\":\"PLAY\",\"videoTs\":0,\"clientTime\":$(date +%s)}"
done | tail -10
# Expected: last few requests return 429
```

**Acceptance criteria:**
- [ ] First 100 requests return 202
- [ ] Request 101+ returns 429 `RATE_LIMIT_EXCEEDED`
- [ ] After 60 seconds, rate limit resets (new events return 202 again)

---

### ✅ Task 13 — Verify All DB Tables Created and Populated

```bash
docker compose exec postgres psql -U admin -d videoplatform -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
"
```

**Expected tables:**
```
users
videos
video_summaries
watch_history
viewer_events
video_heatmap_snapshots
viral_segment_alerts
```

**Check data:**
```bash
docker compose exec postgres psql -U admin -d videoplatform -c "
SELECT 'users' as tbl, COUNT(*) FROM users
UNION ALL SELECT 'videos', COUNT(*) FROM videos
UNION ALL SELECT 'video_summaries', COUNT(*) FROM video_summaries
UNION ALL SELECT 'watch_history', COUNT(*) FROM watch_history
UNION ALL SELECT 'viewer_events', COUNT(*) FROM viewer_events;
"
```

**Acceptance criteria:**
- [ ] All 7 tables exist
- [ ] `users` count ≥ 2 (creator + viewer)
- [ ] `videos` count ≥ 1
- [ ] `video_summaries` count ≥ 1
- [ ] `watch_history` count ≥ 1 (from PLAY event)
- [ ] `viewer_events` count ≥ 10 (from REWIND events)

---

### ✅ Task 14 — Verify MongoDB Processing Logs Written

```bash
docker compose exec mongodb mongosh \
  "mongodb://admin:secret@localhost:27017/videoplatform?authSource=admin" \
  --eval "
    print('=== Processing Logs ===');
    db.processing_logs.find().limit(5).forEach(printjson);
    print('=== Error Logs ===');
    db.error_logs.find().limit(5).forEach(printjson);
  " --quiet
```

**Acceptance criteria:**
- [ ] `processing_logs` has at least 2 docs (1 encoding + 1 thumbnail)
- [ ] Each doc has `status: 'completed'`
- [ ] `error_logs` exists (may be empty — that's fine)

---

### ✅ Task 15 — Update `README.md` with "How to Run"

**What:** Update the project root `README.md` with clear setup + run instructions.

**Sections to add:**

```markdown
## 🚀 How to Run

### Prerequisites
- Docker Desktop (or Docker + Docker Compose)
- 8GB RAM (for AI models in summarization-service)
- 10GB disk space (Docker images + media volume)

### Setup
1. Clone the repository
2. Copy environment file:
   ```bash
   cp .env.example .env
   ```
3. (Optional) Edit `.env` to change credentials

### Start All Services
```bash
docker compose up -d
```
First run takes ~10 minutes (builds all images, downloads AI models).

### Verify Everything Is Running
```bash
docker compose ps    # all services should show "running"
```

### Access the Application
- **Web UI**: http://localhost
- **API Docs**: http://localhost:8001/docs (User Service)
- **API Docs**: http://localhost:8002/docs (Video Service)
... (list all)

### Stop All Services
```bash
docker compose down
```

### Reset All Data
```bash
docker compose down -v  # WARNING: deletes all data + volumes
```
```

**Test / Verify:**
```bash
cat README.md | grep -c "docker compose"
# Should be > 3
```

**Acceptance criteria:**
- [ ] README has "How to Run" section with Docker commands
- [ ] Prerequisites listed (RAM, disk space)
- [ ] Access URLs listed for UI and all API docs
- [ ] `docker compose down -v` warning included

---

### ✅ Task 16 — Final Documentation Review

**Check every doc is accurate and complete:**

| Doc | Check |
|---|---|
| `docs/HLD.md` | Architecture diagram matches final implementation |
| `docs/COPILOT.md` | Session protocol, status table, document map all up to date |
| `docs/database-design.md` | All 7 PostgreSQL tables, Redis keys, MongoDB collections documented |
| `docs/lld.md` | Per-service details match what was built |
| `docs/unique-feature.md` | Heatmap engine description accurate |
| `docs/phases/shared-patterns.md` | All shared patterns documented |
| `docs/tasks/*.md` | All 10 task files complete |

**Run:**
```bash
# Check for dead links in docs (relative paths that don't exist)
find docs/ -name "*.md" -exec grep -l "](\./" {} \; | while read f; do
  grep -oP '\]\(\./[^)]+\)' "$f" | while read link; do
    target=$(echo "$link" | sed 's|](\./||;s|)||')
    dir=$(dirname "$f")
    if [ ! -e "$dir/$target" ]; then
      echo "DEAD LINK in $f: $target"
    fi
  done
done
```

**Acceptance criteria:**
- [ ] No dead links in documentation
- [ ] All architecture decisions in HLD match actual implementation
- [ ] `docs/database-design.md` matches actual DB schema (run `\d+ table_name` and compare)

---

### ✅ Task 17 — Update `COPILOT.md` Status Table

**What:** Mark all phases as ✅ done in the implementation status table.

**Update in `docs/COPILOT.md`:**
```markdown
| Phase | Description | Status | Notes |
|---|---|---|---|
| 1 | Infrastructure & Skeleton | ✅ done | |
| 2 | User Service | ✅ done | |
| 3 | Video Service | ✅ done | |
| 4 | Processing Pipeline | ✅ done | |
| 5 | Streaming Service | ✅ done | |
| 6 | AI Summarization | ✅ done | |
| 7 | Trending & Recommendations | ✅ done | |
| 8a | Event Ingestion Service | ✅ done | |
| 8b | Heatmap Aggregator | ✅ done | |
| 8c | Heatmap API | ✅ done | |
| 9 | Frontend (React.js) | ✅ done | |
| 10 | Integration & Docs | ✅ done | |
```

**Acceptance criteria:**
- [ ] All phases show ✅ done
- [ ] Session notes updated with completion date

---

## Phase Complete Checklist

Before declaring the project **complete**:

- [ ] All 17 tasks above are ✅ done
- [ ] All 64 unit tests passing, 0 failing
- [ ] All 12 E2E smoke test steps pass
- [ ] `docker compose up -d` starts all 16 containers cleanly
- [ ] Full upload → encode → stream → summarize → heatmap flow works end-to-end
- [ ] 401, 403, 429 error scenarios tested and working
- [ ] All 7 PostgreSQL tables exist with correct data
- [ ] MongoDB `processing_logs` has entries for encoding + thumbnail workers
- [ ] Redis `trending:videos`, `heatmap:*`, `session:*` keys all populated
- [ ] README has clear "How to Run" instructions
- [ ] All docs accurate and complete
- [ ] No dead links in documentation
- [ ] `.env` is gitignored, `.env.example` is committed
- [ ] 🎉 **Project ready for submission!**
