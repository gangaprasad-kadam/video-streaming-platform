# Event Ingestion Service — Complete Technical Reference

## 1. What Is This Service?

The **event-ingestion** service is the single write gateway for all viewer interaction events.
Every time a viewer plays, pauses, seeks, or completes a video, the frontend sends a single HTTP
request to this service. It validates the request, applies rate limiting, then publishes the event
to Kafka — returning `202 Accepted` immediately.

**No database writes happen here.** The service is purely a validated, rate-limited Kafka publisher.
Downstream consumers (trending-service, heatmap-aggregator) process the events independently.

**Port:** `8006` (internal Docker network: `event-ingestion:8006`)  
**Cache:** Redis DB 5 (`redis://redis:6379/5`) — rate-limit counters only  
**Kafka:** Producer to `viewer-interaction-events` topic  
**Framework:** FastAPI + aiokafka + redis[asyncio]

---

## 2. Folder Structure

```
event-ingestion/
├── app/
│   ├── main.py                ← FastAPI app, lifespan hooks, global error handlers
│   ├── config.py              ← Pydantic-Settings (REDIS_URL, KAFKA_*, RATE_LIMIT_PER_MINUTE)
│   ├── redis_client.py        ← Singleton Redis connection + get_redis()
│   ├── kafka_producer.py      ← AIOKafkaProducer singleton + get_producer()
│   ├── exceptions.py          ← TooManyRequestsError (extends shared RateLimitError)
│   │
│   └── events/                ← Events domain
│       ├── handler/
│       │   └── router.py      ← HTTP route: POST /events/interaction → 202
│       └── utils/
│           ├── service.py     ← Business logic: rate check → Kafka publish
│           ├── schemas.py     ← InteractionEventRequest + InteractionEventAccepted
│           └── cache.py       ← Redis rate limiter (sliding counter window)
│
├── tests/
│   └── test_events.py         ← 4 tests covering ingest, validation, rate limit, health
├── Dockerfile
├── requirements.txt
└── pytest.ini
```

> **Note:** This service has no database and no `dao/` layer. All data flows out to Kafka.
> There are no migrations.

---

## 3. Three-Layer Architecture

```
HTTP Request
    │
    ▼
handler/router.py       ← Validates schema, calls service, returns 202
    │                      Never touches Redis or Kafka directly
    ▼
utils/service.py        ← Business logic: rate limit check → Kafka publish
    │
    ├──► utils/cache.py  ← Redis rate limiter only
    └──► kafka_producer  ← AIOKafkaProducer.send_and_wait(...)
```

**Rule:** No `dao/` layer exists here — this service writes nothing to a database.

---

## 4. Configuration (config.py)

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/5` | Redis DB 5 (rate-limit counters) |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `KAFKA_TOPIC` | `viewer-interaction-events` | Topic to publish to |
| `RATE_LIMIT_PER_MINUTE` | `60` | Max events per user per 60-second window |

---

## 5. Entry Point (main.py)

The lifespan hook initialises Redis and the Kafka producer at startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_redis()
    await connect_producer()
    yield
    await close_producer()
    await close_redis()
```

**No background tasks** — this service only handles HTTP requests. All async processing is
delegated to Kafka consumers in other services.

---

## 6. Kafka Producer (kafka_producer.py)

```python
_producer: AIOKafkaProducer | None = None

async def connect_producer():
    global _producer
    _producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    await _producer.start()

def get_producer() -> AIOKafkaProducer:
    return _producer
```

The producer is a FastAPI dependency (`Depends(get_producer)`) injected into the router.

**Publish call (in service.py):**
```python
payload = json.dumps(event.model_dump()).encode("utf-8")
key = event.videoId.encode("utf-8")
await producer.send_and_wait(settings.KAFKA_TOPIC, value=payload, key=key)
```

**Why `send_and_wait`?**  
It waits for broker acknowledgement before returning. This ensures the event is durably written
to Kafka before the 202 response is sent. The client can trust the event is accepted.

**Why key = `videoId`?**  
Kafka partitions by key. All events for the same video go to the same partition, preserving
order. This matters for the heatmap-aggregator which tracks per-video engagement over time.

---

## 7. Rate Limiting (utils/cache.py)

