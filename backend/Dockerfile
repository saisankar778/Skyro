# syntax=docker/dockerfile:1

# Use a Debian-based Python image (avoid Alpine due to wheels/builds for uvicorn, pymavlink, lxml)
FROM python:3.10-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    \
    # Bind server to all interfaces inside the container
    HOST=0.0.0.0 \
    PORT=8080

# Install system dependencies required to build/install some Python deps (e.g., lxml for pymavlink)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libxml2-dev \
        libxslt1-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt
 
 # Overwrite DroneKit with our patched file (baked into the image)
 # Source path is relative to the backend build context (./backend)
 COPY patches/dronekit/__init__.py /usr/local/lib/python3.10/site-packages/dronekit/__init__.py

# Copy the backend application code
COPY . .

# Expose the FastAPI port
EXPOSE 8080

# Default command: run the app (main.py reads HOST/PORT envs and uses uvicorn)
CMD ["python", "main.py"]

