@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Desktop Commander Remote - DEBUG
set "PATH=%~dp0node;%PATH%"
"%~dp0node\node.exe" "%~dp0app\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" remote --debug
pause
