#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
fi

# shellcheck disable=SC1091
source .env 2>/dev/null || true
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "ai_cio_db"; then
  echo "ERROR: Legacy container ai_cio_db is running on port 5432."
  echo "Stop it with: docker stop ai_cio_db"
  exit 1
fi

check_port() {
  local port="$1"
  local service="$2"
  local container="$3"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$container"; then
      echo "ERROR: Port ${port} is already in use (needed for ${service})."
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

if ! docker image inspect ai-cio-api:local >/dev/null 2>&1 || \
   ! docker image inspect ai-cio-web:local >/dev/null 2>&1; then
  echo "Building Docker images (first run — use make dev-build after dependency changes)..."
  docker compose build api web
fi

docker compose up -d

./scripts/wait-for-postgres.sh
echo "✓ PostgreSQL healthy"

./scripts/wait-for-api.sh
echo "✓ Database migrations applied"
echo "✓ API started"

./scripts/wait-for-web.sh
echo "✓ Web started"

LLM_STATUS="$(curl -fsS "http://127.0.0.1:${API_PORT}/health" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('llm','unknown'))" 2>/dev/null || echo "unknown")"
case "$LLM_STATUS" in
  ok|configured) echo "✓ AI analysis gateway configured" ;;
  disabled) echo "ℹ AI analysis disabled (deterministic observations only)" ;;
  *) echo "ℹ AI analysis unavailable — deterministic observations continue" ;;
esac

echo ""
echo "AI-CIO:    http://localhost:${WEB_PORT}"
echo "API:       http://localhost:${API_PORT}"
echo "API docs:  http://localhost:${API_PORT}/docs"
echo ""
echo "Stop with: make dev-down"
echo "Logs:      make dev-logs"
echo "Rebuild:   make dev-build  (after dependency or Dockerfile changes)"
echo ""
