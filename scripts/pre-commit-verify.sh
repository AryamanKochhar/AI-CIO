#!/usr/bin/env bash
# Run the full pre-commit verification suite (mirrors .github/workflows/ci.yml).
set -uo pipefail

ROOT="$(cd "$(dirname "${0}")/.." && pwd)"
cd "$ROOT"

QUICK=0
if [[ "${1:-}" == "--quick" ]]; then
  QUICK=1
  shift
fi

declare -a RESULTS=()
FAILED=0

run_check() {
  local name="$1"
  shift
  local start end elapsed status
  start=$(date +%s)
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "▶  $name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  if "$@"; then
    status="PASS"
  else
    status="FAIL"
    FAILED=1
  fi
  end=$(date +%s)
  elapsed=$((end - start))
  RESULTS+=("$status|$name|${elapsed}s")
  if [[ "$status" == "PASS" ]]; then
    echo "✓  $name (${elapsed}s)"
  else
    echo "✗  $name (${elapsed}s)"
  fi
}

echo "AI-CIO pre-commit verification"
echo "Repo: $ROOT"
if [[ "$QUICK" -eq 1 ]]; then
  echo "Mode: quick (skipping build)"
fi

run_check "Frontend typecheck" make typecheck
run_check "Frontend lint" make lint

if [[ "$QUICK" -eq 0 ]]; then
  run_check "Frontend build" make build
fi

run_check "Backend tests (pytest)" make test

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

pass_count=0
fail_count=0
for entry in "${RESULTS[@]}"; do
  IFS='|' read -r status name elapsed <<< "$entry"
  if [[ "$status" == "PASS" ]]; then
    printf "  ✓  %-28s %s\n" "$name" "$elapsed"
    pass_count=$((pass_count + 1))
  else
    printf "  ✗  %-28s %s\n" "$name" "$elapsed"
    fail_count=$((fail_count + 1))
  fi
done

total=$((pass_count + fail_count))
echo ""
if [[ "$FAILED" -eq 0 ]]; then
  echo "Result: ALL CHECKS PASSED ($pass_count/$total)"
  exit 0
fi

echo "Result: FAILED ($fail_count/$total checks failed)"
echo "Fix the failures above, then re-run: make verify"
exit 1
