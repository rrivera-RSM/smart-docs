#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# shellcheck source=node-env.sh
. "$PROJECT_DIR/scripts/node-env.sh"
ensure_smartdocs_node

cd "$PROJECT_DIR"
SMARTDOCS_NER_MODE=rules PYTHONPATH=src:. .venv/bin/python -m pytest \
  --cov=docgen \
  --cov=apps.api \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml

cd "$PROJECT_DIR/apps/web"
npm run typecheck
npm run build
