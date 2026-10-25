@echo off
setlocal
cd /d "%~dp0"
title Arcade Carousel - Setup ^& Dependency Installer

:: Check for Administrator elevation. If not elevated, relaunch cleanly with 'RunAs'.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ============================================================
    echo Requesting Administrator privileges to configure Python,
    echo Windows PATH, and install all Arcade Carousel dependencies...
    echo ============================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: Run the automated PowerShell installer
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_requirements.ps1"

echo.
pause
