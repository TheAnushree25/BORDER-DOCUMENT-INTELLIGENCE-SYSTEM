#!/bin/bash
echo "========================================================"
echo "  BORDER DOCUMENT INTELLIGENCE SYSTEM (PRODUCTION)"
echo "========================================================"
echo ""
echo "Starting Production Server on http://0.0.0.0:5000 ..."
echo ""

cd backend
gunicorn --bind 0.0.0.0:5000 app:app --workers 2 --threads 4 --timeout 120
