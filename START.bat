@echo off
title MerakiMind AIOps Platform Launcher (Windows)
color 0A
cd /d "%~dp0"

echo ========================================================
echo   MerakiMind v4.0 / v5.0 — AI Network Intelligence
echo ========================================================
echo.

echo 🧹 Cleaning up existing processes on ports 8765 and 5173...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo 🚀 Starting MerakiMind Multi-Agent Backend (Python)...
start "MerakiMind Backend (:8765)" cmd /k "python server.py"

echo 🚀 Starting React + Vite Frontend Dev Server (Node.js)...
cd frontend
start "MerakiMind Frontend (:5173)" cmd /k "npm run dev"
cd ..

timeout /t 3 /nobreak >nul
echo 🌐 Opening Dashboard at http://localhost:5173 ...
start http://localhost:5173

echo.
echo ✅ Dashboard launched at http://localhost:5173
echo 💡 To stop MerakiMind, close the opened command prompt windows.
echo.
