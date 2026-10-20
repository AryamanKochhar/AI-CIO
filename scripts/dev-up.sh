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

# Preserve explicit process configuration when loading local defaults.
ai_cio_saved_api_port_set="${API_PORT+x}"
ai_cio_saved_api_port="${API_PORT-}"
ai_cio_saved_web_port_set="${WEB_PORT+x}"
ai_cio_saved_web_port="${WEB_PORT-}"
ai_cio_saved_api_host_set="${API_HOST+x}"
ai_cio_saved_api_host="${API_HOST-}"
ai_cio_saved_web_host_set="${WEB_HOST+x}"
ai_cio_saved_web_host="${WEB_HOST-}"
ai_cio_saved_next_public_api_base_url_set="${NEXT_PUBLIC_API_BASE_URL+x}"
ai_cio_saved_next_public_api_base_url="${NEXT_PUBLIC_API_BASE_URL-}"
ai_cio_saved_api_public_url_set="${API_PUBLIC_URL+x}"
ai_cio_saved_api_public_url="${API_PUBLIC_URL-}"

# shellcheck disable=SC1091
source .env 2>/dev/null || true
if [[ "$ai_cio_saved_api_port_set" == x ]]; then export API_PORT="$ai_cio_saved_api_port"; fi
if [[ "$ai_cio_saved_web_port_set" == x ]]; then export WEB_PORT="$ai_cio_saved_web_port"; fi
if [[ "$ai_cio_saved_api_host_set" == x ]]; then export API_HOST="$ai_cio_saved_api_host"; fi
if [[ "$ai_cio_saved_web_host_set" == x ]]; then export WEB_HOST="$ai_cio_saved_web_host"; fi
if [[ "$ai_cio_saved_next_public_api_base_url_set" == x ]]; then export NEXT_PUBLIC_API_BASE_URL="$ai_cio_saved_next_public_api_base_url"; fi
if [[ "$ai_cio_saved_api_public_url_set" == x ]]; then export API_PUBLIC_URL="$ai_cio_saved_api_public_url"; fi
# AI-CIO host ports are separate from Orbix production and recovery origins.
API_PORT="${API_PORT:-8100}"
WEB_PORT="${WEB_PORT:-3100}"
for ai_cio_port in "$API_PORT" "$WEB_PORT"; do
  if [[ ! "$ai_cio_port" =~ ^[1-9][0-9]{3,4}$ ]] || [[ "$ai_cio_port" -lt 1024 || "$ai_cio_port" -gt 65535 ]]; then
    echo "ERROR: AI-CIO requires numeric host ports between 1024 and 65535." >&2
    exit 1
  fi
  case "$ai_cio_port" in
    3000|8000|18000) echo "ERROR: AI-CIO cannot use Orbix reserved ports 3000, 8000 or 18000." >&2; exit 1 ;;
  esac
done
if [[ "$API_PORT" == "$WEB_PORT" ]]; then
  echo "ERROR: AI-CIO API and web ports must differ." >&2
  exit 1
fi

API_PUBLIC_URL="${API_PUBLIC_URL:-http://localhost:$API_PORT}"
case "$API_PUBLIC_URL" in
  "http://localhost:$API_PORT"|"http://127.0.0.1:$API_PORT") ;;
  *) echo "ERROR: API_PUBLIC_URL must use the selected loopback AI-CIO API port." >&2; exit 1 ;;
esac
# Export the exact values that Compose will use, overriding stale file defaults.
export API_PORT WEB_PORT API_PUBLIC_URL

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
  docker-compose build api web
fi

docker-compose up -d

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
