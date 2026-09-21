# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app \
    XDG_CACHE_HOME=/tmp/.cache \
    HF_HOME=/tmp/huggingface \
    TOKENIZERS_PARALLELISM=false \
    SMARTDOCS_NER_MODE=required \
    SMARTDOCS_NER_MODEL_PATH=/app/.models/roberta-base-bne-capitel-ner-plus \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1 \
    SMARTDOCS_FEATURE_PDF=false \
    SMARTDOCS_FEATURE_IMAGE_OCR=false \
    SMARTDOCS_FEATURE_WEBADMIN=false

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-api.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements-api.txt

COPY src ./src
COPY apps/api ./apps/api
COPY scripts/prepare_ner_model.py ./scripts/prepare_ner_model.py

# El modelo se fija y verifica durante el build. Nunca se descarga al arrancar.
RUN TRANSFORMERS_OFFLINE=0 HF_HUB_OFFLINE=0 \
    python scripts/prepare_ner_model.py \
    && find .models -type d -name .cache -prune -exec rm -rf {} +

RUN useradd --create-home --uid 10001 smartdocs \
    && chown -R smartdocs:smartdocs /app

USER smartdocs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]


FROM node:24.5-alpine AS web-dependencies

WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci


FROM node:24.5-alpine AS web-build

WORKDIR /app

ARG SMARTDOCS_API_PROXY_TARGET=http://api:8000
ARG SMARTDOCS_FEATURE_PDF=false
ARG SMARTDOCS_FEATURE_IMAGE_OCR=false
ARG SMARTDOCS_FEATURE_WEBADMIN=false

ENV SMARTDOCS_API_PROXY_TARGET=$SMARTDOCS_API_PROXY_TARGET \
    NEXT_TELEMETRY_DISABLED=1 \
    SMARTDOCS_FEATURE_PDF=$SMARTDOCS_FEATURE_PDF \
    SMARTDOCS_FEATURE_IMAGE_OCR=$SMARTDOCS_FEATURE_IMAGE_OCR \
    SMARTDOCS_FEATURE_WEBADMIN=$SMARTDOCS_FEATURE_WEBADMIN

COPY --from=web-dependencies /app/node_modules ./node_modules
COPY apps/web ./
RUN npm run build


FROM node:24.5-alpine AS web

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

WORKDIR /app

COPY --from=web-build --chown=node:node /app/.next/standalone ./
COPY --from=web-build --chown=node:node /app/.next/static ./.next/static
COPY --from=web-build --chown=node:node /app/public ./public

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1

CMD ["node", "server.js"]
