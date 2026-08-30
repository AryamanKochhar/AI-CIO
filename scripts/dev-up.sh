#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TIMEOUT="$ROOT/scripts/with-timeout.sh"

docker_t() {
  "$TIMEOUT" 30 docker "$@"
}

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed."
  echo "Install Docker Desktop and retry: https://docs.docker.com/get-docker/"
  exit 1
fi

# shellcheck disable=SC1091
source .env 2>/dev/null || true
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-ai_cio}"

postgres_reachable() {
  export POSTGRES_ADMIN_URL="${POSTGRES_ADMIN_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/postgres}"
  PYTHONPATH=apps/api "$ROOT/.venv/bin/python" -c "
import os, sys
from sqlalchemy import create_engine, text
url = os.environ['POSTGRES_ADMIN_URL']
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    engine.dispose()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null || PYTHONPATH=apps/api python3 -c "
import os, sys
from sqlalchemy import create_engine, text
url = os.environ['POSTGRES_ADMIN_URL']
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    engine.dispose()
    sys.exit(0)
except Exception:
    sys.exit(1)
"
}

legacy_running=0
if docker_t ps --format '{{.Names}}' 2>/dev/null | grep -qx "ai_cio_db"; then
  legacy_running=1
  echo "Stopping legacy container ai_cio_db..."
  docker_t stop ai_cio_db >/dev/null 2>&1 || true
fi

check_port() {
  local port="$1"
  local service="$2"
  local container="$3"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    if ! docker_t ps --format '{{.Names}}' 2>/dev/null | grep -qx "$container"; then
      echo "ERROR: Port ${port} is already in use (needed for ${service})."
      echo "Stop the conflicting process or change the port in .env."
      exit 1
    fi
  fi
}

check_port "$POSTGRES_PORT" "PostgreSQL" "ai_cio_postgres"
check_port "$API_PORT" "API" "ai_cio_api"
check_port "$WEB_PORT" "Web" "ai_cio_web"

echo ""
echo "AI-CIO development environment"
echo "--------------------------------"
echo ""

docker_ok=0
if docker_t info >/dev/null 2>&1; then
  docker_ok=1
else
  echo "WARNING: Docker is not responding (restart Docker Desktop if this persists)."
fi

if [[ "$docker_ok" -eq 1 ]]; then
  echo "Starting Docker Compose stack (no custom image build)..."
  if "$TIMEOUT" 180 docker compose up -d; then
    ./scripts/wait-for-postgres.sh
    echo "✓ PostgreSQL healthy"
    ./scripts/wait-for-api.sh
    echo "✓ Database migrations applied"
    echo "✓ API started"
    ./scripts/wait-for-web.sh
    echo "✓ Web started"
    rm -f .dev/mode 2>/dev/null || true
  else
    echo "WARNING: docker compose up failed or timed out."
    docker_ok=0
  fi
fi

if [[ "$docker_ok" -eq 0 ]]; then
  if postgres_reachable; then
    echo "Falling back to host API/web against running PostgreSQL..."
    ./scripts/dev-up-host.sh
    ./scripts/wait-for-api.sh
    echo "✓ Database migrations applied"
    echo "✓ API started (host)"
    ./scripts/wait-for-web.sh
    echo "✓ Web started (host)"
  else
    echo ""
    echo "ERROR: Could not start the development environment."
    echo "  1. Restart Docker Desktop"
    echo "  2. Run: make dev-up"
    echo ""
    echo "If Docker keeps failing but PostgreSQL is running, use:"
    echo "  ./scripts/dev-up-host.sh"
    exit 1
  fi
fi

echo ""
echo "AI-CIO:    http://localhost:${WEB_PORT}"
echo "API:       http://localhost:${API_PORT}"
echo "API docs:  http://localhost:${API_PORT}/docs"
echo ""
echo "Stop with: make dev-down"
echo "Logs:      make dev-logs"
echo ""
