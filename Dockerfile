# Dockerfile
# GPU-enabled container for PF2e Society Scribe
# Using manual CUDA installation that matches the working host setup

FROM ubuntu:22.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install basic dependencies first
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-dev \
    build-essential \
    git \
    wget \
    curl \
    gnupg \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install NVIDIA drivers
RUN apt-get update && \
    apt-get install -y nvidia-driver-555-open nvidia-utils-555 && \
    apt-get install -y cuda-drivers-555 || true

# Install CUDA 12.5.1 toolkit exactly as on host
RUN wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin && \
    mv cuda-ubuntu2204.pin /etc/apt/preferences.d/cuda-repository-pin-600 && \
    wget https://developer.download.nvidia.com/compute/cuda/12.5.1/local_installers/cuda-repo-ubuntu2204-12-5-local_12.5.1-555.42.06-1_amd64.deb && \
    dpkg -i cuda-repo-ubuntu2204-12-5-local_12.5.1-555.42.06-1_amd64.deb && \
    cp /var/cuda-repo-ubuntu2204-12-5-local/cuda-*-keyring.gpg /usr/share/keyrings/ && \
    apt-get update && \
    apt-get -y install cuda-toolkit-12-5 && \
    rm -f cuda-repo-ubuntu2204-12-5-local_12.5.1-555.42.06-1_amd64.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set CUDA environment variables
ENV PATH=/usr/local/cuda-12.5/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda-12.5/lib64:${LD_LIBRARY_PATH}
ENV CUDA_HOME=/usr/local/cuda-12.5

# Set Python 3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Upgrade pip
RUN python -m pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies EXCEPT llama-cpp-python
RUN grep -v llama-cpp-python requirements.txt > requirements-no-llama.txt && \
    pip install --no-cache-dir -r requirements-no-llama.txt

# Install CUDA-enabled llama-cpp-python using the exact command that works
RUN pip install llama-cpp-python \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu125

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

# Create entrypoint script
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

# Default command
CMD []