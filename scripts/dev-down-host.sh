#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="$ROOT/.dev"

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

if [[ -f "$DEV_DIR/mode" ]] && [[ "$(cat "$DEV_DIR/mode")" == "host" ]]; then
  stop_pid_file "$DEV_DIR/api.pid"
  stop_pid_file "$DEV_DIR/web.pid"
  rm -f "$DEV_DIR/mode"
fi
