param(
    [string]$OutputDir = "",
    [string]$NodeVersion = "22.23.3",
    [string]$DesktopCommanderVersion = "0.2.52"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $root "dist-desktop-commander"
}
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$stage = Join-Path $OutputDir "desktop_commander"
$zipPath = Join-Path $OutputDir "Desktop-Commander-Portable-win-x64.zip"
$temp = Join-Path $OutputDir "_tmp"

Remove-Item -LiteralPath $stage,$temp,$zipPath -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $stage,$temp | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stage "node"),(Join-Path $stage "app") | Out-Null

Write-Host "== Node.js $NodeVersion portable =="
$nodeArchiveName = "node-v$NodeVersion-win-x64.zip"
$nodeZip = Join-Path $temp $nodeArchiveName
$nodeUrl = "https://nodejs.org/dist/v$NodeVersion/$nodeArchiveName"
$nodeSumsUrl = "https://nodejs.org/dist/v$NodeVersion/SHASUMS256.txt"
$sumsPath = Join-Path $temp "SHASUMS256-node.txt"

Invoke-WebRequest -UseBasicParsing -Uri $nodeUrl -OutFile $nodeZip
Invoke-WebRequest -UseBasicParsing -Uri $nodeSumsUrl -OutFile $sumsPath

$sumLine = Get-Content -LiteralPath $sumsPath | Where-Object { $_ -match ([regex]::Escape($nodeArchiveName) + '$') } | Select-Object -First 1
if (-not $sumLine) { throw "Node SHA256 entry was not found." }
$expectedNodeHash = ($sumLine -split '\s+')[0].ToLowerInvariant()
$actualNodeHash = (Get-FileHash -LiteralPath $nodeZip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualNodeHash -ne $expectedNodeHash) {
    throw "Node archive SHA256 mismatch."
}

$nodeExpanded = Join-Path $temp "node"
Expand-Archive -LiteralPath $nodeZip -DestinationPath $nodeExpanded
$nodeSource = Get-ChildItem -LiteralPath $nodeExpanded -Directory | Select-Object -First 1
if (-not $nodeSource) { throw "Node archive layout was not recognized." }
Copy-Item -LiteralPath (Join-Path $nodeSource.FullName "node.exe") -Destination (Join-Path $stage "node\node.exe")
if (Test-Path -LiteralPath (Join-Path $nodeSource.FullName "LICENSE")) {
    Copy-Item -LiteralPath (Join-Path $nodeSource.FullName "LICENSE") -Destination (Join-Path $stage "node\NODE_LICENSE.txt")
}

Write-Host "== Desktop Commander $DesktopCommanderVersion =="
$appDir = Join-Path $stage "app"
@"
{
  "private": true,
  "name": "desktop-commander-portable-runtime",
  "version": "1.0.0"
}
"@ | Set-Content -LiteralPath (Join-Path $appDir "package.json") -Encoding UTF8

Push-Location $appDir
try {
    npm.cmd install --omit=dev --no-audit --no-fund --save-exact "@wonderwhy-er/desktop-commander@$DesktopCommanderVersion"
    if ($LASTEXITCODE -ne 0) { throw "Desktop Commander npm install failed." }
}
finally {
    Pop-Location
}

$dcRoot = Join-Path $appDir "node_modules\@wonderwhy-er\desktop-commander"
$dcIndex = Join-Path $dcRoot "dist\index.js"
$rgVerify = Join-Path $dcRoot "dist\npm-scripts\verify-ripgrep.js"
if (-not (Test-Path -LiteralPath $dcIndex)) { throw "Desktop Commander dist/index.js is missing." }
if (-not (Test-Path -LiteralPath $rgVerify)) { throw "Desktop Commander ripgrep verifier is missing." }

# Remove files that are not needed for the remote runtime.
Remove-Item -LiteralPath (Join-Path $dcRoot "testemonials") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $dcRoot "logo.png") -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $appDir -Directory -Recurse -Filter ".cache" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "== Launchers =="
foreach ($file in @("start.bat","debug.bat","logout.bat","check.bat","README.txt")) {
    Copy-Item -LiteralPath (Join-Path $root "desktop_commander\$file") -Destination $stage
}

$sha = if ($env:GITHUB_SHA) { $env:GITHUB_SHA } else { "local-build" }
@"
Desktop Commander Portable Windows x64
Build commit: $sha
Node.js: $NodeVersion
Desktop Commander: $DesktopCommanderVersion
Node archive SHA256: $actualNodeHash
Upstream: https://github.com/wonderwhy-er/DesktopCommanderMCP
"@ | Set-Content -LiteralPath (Join-Path $stage "VERSION.txt") -Encoding UTF8

Write-Host "== Portable smoke test =="
$portableNode = Join-Path $stage "node\node.exe"
& $portableNode --version
if ($LASTEXITCODE -ne 0) { throw "Portable Node smoke test failed." }

& $portableNode $dcIndex remote --help
if ($LASTEXITCODE -ne 0) { throw "Desktop Commander remote --help failed." }

& $portableNode $rgVerify
if ($LASTEXITCODE -ne 0) { throw "Portable ripgrep verification failed." }

Write-Host "== ZIP =="
$sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
if ($sevenZip) {
    Push-Location $OutputDir
    try {
        & $sevenZip.Source a -tzip -mx=7 (Split-Path -Leaf $zipPath) "desktop_commander" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "7-Zip creation failed." }
    }
    finally {
        Pop-Location
    }
}
else {
    Compress-Archive -Path $stage -DestinationPath $zipPath -CompressionLevel Optimal
}

if (-not (Test-Path -LiteralPath $zipPath)) { throw "Portable ZIP was not created." }

# Validate that extracting directly to C:\ would create C:\desktop_commander.
$verifyDir = Join-Path $temp "verify"
Expand-Archive -LiteralPath $zipPath -DestinationPath $verifyDir
$verifyRoot = Join-Path $verifyDir "desktop_commander"
if (-not (Test-Path -LiteralPath (Join-Path $verifyRoot "start.bat"))) {
    throw "ZIP root validation failed: desktop_commander\start.bat was not found."
}
if (-not (Test-Path -LiteralPath (Join-Path $verifyRoot "node\node.exe"))) {
    throw "ZIP root validation failed: portable node.exe was not found."
}

$zip = Get-Item -LiteralPath $zipPath
$sizeMiB = [math]::Round($zip.Length / 1MB, 2)
$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
"$($hash.Hash.ToLowerInvariant())  $($zip.Name)" | Set-Content -LiteralPath (Join-Path $OutputDir "SHA256SUMS.txt") -Encoding ASCII

Write-Host "Portable ZIP: $zipPath"
Write-Host "Size: $sizeMiB MiB"
Write-Host "SHA256: $($hash.Hash)"
