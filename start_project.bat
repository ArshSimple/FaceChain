@echo off
title FaceChain Launcher
echo ===================================================
echo       🚀 STARTING FACECHAIN SYSTEM 🚀
echo ===================================================

:: ===================================================
:: [CONFIGURATION] DYNAMIC PATH
:: This automatically finds the folder where this file is located.
:: ===================================================
set "PROJECT_ROOT=%~dp0"
echo Detected Root: %PROJECT_ROOT%

:: 1. Start the Backend Server (API)
echo [1/3] Launching Python Backend (Port 5000)...
start "FaceChain Backend" cmd /k "cd /d "%PROJECT_ROOT%backend" && python app.py"

:: 2. Start the Frontend Server (UI)
echo [2/3] Launching Frontend Interface (Port 5500)...
start "FaceChain Frontend" cmd /k "cd /d "%PROJECT_ROOT%frontend" && python -m http.server 5500"

:: 3. Wait 3 seconds for servers to boot, then open Browser
echo [3/3] Opening Browser...
timeout /t 3 >nul

:: Open the Frontend Port (5500)
start http://127.0.0.1:5500/index.html

echo.
echo ===================================================
echo       ✅ SYSTEM IS LIVE! 
echo       You should see TWO terminal windows.
echo ===================================================
pause