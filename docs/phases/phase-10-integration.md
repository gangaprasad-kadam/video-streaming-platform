# Phase 10 — Integration & Documentation

## Goal
Wire all services together in a final `docker-compose.yml`, run an end-to-end smoke test verifying the complete flow from upload to heatmap, and finalize all documentation so the project is ready for submission.

---

## Final docker-compose.yml (complete)

```yaml
version: "3.9"

services:
  # ─── Infrastructure ─────────────────────────────────────
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      retries: 5

  mongodb:
    image: mongo:6
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    volumes:
      - mongo_data:/data/db

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "kafka:9092"]
      interval: 15s
      retries: 5

  kafka-setup:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      kafka:
        condition: service_healthy
    command: >
      bash -c "
        kafka-topics --create --if-not-exists --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1 --topic video.uploaded &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1 --topic video.processed &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:9092 --partitions 12 --replication-factor 1 --topic viewer-interaction-events &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:9092 --partitions 6 --replication-factor 1 --topic heatmap-aggregated &&
        kafka-topics --create --if-not-exists --bootstrap-server kafka:9092 --partitions 3 --replication-factor 1 --topic heatmap-alerts &&
        echo 'Topics created.'
      "
    restart: "no"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - user-service
      - video-service
      - streaming-service
      - summarization-service
      - trending-service
      - event-ingestion
      - heatmap-api
      - frontend

  # ─── Microservices ───────────────────────────────────────
  user-service:
    build: ./services/user-service
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
    volumes:
      - ./services/shared:/app/shared:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  video-service:
    build: ./services/video-service
    environment:
      - POSTGRES_HOST=postgres
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - media_volume:/media
      - ./services/shared:/app/shared:ro
    depends_on:
      postgres:
        condition: service_healthy
      kafka:
        condition: service_healthy

  encoding-worker:
    build: ./services/encoding-worker
    environment:
      - POSTGRES_HOST=postgres
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - media_volume:/media
      - ./services/shared:/app/shared:ro
    depends_on:
      kafka:
        condition: service_healthy

  thumbnail-worker:
    build: ./services/thumbnail-worker
    environment:
      - POSTGRES_HOST=postgres
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - media_volume:/media
      - ./services/shared:/app/shared:ro
    depends_on:
      kafka:
        condition: service_healthy

  streaming-service:
    build: ./services/streaming-service
    environment:
      - REDIS_HOST=redis
    volumes:
      - media_volume:/media
      - ./services/shared:/app/shared:ro
    depends_on:
      redis:
        condition: service_healthy

  summarization-service:
    build: ./services/summarization-service
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - media_volume:/media
      - ./services/shared:/app/shared:ro
    depends_on:
      kafka:
        condition: service_healthy

  trending-service:
    build: ./services/trending-service
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - ./services/shared:/app/shared:ro
    depends_on:
      redis:
        condition: service_healthy

  event-ingestion:
    build: ./services/event-ingestion
    environment:
      - REDIS_HOST=redis
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - ./services/shared:/app/shared:ro
    depends_on:
      redis:
        condition: service_healthy
      kafka:
        condition: service_healthy

  heatmap-aggregator:
    build: ./services/heatmap-aggregator
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
      - KAFKA_BOOTSTRAP_SERVERS=kafka:9092
    volumes:
      - ./services/shared:/app/shared:ro
    depends_on:
      redis:
        condition: service_healthy
      kafka:
        condition: service_healthy

  heatmap-api:
    build: ./services/heatmap-api
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_HOST=redis
    volumes:
      - ./services/shared:/app/shared:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build: ./frontend
    depends_on:
      - nginx

volumes:
  postgres_data:
  mongo_data:
  media_volume:
```

---

## Database Initialization

Each service that owns a PostgreSQL table runs Alembic migrations on container startup before the uvicorn server starts. This is handled in the service `Dockerfile` CMD:

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
```

Services that run migrations: `user-service`, `video-service`, `encoding-worker`, `thumbnail-worker`, `summarization-service`, `trending-service`, `event-ingestion`, `heatmap-aggregator`, `heatmap-api`.

Migration files live in `services/{service}/alembic/versions/`. See [`shared-patterns.md §9`](phases/shared-patterns.md) for the full Alembic setup.

---

## End-to-End Smoke Test

Run these steps manually or via a test script after `docker-compose up`:

### 1. Register & Login
```bash
curl -c cookies.txt -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@test.com","password":"Test1234"}'

curl -c cookies.txt -b cookies.txt -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"Test1234"}'
```

### 2. Upload Video
```bash
curl -b cookies.txt -X POST http://localhost/videos/upload \
  -F "file=@sample.mp4" \
  -F "title=Test Video" \
  -F "description=Smoke test upload"
