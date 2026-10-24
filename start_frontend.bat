@echo off
rem Start the React frontend development server.
rem Run this in a second terminal after start_server.bat is running.

set FRONTEND_DIR=%~dp0frontend

echo ============================================
echo  AI Adaptive Exam System - Frontend Dev Server
echo ============================================
echo.
echo Frontend URL: http://localhost:5173
echo Backend API : http://127.0.0.1:8000
echo.
echo Make sure start_server.bat is running before using the frontend.
echo Press Ctrl+C to stop.
echo.

cd /d "%FRONTEND_DIR%"
npm run dev

pause
