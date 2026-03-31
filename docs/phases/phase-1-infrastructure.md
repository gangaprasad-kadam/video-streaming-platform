# Phase 1 — Infrastructure & Project Skeleton

## Goal
Bring up all shared infrastructure services and establish the mono-repo folder structure. After this phase, `docker-compose up` should start PostgreSQL, MongoDB, Redis, Kafka, and NGINX — all healthy and reachable.

---

## Folder Structure to Create

```
project/
├── docker-compose.yml
├── .env.example
├── nginx/
│   └── nginx.conf
├── services/
│   └── shared/            ← shared Python module (see Shared Python Module section)
│       ├── __init__.py
│       ├── dependencies.py
│       ├── exceptions.py
│       └── schemas.py
└── frontend/          ← empty, populated in Phase 9
```

---

## Services in docker-compose.yml

| Service | Image | Port | Purpose |
|---|---|---|---|
| `postgres` | `postgres:15` | 5432 | Primary relational DB |
| `mongodb` | `mongo:6` | 27017 | Logs, flexible docs |
| `redis` | `redis:7-alpine` | 6379 | Sessions, cache, counters |
| `zookeeper` | `confluentinc/cp-zookeeper:7` | 2181 | Kafka coordination |
| `kafka` | `confluentinc/cp-kafka:7` | 9092 | Event streaming |
| `nginx` | `nginx:alpine` | 80 | API Gateway / Load Balancer |

---

## docker-compose.yml (skeleton)

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
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
    ports:
      - "27017:27017"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "kafka:9092"]
      interval: 15s
      retries: 5

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - kafka  # ensures infra is up before gateway starts

volumes:
  postgres_data:
  mongo_data:
```

---

## NGINX Configuration

```nginx
# nginx/nginx.conf
events { worker_connections 1024; }

http {
  upstream user_service       { server user-service:8001; }
  upstream video_service      { server video-service:8002; }
  upstream streaming_service  { server streaming-service:8003; }
  upstream summarization_svc  { server summarization-service:8004; }
  upstream trending_service   { server trending-service:8005; }
  upstream event_ingestion    { server event-ingestion:8006; }
  upstream heatmap_api        { server heatmap-api:8007; }

  server {
    listen 80;

    location /auth/        { proxy_pass http://user_service/auth/; }
    location /users/       { proxy_pass http://user_service/users/; }
    location /videos/      { proxy_pass http://video_service/videos/; }
    location /stream/      { proxy_pass http://streaming_service/stream/; }
    location /summary/     { proxy_pass http://summarization_svc/summary/; }
    location /trending/    { proxy_pass http://trending_service/trending/; }
    location /recommendations/ { proxy_pass http://trending_service/recommendations/; }
    location /events/      { proxy_pass http://event_ingestion/events/; }
    location /heatmap/     { proxy_pass http://heatmap_api/heatmap/; }

    # Frontend (Phase 9)
    location / {
      proxy_pass http://frontend:3000;
    }
  }
}
```

---

## .env.example

```env
# PostgreSQL
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
POSTGRES_DB=videoplatform
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# MongoDB
MONGO_USER=admin
MONGO_PASSWORD=secret
MONGO_HOST=mongodb
MONGO_PORT=27017

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Session
SESSION_SECRET=change_me_in_production
SESSION_TTL_SECONDS=86400

# AI (Phase 6)
WHISPER_MODEL=base
HF_MODEL=facebook/bart-large-cnn
```

---

## Kafka Topics to Pre-create

| Topic | Partitions | Purpose |
|---|---|---|
| `video.uploaded` | 3 | Video Service → Processing Workers |
| `video.processed` | 3 | Processing Workers → Summarization |
| `viewer-interaction-events` | 12 | Event Ingestion → Aggregator |
| `heatmap-aggregated` | 6 | Aggregator → Heatmap API |
| `heatmap-alerts` | 3 | Aggregator → Notification (future) |

Topics are created via a one-shot `kafka-setup` init container in docker-compose.

```yaml
# Add to docker-compose.yml
kafka-setup:
  image: confluentinc/cp-kafka:7.5.0
  depends_on:
    kafka:
      condition: service_healthy
  entrypoint: ["/bin/sh", "-c"]
  command: >
    "kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic video.uploaded            --partitions 3  --replication-factor 1 &&
     kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic video.processed           --partitions 3  --replication-factor 1 &&
     kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic viewer-interaction-events --partitions 12 --replication-factor 1 &&
     kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic heatmap-aggregated        --partitions 6  --replication-factor 1 &&
     kafka-topics --bootstrap-server kafka:9092 --create --if-not-exists --topic heatmap-alerts            --partitions 3  --replication-factor 1"
  restart: on-failure
```

---

## Verification Checklist

- [ ] `docker-compose up -d` starts all 6 infra services
- [ ] `docker-compose ps` shows all services healthy
- [ ] `redis-cli ping` returns `PONG`
- [ ] `psql -U admin -d videoplatform` connects successfully
- [ ] Kafka topic list shows all 5 pre-created topics
- [ ] Alembic migrations run cleanly (`alembic upgrade head`) in each service that owns a PostgreSQL table

---

## Shared Python Module

`services/shared/` is a Python package that is bind-mounted (read-only) into every service container. It provides:

| File | Contents |
|---|---|
| `dependencies.py` | FastAPI `Depends`: `get_db`, `get_redis`, `get_current_user` |
| `exceptions.py` | `AppException` hierarchy (`NotFoundError`, `AuthError`, `ForbiddenError`, `ConflictError`, `RateLimitError`) |
| `schemas.py` | `SuccessResponse[T]`, `ErrorResponse`, `PagedResponse[T]` |

See **shared-patterns.md Section 2** for full source code of each file.

Mount in each service's `docker-compose.yml` entry:

```yaml
volumes:
  - ./services/shared:/app/shared:ro
```

---

## Database Initialization

Every service that owns a PostgreSQL table runs Alembic migrations at container startup before the uvicorn process begins:

```dockerfile
# services/{service}/Dockerfile — CMD
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
```

Migration files live at `services/{service}/alembic/versions/`. The `alembic upgrade head` command is idempotent — running it twice is safe.

See **shared-patterns.md Section 9** for the full Alembic pattern.

---

## Cross-Cutting Patterns

All services built in subsequent phases follow the shared conventions defined in **`docs/phases/shared-patterns.md`**:

- **Section 1** — Layered architecture (Router → Service → Repository → Cache)
- **Section 2** — Shared `services/shared/` module
- **Section 3** — Standard `main.py` template (lifespan hooks, global exception handler)
- **Section 5** — Standard response envelope (`SuccessResponse`, `ErrorResponse`)
- **Section 9** — Alembic migration pattern
- **Section 10** — Idempotency in Kafka consumers

Phase docs reference `shared-patterns.md` rather than repeating boilerplate.
