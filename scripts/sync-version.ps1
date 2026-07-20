[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VersionFile = Join-Path $ProjectRoot "version.json"
if (-not (Test-Path -LiteralPath $VersionFile)) {
    throw "Version file not found at '$VersionFile'."
}

$VersionDocument = Get-Content -LiteralPath $VersionFile -Raw | ConvertFrom-Json
$Version = [string]$VersionDocument.version
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "version.json must contain a three-part numeric version such as 1.0.0. Found '$Version'."
}

function Update-VersionText {
    param(
        [Parameter(Mandatory)] [string]$RelativePath,
        [Parameter(Mandatory)] [string]$Pattern,
        [Parameter(Mandatory)] [string]$Replacement
    )

    $Path = Join-Path $ProjectRoot $RelativePath
    $Text = [IO.File]::ReadAllText($Path)
    $Matches = [regex]::Matches($Text, $Pattern, [Text.RegularExpressions.RegexOptions]::Multiline)
    if ($Matches.Count -ne 1) {
        throw "Expected one version field in '$RelativePath', but found $($Matches.Count)."
    }
    $Updated = [regex]::Replace(
        $Text,
        $Pattern,
        $Replacement,
        [Text.RegularExpressions.RegexOptions]::Multiline
    )
    if ($Updated -ne $Text) {
        [IO.File]::WriteAllText($Path, $Updated, [Text.UTF8Encoding]::new($false))
        Write-Host "Updated $RelativePath to $Version"
    }
    else {
        Write-Host "$RelativePath is already $Version"
    }
}

Update-VersionText "package.json" `
    '(?m)^(\s*"version"\s*:\s*")[^"]+("\s*,\s*)$' `
    "`${1}$Version`${2}"
Update-VersionText "src-tauri\tauri.conf.json" `
    '(?m)^(\s*"version"\s*:\s*")[^"]+("\s*,\s*)$' `
    "`${1}$Version`${2}"
Update-VersionText "src-tauri\Cargo.toml" `
    '(?m)^(version\s*=\s*")[^"]+("\s*)$' `
    "`${1}$Version`${2}"
Update-VersionText "backend\config.py" `
    '(?m)^(\s*app_version:\s*str\s*=\s*")[^"]+("\s*)$' `
    "`${1}$Version`${2}"

$CargoLockPath = Join-Path $ProjectRoot "src-tauri\Cargo.lock"
$CargoLock = [IO.File]::ReadAllText($CargoLockPath)
$CargoPattern = '(?ms)(\[\[package\]\]\s*name\s*=\s*"sped-packet-studio"\s*version\s*=\s*")[^"]+("\s*)'
if ([regex]::Matches($CargoLock, $CargoPattern).Count -ne 1) {
    throw "Could not uniquely locate the SpEd Packet Studio package version in src-tauri\Cargo.lock."
}
$UpdatedCargoLock = [regex]::Replace($CargoLock, $CargoPattern, "`${1}$Version`${2}")
if ($UpdatedCargoLock -ne $CargoLock) {
    [IO.File]::WriteAllText($CargoLockPath, $UpdatedCargoLock, [Text.UTF8Encoding]::new($false))
    Write-Host "Updated src-tauri\Cargo.lock to $Version"
}
else {
    Write-Host "src-tauri\Cargo.lock is already $Version"
}

function Assert-VersionValue {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Actual
    )
    if ($Actual -ne $Version) {
        throw "Version synchronization failed for $Name. Expected '$Version', found '$Actual'."
    }
}

$PackageVersion = [string](Get-Content (Join-Path $ProjectRoot "package.json") -Raw | ConvertFrom-Json).version
$TauriVersion = [string](Get-Content (Join-Path $ProjectRoot "src-tauri\tauri.conf.json") -Raw | ConvertFrom-Json).version
$CargoToml = [IO.File]::ReadAllText((Join-Path $ProjectRoot "src-tauri\Cargo.toml"))
$BackendConfig = [IO.File]::ReadAllText((Join-Path $ProjectRoot "backend\config.py"))
$CargoLock = [IO.File]::ReadAllText($CargoLockPath)
$RustStartup = [IO.File]::ReadAllText((Join-Path $ProjectRoot "src-tauri\src\lib.rs"))

Assert-VersionValue "package.json" $PackageVersion
Assert-VersionValue "src-tauri/tauri.conf.json" $TauriVersion
Assert-VersionValue "src-tauri/Cargo.toml" ([regex]::Match($CargoToml, '(?m)^version\s*=\s*"([^"]+)"').Groups[1].Value)
Assert-VersionValue "backend/config.py" ([regex]::Match($BackendConfig, 'app_version:\s*str\s*=\s*"([^"]+)"').Groups[1].Value)
Assert-VersionValue "src-tauri/Cargo.lock" ([regex]::Match(
    $CargoLock,
    '(?ms)\[\[package\]\]\s*name\s*=\s*"sped-packet-studio"\s*version\s*=\s*"([^"]+)"'
).Groups[1].Value)

if ($RustStartup -notmatch 'env!\("CARGO_PKG_VERSION"\)') {
    throw "Rust startup must derive backend readiness from CARGO_PKG_VERSION."
}
if ($RustStartup -match 'app_version\\?"\s*:\s*\\?"\d+\.\d+\.\d+') {
    throw "Rust startup contains a hard-coded numeric backend version. Use CARGO_PKG_VERSION instead."
}

Write-Host "Version synchronization complete: $Version" -ForegroundColor Green
