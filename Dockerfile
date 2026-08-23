# Production Dockerfile for Border Document Intelligence System
FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

# Install system dependencies for OpenCV, Tesseract OCR, and Hindi language support
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    procps \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend, frontend, and WSGI entry point
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY wsgi.py ./
COPY app.py ./

# Ensure uploads directory exists
RUN mkdir -p backend/uploads

# Expose default port
EXPOSE 5000

# Healthcheck for both /health and /api/health
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || curl -f http://localhost:${PORT}/health || exit 1

# Start production Gunicorn server with /dev/shm heartbeat and 180s timeout
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} wsgi:app --workers 2 --threads 4 --timeout 180 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile -"]
