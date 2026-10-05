@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo PLC Exporter - portable start
echo ==========================================

if exist "%~dp0config.cmd" (
    echo Nacitam lokalni config.cmd...
    call "%~dp0config.cmd"
)

if not exist "%~dp0Python\python.exe" (
    echo CHYBA: chybi Python\python.exe
    pause
    exit /b 1
)
if not exist "%~dp0prometheus\prometheus.exe" (
    echo CHYBA: chybi prometheus\prometheus.exe
    pause
    exit /b 1
)

if not exist "%~dp0var" mkdir "%~dp0var"
if not exist "%~dp0prometheus\data" mkdir "%~dp0prometheus\data"

set "PYTHONUTF8=1"
if not defined EVENT_DB_PATH set "EVENT_DB_PATH=%~dp0var\observations.sqlite3"
if not defined PROM_RETENTION_TIME set "PROM_RETENTION_TIME=30d"
if not defined PROM_RETENTION_SIZE set "PROM_RETENTION_SIZE=512MB"

powershell -NoProfile -Command "$x=Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue; if($x){exit 0}else{exit 1}"
if errorlevel 1 (
    echo Startuji PLC exporter...
    start "PLC Exporter" /min "%~dp0Python\python.exe" "%~dp0exporter.py"
    timeout /t 3 /nobreak >nul
) else (
    echo Port 8000 uz posloucha - exporter znovu nespoustim.
)

powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/metrics' -TimeoutSec 5 -ErrorAction Stop; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if errorlevel 1 (
    echo CHYBA: exporter na http://127.0.0.1:8000/metrics neodpovida.
    echo Prometheus nebude spusten.
    pause
    exit /b 1
)

powershell -NoProfile -Command "$x=Get-NetTCPConnection -State Listen -LocalPort 9090 -ErrorAction SilentlyContinue; if($x){exit 0}else{exit 1}"
if errorlevel 1 (
    echo Startuji Prometheus...
    start "PLC Prometheus" /min "%~dp0prometheus\prometheus.exe" --config.file="%~dp0prometheus\prometheus.yml" --storage.tsdb.path="%~dp0prometheus\data" --storage.tsdb.retention.time=%PROM_RETENTION_TIME% --storage.tsdb.retention.size=%PROM_RETENTION_SIZE%
    timeout /t 3 /nobreak >nul
) else (
    echo Port 9090 uz posloucha - Prometheus znovu nespoustim.
)

powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9090/-/healthy' -TimeoutSec 5 -ErrorAction Stop; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if errorlevel 1 (
    echo VAROVANI: Prometheus zatim neodpovida na portu 9090.
    echo Spust check.bat za nekolik sekund.
) else (
    echo.
    echo OK - PLC exporter: http://127.0.0.1:8000/metrics
    echo OK - Prometheus:   http://127.0.0.1:9090
)

echo.
echo Data Promethea jsou omezena na %PROM_RETENTION_TIME% nebo %PROM_RETENTION_SIZE% podle toho, co nastane drive.
pause
exit /b 0
