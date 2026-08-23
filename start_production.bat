@echo off
title Border Document Intelligence System - Production Server
echo ========================================================
echo   BORDER DOCUMENT INTELLIGENCE SYSTEM (LOCAL SERVER)
echo ========================================================
echo.
echo Starting Local Server on http://localhost:5000 ...
echo.

python -c "
try:
    import waitress, sys
    sys.path.insert(0, 'backend')
    from app import app
    print('>>> Server online with Waitress at http://127.0.0.1:5000 (Press Ctrl+C to stop)')
    waitress.serve(app, host='0.0.0.0', port=5000, threads=6)
except ImportError:
    from app import app
    print('>>> Server online with Flask Multi-threading at http://127.0.0.1:5000 (Press Ctrl+C to stop)')
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
"

pause
