import os
import sys

# Ensure root, parent, and backend directories are in sys.path
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

for p in [ROOT_DIR, BACKEND_DIR]:
    if p and p not in sys.path and os.path.exists(p):
        sys.path.insert(0, p)

try:
    from backend.app import app
except ImportError:
    from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f">>> Border Intelligence Server running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
