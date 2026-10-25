@echo off
cd /d "%~dp0"

:: Check for Administrator elevation. If not elevated, relaunch cleanly with 'RunAs'.
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'pythonw.exe' -ArgumentList '\"%~dp0arcade_carousel.py\"' -Verb RunAs"
    exit /b
)

:: Already elevated: run Arcade Carousel without console window
start "" pythonw.exe "%~dp0arcade_carousel.py"
exit /b
