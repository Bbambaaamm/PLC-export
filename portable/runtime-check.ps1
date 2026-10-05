param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("port", "exporter-health", "prometheus-health")]
    [string]$Mode,
    [int]$Port = 0,
    [string]$ExpectedExecutable = ""
)

$ErrorActionPreference = "Stop"

function Test-PortOwner {
    if ($Port -le 0 -or [string]::IsNullOrWhiteSpace($ExpectedExecutable)) {
        throw "Mode port vyzaduje -Port a -ExpectedExecutable."
    }

    $expected = [IO.Path]::GetFullPath($ExpectedExecutable)
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) {
        Write-Host "Port $Port neposloucha."
        exit 1
    }

    foreach ($listener in $listeners) {
        try {
            $process = Get-Process -Id $listener.OwningProcess -ErrorAction Stop
            if ([string]::IsNullOrWhiteSpace($process.Path)) {
                throw "Cesta procesu neni dostupna."
            }
            $actual = [IO.Path]::GetFullPath($process.Path)
            if (-not [string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
                Write-Host "CHYBA: port $Port pouziva jiny proces: $actual"
                exit 2
            }
        }
        catch {
            Write-Host "CHYBA: nelze overit vlastnika portu ${Port}: $($_.Exception.Message)"
            exit 2
        }
    }

    Write-Host "Port $Port vlastni ocekavany proces."
    exit 0
}

function Test-ExporterHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/metrics" -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -ne 200) {
            throw "HTTP status $($response.StatusCode)"
        }

        $required = @(
            "plc_data_valid",
            "plc_poll_total",
            "plc_data_staleness_seconds",
            "excel_data_valid",
            "event_journal_healthy"
        )
        $missing = @(
            $required | Where-Object {
                $response.Content -notmatch ("(?m)^" + [regex]::Escape($_) + "\s")
            }
        )
        if ($missing.Count -gt 0) {
            throw "Chybi ocekavane PLC metriky: $($missing -join ', ')"
        }

        ($response.Content -split [Environment]::NewLine) |
            Select-String "^(plc_data_valid|plc_poll_total|plc_data_staleness_seconds|excel_data_valid|event_journal_healthy) "
        exit 0
    }
    catch {
        Write-Host "CHYBA: PLC exporter health: $($_.Exception.Message)"
        exit 1
    }
}

function Test-PrometheusHealth {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:9090/-/healthy" -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -ne 200) {
            throw "HTTP status $($response.StatusCode)"
        }
        Write-Host $response.Content
        exit 0
    }
    catch {
        Write-Host "CHYBA: Prometheus health: $($_.Exception.Message)"
        exit 1
    }
}

switch ($Mode) {
    "port" { Test-PortOwner }
    "exporter-health" { Test-ExporterHealth }
    "prometheus-health" { Test-PrometheusHealth }
}
