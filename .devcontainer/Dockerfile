FROM python:3.13-slim

# Avoid interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies needed for Python packages and dev tooling
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace

# Pre-install Python dependencies for layer caching
# (actual install with editable project happens in post-create)
COPY requirements.txt requirements-test.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-test.txt
