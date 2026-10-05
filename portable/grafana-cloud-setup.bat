@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0grafana-cloud-setup.ps1"
if errorlevel 1 (
    echo.
    echo CHYBA: Grafana Cloud token se nepodarilo ulozit.
    pause
    exit /b 1
)

echo.
echo Token je ulozen. Pokud Prometheus uz bezi, spust stop.bat a potom start.bat.
echo Pri dalsich updatech ZIPu token zustane zachovan.
pause
exit /b 0
