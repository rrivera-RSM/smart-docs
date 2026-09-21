#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

docker compose --env-file .env up --build --detach --remove-orphans
docker compose ps

WEB_PORT="${SMARTDOCS_WEB_PORT:-3003}"
echo "SmartDocs desplegado en http://127.0.0.1:${WEB_PORT}"
