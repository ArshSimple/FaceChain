@echo off
echo ===================================================
echo       🚀 STARTING FACECHAIN SYSTEM 🚀
echo ===================================================

:: 1. Start the Backend Server in a new window
echo [1/3] Launching Python Backend (Port 5000)...
start "FaceChain Backend" cmd /k "cd backend && python app.py"

:: 2. Start the Frontend Server in a new window
echo [2/3] Launching Frontend Interface (Port 5500)...
start "FaceChain Frontend" cmd /k "cd frontend && python -m http.server 5500"

:: 3. Wait 3 seconds for servers to boot, then open Chrome/Edge
echo [3/3] Opening Browser...
timeout /t 3 >nul
start http://127.0.0.1:5500/index.html

echo.
echo ===================================================
echo      ✅ SYSTEM IS LIVE! DO NOT CLOSE WINDOWS.
echo ===================================================
pause