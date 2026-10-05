@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PATH=%~dp0node;%PATH%"
"%~dp0node\node.exe" "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" remote --logout
echo.
echo Lokalni prihlaseni bylo odebrano. Pro uplne odebrani zarizeni pouzij i dashboard Desktop Commanderu.
pause
