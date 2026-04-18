# REALMS Dockerfile
# Based on the estimabio Dockerfile but for realms service

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml .
COPY realms/requirements.txt .

RUN pip install --no-cache-dir -r realms/requirements.txt

# Copy source code
COPY realms/ ./realms/
COPY tools/ ./tools/
COPY agents/ ./agents/
COPY models/ ./models/
COPY graph/ ./graph/
COPY scripts/ ./scripts/
COPY api/ ./api/
COPY main.py ./
COPY pyproject.toml ./
COPY prompts/ ./prompts/
COPY config/ ./config/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app
USER app

# Expose port
EXPOSE 8001

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# Default command
CMD ["./run_realms_api.sh"]