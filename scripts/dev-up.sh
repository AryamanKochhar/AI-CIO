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
  echo "Install Docker Desktop and retry: https://docs.docker.com/get-docker/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not running."
  echo "Start Docker Desktop and retry."
  exit 1
fi

# shellcheck disable=SC1091
source .env 2>/dev/null || true
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3000}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

if docker ps --format '{{.Names}}' | grep -qx "ai_cio_db"; then
  echo "ERROR: Legacy container ai_cio_db is still running and holds port 5432."
  echo "Stop it with: docker stop ai_cio_db"
  echo "Then run make dev-up again."
  exit 1
fi

check_port() {
  local port="$1"
  local service="$2"
  local container="$3"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    if ! docker ps --format '{{.Names}}' | grep -qx "$container"; then
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

docker compose up -d --build

./scripts/wait-for-postgres.sh
echo "✓ PostgreSQL healthy"

./scripts/wait-for-api.sh
echo "✓ Database migrations applied"
echo "✓ API started"

./scripts/wait-for-web.sh
echo "✓ Web started"

echo ""
echo "AI-CIO:    http://localhost:${WEB_PORT}"
echo "API:       http://localhost:${API_PORT}"
echo "API docs:  http://localhost:${API_PORT}/docs"
echo ""
echo "Stop with: make dev-down"
echo "Logs:      make dev-logs"
echo ""
