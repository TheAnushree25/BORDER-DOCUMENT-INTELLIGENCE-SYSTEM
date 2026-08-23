#!/bin/bash
echo "========================================================"
echo "  BORDER DOCUMENT INTELLIGENCE SYSTEM (PRODUCTION)"
echo "========================================================"
echo ""
echo "Starting Production Server on http://0.0.0.0:5000 ..."
echo ""

export PORT=5000
gunicorn wsgi:app -c gunicorn.conf.py
