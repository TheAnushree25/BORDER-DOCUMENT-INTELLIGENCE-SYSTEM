# Production Dockerfile for Border Document Intelligence System
FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Install required system packages for OpenCV, Tesseract OCR, and C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
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

# Copy source code and entry points
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY wsgi.py ./
COPY app.py ./
COPY gunicorn.conf.py ./

# Ensure uploads directory exists
RUN mkdir -p backend/uploads

# Expose default port
EXPOSE 10000

# Healthcheck for /health and /api/health
HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || curl -f http://localhost:${PORT}/api/health || exit 1

# Start production server with Gunicorn loading gunicorn.conf.py
CMD ["gunicorn", "wsgi:app", "-c", "gunicorn.conf.py"]