Rate limiting uses a **Redis counter with automatic TTL expiry**:

```python
async def check_rate_limit(redis: Redis, user_id: str) -> bool:
    key = f"ratelimit:events:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, RATE_LIMIT_TTL)  # 60 seconds
    return count <= settings.RATE_LIMIT_PER_MINUTE  # 60 events/min
```

**How it works:**
1. `INCR ratelimit:events:{userId}` — atomically increments. Returns 1 on first call.
2. On first call (count == 1), set a 60-second TTL on the key.
3. If the count exceeds 60, return `False` — event is rejected with 429.
4. After 60 seconds, the key expires and the window resets automatically.

**Redis key pattern:**

| Key | Value | TTL |
|---|---|---|
| `ratelimit:events:{userId}` | integer count | 60s (auto-expires) |

**Why not a sliding window?**  
A fixed window (reset every 60s) is simpler and cheaper (one `INCR` + optional `EXPIRE`).
For viewer events, a burst at the window boundary is acceptable — we're protecting against
automated flooding, not enforcing strict fairness.

---

## 8. API Endpoint

### Health Check

| Method | URL | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Service health check |

**Response:**
```json
{ "status": "ok", "service": "event-ingestion" }
```

---

### POST `/events/interaction`

Accept a viewer interaction event and publish it to Kafka.

**Auth Required:** No (rate limiting by userId from the request body)

**Request Body:**
```json
{
  "userId":    "550e8400-e29b-41d4-a716-446655440001",
  "videoId":   "550e8400-e29b-41d4-a716-446655440002",
  "action":    "PLAY",
  "videoTs":   45.2,
  "creatorId": "550e8400-e29b-41d4-a716-446655440003",
  "sessionId": "sess-abc-123",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

| Field | Required | Description |
|---|---|---|
| `userId` | ✅ | UUID of the viewer |
| `videoId` | ✅ | UUID of the video being watched |
| `action` | ✅ | Must be one of: `PLAY`, `WATCH_COMPLETE`, `REWIND`, `SEEK`, `PAUSE`, `SKIP` |
| `videoTs` | ✗ | Timestamp in video (seconds) when action occurred. Default: `0.0` |
| `creatorId` | ✗ | UUID of the video creator. Required for watch history tracking in trending-service |
| `sessionId` | ✗ | Browser session ID for future deduplication |
| `timestamp` | ✗ | ISO 8601 wall-clock time. Auto-set to `utcnow()` if omitted |

**Success Response — 202 Accepted:**
```json
{
  "accepted": true,
  "action": "PLAY",
  "videoId": "550e8400-e29b-41d4-a716-446655440002"
}
```

**Error Responses:**

| Status | Error Code | Cause |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Invalid `action` value, missing required fields |
| 429 | `RATE_LIMIT_EXCEEDED` | User has sent > 60 events in 60 seconds |

**Internal Flow:**
```
POST /events/interaction
    → handler/router.py → event_service.ingest_event(producer, redis, event)
        → cache.check_rate_limit(redis, userId)
            → INCR ratelimit:events:{userId}
            → if count > 60: raise TooManyRequestsError → 429
        → producer.send_and_wait("viewer-interaction-events", payload, key=videoId)
    ← return InteractionEventAccepted(accepted=True, action=..., videoId=...)
    ← 202 response
```

---

## 9. Request Schema (utils/schemas.py)

```python
VALID_ACTIONS = Literal["PLAY", "WATCH_COMPLETE", "REWIND", "SEEK", "PAUSE", "SKIP"]

class InteractionEventRequest(BaseModel):
    userId: str = Field(..., min_length=1)
    videoId: str = Field(..., min_length=1)
    action: VALID_ACTIONS
    videoTs: float = Field(default=0.0, ge=0)
    creatorId: str = ""
    sessionId: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class InteractionEventAccepted(BaseModel):
    accepted: bool = True
    action: str
    videoId: str
```

Pydantic enforces `action` as a `Literal` type — any other string is immediately rejected with 422.

---

## 10. Error Response Format

All errors follow this envelope:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "detail": null
}
```

