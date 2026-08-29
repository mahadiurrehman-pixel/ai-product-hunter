FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl bash && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ config/
COPY database/ database/
COPY models/ models/
COPY services/ services/
COPY ui/ ui/
COPY pages/ pages/
COPY scripts/ scripts/
COPY utils/ utils/
COPY app.py .

# Create directories and grant full permissions
RUN mkdir -p /app/data /app/data/cache /app/data/backups && \
    chmod -R 777 /app/data && \
    chmod +x scripts/entrypoint.sh

EXPOSE 8501 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8501/_stcore/health && \
        curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["bash", "scripts/entrypoint.sh"]