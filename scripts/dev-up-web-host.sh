#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="$ROOT/.dev"
mkdir -p "$DEV_DIR"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
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

stop_pid_file "$DEV_DIR/web.pid"
nohup pnpm --filter @ai-cio/web dev --hostname 0.0.0.0 --port "${WEB_PORT:-3000}" >"$DEV_DIR/web.log" 2>&1 &
echo $! >"$DEV_DIR/web.pid"
echo "host-web" >"$DEV_DIR/mode"
