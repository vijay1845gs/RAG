@echo off
REM ====================================================================
REM  RAG Platform -- Local Development Launcher
REM
REM  Launches in separate named CMD windows (startup order with delays):
REM    1. Redis Server        (immediate)
REM    2. FastAPI Backend     (+2s)
REM    3. React Frontend      (+3s)
REM    4. Celery Worker       (+3s, reuses backend\start_worker.bat)
REM
REM  Space-safe: paths are passed via helper scripts that use %%~dp0.
REM  No nested quoting. Works with any path containing spaces.
REM ====================================================================

@echo off
setlocal

REM -- Resolve directories from this script's own location ---------------
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

cls
echo.
echo  ====================================================
echo   RAG Platform  ^|  Local Dev Launcher
echo  ====================================================
echo   Root     : %ROOT%
echo   Backend  : %BACKEND%
echo   Frontend : %FRONTEND%
echo  ====================================================
echo.

REM -- Validate directories -----------------------------------------------
if not exist "%BACKEND%" (
    echo [ERROR] Backend directory not found: %BACKEND%
    pause & exit /b 1
)
if not exist "%FRONTEND%" (
    echo [ERROR] Frontend directory not found: %FRONTEND%
    pause & exit /b 1
)

REM -- Validate helper scripts exist --------------------------------------
if not exist "%BACKEND%\start_backend.bat" (
    echo [ERROR] Missing: %BACKEND%\start_backend.bat
    pause & exit /b 1
)
if not exist "%FRONTEND%\start_frontend.bat" (
    echo [ERROR] Missing: %FRONTEND%\start_frontend.bat
    pause & exit /b 1
)
if not exist "%BACKEND%\start_worker.bat" (
    echo [ERROR] Missing: %BACKEND%\start_worker.bat
    pause & exit /b 1
)

REM -- Check Redis --------------------------------------------------------
set "REDIS_AVAILABLE=0"
where redis-server >nul 2>&1
if %ERRORLEVEL% EQU 0 set "REDIS_AVAILABLE=1"

if "%REDIS_AVAILABLE%"=="0" (
    echo [WARN]  redis-server not found on PATH.
    echo         If Redis is running via Docker or WSL2, this is fine.
    echo         Otherwise: https://github.com/microsoftarchive/redis/releases
    echo.
)

echo  Starting services. Each will open in its own named window.
echo  ====================================================

REM ====================================================================
REM  [1] REDIS SERVER
REM  Passed directly -- no path quoting needed since redis-server is on PATH.
REM ====================================================================
echo  [1/4] Starting Redis Server...

if "%REDIS_AVAILABLE%"=="1" (
    start "Redis Server" cmd /k "title Redis Server && echo. && echo [Redis] Starting on localhost:6379... && echo. && redis-server && echo. && echo [Redis] Stopped. && pause"
) else (
    echo  [SKIP] Redis not on PATH -- assumed already running.
)

echo  [1/4] Waiting 2s for Redis to bind...
ping 127.0.0.1 -n 3 >nul

REM ====================================================================
REM  [2] FASTAPI BACKEND
REM  Calls backend\start_backend.bat via its FULL QUOTED path.
REM  No nested quoting issue -- the helper handles its own cd internally.
REM ====================================================================
echo  [2/4] Starting FastAPI Backend...

start "FastAPI Backend" cmd /k ""%BACKEND%\start_backend.bat""

echo  [2/4] Waiting 3s for FastAPI to bind...
ping 127.0.0.1 -n 4 >nul

REM ====================================================================
REM  [3] REACT FRONTEND
REM  Calls frontend\start_frontend.bat via its FULL QUOTED path.
REM ====================================================================
echo  [3/4] Starting React Frontend...

start "React Frontend" cmd /k ""%FRONTEND%\start_frontend.bat""

echo  [3/4] Waiting 3s for Vite to compile...
ping 127.0.0.1 -n 4 >nul

REM -- Open browser after Vite has had time to compile -------------------
echo  Opening browser at http://localhost:5173...
start http://localhost:5173

REM ====================================================================
REM  [4] CELERY WORKER
REM  Reuses backend\start_worker.bat -- no duplicated logic.
REM ====================================================================
echo  [4/4] Starting Celery Worker...

start "Celery Worker" cmd /k ""%BACKEND%\start_worker.bat""

echo  [4/4] Worker window launched.

REM ====================================================================
REM  DONE
REM ====================================================================
echo.
echo  ====================================================
echo   All services launched!
echo  ====================================================
echo.
echo   FastAPI Backend  --  http://localhost:8000
echo   API Docs         --  http://localhost:8000/docs
echo   React Frontend   --  http://localhost:5173
echo   Redis            --  localhost:6379
echo   Flower (opt)     --  http://localhost:5555
echo.
echo   Run .\stop_rag_project.bat to stop everything.
echo  ====================================================
echo.

endlocal
