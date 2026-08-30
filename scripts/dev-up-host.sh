#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DEV_DIR="$ROOT/.dev"
mkdir -p "$DEV_DIR"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-ai_cio}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
DATABASE_URL="${DATABASE_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB}}"

PYTHON_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

stop_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

echo "Starting API and web on host (Docker images not used)..."
stop_pid_file "$DEV_DIR/api.pid"
stop_pid_file "$DEV_DIR/web.pid"

export PYTHONPATH=apps/api
export DATABASE_URL
export API_HOST="${API_HOST:-127.0.0.1}"
export API_PORT="${API_PORT:-8000}"

"$PYTHON_BIN" -m pip install -q -r requirements.txt
PYTHONPATH=apps/api "$ROOT/.venv/bin/alembic" upgrade head 2>/dev/null \
  || PYTHONPATH=apps/api alembic upgrade head

nohup env PYTHONPATH=apps/api DATABASE_URL="$DATABASE_URL" API_HOST=0.0.0.0 API_PORT="$API_PORT" \
  "$PYTHON_BIN" -m ai_cio.api >"$DEV_DIR/api.log" 2>&1 &
echo $! >"$DEV_DIR/api.pid"

nohup pnpm --filter @ai-cio/web dev --hostname 0.0.0.0 --port "${WEB_PORT:-3000}" >"$DEV_DIR/web.log" 2>&1 &
echo $! >"$DEV_DIR/web.pid"

echo "host" >"$DEV_DIR/mode"
