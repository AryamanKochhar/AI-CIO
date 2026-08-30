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

API_PORT="${API_PORT:-8000}"
API_URL="http://127.0.0.1:${API_PORT}/health"
MAX_ATTEMPTS="${1:-60}"

echo "Waiting for API to become healthy..."
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if curl -fsS "$API_URL" >/dev/null 2>&1; then
    echo "API is ready."
    exit 0
  fi
  sleep 1
done

echo "ERROR: API did not become healthy within ${MAX_ATTEMPTS}s."
echo "Check logs: make dev-logs SERVICE=api"
exit 1
