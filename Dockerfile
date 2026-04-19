# REALMS Dockerfile
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

RUN chmod +x run_realms_api.sh && \
    mkdir -p data/logs data/reports data/raw && \
    useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app

USER app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

CMD ["./run_realms_api.sh"]
