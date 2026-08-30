#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-ai_cio}"
MAX_ATTEMPTS="${1:-60}"

echo "Waiting for PostgreSQL to become healthy..."
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    echo "PostgreSQL is ready."
    exit 0
  fi
  sleep 1
done

echo "ERROR: PostgreSQL did not become healthy within ${MAX_ATTEMPTS}s."
echo "Check logs: make dev-logs SERVICE=postgres"
exit 1
