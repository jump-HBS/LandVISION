@echo off
title LandVISION Launcher
setlocal EnableDelayedExpansion
echo ==================================================
echo   LandVISION one-click start
echo   backend :8000  +  frontend :5173
echo ==================================================
echo.

rem ---- backend port check ----
netstat -ano | findstr /C:":8000 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto :start_backend
echo [Backend ] Port 8000 is already listening -- backend is running, skip.
goto :check_frontend

:start_backend
echo [Backend ] Starting FastAPI on http://127.0.0.1:8000 ...
echo            (falls back to DEMO mode if PostgreSQL is unreachable)
start "LandVISION-Backend" /D "%~dp0backend" cmd /k "..\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:check_frontend
rem ---- frontend port check ----
netstat -ano | findstr /C:":5173 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 goto :start_frontend
echo [Frontend] Port 5173 is already listening -- frontend is running, skip.
goto :wait_ready

:start_frontend
where npm >nul 2>&1
if errorlevel 1 (
    echo [Frontend] ERROR: command "npm" not found.
    echo            Please install Node.js from https://nodejs.org
    echo            then reboot and try again.
    goto :wait_ready
)
echo [Frontend] Starting Vite dev server (strict port 5173) ...
start "LandVISION-Frontend" /D "%~dp0frontend" cmd /k "npm run dev:strict"

:wait_ready
echo.
echo Waiting for the frontend to be ready (up to 30 seconds) ...
set READY=0
for /L %%i in (1,1,30) do (
    if "!READY!"=="0" (
        curl -s -o nul http://localhost:5173 >nul 2>&1
        if not errorlevel 1 set READY=1
        >nul timeout /t 1 /nobreak
    )
)
if "!READY!"=="1" (
    echo [OK] Frontend is ready. Opening browser: http://localhost:5173
    start "" http://localhost:5173
) else (
    echo [WARN] Frontend is not ready after 30 seconds.
    echo        Please check the "LandVISION-Frontend" window for error messages.
)

echo.
echo --------------------------------------------
echo Tips:
echo   1. The two black windows are backend / frontend.
echo      Close them (or double-click the stop .bat) to stop the project.
echo   2. If a port is busy, run the stop .bat first, then launch again.
echo   3. Backend API docs: http://127.0.0.1:8000/docs
echo --------------------------------------------
pause
