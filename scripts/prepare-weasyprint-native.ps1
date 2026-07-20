param(
    [string]$SourceBin = $env:WEASYPRINT_NATIVE_BIN,
    [string]$DestinationBin = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $DestinationBin) {
    $DestinationBin = Join-Path $ProjectRoot "packaging\windows\weasyprint-native\bin"
}

$CommonRuntimeBins = @(
    "C:\Program Files\GTK3-Runtime Win64\bin",
    "C:\Program Files (x86)\GTK3-Runtime Win64\bin"
)

if (-not $SourceBin) {
    foreach ($Candidate in $CommonRuntimeBins) {
        if (Test-Path -LiteralPath (Join-Path $Candidate "libpango-1.0-0.dll")) {
            $SourceBin = $Candidate
            break
        }
    }
}

if (-not $SourceBin) {
    $Pango = Get-Command "libpango-1.0-0.dll" -ErrorAction SilentlyContinue
    if ($Pango) { $SourceBin = Split-Path -Parent $Pango.Source }
}

if (-not $SourceBin -or -not (Test-Path -LiteralPath (Join-Path $SourceBin "libpango-1.0-0.dll"))) {
    throw "WeasyPrint native DLLs were not found. Install the GTK3 runtime or set WEASYPRINT_NATIVE_BIN to its bin directory."
}

$ExcludedNativeDlls = @(
    "libcairo-script-interpreter-2.dll",
    "libtiff-5.dll"
)

New-Item -ItemType Directory -Force -Path $DestinationBin | Out-Null
Get-ChildItem -LiteralPath $DestinationBin -Filter "*.dll" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force

$Copied = 0
Get-ChildItem -LiteralPath $SourceBin -Filter "*.dll" -File | ForEach-Object {
    if ($_.Name -notin $ExcludedNativeDlls) {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $DestinationBin $_.Name) -Force
        $Copied += 1
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $DestinationBin "libpango-1.0-0.dll"))) {
    throw "Prepared runtime is missing libpango-1.0-0.dll."
}

Write-Output "Prepared $Copied WeasyPrint native DLLs."
Write-Output "Source: $SourceBin"
Write-Output "Destination: $DestinationBin"
