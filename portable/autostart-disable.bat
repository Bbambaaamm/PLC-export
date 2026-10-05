@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autostart.ps1" disable
if errorlevel 1 (
    echo.
    echo CHYBA: automaticke spousteni se nepodarilo vypnout.
    pause
    exit /b 1
)

echo.
echo Automaticke spousteni je vypnute.
pause
exit /b 0
