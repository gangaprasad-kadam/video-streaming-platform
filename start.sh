#!/usr/bin/env bash
# =============================================================================
# start.sh  —  Distributed Video Streaming Platform
#
# Usage:
#   ./start.sh           Start all currently implemented services
#   ./start.sh infra     Start infrastructure only (no microservices)
#   ./start.sh down      Stop and remove all containers
#   ./start.sh logs      Tail logs for all running services
#   ./start.sh status    Show running container status
#
# As you complete each phase, uncomment the corresponding service(s)
# in the MICROSERVICES section below.
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Sanity checks ─────────────────────────────────────────────────────────────
command -v docker  >/dev/null 2>&1 || error "Docker is not installed"
command -v docker compose >/dev/null 2>&1 || error "Docker Compose v2 is not installed"
[ -f ".env" ] || error ".env file not found — copy .env.example and fill in values"

# =============================================================================
# COMMAND DISPATCH
# =============================================================================
CMD="${1:-up}"

case "$CMD" in

  # ── Tear-down ──────────────────────────────────────────────────────────────
  down)
    info "Stopping and removing all containers..."
    docker compose --profile services down
    success "All containers stopped."
    exit 0
    ;;

  # ── Log tailing ───────────────────────────────────────────────────────────
  logs)
    docker compose --profile services logs -f --tail=50
    exit 0
    ;;

  # ── Status ────────────────────────────────────────────────────────────────
  status)
    docker compose --profile services ps
    exit 0
    ;;

  # ── Infrastructure only ───────────────────────────────────────────────────
  infra)
    info "Starting infrastructure only (no microservices)..."
    start_infra
    success "Infrastructure is up. Run './start.sh' to also start microservices."
    exit 0
    ;;

  # ── Default: full start ───────────────────────────────────────────────────
  up|"")
    : # fall through to the main startup logic below
    ;;

  *)
    error "Unknown command '$CMD'. Usage: ./start.sh [up|infra|down|logs|status]"
    ;;
esac

# =============================================================================
# STEP 1 — INFRASTRUCTURE LAYER
# Databases, cache, message broker, and API gateway.
# These never change; start them all every time.
# =============================================================================
start_infra() {
  info "Starting infrastructure services..."
  # postgres  — PostgreSQL 15      : primary relational store
  # mongodb   — MongoDB 6          : (reserved for logs / future use)
  # redis     — Redis 7            : sessions, cache, heatmap counters
  # zookeeper — ZooKeeper          : required by Kafka
  # kafka     — Kafka              : event streaming backbone
  # nginx     — NGINX              : API gateway on port 80
  docker compose up -d \
    postgres \
    mongodb \
    redis \
    zookeeper \
    kafka \
    nginx
  success "Infrastructure containers started."
}
start_infra

# =============================================================================
# STEP 2 — KAFKA TOPIC SETUP  (one-shot container)
# Waits for Kafka to be healthy, then creates all required topics.
# Safe to re-run; uses --if-not-exists so topics are never duplicated.
#
# Topics created:
#   video.uploaded             (partitions: 3)  — Phase 3 → 4
#   video.processed            (partitions: 3)  — Phase 4 → 5
#   viewer-interaction-events  (partitions: 12) — Phase 8a → 8b
#   heatmap-aggregated         (partitions: 6)  — Phase 8b → 8c
#   heatmap-alerts             (partitions: 3)  — Phase 8b → 8c
# =============================================================================
info "Waiting for Kafka to become healthy..."
until docker compose exec kafka kafka-broker-api-versions \
      --bootstrap-server kafka:9092 >/dev/null 2>&1; do
  echo -n "."
  sleep 3
done
echo ""
success "Kafka is ready."

info "Creating Kafka topics (idempotent — safe to re-run)..."
docker compose up kafka-setup
success "Kafka topics are ready."

# =============================================================================
# STEP 3 — MICROSERVICES
# Uncomment each service as you complete its phase.
# Every service uses  profiles: ["services"]  in docker-compose.yml,
# so they are started explicitly by name here rather than via --profile.
# =============================================================================

SERVICES=()   # accumulate service names; add one per phase below

# ── Phase 2: User Service (port 8001) ─────────────────────────────────────
# Handles: registration, login/logout, session management (Redis)
SERVICES+=(user-service)

# ── Phase 3: Video Service (port 8002) ────────────────────────────────────
# Handles: video upload (raw file), metadata CRUD, Kafka publish on upload
SERVICES+=(video-service)

# ── Phase 4: Processing Pipeline (no HTTP port) ───────────────────────────
# encoding-worker  : Kafka consumer → ffmpeg HLS encoding
# thumbnail-worker : Kafka consumer → ffmpeg thumbnail extraction
# Uncomment both when Phase 4 is complete:
# SERVICES+=(encoding-worker)
# SERVICES+=(thumbnail-worker)

# ── Phase 5: Streaming Service (port 8003) ────────────────────────────────
# Handles: HLS playlist + segment delivery, byte-range requests
# Uncomment when Phase 5 is complete:
# SERVICES+=(streaming-service)

# ── Phase 6: AI Summarization Service (port 8004) ─────────────────────────
# Handles: Whisper transcription, BART summarization, stores to DB
# NOTE: first start is slow — Whisper + BART models are downloaded (~1.5 GB)
# Uncomment when Phase 6 is complete:
# SERVICES+=(summarization-service)

