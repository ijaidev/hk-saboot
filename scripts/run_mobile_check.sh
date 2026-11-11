#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${SABOOT_PORT:-8765}"
BASE_URL="http://127.0.0.1:${PORT}"
export SABOOT_BASE_URL="$BASE_URL"

rm -rf proof/mobile test-results
mkdir -p proof/mobile

PYTHONPATH=src python3 -m saboot.webapp --port "$PORT" > proof/mobile/server.log 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
  wait "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 60); do
  if curl -sf "${BASE_URL}/api/health" >/dev/null; then
    break
  fi
  sleep 0.2
done

set +e
npx playwright test tests/ui/mobile.spec.js --reporter=line > proof/mobile/mobile.log 2>&1
CODE=$?
set -e

cleanup
trap - EXIT
printf '\nexit_code=%s\n' "$CODE" >> proof/mobile/mobile.log
cat proof/mobile/mobile.log
exit "$CODE"
