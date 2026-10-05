@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Desktop Commander Remote

echo ==========================================
echo Desktop Commander Remote - portable
echo ==========================================
echo.

if not exist "%~dp0node\node.exe" (
    echo CHYBA: chybi node\node.exe
    pause
    exit /b 1
)

if not exist "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" (
    echo CHYBA: chybi Desktop Commander runtime.
    pause
    exit /b 1
)

set "PATH=%~dp0node;%PATH%"

echo Prvni spusteni otevre autorizaci v prohlizeci.
echo Po sparovani nech toto okno otevrene.
echo.
"%~dp0node\node.exe" "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" remote

set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Desktop Commander skoncil s kodem %RC%.
echo Pro znovupripojeni spust znovu start.bat.
pause
exit /b %RC%
