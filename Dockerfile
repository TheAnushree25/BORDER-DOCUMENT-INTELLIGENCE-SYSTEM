# Production Dockerfile for Border Document Intelligence System
FROM python:3.11-slim-bookworm

# PORT: Render/Railway/Hugging Face override it. DATA_DIR: mount a persistent disk here to keep scans.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000 \
    DATA_DIR=/app/data \
    TZ=Asia/Kolkata

# Tesseract OCR (fallback engine) and the shared libraries OpenCV needs
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy source code and entry points
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY wsgi.py app.py gunicorn.conf.py ./

# Writable data directory (some hosts, e.g. Hugging Face Spaces, run the container as uid 1000)
RUN mkdir -p /app/data/uploads && chmod -R 777 /app/data

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

# Start production server with Gunicorn loading gunicorn.conf.py
CMD ["gunicorn", "wsgi:app", "-c", "gunicorn.conf.py"]
