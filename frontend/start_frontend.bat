@echo off
REM ─── React Frontend Service ──────────────────────────────────────────────────
REM Called by start_rag_project.bat via: start "React Frontend" cmd /k "..."
REM %~dp0 always resolves to THIS script's directory (frontend\), even with spaces.

cd /d "%~dp0"

echo [Frontend] Starting Vite dev server on http://localhost:5173
echo.
npm run dev

echo.
echo [Frontend] Dev server stopped.
pause
