@echo off
REM ====================================================================
REM  RAG Platform - Clean Stop Script
REM  Terminates all RAG dev services: Python, Node.js, Redis
REM
REM  WARNING: This will kill ALL python.exe, node.exe, and redis-server.exe
REM  processes on this machine. Close other Python/Node projects first
REM  if you don't want them affected.
REM ====================================================================

setlocal EnableDelayedExpansion

cls
echo.
echo  ====================================================
echo   RAG Platform  ^|  Stop All Services
echo  ====================================================
echo.
echo  This will terminate:
echo    - python.exe / python3*.exe  (FastAPI backend + Celery worker)
echo    - node.exe       (React/Vite frontend)
echo    - redis-server   (Redis cache/broker)
echo.
echo  Press Ctrl+C NOW to abort, or...
timeout /t 5 /nobreak
echo.
echo  ====================================================

REM -- Stop FastAPI + Celery (Python) ---------------------------------------
echo  Stopping Python processes (FastAPI + Celery)...
set "PYTHON_STOPPED=0"

for %%P in (python.exe python3.exe python3.11.exe py.exe) do (
    taskkill /F /IM %%P >nul 2>&1
    if !ERRORLEVEL! EQU 0 set "PYTHON_STOPPED=1"
)

if "%PYTHON_STOPPED%"=="1" (
    echo  [OK]  Python processes terminated.
) else (
    echo  [--]  No Python processes found.
)

REM -- Stop React/Vite (node.exe) -------------------------------------------
echo  Stopping Node.js processes (React/Vite)...
taskkill /F /IM node.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [OK]  Node.js processes terminated.
) else (
    echo  [--]  No Node.js processes found.
)

REM -- Stop Redis -----------------------------------------------------------
echo  Stopping Redis server...
taskkill /F /IM redis-server.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [OK]  Redis server terminated.
) else (
    echo  [--]  No Redis server process found.
)

REM -- Done -----------------------------------------------------------------
echo.
echo  ====================================================
echo   All RAG services stopped.
echo   Run start_rag_project.bat to restart.
echo  ====================================================
echo.
pause

endlocal
