FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The service is a package: copy this folder as /app/dmr_incoming_service
COPY . /app/dmr_incoming_service

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8095/health || exit 1

# One worker: the stale-message sweeper and the background tasks run in-process
CMD ["uvicorn", "dmr_incoming_service.app:app", "--host", "0.0.0.0", "--port", "8095", "--workers", "1"]
