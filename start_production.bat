@echo off
title Border Document Intelligence System - Production Server
cd /d "%~dp0"
echo ========================================================
echo   BORDER DOCUMENT INTELLIGENCE SYSTEM (LOCAL SERVER)
echo ========================================================
echo.
echo Starting Waitress server on http://localhost:5000 ...
echo.

python -m waitress --listen=0.0.0.0:5000 --threads=6 wsgi:app

pause
