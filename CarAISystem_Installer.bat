@echo off
chcp 65001 >nul
title Car AI System Installer
setlocal enabledelayedexpansion

echo ========================================
echo   CAR AI SYSTEM - COMPLETE INSTALLER
echo ========================================
echo.

set INSTALL_DIR=%USERPROFILE%\CarAISystem

echo 🔍 Checking if Python is installed...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found!
    echo.
    echo 📥 Please install Python 3.8+ from:
    echo    https://www.python.org/downloads/
    echo.
    echo 💡 During installation, MAKE SURE to check:
    echo    "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo ✅ Python is installed
echo.

echo 📁 Creating installation directory...
if exist "%INSTALL_DIR%" (
    echo ⚠️ Installation directory already exists. Overwriting...
    rmdir /s /q "%INSTALL_DIR%" >nul 2>&1
)
mkdir "%INSTALL_DIR%"

echo 📦 Copying application files...
copy "main.py" "%INSTALL_DIR%" >nul && echo ✅ main.py
copy "ai_module.py" "%INSTALL_DIR%" >nul && echo ✅ ai_module.py
copy "connectivity_module.py" "%INSTALL_DIR%" >nul && echo ✅ connectivity_module.py
copy "server_module.py" "%INSTALL_DIR%" >nul && echo ✅ server_module.py
copy "gui_module.py" "%INSTALL_DIR%" >nul && echo ✅ gui_module.py
copy "run.bat" "%INSTALL_DIR%" >nul && echo ✅ run.bat

echo 📁 Creating data directories...
mkdir "%INSTALL_DIR%\ai_model_storage" >nul 2>&1
mkdir "%INSTALL_DIR%\vehicle_data" >nul 2>&1

echo.
echo 🔧 Installing Python dependencies...
echo 📥 This may take a few minutes...
echo.

echo Installing core data science libraries...
pip install pandas numpy scikit-learn matplotlib

echo Installing connectivity libraries...
pip install obd bleak requests

echo Installing AI libraries...
pip install xgboost shap

echo Installing optional libraries...
pip install tensorflow

echo.
echo 🎉 INSTALLATION COMPLETE!
echo.
echo ========================================
echo   QUICK START GUIDE
echo ========================================
echo.
echo 🚗 TO START THE APPLICATION:
echo.
echo Method 1 - Easy:
echo   Double-click: "%INSTALL_DIR%\run.bat"
echo.
echo Method 2 - Manual:
echo   1. Open: "%INSTALL_DIR%"
echo   2. Double-click: "run.bat"
echo.
echo Method 3 - Command Line:
echo   cd "%INSTALL_DIR%"
echo   python main.py
echo.
echo 📍 Location: %INSTALL_DIR%
echo.
echo 🔧 Features Included:
echo   ✅ Real-time OBD-II monitoring
echo   ✅ Bluetooth connectivity  
echo   ✅ AI failure prediction
echo   ✅ Vehicle profiles
echo   ✅ D: Drive server
echo.
pause