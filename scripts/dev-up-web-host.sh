#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEV_DIR="$ROOT/.dev"
mkdir -p "$DEV_DIR"

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

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

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
API_HOST="${API_HOST:-127.0.0.1}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"
case "$API_HOST/$WEB_HOST" in
  127.0.0.1/127.0.0.1|127.0.0.1/localhost|localhost/127.0.0.1|localhost/localhost) ;;
  *) echo "ERROR: AI-CIO native services must bind to loopback." >&2; exit 1 ;;
esac
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:$API_PORT}"
case "$NEXT_PUBLIC_API_BASE_URL" in
  "http://localhost:$API_PORT"|"http://127.0.0.1:$API_PORT") ;;
  *) echo "ERROR: NEXT_PUBLIC_API_BASE_URL must use the selected loopback AI-CIO API port." >&2; exit 1 ;;
esac
export API_PORT WEB_PORT API_HOST WEB_HOST NEXT_PUBLIC_API_BASE_URL

# Fail before stopping any recorded process when a selected port is occupied.
for ai_cio_port in "$API_PORT" "$WEB_PORT"; do
  if command -v lsof >/dev/null 2>&1; then
    if lsof -nP -iTCP:"$ai_cio_port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "ERROR: Port $ai_cio_port is occupied; no services were stopped." >&2
      exit 1
    fi
  elif command -v ss >/dev/null 2>&1; then
    if ss -ltnH "sport = :$ai_cio_port" | grep -q .; then
      echo "ERROR: Port $ai_cio_port is occupied; no services were stopped." >&2
      exit 1
    fi
  else
    echo "ERROR: Install lsof or ss so AI-CIO can check ports before starting." >&2
    exit 1
  fi
done

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
nohup pnpm --filter @ai-cio/web exec next dev --hostname "$WEB_HOST" --port "$WEB_PORT" >"$DEV_DIR/web.log" 2>&1 &
echo $! >"$DEV_DIR/web.pid"
echo "host-web" >"$DEV_DIR/mode"
