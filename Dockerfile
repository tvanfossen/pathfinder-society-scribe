# Multi-stage Dockerfile for PF2e Campaign Manager
# Build environment: Ubuntu 22.04, Python 3.10+

# Stage 1: Base system with Python and system dependencies
FROM ubuntu:22.04 AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    # For model runtime (llama.cpp dependencies)
    libopenblas-dev \
    liblapack-dev \
    libgomp1 \
    # For potential audio processing
    libsndfile1 \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directories
RUN useradd -m -s /bin/bash appuser && \
    mkdir -p /app /app/data /app/models /app/campaign-data && \
    chown -R appuser:appuser /app

WORKDIR /app

# Stage 2: Python dependencies
FROM base AS dependencies

# Copy requirements file
COPY docker-requirements.txt /tmp/requirements.txt

# Install Python packages
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir -r /tmp/requirements.txt

# Stage 3: Application
FROM dependencies AS application

# Copy application code
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser tests/ /app/tests/

# Create necessary directories
RUN mkdir -p \
    /app/logs \
    /app/tmp \
    /app/campaign-data \
    /app/data \
    /app/models && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONPATH=/app
ENV CAMPAIGN_DATA_PATH=/app/campaign-data
ENV MODEL_PATH=/app/models
ENV PF2E_DB_PATH=/app/data/pf2e.db
ENV PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Expose port for web UI
EXPOSE 8000

# Default command (will be replaced with actual app startup in later phases)
CMD ["python3", "-c", "print('PF2e Campaign Manager - Container Ready'); import time; time.sleep(3600)"]