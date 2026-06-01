@echo off
chcp 65001 >nul
title PREDICT Vehicle Intelligence Platform
cd /d "%~dp0"

echo ============================================================
echo  PREDICT v3.0.0 - Vehicle Intelligence Platform
echo ============================================================
echo.

REM Check Python
python --version 2>nul
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.12+ and ensure it is in your PATH.
    pause
    exit /b 1
)

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Create data directories
if not exist "data\logs" mkdir data\logs
if not exist "data\backups" mkdir data\backups
if not exist "data\parquet" mkdir data\parquet
if not exist "data\exports" mkdir data\exports

echo Starting Desktop mode...
python -m predict --desktop

echo.
pause
