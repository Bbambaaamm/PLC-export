@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Zkousim nejprve start pri bootu pres Windows Task Scheduler.
echo Pokud to prava nebo firemni politika nepovoli, nastavi se Startup fallback.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autostart.ps1" enable
if errorlevel 1 (
    echo.
    echo CHYBA: automaticke spousteni se nepodarilo nastavit.
    pause
    exit /b 1
)

echo.
echo Hotovo. Vysledny rezim zkontroluj pres autostart-status.bat.
pause
exit /b 0
