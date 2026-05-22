@echo off
REM ─── FastAPI Backend Service ─────────────────────────────────────────────────
REM Called by start_rag_project.bat via: start "FastAPI Backend" cmd /k "..."
REM %~dp0 always resolves to THIS script's directory (backend\), even with spaces.

cd /d "%~dp0"

REM Auto-activate venv if present
if exist "%~dp0venv\Scripts\activate.bat" (
    echo [Backend] Activating virtual environment...
    call "%~dp0venv\Scripts\activate.bat"
)

echo [Backend] Starting FastAPI on http://127.0.0.1:8000
echo.
python -m uvicorn app.main:app --reload

echo.
echo [Backend] Server stopped.
pause
