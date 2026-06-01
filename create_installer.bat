@echo off
chcp 65001 >nul
title Car AI System Installer Builder

echo ========================================
echo   CAR AI SYSTEM - INSTALLER BUILDER
echo ========================================
echo.

echo 🔧 Building installer...
python build_installer.py

if errorlevel 1 (
    echo.
    echo ❌ Build failed!
    pause
    exit /b 1
)

echo.
echo ✅ Build completed successfully!
echo 📦 Your installer is ready: Output\CarAISystem_Setup.exe
echo.
echo 🎯 You can now give this single file to your friend!
echo.
pause