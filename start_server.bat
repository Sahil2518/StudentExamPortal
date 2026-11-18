@echo off
rem Start the AI Adaptive Exam System backend server.
rem
rem Root cause: the venv at C:\Users\Sahil\OneDrive\Desktop\StudentExamPortal\venv
rem is stored on OneDrive which causes OSError [Errno 22] when Python reads
rem .pyc bytecode cache files (OneDrive uses file placeholders for cloud-only files).
rem
rem Solution: Use a proper local environment that does NOT
rem have this OneDrive sync issue.
rem
rem Usage:
rem   Double-click this file, OR
rem   Open a command prompt at the project root and run: start_server.bat

set PROJECT_DIR=%~dp0ai_exam_system
set PYTHONPATH=%PROJECT_DIR%

echo ============================================
echo  AI Adaptive Exam System - Backend Server
echo ============================================
echo.
echo Server URL  : http://127.0.0.1:8000
echo API Docs    : http://127.0.0.1:8000/docs
echo Health check: http://127.0.0.1:8000/ready
echo.
echo Press Ctrl+C to stop.
echo.

if exist "%PROJECT_DIR%\venv\Scripts\python.exe" (
    echo Using project virtualenv: %PROJECT_DIR%\venv\Scripts\python.exe
    "%PROJECT_DIR%\venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir "%PROJECT_DIR%"
) else if exist "%~dp0venv\Scripts\python.exe" (
    echo Using root virtualenv: %~dp0venv\Scripts\python.exe
    "%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir "%PROJECT_DIR%"
) else (
    echo Using system Python
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir "%PROJECT_DIR%"
)

pause
