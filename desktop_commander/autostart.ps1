param(
    [ValidateSet("enable", "disable", "status")]
    [string]$Action = "enable"
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$launcher = Join-Path $root "start-hidden.vbs"
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Desktop Commander.lnk"

function Get-WScriptPath {
    $path = Join-Path $env:SystemRoot "System32\wscript.exe"
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Chybi Windows Script Host: $path"
    }
    return $path
}

function Enable-Autostart {
    if (-not (Test-Path -LiteralPath $launcher)) {
        throw "Chybi launcher: $launcher"
    }

    $wscript = Get-WScriptPath
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wscript
    $shortcut.Arguments = '"' + $launcher + '"'
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = "Desktop Commander - hidden startup"
    $shortcut.WindowStyle = 7
    $shortcut.Save()

    Write-Host "AUTOSTART ENABLED"
    Write-Host "Desktop Commander se spusti skryte po prihlaseni tohoto Windows uzivatele."
    Write-Host "Shortcut: $shortcutPath"
    Write-Host "Launcher: $launcher"
}

function Disable-Autostart {
    Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
    Write-Host "AUTOSTART DISABLED"
    Write-Host "Shortcut odstranen: $shortcutPath"
}

function Show-Status {
    if (-not (Test-Path -LiteralPath $shortcutPath)) {
        Write-Host "MODE: DISABLED"
        return 1
    }

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $expectedTarget = Get-WScriptPath
    $expectedArgs = '"' + $launcher + '"'

    if (-not [string]::Equals($shortcut.TargetPath, $expectedTarget, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "MODE: INVALID"
        Write-Host "Unexpected target: $($shortcut.TargetPath)"
        return 2
    }

    if (-not [string]::Equals($shortcut.Arguments, $expectedArgs, [StringComparison]::Ordinal)) {
        Write-Host "MODE: INVALID"
        Write-Host "Unexpected arguments: $($shortcut.Arguments)"
        return 2
    }

    Write-Host "MODE: STARTUP"
    Write-Host "Spusteni: po prihlaseni uzivatele"
    Write-Host "Shortcut: $shortcutPath"
    Write-Host "Launcher: $launcher"
    return 0
}

switch ($Action) {
    "enable" { Enable-Autostart }
    "disable" { Disable-Autostart }
    "status" { exit (Show-Status) }
}
