@echo off
title LandVISION Stopper
echo ==================================================
echo   LandVISION stop: close service windows
echo   and clean leftover processes on 8000 / 5173
echo ==================================================
echo.

echo [1/2] Closing LandVISION service windows ...
taskkill /FI "WINDOWTITLE eq LandVISION-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq LandVISION-Frontend*" /T /F >nul 2>&1

echo [2/2] Cleaning leftover processes on ports 8000 / 5173 ...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":8000 " /C:":5173 " ^| findstr "LISTENING"') do (
    echo    killing PID %%p
    taskkill /PID %%p /T /F >nul 2>&1
)

echo.
echo Done. You can double-click the launch .bat again now.
pause
