param(
    [ValidateSet("enable", "disable", "status")]
    [string]$Action = "enable"
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$launcher = Join-Path $root "start-hidden.vbs"
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "PLC Exporter.lnk"

switch ($Action) {
    "enable" {
        if (-not (Test-Path -LiteralPath $launcher)) {
            throw "Chybi launcher: $launcher"
        }

        $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
        if (-not (Test-Path -LiteralPath $wscript)) {
            throw "Chybi Windows Script Host: $wscript"
        }

        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $wscript
        $shortcut.Arguments = '"' + $launcher + '"'
        $shortcut.WorkingDirectory = $root
        $shortcut.Description = "PLC Exporter - hidden startup"
        $shortcut.WindowStyle = 7
        $shortcut.Save()

        Write-Host "AUTOSTART ENABLED"
        Write-Host "Po prihlaseni do Windows se PLC Exporter spusti skryte."
        Write-Host "Shortcut: $shortcutPath"
        Write-Host "Launcher: $launcher"
    }

    "disable" {
        Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
        Write-Host "AUTOSTART DISABLED"
        Write-Host "Shortcut odstraneny: $shortcutPath"
    }

    "status" {
        if (Test-Path -LiteralPath $shortcutPath) {
            Write-Host "AUTOSTART ENABLED"
            Write-Host $shortcutPath
            exit 0
        }

        Write-Host "AUTOSTART DISABLED"
        exit 1
    }
}
