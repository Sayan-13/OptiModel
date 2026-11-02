@echo off
setlocal

:: ------------------------------------------------------------------
::  One-Click Starter: BPMN Workflow Analysis & Optimization System
:: ------------------------------------------------------------------

cd /d "%~dp0"

:: 1. Ensure a virtual environment exists
if not exist "backend\.venv" (
    echo [INFO] Creating Python virtual environment in backend\.venv ...
    python -m venv backend\.venv
    call backend\.venv\Scripts\activate
    pip install -r backend\requirements.txt
) else (
    call backend\.venv\Scripts\activate
)

:: 2. Launch FastAPI backend in its own window
echo [INFO] Starting FastAPI Backend on http://localhost:8000 ...
start "BPMN Analyzer - Backend API" cmd /k "cd /d "%~dp0backend" && ..\backend\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000"

:: 3. Launch Frontend HTTP Server in its own window
echo [INFO] Starting Frontend Web Server on http://localhost:8080 ...
start "BPMN Analyzer - Frontend UI" cmd /k "cd /d "%~dp0frontend" && python -m http.server 8080"

:: 4. Wait 3 seconds and open in default browser
echo [INFO] Launching dashboard in your default browser...
ping -n 4 127.0.0.1 >nul 2>&1
start "" "http://localhost:8080"

echo [SUCCESS] System started! You can upload 1.xml or 2.xml to analyze and optimize.
endlocal
