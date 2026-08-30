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

docker_ready() {
  docker_t info 2>/dev/null | grep -q "Server Version"
}

wait_for_docker() {
  local attempts="${1:-30}"
  for _ in $(seq 1 "$attempts"); do
    if docker_ready; then
      return 0
    fi
    sleep 2
  done
  return 1
}

restart_docker_desktop() {
  echo "Restarting Docker Desktop..."
  osascript -e 'quit app "Docker"' 2>/dev/null || true
  killall com.docker.backend 2>/dev/null || true
  killall Docker 2>/dev/null || true
  sleep 3
  open -a Docker
  wait_for_docker 60
}

compose_stack_running() {
  docker_t compose ps --status running --services 2>/dev/null | grep -qx postgres
}


start_compose_stack() {
  echo "Starting Docker Compose stack (no custom image build)..."
  if ! "$TIMEOUT" 120 docker compose up -d postgres; then
    return 1
  fi
  if ! compose_stack_running; then
    return 1
  fi
  if ! "$TIMEOUT" 300 docker compose up -d; then
    return 1
  fi
  compose_stack_running
}

docker_ok=0
if wait_for_docker 5; then
  docker_ok=1
else
  echo "WARNING: Docker daemon is not ready; attempting restart..."
  restart_docker_desktop && docker_ok=1 || docker_ok=0
fi

stack_ready=0
if [[ "$docker_ok" -eq 1 ]]; then
  if start_compose_stack || { restart_docker_desktop && start_compose_stack; }; then
    stack_ready=1
  else
    echo "WARNING: docker compose up failed or stack did not start."
    docker_ok=0
  fi
fi

if [[ "$stack_ready" -eq 1 ]]; then
  ./scripts/wait-for-postgres.sh
  echo "✓ PostgreSQL healthy"
  ./scripts/wait-for-api.sh
  echo "✓ Database migrations applied"
  echo "✓ API started"
  ./scripts/wait-for-web.sh
  echo "✓ Web started"
  rm -f .dev/mode 2>/dev/null || true
elif [[ "$docker_ok" -eq 0 ]]; then
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