# Returns: { "id": "<videoId>", "status": "uploading" }
```

### 3. Poll Status Until Ready
```bash
watch -n 3 curl -s http://localhost/videos/<videoId>/status
# Expected: status transitions uploading → processing → ready
```

### 4. Fetch Summary
```bash
curl http://localhost/summary/<videoId>
# Returns: { "summary": "...", "keyMoments": [...] }
```

### 5. Stream Video
```bash
curl http://localhost/stream/<videoId>/index.m3u8
# Returns: HLS manifest with segment list
```

### 6. Send Interaction Event
```bash
curl -b cookies.txt -X POST http://localhost/events/interaction \
  -H "Content-Type: application/json" \
  -d '{"videoId":"<videoId>","eventType":"REWIND","videoTs":142.5}'
# Returns: 202 Accepted
```

### 7. Fetch Heatmap
```bash
# Wait ~10s for aggregator to process
curl -b cookies.txt http://localhost/heatmap/<videoId>
# Returns: { "segments": [...], "hotSegment": {...} }
```

### 8. Check Trending
```bash
curl http://localhost/trending
# Returns: list with the uploaded video appearing
```

### 9. Test 401 — Unauthenticated Access
```bash
# Access a protected endpoint without a session cookie
curl -s http://localhost/recommendations/some-user-id
# Expected: 401 { "error": "UNAUTHORIZED", "message": "Not authenticated" }
```

### 10. Test 403 — Non-Creator Heatmap Access
```bash
# Register and login as a second user (non-creator)
curl -c cookies2.txt -X POST http://localhost/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"viewer","email":"viewer@test.com","password":"Test1234"}'

curl -c cookies2.txt -b cookies2.txt -X POST http://localhost/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"viewer@test.com","password":"Test1234"}'

# Attempt to access the creator's heatmap as the viewer
curl -b cookies2.txt http://localhost/heatmap/<videoId>
# Expected: 403 { "error": "FORBIDDEN", "message": "Access denied" }
```

---

## Full System Architecture Summary

```
                        ┌──────────────────────────────────────┐
                        │         NGINX API GATEWAY (:80)      │
                        └──────────────────┬───────────────────┘
                                           │
    ┌──────────────┬───────────────┬───────┴──────┬─────────────────┐
    ▼              ▼               ▼               ▼                 ▼
user-svc      video-svc     streaming-svc   summarization    event-ingestion
(:8001)       (:8002)          (:8003)        (:8004)           (:8006)
    │              │                               │                 │
    │         Kafka: video.uploaded ──────────────▶│                 │
    │              │                               │          Kafka: viewer-
    │         encoding-worker                      │          interaction-events
    │         thumbnail-worker                     │                 │
    │              │                               │          heatmap-aggregator
    │         Kafka: video.processed               │                 │
    │                                              │          heatmap-api (:8007)
    │                                        trending-svc            │
    │                                           (:8005)              │
    │                                                                 │
    └─────────────────── Redis ──────────────────────────────────────┘
    └─────────────────── PostgreSQL ─────────────────────────────────┘
    └─────────────────── Kafka ──────────────────────────────────────┘
```

---

## Documentation Files

After Phase 10, the `docs/` folder contains:

```
docs/
├── intro.md                          ← Project overview + architecture
├── unique-feature.md                 ← Heatmap Engine deep-dive
└── phases/
    ├── README.md                     ← Phase index + dependency graph
    ├── phase-1-infrastructure.md
    ├── phase-2-user-service.md
    ├── phase-3-video-service.md
    ├── phase-4-processing-pipeline.md
    ├── phase-5-streaming-service.md
    ├── phase-6-ai-summarization.md
    ├── phase-7-trending-recommendations.md
    ├── phase-8-heatmap-engine.md
    ├── phase-9-frontend.md
    └── phase-10-integration.md       ← you are here
```

---

## Submission Checklist

- [ ] `docker-compose up` starts all 13 services cleanly
- [ ] All 10 smoke test steps pass (including 401 and 403 error scenarios)
- [ ] Tests pass for User Service, Video Service, Heatmap Engine
- [ ] Creator dashboard shows live heatmap after sending events
- [ ] Video player fires interaction events and they appear in heatmap
- [ ] AI summary loads on video player page
- [ ] Trending updates after watching a video
- [ ] `watch_history` row exists in PostgreSQL after sending a `PLAY` event
- [ ] `viral_segment_alerts` row exists after a simulated rewind spike (sigma > 3)
- [ ] Alembic migrations ran successfully on all services (check logs on startup)
- [ ] All docs in `docs/` are complete and accurate
- [ ] `README.md` has clear "How to run" instructions
- [ ] `.env.example` is committed (no secrets in `.env`)
