param(
    [string]$OutputDir = "",
    [string]$PythonVersion = "3.12.10",
    [string]$PrometheusVersion = "3.15.0"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $root "dist"
}
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$stage = Join-Path $OutputDir "plc_exporter"
$zipPath = Join-Path $OutputDir "PLC-export-portable-win-x64.zip"
$temp = Join-Path $OutputDir "_portable_tmp"

Remove-Item -LiteralPath $stage,$temp,$zipPath -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $stage,$temp | Out-Null

Write-Host "== Application runtime =="
Get-ChildItem -LiteralPath $root -Filter "*.py" -File | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $stage
}
foreach ($dir in @("akl","dataExcelImport","gebhardt","ranpak","smartlog","teleskop","templates")) {
    Copy-Item -LiteralPath (Join-Path $root $dir) -Destination $stage -Recurse
}
Copy-Item -LiteralPath (Join-Path $root "requirements.txt") -Destination (Join-Path $stage "requirements-runtime.txt")
New-Item -ItemType Directory -Path (Join-Path $stage "var") | Out-Null

Write-Host "== Portable launchers =="
Copy-Item -LiteralPath (Join-Path $root "portable\start.bat") -Destination $stage
Copy-Item -LiteralPath (Join-Path $root "portable\stop.bat") -Destination $stage
Copy-Item -LiteralPath (Join-Path $root "portable\check.bat") -Destination $stage
Copy-Item -LiteralPath (Join-Path $root "portable\config.cmd.example") -Destination $stage
Copy-Item -LiteralPath (Join-Path $root "portable\README.txt") -Destination $stage

Write-Host "== Python embeddable $PythonVersion =="
$pythonZip = Join-Path $temp "python-embed.zip"
$pythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
Invoke-WebRequest -UseBasicParsing -Uri $pythonUrl -OutFile $pythonZip
$pythonDir = Join-Path $stage "Python"
New-Item -ItemType Directory -Path $pythonDir | Out-Null
Expand-Archive -LiteralPath $pythonZip -DestinationPath $pythonDir

$sitePackages = Join-Path $pythonDir "Lib\site-packages"
New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
python -m pip install --disable-pip-version-check --no-compile --only-binary=:all: --target $sitePackages -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Runtime dependency install failed." }

$pth = Get-ChildItem -LiteralPath $pythonDir -Filter "python*._pth" | Select-Object -First 1
if (-not $pth) { throw "Embeddable Python _pth file was not found." }
$versionParts = $PythonVersion.Split(".")
$zipStdlib = "python" + (($versionParts[0], $versionParts[1]) -join "") + ".zip"
@(
    $zipStdlib
    "."
    "Lib\site-packages"
    ".."
    "import site"
) | Set-Content -LiteralPath $pth.FullName -Encoding ASCII

Get-ChildItem -LiteralPath $sitePackages -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "== Prometheus $PrometheusVersion =="
$promZip = Join-Path $temp "prometheus.zip"
$promUrl = "https://github.com/prometheus/prometheus/releases/download/v$PrometheusVersion/prometheus-$PrometheusVersion.windows-amd64.zip"
Invoke-WebRequest -UseBasicParsing -Uri $promUrl -OutFile $promZip
$promExpanded = Join-Path $temp "prometheus"
Expand-Archive -LiteralPath $promZip -DestinationPath $promExpanded
$promSource = Get-ChildItem -LiteralPath $promExpanded -Directory | Select-Object -First 1
if (-not $promSource) { throw "Prometheus archive layout was not recognized." }
$promDest = Join-Path $stage "prometheus"
New-Item -ItemType Directory -Path (Join-Path $promDest "data") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $promSource.FullName "prometheus.exe") -Destination $promDest
foreach ($licenseFile in @("LICENSE","NOTICE")) {
    $source = Join-Path $promSource.FullName $licenseFile
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination $promDest
    }
}
Copy-Item -LiteralPath (Join-Path $root "portable\prometheus.yml") -Destination $promDest

$sha = if ($env:GITHUB_SHA) { $env:GITHUB_SHA } else { "local-build" }
@"
PLC-export portable Windows x64
Commit: $sha
Python: $PythonVersion embeddable
Prometheus: $PrometheusVersion
Runtime dependencies:
$(Get-Content -LiteralPath (Join-Path $root "requirements.txt") -Raw)
"@ | Set-Content -LiteralPath (Join-Path $stage "VERSION.txt") -Encoding UTF8

Write-Host "== Portable smoke test =="
Push-Location $stage
try {
    & ".\Python\python.exe" -c "import flask, openpyxl, xlrd, snap7; import exporter; print('PORTABLE IMPORT OK')"
    if ($LASTEXITCODE -ne 0) { throw "Portable Python import smoke test failed." }
    & ".\prometheus\prometheus.exe" --version
    if ($LASTEXITCODE -ne 0) { throw "Prometheus smoke test failed." }
}
finally {
    Pop-Location
}

Write-Host "== ZIP =="
$sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
if ($sevenZip) {
    Push-Location $OutputDir
    try {
        & $sevenZip.Source a -tzip -mx=9 -mfb=258 -mpass=15 (Split-Path -Leaf $zipPath) "plc_exporter" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "7-Zip creation failed." }
    }
    finally {
        Pop-Location
    }
}
else {
    Compress-Archive -Path $stage -DestinationPath $zipPath -CompressionLevel Optimal
}

# Ověř, že rozbalení ZIPu přímo na C:\ vytvoří C:\plc_exporter\start.bat.
$verifyDir = Join-Path $temp "zip-verify"
Remove-Item -LiteralPath $verifyDir -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath $zipPath -DestinationPath $verifyDir
if (-not (Test-Path -LiteralPath (Join-Path $verifyDir "plc_exporter\start.bat"))) {
    throw "ZIP root validation failed: plc_exporter\start.bat was not found."
}
if (-not (Test-Path -LiteralPath (Join-Path $verifyDir "plc_exporter\Python\python.exe"))) {
    throw "ZIP root validation failed: portable Python was not found."
}

$zip = Get-Item -LiteralPath $zipPath
$sizeMiB = [math]::Round($zip.Length / 1MB, 2)
if ($zip.Length -gt 180MB) {
    throw "Portable ZIP is $sizeMiB MiB; size budget is 180 MiB."
}

$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
"$($hash.Hash.ToLower())  $($zip.Name)" | Set-Content -LiteralPath (Join-Path $OutputDir "SHA256SUMS.txt") -Encoding ASCII

Write-Host "Portable ZIP: $zipPath"
Write-Host "Size: $sizeMiB MiB"
Write-Host "SHA256: $($hash.Hash)"
