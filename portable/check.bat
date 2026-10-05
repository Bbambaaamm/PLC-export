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
powershell -NoProfile -Command "$expected=[IO.Path]::GetFullPath('%~dp0Python\python.exe'); $xs=Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; if(-not $xs){Write-Host 'Port 8000 neposloucha.'; exit 1}; foreach($x in $xs){try{$p=Get-Process -Id $x.OwningProcess -ErrorAction Stop; $actual=[IO.Path]::GetFullPath($p.Path); if(-not [string]::Equals($actual,$expected,[StringComparison]::OrdinalIgnoreCase)){Write-Host ('Port 8000 pouziva jiny proces: ' + $actual); exit 1}}catch{Write-Host ('Nelze overit vlastnika portu 8000: ' + $_.Exception.Message); exit 1}}; try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/metrics' -TimeoutSec 5 -ErrorAction Stop; $required=@('plc_data_valid','plc_poll_total','plc_data_staleness_seconds','excel_data_valid','event_journal_healthy'); $missing=@($required | Where-Object {$r.Content -notmatch ('(?m)^' + [regex]::Escape($_) + '\s')}); if($missing.Count -gt 0){Write-Host ('Chybi ocekavane PLC metriky: ' + ($missing -join ', ')); exit 1}; ($r.Content -split [Environment]::NewLine) | Select-String '^(plc_data_valid|plc_poll_total|plc_data_staleness_seconds|excel_data_valid|event_journal_healthy) '; exit 0}catch{Write-Host $_.Exception.Message; exit 1}"
if errorlevel 1 set "FAILED=1"

echo.
echo === Prometheus ===
powershell -NoProfile -Command "$expected=[IO.Path]::GetFullPath('%~dp0prometheus\prometheus.exe'); $xs=Get-NetTCPConnection -State Listen -LocalPort 9090 -ErrorAction SilentlyContinue; if(-not $xs){Write-Host 'Port 9090 neposloucha.'; exit 1}; foreach($x in $xs){try{$p=Get-Process -Id $x.OwningProcess -ErrorAction Stop; $actual=[IO.Path]::GetFullPath($p.Path); if(-not [string]::Equals($actual,$expected,[StringComparison]::OrdinalIgnoreCase)){Write-Host ('Port 9090 pouziva jiny proces: ' + $actual); exit 1}}catch{Write-Host ('Nelze overit vlastnika portu 9090: ' + $_.Exception.Message); exit 1}}; try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9090/-/healthy' -TimeoutSec 5 -ErrorAction Stop; Write-Host $r.Content; exit 0}catch{Write-Host $_.Exception.Message; exit 1}"
if errorlevel 1 set "FAILED=1"

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
