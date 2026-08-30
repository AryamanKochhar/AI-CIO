#!/usr/bin/env bash
# Run a command with a timeout (macOS-compatible; no GNU timeout required).
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: with-timeout.sh SECONDS COMMAND [ARGS...]" >&2
  exit 2
fi

secs="$1"
shift

if command -v timeout >/dev/null 2>&1; then
  exec timeout "$secs" "$@"
fi

if command -v gtimeout >/dev/null 2>&1; then
  exec gtimeout "$secs" "$@"
fi

"$@" &
cmd_pid=$!
(
  sleep "$secs"
  kill "$cmd_pid" 2>/dev/null || true
) &
watchdog_pid=$!

if wait "$cmd_pid" 2>/dev/null; then
  kill "$watchdog_pid" 2>/dev/null || true
  exit 0
fi

status=$?
kill "$watchdog_pid" 2>/dev/null || true
if kill -0 "$cmd_pid" 2>/dev/null; then
  kill "$cmd_pid" 2>/dev/null || true
  echo "ERROR: Command timed out after ${secs}s: $*" >&2
  exit 124
fi
exit "$status"
