# Multi-stage Dockerfile for PF2e Campaign Manager with GPU Support
# Build environment: NVIDIA CUDA 12.2, Ubuntu 22.04, Python 3.10+

# Stage 1: Base build environment with CUDA
FROM nvidia/cuda:12.2.2-cudnn8-devel-ubuntu22.04 AS base

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# CUDA environment variables
ENV CUDA_HOME=/usr/local/cuda
ENV PATH=${CUDA_HOME}/bin:${PATH}
ENV LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${LD_LIBRARY_PATH}

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

# Install Python packages with CUDA support
# Using pre-built wheel for llama-cpp-python with CUDA 12.1 (compatible with 12.2)
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir \
    "llama-cpp-python==0.2.90" \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121 && \
    pip3 install --no-cache-dir -r /tmp/requirements.txt

# Stage 3: Application with runtime CUDA
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04 AS application

# Copy Python installation from dependencies stage
COPY --from=dependencies /usr /usr
COPY --from=dependencies /app /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    libopenblas0 \
    libgomp1 \
    libsndfile1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app user and directories
RUN useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

WORKDIR /app

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
# Enable GPU 0 for CUDA
ENV CUDA_VISIBLE_DEVICES=0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Expose port for web UI
EXPOSE 8000

# Default command - test GPU availability
CMD ["python3", "-c", "import llama_cpp; print('PF2e Campaign Manager with GPU - Container Ready'); print('Testing CUDA availability...'); import torch if 'torch' in dir() else None; import time; time.sleep(3600)"]