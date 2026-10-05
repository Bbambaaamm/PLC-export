param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("exporter", "prometheus")]
    [string]$Component
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Start-NoConsoleProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $psi.Arguments = $Arguments
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

    $process = [System.Diagnostics.Process]::Start($psi)
    if ($null -eq $process) {
        throw "Proces se nepodarilo spustit: $FilePath"
    }
}

switch ($Component) {
    "exporter" {
        $python = Join-Path $root "Python\python.exe"
        $script = Join-Path $root "exporter.py"
        Start-NoConsoleProcess -FilePath $python -Arguments ('"' + $script + '"') -WorkingDirectory $root
    }

    "prometheus" {
        $prometheus = Join-Path $root "prometheus\prometheus.exe"
        $config = Join-Path $root "prometheus\prometheus.runtime.yml"
        $data = Join-Path $root "prometheus\data"

        $retentionTime = if ($env:PROM_RETENTION_TIME) { $env:PROM_RETENTION_TIME } else { "30d" }
        $retentionSize = if ($env:PROM_RETENTION_SIZE) { $env:PROM_RETENTION_SIZE } else { "512MB" }

        $arguments = @(
            '--config.file="' + $config + '"'
            '--storage.tsdb.path="' + $data + '"'
            '--storage.tsdb.retention.time=' + $retentionTime
            '--storage.tsdb.retention.size=' + $retentionSize
        ) -join " "

        Start-NoConsoleProcess -FilePath $prometheus -Arguments $arguments -WorkingDirectory (Join-Path $root "prometheus")
    }
}
