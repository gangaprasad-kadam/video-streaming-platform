# VidStream — Presentation Script

> **Format:** 2–3 min (Features & Tech) + 4–5 min (Code & Infra Walkthrough)

---

## PART 1 — Features & Technologies (2–3 min)

### Opening Line
> *"VidStream is a distributed video streaming platform — similar in spirit to YouTube — built as a full-stack microservices system. It covers the full lifecycle: user authentication, video upload, encoding, HLS streaming, AI summaries, live heatmaps, and personalised recommendations."*

---

### Features

| Feature | One-line description |
|---|---|
| **Auth** | Register & Login with server-side sessions stored in Redis |
| **Upload** | Upload MP4 / WebM / MOV with title, description, and tags |
| **Encoding** | FFmpeg transcodes to HLS — H.264 video + AAC audio |
| **Streaming** | Adaptive HLS playback via hls.js — works in all browsers |
| **Thumbnails** | Auto-generated from the video at the 3-second mark |
| **AI Summary** | Whisper transcription → GPT summary with clickable timestamps |
| **Live Heatmap** | Real-time viewer engagement chart — visible only to the creator |
| **Trending** | Kafka-driven score with time decay — top videos ranked by interaction |
| **Recommendations** | 60% trending (unwatched) + 40% from creators you've watched |
| **Watch History** | History page shows all watched videos — click to go back |
| **Resume** | Auto-resumes from where you left off — per user, per video |
| **Tags + Delete** | Creators can add tags and delete their videos |
| **Dark / Light mode** | Full theme support via CSS variables |

---

### Technologies

**Backend**
- **FastAPI (Python)** — all 10 microservices
- **PostgreSQL** — user accounts, video metadata
- **MongoDB** — heatmap aggregates per video segment
- **Redis** — sessions, video cache, trending scores, heatmap live data
- **Apache Kafka** — async event streaming between services
- **FFmpeg** — video encoding and thumbnail extraction
- **NGINX** — API gateway (single entry point on port 80)
- **Docker Compose** — entire backend runs with one command

**Frontend**
- **React 18 + Vite** — SPA with CSS Modules
- **hls.js** — HLS video playback in the browser
- **React Router** — client-side navigation
- **Axios** — HTTP client with a custom response interceptor

---

### Key Numbers to Remember

| What | Value |
|---|---|
| Backend microservices | 10 |
| Databases | 3 (PostgreSQL, MongoDB, Redis) |
| Message broker | Apache Kafka |
| Frontend pages | 7 |
| Tests | 55 passing |
| Recommendation split | 60% trending + 40% creator affinity |
| Heatmap Redis TTL | 10 minutes per live segment |

---

---

## PART 2 — Code & Infra Walkthrough (4–5 min)

> Go through 4 segments in order. Open each file while talking.

---

### Segment A — Infrastructure (45 sec)

**File to open:** `backend/docker-compose.yml`

> *"Everything runs in Docker. This compose file brings up 15+ containers — Kafka, Zookeeper, Postgres, MongoDB, Redis, NGINX, and the 9 active microservices. NGINX on port 80 is the single entry point. Services talk to each other internally — nothing else is exposed."*

**Point at this line:**
```yaml
nginx:
  ports: ["80:80"]
```

---

### Segment B — Backend: Upload & Encoding Flow (1.5 min)

**Files to open in order:**

1. `backend/nginx/nginx.conf`
   > *"NGINX routes by path prefix — /auth → auth-service, /videos → video-service, /trending → trending-service."*

2. `backend/services/video-service/app/videos/handler/router.py`
   > *"POST /videos/upload accepts the file, title, description, and tags. It saves the file to disk, creates the DB row, then publishes a Kafka event — video.uploaded."*

3. `backend/services/encoding-worker/app/encoding/utils/ffmpeg.py`
   > *"The encoding worker consumes that event and runs FFmpeg — H.264 video, AAC audio, packaged into HLS .ts segments with an index.m3u8 manifest."*

   **Point at this command:**
   ```python
   "-c:v", "libx264",
   "-c:a", "aac",
   "-f", "hls",
   ```

4. Status polling — frontend polls `GET /videos/{id}/status` every 2 seconds until `status = 'ready'`.

---

### Segment C — Event-Driven Services (1 min)

**Files to open:**

1. `backend/services/event-ingestion/` (show the Kafka publish)
   > *"Every viewer action — play, pause, seek, rewind — is sent from the browser to the event-ingestion service, which publishes it to Kafka."*

2. `backend/services/trending-service/app/trending/handler/consumer.py`
   > *"The trending-service consumes these events, increments a Redis sorted set score — REWIND scores highest because it means the viewer found something interesting — and applies 10% hourly time decay so old content naturally falls off."*

3. Mention briefly:
   - `heatmap-aggregator` — same events, but stored per video segment in MongoDB
   - `watch_history` table — PLAY events also write the user's creator history, which powers recommendations

---

### Segment D — Frontend Architecture (1 min)

**Files to open:**

1. `frontend/src/` — show the folder structure briefly
   > *"Seven pages: Home, Browse, Player, Upload, Dashboard, History, and Auth. Each page has its own CSS module — scoped styles, no conflicts."*

2. `frontend/src/api/client.js`
   > *"All API calls go through one Axios client. The response interceptor auto-unwraps the backend's SuccessResponse envelope, so components always get clean data."*

3. `frontend/src/components/HlsPlayer.jsx`
   > *"HLS playback — two lines. hls.loadSource loads the manifest, attachMedia links it to the video element. hls.js handles buffering and segment loading automatically."*

   **Point at:**
   ```js
   hls.loadSource(src)
   hls.attachMedia(video)
   ```

4. `frontend/src/pages/PlayerPage.jsx`
   > *"The heatmap is shown only to the creator — this guard checks user ID against the video's creator ID. Recommendations and history also depend on the user being logged in."*

   **Point at:**
   ```js
   user?.id === video.creator_id
   ```

---

### Closing Line
> *"The entire system — 10 backend services, async workers, event-driven pipelines, and a full React frontend — starts with just two commands: `docker compose up` on the backend, and `npm run dev` on the frontend."*

---

---

## Quick Reference — Commands

```bash
# Start backend
cd backend && ./start.sh

# Start frontend (dev)
cd frontend && npm run dev

# Frontend at:  http://localhost:5173
# Backend API:  http://localhost:80
```

---

## File Path Cheat Sheet

| What to show | File |
|---|---|
| All containers | `backend/docker-compose.yml` |
| NGINX routing | `backend/nginx/nginx.conf` |
| Upload endpoint | `backend/services/video-service/app/videos/handler/router.py` |
| FFmpeg encoding | `backend/services/encoding-worker/app/encoding/utils/ffmpeg.py` |
| Kafka consumer | `backend/services/trending-service/app/trending/handler/consumer.py` |
| Axios client | `frontend/src/api/client.js` |
| HLS player | `frontend/src/components/HlsPlayer.jsx` |
| Player page | `frontend/src/pages/PlayerPage.jsx` |
