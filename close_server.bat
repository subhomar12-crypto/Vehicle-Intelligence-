@echo off
echo Killing PREDICT server...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM uvicorn.exe 2>nul
echo Server killed.
pause
