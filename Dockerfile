# REALMS Dockerfile — multi-stage: Node build (web-next → static) + Python runtime.

# ── Stage 1: Astro static build ────────────────────────────────────────────
FROM node:22-slim AS web-build
WORKDIR /src
# npm install first so layer caches on package.json changes only.
COPY web-next/package.json web-next/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY web-next/ ./
# Point the build-time loader at the API inside the same docker network.
ARG REALMS_API_ORIGIN=http://realms-api:8001
ARG REALMS_PUBLIC_ORIGIN=https://realms.org
ENV REALMS_API_ORIGIN=$REALMS_API_ORIGIN \
    REALMS_PUBLIC_ORIGIN=$REALMS_PUBLIC_ORIGIN
# Build may be skipped at image build time (API not yet up in CI). The
# postbuild script dummies an empty snapshot in that case.
RUN npm run build || (echo 'web build failed; keeping empty dist' && mkdir -p dist)

# ── Stage 2: Python runtime ────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY realms/requirements.txt ./realms/requirements.txt
RUN pip install --no-cache-dir -r realms/requirements.txt

# Copy REALMS source
COPY realms/ ./realms/
COPY scripts/ ./scripts/
COPY web/ ./web/
COPY data/seed_sources.yaml ./data/seed_sources.yaml
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY pyproject.toml ./
COPY run_realms_api.sh ./

# Bring in the Astro build output (may be empty — see stage 1 fallback).
COPY --from=web-build /src/dist /app/web-next/dist

RUN chmod +x run_realms_api.sh && \
    mkdir -p data/logs data/reports data/raw data/pubmed data/archive_org && \
    useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["./run_realms_api.sh"]
