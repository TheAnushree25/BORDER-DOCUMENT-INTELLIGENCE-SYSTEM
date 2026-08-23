import os

# Gunicorn Production Configuration
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "180"))
keepalive = 5
preload_app = False

# Worker recycling prevents memory leaks during heavy AI inference
max_requests = 500
max_requests_jitter = 50

# Shared memory directory for heartbeat (prevents container worker timeouts)
if os.path.exists("/dev/shm"):
    worker_tmp_dir = "/dev/shm"

accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True
enable_stdio_inheritance = True
