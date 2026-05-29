#!/usr/bin/env bash
# =============================================================================
# start.sh — Distributed Video Streaming Platform
#
# Usage:
#   ./start.sh           Start all services
#   ./start.sh infra     Start infrastructure only
#   ./start.sh down      Stop and remove all containers
#   ./start.sh logs      Tail logs for all running services
#   ./start.sh status    Show running container status
# =============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

command -v docker  >/dev/null 2>&1 || error "Docker is not installed"
command -v docker compose >/dev/null 2>&1 || error "Docker Compose v2 is not installed"
[ -f ".env" ] || error ".env file not found — copy .env.example and fill in values"

CMD="${1:-up}"

case "$CMD" in
  down)
    info "Stopping all containers..."
    docker compose down
    success "All containers stopped."
    exit 0
    ;;
  logs)
    docker compose logs -f --tail=50
    exit 0
    ;;
  status)
    docker compose ps
    exit 0
    ;;
  infra)
    info "Starting infrastructure only..."
    docker compose up -d postgres redis zookeeper kafka nginx
    info "Waiting for Kafka..."
    until docker compose exec kafka kafka-broker-api-versions \
          --bootstrap-server kafka:9092 >/dev/null 2>&1; do
      echo -n "."
      sleep 3
    done
    echo ""
    docker compose up kafka-setup
    success "Infrastructure is up."
    exit 0
    ;;
  up|"")
    : # fall through
    ;;
  *)
    error "Unknown command '$CMD'. Usage: ./start.sh [up|infra|down|logs|status]"
    ;;
esac

# ── Start infrastructure ────────────────────────────────────────────────────
info "Starting infrastructure..."
docker compose up -d postgres redis zookeeper kafka nginx

info "Waiting for Kafka..."
until docker compose exec kafka kafka-broker-api-versions \
      --bootstrap-server kafka:9092 >/dev/null 2>&1; do
  echo -n "."
  sleep 3
done
echo ""
success "Kafka is ready."

info "Creating Kafka topics..."
docker compose up kafka-setup
success "Kafka topics ready."

# ── Start microservices ──────────────────────────────────────────────────────
info "Starting microservices..."
docker compose up -d \
  user-service \
  video-service \
  streaming-service \
  summarization-service \
  trending-service \
  event-ingestion \
  heatmap-aggregator \
  heatmap-api \
  encoding-worker \
  thumbnail-worker
success "All backend services started."

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN} ✅  VidStream Backend is up!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || docker compose ps
echo ""
info "API Gateway      → http://localhost (port 80)"
info "User Svc Docs    → http://localhost:8001/docs"
info "Video Svc Docs   → http://localhost:8002/docs"
info ""
info "Now start the frontend:"
info "  Dev  → cd ../frontend && npm run dev    (http://localhost:5173)"
info "  Docker → cd ../frontend && docker compose up --build"
info ""
info "Run './start.sh logs'   to tail service logs"
info "Run './start.sh status' to see container health"
info "Run './start.sh down'   to stop everything"
