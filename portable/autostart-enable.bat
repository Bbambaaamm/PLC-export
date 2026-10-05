@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autostart.ps1" enable
if errorlevel 1 (
    echo.
    echo CHYBA: automaticke spousteni se nepodarilo zapnout.
    pause
    exit /b 1
)

echo.
echo Hotovo. Admin prava nejsou potreba.
echo PLC Exporter se spusti skryte po prihlaseni uzivatele do Windows.
pause
exit /b 0
