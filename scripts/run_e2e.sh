#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${SABOOT_PORT:-8765}"
BASE_URL="http://127.0.0.1:${PORT}"
export SABOOT_BASE_URL="$BASE_URL"

rm -rf proof/ui test-results
mkdir -p proof/ui

PYTHONPATH=src python3 -m saboot.webapp --port "$PORT" > proof/ui/server.log 2>&1 &
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
npx playwright test tests/ui/saboot.spec.js --reporter=line > proof/ui/e2e.log 2>&1
E2E_CODE=$?
set -e

cleanup
trap - EXIT
printf '\nexit_code=%s\n' "$E2E_CODE" >> proof/ui/e2e.log

if [ "$E2E_CODE" -eq 0 ]; then
  VIDEO="$(find test-results -name 'video.webm' 2>/dev/null | head -1 || true)"
  if [ -n "$VIDEO" ]; then
    cp "$VIDEO" proof/ui/e2e.webm
    if command -v ffmpeg >/dev/null 2>&1; then
      ffmpeg -y -loglevel error -i proof/ui/e2e.webm \
        -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
        proof/ui/e2e.mp4 || true
    fi
  fi
fi

cat proof/ui/e2e.log
exit "$E2E_CODE"
