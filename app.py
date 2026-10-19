import os
import sys

# Make the backend package importable when running "python app.py" from the project root
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f">>> Border Intelligence Server running on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
