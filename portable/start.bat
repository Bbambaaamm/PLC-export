@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "HIDDEN_MODE=0"
set "BOOT_MODE=0"
if /I "%~1"=="--hidden" set "HIDDEN_MODE=1"
if /I "%~2"=="--hidden" set "HIDDEN_MODE=1"
if /I "%~1"=="--boot" set "BOOT_MODE=1"
if /I "%~2"=="--boot" set "BOOT_MODE=1"

echo ==========================================
echo PLC Exporter - portable start
echo ==========================================

if exist "%~dp0config.cmd" (
    echo Nacitam lokalni config.cmd...
    call "%~dp0config.cmd"
)
if "%BOOT_MODE%"=="1" if exist "%~dp0config.boot.cmd" (
    echo Nacitam boot override config.boot.cmd...
    call "%~dp0config.boot.cmd"
)

if not exist "%~dp0Python\python.exe" (
    echo CHYBA: chybi Python\python.exe
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)
if not exist "%~dp0prometheus\prometheus.exe" (
    echo CHYBA: chybi prometheus\prometheus.exe
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare-prometheus.ps1"
if errorlevel 1 (
    echo CHYBA: nepodarilo se pripravit Prometheus konfiguraci.
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)

if not exist "%~dp0var" mkdir "%~dp0var"
if not exist "%~dp0prometheus\data" mkdir "%~dp0prometheus\data"

set "PYTHONUTF8=1"
if not defined EVENT_DB_PATH set "EVENT_DB_PATH=%~dp0var\observations.sqlite3"
if not defined PROM_RETENTION_TIME set "PROM_RETENTION_TIME=30d"
if not defined PROM_RETENTION_SIZE set "PROM_RETENTION_SIZE=512MB"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode port -Port 8000 -ExpectedExecutable "%~dp0Python\python.exe"
set "PORT8000_RC=%ERRORLEVEL%"
if "%PORT8000_RC%"=="2" (
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)
if "%PORT8000_RC%"=="1" (
    echo Startuji PLC exporter...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-hidden.ps1" exporter
    if errorlevel 1 (
        echo CHYBA: PLC exporter se nepodarilo spustit.
        if "%HIDDEN_MODE%"=="0" pause
        exit /b 1
    )
    timeout /t 3 /nobreak >nul
) else (
    echo Port 8000 uz pouziva tato instance PLC Exporteru - znovu nespoustim.
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode exporter-health
if errorlevel 1 (
    echo CHYBA: exporter na http://127.0.0.1:8000/metrics neodpovida.
    echo Prometheus nebude spusten.
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode port -Port 9090 -ExpectedExecutable "%~dp0prometheus\prometheus.exe"
set "PORT9090_RC=%ERRORLEVEL%"
if "%PORT9090_RC%"=="2" (
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)
if "%PORT9090_RC%"=="1" (
    echo Startuji Prometheus...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch-hidden.ps1" prometheus
    if errorlevel 1 (
        echo CHYBA: Prometheus se nepodarilo spustit.
        if "%HIDDEN_MODE%"=="0" pause
        exit /b 1
    )
    timeout /t 3 /nobreak >nul
) else (
    echo Port 9090 uz pouziva tato instance Promethea - znovu nespoustim.
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime-check.ps1" -Mode prometheus-health
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
if "%HIDDEN_MODE%"=="0" pause
exit /b 0
