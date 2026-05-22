@echo off
REM ─── Phase 7: Start Flower Queue Monitor (optional) ───────────────────────
REM Flower provides a web UI at http://localhost:5555
REM Shows: active workers, queued tasks, completed tasks, failures
REM
REM Prerequisites: pip install flower
REM Run AFTER starting the Celery worker.

echo Starting Flower queue monitor...
echo Dashboard: http://localhost:5555
echo.

cd /d "%~dp0"
python -m celery -A app.core.celery_app flower --port=5555 --broker=redis://localhost:6379/0
