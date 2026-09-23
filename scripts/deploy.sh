#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

ENV_FILE="${SMARTDOCS_ENV_FILE:-.env}"
DEPLOY_TIMEOUT="${SMARTDOCS_DEPLOY_TIMEOUT:-300}"
COMPOSE=(docker compose --env-file "$ENV_FILE")

if ! "${COMPOSE[@]}" up --build --detach --wait --wait-timeout "$DEPLOY_TIMEOUT"; then
  echo "El despliegue no ha alcanzado un estado saludable." >&2
  "${COMPOSE[@]}" ps -a || true
  "${COMPOSE[@]}" logs --tail=80 api web || true
  exit 1
fi

"${COMPOSE[@]}" ps
echo "SmartDocs listo. Puertos publicados:"
"${COMPOSE[@]}" port web 3050
"${COMPOSE[@]}" port api 8050
