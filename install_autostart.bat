@echo off
setlocal
set "APP=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\Arcade Carousel.vbs"

:: Clean up old startup entries if present
if exist "%STARTUP%\Arcade Carousel.bat" del /q "%STARTUP%\Arcade Carousel.bat"
if exist "%STARTUP%\run_arcade - Shortcut.lnk" del /q "%STARTUP%\run_arcade - Shortcut.lnk"

:: 1. Add Scheduled Task with highest privileges (runs as Admin on logon)
schtasks /create /tn "ArcadeCarousel" /tr "pythonw.exe \"%APP%arcade_carousel.py\"" /sc onlogon /rl highest /f >nul 2>&1

:: 2. Also place startup VBS as fallback (arcade_carousel self-elevates if launched from here)
> "%VBS%" echo Set shell = CreateObject^("WScript.Shell"^)
>> "%VBS%" echo shell.Run "pythonw.exe ""%APP%arcade_carousel.py""", 0, False

echo ========================================================
echo Arcade Carousel autostart configured with Administrator privileges:
echo - Scheduled Task: ArcadeCarousel (highest privileges at logon)
echo - Startup script: %VBS%
echo ========================================================
pause
