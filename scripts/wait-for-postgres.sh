#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
TIMEOUT="$ROOT/scripts/with-timeout.sh"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-ai_cio}"
MAX_ATTEMPTS="${1:-60}"

echo "Waiting for PostgreSQL to become healthy..."
for _ in $(seq 1 "$MAX_ATTEMPTS"); do
  if $TIMEOUT 10 docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    echo "PostgreSQL is ready."
    exit 0
  fi
  export POSTGRES_ADMIN_URL="${POSTGRES_ADMIN_URL:-postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/postgres}"
  if PYTHONPATH=apps/api "$ROOT/.venv/bin/python" -c "
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
" 2>/dev/null; then
    echo "PostgreSQL is ready."
    exit 0
  fi
  sleep 1
done

echo "ERROR: PostgreSQL did not become healthy within ${MAX_ATTEMPTS}s."
echo "Check logs: make dev-logs SERVICE=postgres"
exit 1
