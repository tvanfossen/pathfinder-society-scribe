# Dockerfile
# GPU-enabled container for PF2e Society Scribe

ARG CUDA_VERSION=12.2.2
FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-dev \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Upgrade pip
RUN python -m pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install llama-cpp-python with CUDA support using pre-compiled wheels
# For CUDA 12.2 (matches our base image)
RUN pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122

# Copy application code
COPY src/ /app/src/
COPY tests/ /app/tests/
COPY conftest.py /app/
COPY pytest.ini /app/

# Create necessary directories
RUN mkdir -p /campaign-data /models /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV CAMPAIGN_DATA_PATH=/campaign-data
ENV MODEL_PATH=/models
ENV PF2E_DB_PATH=/app/data/pf2e.db
ENV PORT=8000

# Create a simple entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Check if running tests\n\
if [[ "$1" == "pytest" ]]; then\n\
    exec "$@"\n\
# Check if running shell\n\
elif [[ "$1" == "/bin/bash" ]] || [[ "$1" == "bash" ]]; then\n\
    exec "$@"\n\
# Default: run the web application\n\
else\n\
    echo "Starting PF2e Society Scribe..."\n\
    echo "Model: ${MODEL_FILE:-Not specified}"\n\
    echo "Port: ${PORT}"\n\
    echo "Campaign: ${CAMPAIGN_NAME:-default}"\n\
    \n\
    # Run the application\n\
    if [ -f /app/src/web/app.py ]; then\n\
        exec python -m uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT}\n\
    else\n\
        echo "Application not found. Starting Python shell..."\n\
        exec python\n\
    fi\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD []