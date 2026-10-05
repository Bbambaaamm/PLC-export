@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "FAILED=0"

echo === Portable Python ===
"%~dp0Python\python.exe" --version
if errorlevel 1 set "FAILED=1"

echo.
echo === Runtime importy ===
"%~dp0Python\python.exe" -c "import flask, openpyxl, xlrd, snap7; import exporter; print('IMPORT OK')"
if errorlevel 1 set "FAILED=1"

echo.
echo === PLC exporter /metrics ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode port -Port 8000 -ExpectedExecutable "%~dp0Python\python.exe"
if errorlevel 1 (
    set "FAILED=1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode exporter-health
)
if errorlevel 1 set "FAILED=1"

echo.
echo === Prometheus ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode port -Port 9090 -ExpectedExecutable "%~dp0prometheus\prometheus.exe"
if errorlevel 1 (
    set "FAILED=1"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode prometheus-health
    if errorlevel 1 set "FAILED=1"
)

echo.
echo === Grafana Cloud ===
if exist "%LOCALAPPDATA%\PLC-export\grafana-cloud.token" (
    echo Token: ulozen mimo C:\plc_exporter
    findstr /C:"remote_write:" "%~dp0prometheus\prometheus.runtime.yml" >nul 2>&1
    if errorlevel 1 (
        echo VAROVANI: runtime config nema remote_write. Restartuj stop.bat + start-hidden.vbs.
    ) else (
        echo remote_write: nakonfigurovan
    )
) else (
    echo Grafana Cloud: token zatim neni ulozen.
    echo Jednou spust grafana-cloud-setup.bat.
)

echo.
echo === Autostart ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autostart.ps1" status
if errorlevel 1 echo INFO: autostart neni aktivni; runtime muze byt presto v poradku.

echo.
if "%FAILED%"=="0" (
    echo CHECK OK
) else (
    echo CHECK FAILED - viz zpravy vyse.
)
pause
exit /b %FAILED%
