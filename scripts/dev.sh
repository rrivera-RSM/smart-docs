#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# shellcheck source=node-env.sh
. "$PROJECT_DIR/scripts/node-env.sh"
ensure_smartdocs_node

cd "$PROJECT_DIR"

API_PORT="${SMARTDOCS_API_PORT:-8000}"
while ss -H -ltn "sport = :$API_PORT" | grep -q .; do
  API_PORT=$((API_PORT + 1))
done

WEB_PORT="${SMARTDOCS_WEB_PORT:-3000}"
while ss -H -ltn "sport = :$WEB_PORT" | grep -q .; do
  WEB_PORT=$((WEB_PORT + 1))
done

echo "SmartDocs: http://127.0.0.1:$WEB_PORT"
echo "SmartDocs API: http://127.0.0.1:$API_PORT/docs"

PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR" \
  "$PROJECT_DIR/.venv/bin/uvicorn" apps.api.main:app \
  --reload \
  --host 127.0.0.1 \
  --port "$API_PORT" &
API_PID=$!

(
  cd "$PROJECT_DIR/apps/web"
  SMARTDOCS_API_PROXY_TARGET="http://127.0.0.1:$API_PORT" \
    npm run dev -- --hostname 127.0.0.1 --port "$WEB_PORT"
) &
WEB_PID=$!

cleanup() {
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM
wait -n "$API_PID" "$WEB_PID"
