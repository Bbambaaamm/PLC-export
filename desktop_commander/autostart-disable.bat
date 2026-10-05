@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autostart.ps1" disable
if errorlevel 1 (
    echo.
    echo CHYBA: automaticke spousteni Desktop Commanderu se nepodarilo vypnout.
    pause
    exit /b 1
)

echo.
echo Automaticke spousteni Desktop Commanderu je vypnute.
pause
exit /b 0