# ── Phase 7: Trending & Recommendations Service (port 8005) ───────────────
# Handles: view-count based trending, user-affinity recommendations
# Uncomment when Phase 7 is complete:
# SERVICES+=(trending-service)

# ── Phase 8a: Event Ingestion Service (port 8006) ─────────────────────────
# Handles: viewer interaction events (pause, seek, rewatch) → Kafka
# Uncomment when Phase 8a is complete:
# SERVICES+=(event-ingestion)

# ── Phase 8b: Heatmap Aggregator (no HTTP port) ───────────────────────────
# Kafka consumer → aggregates events into Redis heatmap buckets
# Uncomment when Phase 8b is complete:
# SERVICES+=(heatmap-aggregator)

# ── Phase 8c: Heatmap API (port 8007) ─────────────────────────────────────
# Handles: REST + SSE endpoints for heatmap data
# Uncomment when Phase 8c is complete:
# SERVICES+=(heatmap-api)

# ── Phase 9: Frontend (port 3000) ─────────────────────────────────────────
# React 18 + Vite SPA; also add --profile frontend to docker compose up
# Uncomment when Phase 9 is complete:
# SERVICES+=(frontend)

# ── Start accumulated services ─────────────────────────────────────────────
if [ ${#SERVICES[@]} -gt 0 ]; then
  info "Starting microservices: ${SERVICES[*]}"
  docker compose up -d "${SERVICES[@]}"
  success "Microservices started."
else
  warn "No microservices enabled. Run './start.sh infra' if you only need infra."
fi

# =============================================================================
# STEP 4 — HEALTH SUMMARY
# =============================================================================
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN} ✅  Platform is up!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps
echo ""

# =============================================================================
# QUICK-TEST GUIDE  (via Postman or curl)
# =============================================================================
# All requests go through NGINX on http://localhost (port 80).
# NGINX routes by URL prefix — no port number needed in your requests.
#
# NGINX ROUTING MAP:
#   /auth/           → user-service:8001
#   /users/          → user-service:8001
#   /videos/         → video-service:8002
#   /stream/         → streaming-service:8003   (Phase 5)
#   /summary/        → summarization-service:8004 (Phase 6)
#   /trending/       → trending-service:8005    (Phase 7)
#   /recommendations/→ trending-service:8005    (Phase 7)
#   /events/         → event-ingestion:8006     (Phase 8a)
#   /heatmap/        → heatmap-api:8007         (Phase 8c)
#
# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — User Service
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. Register a new user
#    POST  http://localhost/auth/register
#    Body (JSON):
#      { "username": "alice", "email": "alice@test.com", "password": "Test1234!" }
#    Expected: 201  { "data": { "id": "...", "username": "alice", ... } }
#
# 2. Login
#    POST  http://localhost/auth/login
#    Body (JSON):
#      { "email": "alice@test.com", "password": "Test1234!" }
#    Expected: 200 + Set-Cookie: session_id=...
#    → Postman stores this cookie automatically for subsequent requests
#
# 3. Get current user profile  (requires login cookie)
#    GET   http://localhost/users/me
#    Expected: 200  { "data": { "id": "...", "username": "alice", ... } }
#
# 4. Logout
#    POST  http://localhost/auth/logout
#    Expected: 200  { "message": "Logged out" }
#
# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Video Service  (login required for all endpoints)
# ─────────────────────────────────────────────────────────────────────────────
#
# 5. Upload a video
#    POST  http://localhost/videos/upload
#    Body (form-data):
#      file        → select an .mp4 file
#      title       → "My Test Video"
#      description → "A quick upload test"
#    Expected: 201  { "data": { "id": "...", "status": "pending", ... } }
#    → Note the video "id" from the response; you need it for steps 6–9
#
# 6. Get video details
#    GET   http://localhost/videos/{video_id}
#    Expected: 200  { "data": { "id": "...", "title": "...", "status": "pending" } }
#
# 7. List all videos (paginated)
#    GET   http://localhost/videos/?page=1&page_size=10
#    Expected: 200  { "data": [...], "total": N, "page": 1 }
#
# 8. Update video metadata
#    PATCH http://localhost/videos/{video_id}
#    Body (JSON):
#      { "title": "Updated Title", "description": "New description" }
#    Expected: 200  { "data": { "title": "Updated Title", ... } }
#
# 9. Check video processing status
#    GET   http://localhost/videos/{video_id}/status
#    Expected: 200  { "data": { "status": "pending" } }
#    (will remain "pending" until Phase 4 — encoding-worker — is implemented)
#
# ─────────────────────────────────────────────────────────────────────────────
# SWAGGER / INTERACTIVE DOCS  (alternative to Postman)
# ─────────────────────────────────────────────────────────────────────────────
#   User Service:  http://localhost:8001/docs
#   Video Service: http://localhost:8002/docs
#
# Tip: Use Swagger UI to explore request schemas and try endpoints interactively
#      without needing Postman at all.
# =============================================================================

info "Swagger docs → http://localhost:8001/docs  (user-service)"
info "Swagger docs → http://localhost:8002/docs  (video-service)"
info "Run './start.sh logs' to tail all service logs"
