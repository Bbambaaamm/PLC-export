$ErrorActionPreference = "Stop"

$tokenDir = Join-Path $env:LOCALAPPDATA "PLC-export"
$tokenPath = Join-Path $tokenDir "grafana-cloud.token"

Write-Host "=========================================="
Write-Host "Grafana Cloud setup - PLC Exporter"
Write-Host "=========================================="
Write-Host "Metrics ID: 1009857"
Write-Host "Endpoint: https://prometheus-prod-24-prod-eu-west-2.grafana.net/api/prom/push"
Write-Host ""
Write-Host "Vloz token z access policy stack-654487-hm-write (scope metrics:write)."
Write-Host "Token se nebude zobrazovat ani ukladat do C:\plc_exporter."
Write-Host ""

$secure = Read-Host "Grafana Cloud token" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($token)) { throw "Token je prazdny." }

    New-Item -ItemType Directory -Path $tokenDir -Force | Out-Null
    [IO.File]::WriteAllText($tokenPath, $token.Trim(), [Text.UTF8Encoding]::new($false))
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

Write-Host ""
Write-Host "OK - token ulozen mimo portable slozku:"
Write-Host $tokenPath
Write-Host "Pri dalsich updatech C:\plc_exporter zustane zachovan."
