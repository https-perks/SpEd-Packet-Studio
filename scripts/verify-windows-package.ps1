param(
    [string]$Sidecar = "",
    [string]$Installer = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VersionFile = Join-Path $ProjectRoot "version.json"
if (-not (Test-Path -LiteralPath $VersionFile)) { throw "Version file not found: $VersionFile" }
$Version = [string](Get-Content -LiteralPath $VersionFile -Raw | ConvertFrom-Json).version
if (-not $Sidecar) {
    $Sidecar = Join-Path $ProjectRoot "src-tauri\binaries\sped-packet-backend-x86_64-pc-windows-msvc.exe"
}
if (-not $Installer) {
    $Installer = Join-Path $ProjectRoot "src-tauri\target\release\bundle\nsis\SpEd Packet Studio_${Version}_x64-setup.exe"
}
if (-not (Test-Path -LiteralPath $Sidecar)) { throw "Sidecar not found: $Sidecar" }
if (-not (Test-Path -LiteralPath $Installer)) { throw "NSIS installer not found: $Installer" }

$TestRoot = Join-Path $env:TEMP "SpEd Packet Verification - Ryañ"
$Runtime = Join-Path $TestRoot "installed files"
$AppData = Join-Path $TestRoot "Local App Data\SpEd Packet Studio"
if (Test-Path -LiteralPath $TestRoot) { Remove-Item -LiteralPath $TestRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Runtime, $AppData | Out-Null
Copy-Item -LiteralPath $Sidecar -Destination (Join-Path $Runtime "sped-packet-backend.exe")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "assets") -Destination (Join-Path $Runtime "assets") -Recurse
Copy-Item -LiteralPath (Join-Path $ProjectRoot "templates") -Destination (Join-Path $Runtime "templates") -Recurse

$OriginalPath = $env:PATH
$PathEntries = @(
    $Runtime,
    (Join-Path $Runtime "native"),
    (Join-Path $Runtime "_internal\native"),
    $env:SystemRoot,
    (Join-Path $env:SystemRoot "System32"),
    $OriginalPath
) | Where-Object { $_ }
$env:PATH = ($PathEntries -join ";")
$env:SPED_PACKET_APP_DATA_DIR = $AppData
$env:SPED_PACKET_RESOURCE_DIR = $Runtime
$env:SPED_PACKET_CACHE_DIR = Join-Path $AppData "cache"
$env:SPED_PACKET_TEMP_DIR = Join-Path $AppData "temp"
$env:SPED_PACKET_LOG_DIR = Join-Path $AppData "logs"
$env:PACKET_STUDIO_ENV = "packaged-verification"
$env:PACKET_STUDIO_API_HOST = "127.0.0.1"
$env:PACKET_STUDIO_API_PORT = "8765"
Remove-Item Env:SPED_PACKET_PARENT_PID -ErrorAction SilentlyContinue

try {
    Push-Location $env:TEMP
    try {
        $SelfTest = Start-Process -FilePath (Join-Path $Runtime "sped-packet-backend.exe") `
            -ArgumentList "--self-test" -WorkingDirectory $env:TEMP -Wait -PassThru
        if ($SelfTest.ExitCode -ne 0) { throw "Frozen PDF self-test failed with exit code $($SelfTest.ExitCode)." }
    } finally { Pop-Location }
    $Pdf = Join-Path $AppData "cache\sidecar-self-test.pdf"
    if (-not (Test-Path -LiteralPath $Pdf) -or (Get-Item $Pdf).Length -lt 1000) {
        throw "Representative packaged PDF was not generated."
    }

    $UserFiles = @(
        (Join-Path $AppData "settings\verification-setting.json"),
        (Join-Path $AppData "templates\verification-template.json"),
        (Join-Path $AppData "brand-kits\verification-brand.txt")
    )
    foreach ($File in $UserFiles) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $File) | Out-Null
        Set-Content -LiteralPath $File -Value "preserve-on-upgrade" -Encoding UTF8
    }

    $Backend = Start-Process -FilePath (Join-Path $Runtime "sped-packet-backend.exe") -WorkingDirectory $env:TEMP -WindowStyle Hidden -PassThru
    try {
        $Health = $null
        for ($Attempt = 0; $Attempt -lt 60; $Attempt++) {
            Start-Sleep -Milliseconds 250
            try { $Health = Invoke-RestMethod "http://127.0.0.1:8765/api/v1/health"; break } catch {}
        }
        if (-not $Health -or $Health.status -ne "ok" -or $Health.app_version -ne $Version) {
            throw "Frozen backend health endpoint did not report versioned readiness."
        }
        $Cors = Invoke-WebRequest "http://127.0.0.1:8765/api/v1/health" -UseBasicParsing `
            -Headers @{ Origin = "http://tauri.localhost" }
        if ($Cors.Headers["Access-Control-Allow-Origin"] -ne "http://tauri.localhost") {
            throw "Frozen backend did not allow the production Tauri webview origin."
        }
    } finally {
        Stop-Process -Id $Backend.Id -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        Get-Process "sped-packet-backend" -ErrorAction SilentlyContinue |
            Stop-Process -Force -ErrorAction SilentlyContinue
    }

    foreach ($File in $UserFiles) {
        if ((Get-Content -LiteralPath $File -Raw).Trim() -ne "preserve-on-upgrade") {
            throw "User data was changed during upgrade-style restart: $File"
        }
    }
    $Database = Join-Path $AppData "data\packet-studio.sqlite3"
    if (-not (Test-Path -LiteralPath $Database)) { throw "Database was not created under Local AppData." }
    if (Get-ChildItem -LiteralPath $Runtime -Filter "*.sqlite3" -Recurse) {
        throw "Mutable database was written into the packaged runtime directory."
    }
    Write-Output "Frozen runtime verification passed"
    Write-Output "Runtime: $Runtime"
    Write-Output "AppData: $AppData"
    Write-Output "Installer: $Installer"
} finally {
    $env:PATH = $OriginalPath
}
