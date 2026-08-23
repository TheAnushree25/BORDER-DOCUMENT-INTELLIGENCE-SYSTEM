@echo off
title Border Document Intelligence System - Production Server
echo ========================================================
echo   BORDER DOCUMENT INTELLIGENCE SYSTEM (PRODUCTION)
echo ========================================================
echo.
echo Starting Production Server on http://localhost:5000 ...
echo.

python -c "import waitress, sys; sys.path.insert(0, 'backend'); from app import app; print('>>> Server online at http://0.0.0.0:5000 (Press Ctrl+C to stop)'); waitress.serve(app, host='0.0.0.0', port=5000, threads=6)"

pause
