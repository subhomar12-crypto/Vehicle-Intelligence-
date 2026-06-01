@echo off
chcp 65001 >nul
echo 🚗 OBD-II Monitoring System Quick Start
echo ========================================
echo.

echo 🔧 Checking Python installation...
"C:\Program Files\Python312\python.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo 💡 Please install Python from https://"C:\Program Files\Python312\python.exe".org
    pause
    exit /b 1
)

echo ✅ Python is installed

echo.
echo 📦 Installing dependencies...
"C:\Program Files\Python312\python.exe" install_dependencies.py

echo.
echo 🧪 Testing connection...
"C:\Program Files\Python312\python.exe" test_connection.py

echo.
echo 🚀 Starting main application...
"C:\Program Files\Python312\python.exe" gui_module.py

pause