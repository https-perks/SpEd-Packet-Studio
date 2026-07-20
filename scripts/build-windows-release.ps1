[CmdletBinding()]
param(
    [ValidateSet("nsis", "msi", "all")]
    [string]$Bundle = "nsis",
    [string]$NativeBin = $env:WEASYPRINT_NATIVE_BIN,
    [switch]$SkipTests,
    [switch]$SkipVerification
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PackageJson = Join-Path $ProjectRoot "package.json"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]$Description,
        [Parameter(Mandatory)] [scriptblock]$Command
    )

    Write-Host "`n==> $Description" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

if ($env:OS -ne "Windows_NT") {
    throw "This release script must run on Windows."
}
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python virtual environment not found at '$Python'. Create it and install the backend build dependencies first."
}
if (-not (Test-Path -LiteralPath $PackageJson)) {
    throw "package.json was not found at '$PackageJson'."
}
foreach ($CommandName in @("rustc", "cargo", "corepack")) {
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Required build command '$CommandName' is not available on PATH."
    }
}

Push-Location $ProjectRoot
try {
    Invoke-Checked "Synchronizing release version from version.json" {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
            (Join-Path $PSScriptRoot "sync-version.ps1")
    }

    if (-not $SkipTests) {
        Invoke-Checked "Compile-checking the Python backend" {
            & $Python -m compileall -q backend
        }
        Invoke-Checked "Running backend tests" {
            & $Python -m unittest discover -s backend/tests -v
        }
    }

    Invoke-Checked "Building the frozen Windows backend sidecar" {
        $SidecarArguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $PSScriptRoot "build-sidecar.ps1")
        )
        if ($NativeBin) {
            $SidecarArguments += @("-NativeBin", $NativeBin)
        }
        & powershell.exe @SidecarArguments
    }

    $BundleArgument = switch ($Bundle) {
        "nsis" { "nsis" }
        "msi" { "msi" }
        "all" { "nsis,msi" }
    }
    $TauriArguments = @("pnpm@10.18.3", "tauri", "build", "--bundles", $BundleArgument)
    Invoke-Checked "Building the frontend, desktop EXE, and $Bundle bundle" {
        & corepack @TauriArguments
    }

    if (-not $SkipVerification) {
        $ReleaseVersion = (Get-Content -LiteralPath (Join-Path $ProjectRoot "version.json") -Raw | ConvertFrom-Json).version
        $InstallerToVerify = if ($Bundle -eq "msi") {
            Join-Path $ProjectRoot "src-tauri\target\release\bundle\msi\SpEd Packet Studio_${ReleaseVersion}_x64_en-US.msi"
        }
        else {
            Join-Path $ProjectRoot "src-tauri\target\release\bundle\nsis\SpEd Packet Studio_${ReleaseVersion}_x64-setup.exe"
        }
        Invoke-Checked "Verifying the packaged Windows runtime" {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
                (Join-Path $PSScriptRoot "verify-windows-package.ps1") -Installer $InstallerToVerify
        }
    }

    $TargetTriple = (& rustc --print host-tuple).Trim()
    $Outputs = @(
        Join-Path $ProjectRoot "src-tauri\binaries\sped-packet-backend-$TargetTriple.exe"
        Join-Path $ProjectRoot "src-tauri\target\release\sped-packet-studio.exe"
    )
    if ($Bundle -in @("nsis", "all")) {
        $Outputs += Get-ChildItem (Join-Path $ProjectRoot "src-tauri\target\release\bundle\nsis") `
            -Filter "*-setup.exe" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if ($Bundle -in @("msi", "all")) {
        $Outputs += Get-ChildItem (Join-Path $ProjectRoot "src-tauri\target\release\bundle\msi") `
            -Filter "*.msi" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
    }

    Write-Host "`nRelease build completed successfully." -ForegroundColor Green
    foreach ($Output in $Outputs) {
        if ($Output -and (Test-Path -LiteralPath $Output)) {
            $Item = Get-Item -LiteralPath $Output
            Write-Host ("  {0}  ({1:N1} MB)" -f $Item.FullName, ($Item.Length / 1MB))
        }
    }
}
finally {
    Pop-Location
}
