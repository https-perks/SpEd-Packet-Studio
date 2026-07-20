param(
    [string]$TargetTriple = "",
    [string]$NativeBin = $env:WEASYPRINT_NATIVE_BIN
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found at $Python"
}
if (-not $TargetTriple) {
    $TargetTriple = (& rustc --print host-tuple).Trim()
}
if (-not $NativeBin) {
    $PreparedNativeBin = Join-Path $ProjectRoot "packaging\windows\weasyprint-native\bin"
    if (Test-Path -LiteralPath (Join-Path $PreparedNativeBin "libpango-1.0-0.dll")) {
        $NativeBin = $PreparedNativeBin
    }
}
if (-not $NativeBin) {
    $CommonRuntimeBins = @(
        "C:\Program Files\GTK3-Runtime Win64\bin",
        "C:\Program Files (x86)\GTK3-Runtime Win64\bin"
    )
    foreach ($Candidate in $CommonRuntimeBins) {
        if (Test-Path -LiteralPath (Join-Path $Candidate "libpango-1.0-0.dll")) {
            $NativeBin = $Candidate
            break
        }
    }
}
if (-not $NativeBin) {
    $Pango = Get-Command "libpango-1.0-0.dll" -ErrorAction SilentlyContinue
    if ($Pango) { $NativeBin = Split-Path -Parent $Pango.Source }
}
if (-not $NativeBin -or -not (Test-Path -LiteralPath (Join-Path $NativeBin "libpango-1.0-0.dll"))) {
    throw "WeasyPrint native DLLs were not found. Set WEASYPRINT_NATIVE_BIN to the GTK runtime bin directory."
}

$BinaryDir = Join-Path $ProjectRoot "src-tauri\binaries"
$WorkDir = Join-Path $ProjectRoot "build\pyinstaller"
$DistDir = Join-Path $ProjectRoot "build\sidecar-dist"
New-Item -ItemType Directory -Force -Path $BinaryDir, $WorkDir, $DistDir | Out-Null
& $Python (Join-Path $ProjectRoot "scripts\generate-test-font.py")
if ($LASTEXITCODE -ne 0) { throw "Custom font generation failed." }

# The GTK runtime includes optional Cairo script-interpreter and TIFF DLLs.
# Neither is used by WeasyPrint in this application, and both reference image-
# codec DLLs that are not distributed by the GTK runtime installer. Avoid
# sweeping those unused components into the frozen backend.
$ExcludedNativeDlls = @(
    "libcairo-script-interpreter-2.dll",
    "libtiff-5.dll"
)
$NativeDllArguments = @()
Get-ChildItem -LiteralPath $NativeBin -Filter "*.dll" -File | ForEach-Object {
    if ($_.Name -notin $ExcludedNativeDlls) {
        $NativeDllArguments += @("--add-binary", "$($_.FullName);weasyprint-native")
    }
}
if (-not $NativeDllArguments) {
    throw "No WeasyPrint native DLLs were found under $NativeBin"
}
Write-Output "Using WeasyPrint native runtime: $NativeBin"

$PyInstallerArguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "sped-packet-backend",
    "--paths", $ProjectRoot,
    "--collect-all", "weasyprint",
    "--collect-all", "uvicorn",
    "--add-data", "$(Join-Path $ProjectRoot "assets");assets",
    "--hidden-import", "backend.main"
) + $NativeDllArguments + @(
    "--workpath", $WorkDir,
    "--specpath", $WorkDir,
    "--distpath", $DistDir,
    (Join-Path $ProjectRoot "backend\__main__.py")
)
& $Python @PyInstallerArguments
if ($LASTEXITCODE -ne 0) { throw "PyInstaller backend build failed." }

$Extension = if ($env:OS -eq "Windows_NT") { ".exe" } else { "" }
$Source = Join-Path $DistDir "sped-packet-backend$Extension"
$Destination = Join-Path $BinaryDir "sped-packet-backend-$TargetTriple$Extension"
Copy-Item -LiteralPath $Source -Destination $Destination -Force
Write-Output $Destination
