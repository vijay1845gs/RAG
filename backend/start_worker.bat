@echo off
REM ─── Phase 7: Start Celery Worker (Windows) ───────────────────────────────
REM Pool: solo (required for Windows — no fork support)
REM For production: migrate to Linux/WSL2 and switch to prefork pool
REM
REM Prerequisites:
REM   1. Redis must be running: redis-server (or via Docker)
REM   2. pip install celery[redis] redis
REM   3. Run from the backend/ directory:  cd backend && start_worker.bat

echo Starting Celery worker (solo pool, Windows)...
echo Broker: redis://localhost:6379/0
echo Backend: rpc://
echo Queue: document_processing
echo.
echo Press Ctrl+C to stop the worker.
echo.

cd /d "%~dp0"
python -m celery -A app.core.celery_app worker --loglevel=info --pool=solo -Q document_processing
