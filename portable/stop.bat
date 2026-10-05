@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Zastavuji pouze procesy z teto portable slozky na portech 8000 a 9090...
powershell -NoProfile -Command "$root=[IO.Path]::GetFullPath('%~dp0'); $ids=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.LocalPort -eq 8000 -or $_.LocalPort -eq 9090} | Select-Object -ExpandProperty OwningProcess -Unique; foreach($id in $ids){try{$p=Get-Process -Id $id -ErrorAction Stop; $path=$p.Path; if($path -and [IO.Path]::GetFullPath($path).StartsWith($root,[StringComparison]::OrdinalIgnoreCase)){Write-Host ('Stop ' + $p.ProcessName + ' PID=' + $id); Stop-Process -Id $id -Force -ErrorAction Stop}}catch{Write-Host $_.Exception.Message}}"

echo Hotovo.
pause
