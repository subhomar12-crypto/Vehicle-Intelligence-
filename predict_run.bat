@echo off
title PREDICT Vehicle Intelligence Platform
echo ============================================================
echo  PREDICT v3.0.0 - Vehicle Intelligence Platform
echo ============================================================
echo.

REM Check Python
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    pause
    exit /b 1
)

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install dependencies if needed
if not exist "venv\Lib\site-packages\fastapi" (
    echo Installing dependencies...
    pip install -e ".[dev]"
)

REM Create data directories
if not exist "data\logs" mkdir data\logs
if not exist "data\backups" mkdir data\backups
if not exist "data\parquet" mkdir data\parquet
if not exist "data\exports" mkdir data\exports

echo.
echo Choose mode:
echo   1. Desktop (GUI + Server)
echo   2. Headless (Server only)
echo   3. Run tests
echo   4. Run migrations (alembic upgrade head)
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo Starting Desktop mode...
    python -m predict --desktop
) else if "%choice%"=="2" (
    echo Starting Headless mode...
    python -m predict --headless --host 0.0.0.0 --port 8000
) else if "%choice%"=="3" (
    echo Running tests...
    pytest tests/ -v --tb=short
) else if "%choice%"=="4" (
    echo Running migrations...
    alembic upgrade head
) else (
    echo Invalid choice
)

pause
