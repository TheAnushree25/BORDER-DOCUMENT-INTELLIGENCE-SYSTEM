#!/bin/bash
cd "$(dirname "$0")"
echo "========================================================"
echo "  BORDER DOCUMENT INTELLIGENCE SYSTEM (PRODUCTION)"
echo "========================================================"
echo ""
echo "Starting Production Server on http://0.0.0.0:5000 ..."
echo ""

export PORT=5000
exec gunicorn wsgi:app -c gunicorn.conf.py
