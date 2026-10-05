@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "FAILED=0"

echo === Node ===
"%~dp0node\node.exe" --version
if errorlevel 1 set "FAILED=1"

echo.
echo === Desktop Commander Remote CLI ===
"%~dp0node\node.exe" "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" remote --help
if errorlevel 1 set "FAILED=1"

echo.
echo === ripgrep ===
"%~dp0node\node.exe" "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\npm-scripts\verify-ripgrep.js"
if errorlevel 1 set "FAILED=1"

echo.
if "%FAILED%"=="0" (
    echo CHECK OK - portable runtime je pripraven.
    echo Sit a prihlaseni se overi az pri start.bat.
) else (
    echo CHECK FAILED - viz zpravy vyse.
)
pause
exit /b %FAILED%
