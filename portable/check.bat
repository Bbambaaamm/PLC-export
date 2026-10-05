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
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/metrics' -TimeoutSec 5 -ErrorAction Stop; ($r.Content -split [Environment]::NewLine) | Select-String '^(plc_data_valid|plc_poll_total|plc_data_staleness_seconds|excel_data_valid|event_journal_healthy) '; exit 0}catch{Write-Host $_.Exception.Message; exit 1}"
if errorlevel 1 set "FAILED=1"

echo.
echo === Prometheus ===
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9090/-/healthy' -TimeoutSec 5 -ErrorAction Stop; Write-Host $r.Content; exit 0}catch{Write-Host $_.Exception.Message; exit 1}"
if errorlevel 1 set "FAILED=1"

echo.
if "%FAILED%"=="0" (
    echo CHECK OK
) else (
    echo CHECK FAILED - viz zpravy vyse.
)
pause
exit /b %FAILED%