| Error Code | HTTP Status | When |
|---|---|---|
| `RATE_LIMIT_EXCEEDED` | 429 | User exceeded 60 events/minute |
| `VALIDATION_ERROR` | 422 | Invalid action or missing fields |

---

## 11. Exceptions Hierarchy

```
shared.exceptions.AppException (base)
    └── RateLimitError → 429 RATE_LIMIT_EXCEEDED

Service-specific (app/exceptions.py):
    TooManyRequestsError(RateLimitError)
        → "Too many events from user {userId}. Limit: 60 per minute."
```

---

## 12. Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006"]
```

**Key points:**
- No database → no Alembic → no migration step in CMD
- `shared/` module is bind-mounted from host at `/app/shared` via docker-compose
- Starts on port 8006

---

## 13. Key Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.110.0 | HTTP framework |
| `uvicorn[standard]` | 0.29.0 | ASGI server |
| `redis[asyncio]` | 5.0.3 | Async Redis client (rate limiting) |
| `aiokafka` | 0.10.0 | Async Kafka producer |
| `pydantic[email]` | 2.6.4 | Request/response validation |
| `pydantic-settings` | 2.2.1 | Config from environment |

---

## 14. Testing

**Test runner:** `pytest` with `pytest-asyncio`

**Test strategy:**
- **Kafka:** `AsyncMock` for `AIOKafkaProducer.send_and_wait` — no real Kafka broker needed
- **Redis:** `AsyncMock` for all Redis operations; `incr` return value controls rate-limit simulation
- **FastAPI `dependency_overrides`:** Injects mock producer and mock Redis

**Run tests:**
```bash
cd services/event-ingestion
python -m pytest tests/ -v
# Expected: 4 passed
```

**Test coverage:**

| Test | What it covers |
|---|---|
| `test_ingest_play_event` | 202 response, Kafka called once, correct videoId in response |
| `test_ingest_invalid_action` | Unknown action → 422 VALIDATION_ERROR |
| `test_rate_limit_exceeded` | `incr` returns 61 → 429, Kafka NOT called |
| `test_health` | Health endpoint returns `{"status": "ok"}` |

---

## 15. How It Fits in the Full Pipeline

```
[Frontend / Postman]
POST /events/interaction
        │
        │  (rate check via Redis DB 5)
        │
        ▼
[Kafka topic: viewer-interaction-events]
        │
        ├──────────────────────────────────────────────────┐
        ▼                                                  ▼
[trending-service consumer]                    [heatmap-aggregator consumer]
  ZINCRBY trending:scores → Redis DB 4           bucket scoring → Redis DB 6
  upsert watch_history → PostgreSQL              upsert heatmap_buckets → MongoDB
```

The single write point fans out to multiple consumers — each service processes the same event
independently for its own purpose. Adding a new consumer (e.g., a notification service) requires
zero changes to event-ingestion.

---

## 16. Data Flow Diagram

```
CLIENT                  NGINX            EVENT-INGESTION          REDIS(DB5)    KAFKA
  │                       │                    │                       │           │
  │── POST /events/inter ──►                   │                       │           │
  │                       │──► router.py       │                       │           │
  │                       │      └─ service.ingest_event()             │           │
  │                       │           ├─ cache.check_rate_limit() ────►│           │
  │                       │           │         INCR key               │           │
  │                       │           │      ◄── count (e.g. 3)        │           │
  │                       │           └─ producer.send_and_wait() ─────────────────►│
  │◄── 202 {accepted:true} ┤                   │                       │           │
```

---

## 17. Design Decisions

1. **202 vs 200:** `202 Accepted` is semantically correct — the event is accepted for processing
   but not yet processed. The client should not assume the event has been recorded in any DB.

2. **No auth check:** Events are keyed by `userId` from the body. The assumption is that only
   authenticated frontend sessions send events (authenticated at the API gateway level via cookie).
   Rate limiting by `userId` prevents event stuffing even without service-level auth.

3. **Fire-and-forget Kafka:** `send_and_wait` waits for broker ack, but does not wait for any
   consumer to finish. This keeps latency under 5ms even under high event load.

4. **No DAO layer:** There is no database write here by design. Keeping writes out of the ingestion
   path means this service can scale horizontally with zero shared state (beyond Redis rate limits).
