param([string]$Root = $PSScriptRoot)

$ErrorActionPreference = "Stop"

$baseConfig = Join-Path $Root "prometheus\prometheus.yml"
$runtimeConfig = Join-Path $Root "prometheus\prometheus.runtime.yml"
$tokenDir = Join-Path $env:LOCALAPPDATA "PLC-export"
$tokenPath = Join-Path $tokenDir "grafana-cloud.token"

if (-not (Test-Path -LiteralPath $baseConfig)) {
    throw "Chybi zakladni Prometheus konfigurace: $baseConfig"
}

$yaml = (Get-Content -LiteralPath $baseConfig -Raw).TrimEnd() + [Environment]::NewLine
$cloudEnabled = $false

if (Test-Path -LiteralPath $tokenPath) {
    $token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
    if (-not [string]::IsNullOrWhiteSpace($token)) {
        $passwordFile = $tokenPath.Replace("\", "/").Replace("'", "''")
        $yaml += @"

remote_write:
  - url: https://prometheus-prod-24-prod-eu-west-2.grafana.net/api/prom/push
    basic_auth:
      username: "1009857"
      password_file: '$passwordFile'
"@
        $cloudEnabled = $true
    }
}

[IO.File]::WriteAllText($runtimeConfig, $yaml, [Text.UTF8Encoding]::new($false))

if ($cloudEnabled) {
    Write-Host "Grafana Cloud remote_write: ENABLED"
} else {
    Write-Host "Grafana Cloud remote_write: disabled (token neni ulozen)"
}
Write-Host "Prometheus config: $runtimeConfig"
