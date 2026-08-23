import os
import sys

# Ensure root and backend directories are in sys.path for Vercel Serverless runtime
CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

for p in [ROOT_DIR, BACKEND_DIR]:
    if p and p not in sys.path and os.path.exists(p):
        sys.path.insert(0, p)

try:
    from backend.app import app
except ImportError:
    from app import app

# Vercel entry point
handler = app
