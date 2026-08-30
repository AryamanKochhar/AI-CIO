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

WEB_PORT="${WEB_PORT:-3000}"
WEB_URL="http://127.0.0.1:${WEB_PORT}"
MAX_ATTEMPTS="${1:-90}"

echo "Waiting for web to become ready..."
for _ in $(seq 1 "$MAX_ATTEMPTS"); do
  if curl -fsS "$WEB_URL" >/dev/null 2>&1; then
    echo "Web is ready."
    exit 0
  fi
  sleep 1
done

echo "ERROR: Web did not become ready within ${MAX_ATTEMPTS}s."
echo "Check logs: make dev-logs SERVICE=web"
exit 1
