@echo off
setlocal EnableExtensions
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autostart.ps1" status
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%
