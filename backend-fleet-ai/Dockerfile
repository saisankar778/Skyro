# Dockerfile for backend-fleet-ai
# Lightweight Python 3.11 image — no DroneKit/MAVLink needed here.

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Expose Fleet AI port
EXPOSE 8002

# Environment defaults (overridden in docker-compose)
ENV HOST=0.0.0.0 \
    PORT=8002 \
    DRONE_BACKEND_URL=http://backend:8080 \
    DRONE_BACKEND_WS=ws://backend:8080/ws \
    ORDERS_API_BASE=http://backend-orders:8000 \
    CORS_ORIGINS=*

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8002/',timeout=2).status<500 else sys.exit(1)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--log-level", "info"]
