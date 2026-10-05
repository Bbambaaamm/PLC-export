@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Desktop Commander Remote

set "HIDDEN_MODE=0"
if /I "%~1"=="--hidden" set "HIDDEN_MODE=1"

echo ==========================================
echo Desktop Commander Remote - portable
echo ==========================================
echo.

if not exist "%~dp0node\node.exe" (
    echo CHYBA: chybi node\node.exe
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)

if not exist "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" (
    echo CHYBA: chybi Desktop Commander runtime.
    if "%HIDDEN_MODE%"=="0" pause
    exit /b 1
)

set "PATH=%~dp0node;%PATH%"

if "%HIDDEN_MODE%"=="0" (
    echo Prvni spusteni otevre autorizaci v prohlizeci.
    echo Po sparovani nech toto okno otevrene.
    echo.
)
"%~dp0node\node.exe" "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" remote

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Desktop Commander skoncil s kodem %RC%.
echo Pro znovupripojeni spust znovu start.bat.
if "%HIDDEN_MODE%"=="0" pause
exit /b %RC%
