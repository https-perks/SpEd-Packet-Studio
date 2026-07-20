param(
    [string]$IdentityName = $env:MSIX_IDENTITY_NAME,
    [string]$Publisher = $env:MSIX_PUBLISHER,
    [string]$PublisherDisplayName = $env:MSIX_PUBLISHER_DISPLAY_NAME,
    [string]$Version = $env:MSIX_VERSION,
    [string]$CertificatePath = $env:MSIX_CERTIFICATE_PATH,
    [string]$CertificatePassword = $env:MSIX_CERTIFICATE_PASSWORD,
    [string]$TimestampUrl = $env:MSIX_TIMESTAMP_URL
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VersionFile = Join-Path $ProjectRoot "version.json"
if (-not $Version) {
    if (-not (Test-Path -LiteralPath $VersionFile)) { throw "Version file not found: $VersionFile" }
    $AppVersion = [string](Get-Content -LiteralPath $VersionFile -Raw | ConvertFrom-Json).version
    if ($AppVersion -notmatch '^\d+\.\d+\.\d+$') { throw "version.json contains an invalid version: $AppVersion" }
    $Version = "$AppVersion.0"
}
$Payload = Join-Path $ProjectRoot "build\msix\payload"
$Artifacts = Join-Path $ProjectRoot "build\msix\artifacts"
$ManifestTemplate = Join-Path $ProjectRoot "packaging\windows\AppxManifest.xml.template"

foreach ($value in @{
    MSIX_IDENTITY_NAME = $IdentityName
    MSIX_PUBLISHER = $Publisher
    MSIX_PUBLISHER_DISPLAY_NAME = $PublisherDisplayName
    MSIX_VERSION = $Version
}.GetEnumerator()) {
    if (-not $value.Value) { throw "$($value.Key) is required." }
}
if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "MSIX_VERSION must contain four numeric parts, for example 0.1.0.0."
}

function Find-WindowsSdkTool([string]$Name) {
    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Command) { return $Command.Source }
    $SdkBin = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
    $Match = Get-ChildItem $SdkBin -Filter $Name -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\' } |
        Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $Match) { throw "$Name was not found. Install the Windows SDK MSIX Packaging Tools." }
    return $Match.FullName
}

$MakeAppx = Find-WindowsSdkTool "makeappx.exe"
$SignTool = Find-WindowsSdkTool "signtool.exe"
$DesktopExe = Join-Path $ProjectRoot "src-tauri\target\release\sped-packet-studio.exe"
$SidecarExe = Join-Path $ProjectRoot "src-tauri\target\release\sped-packet-backend.exe"
if (-not (Test-Path -LiteralPath $DesktopExe)) { throw "Release desktop executable is missing. Run the desktop release build first." }
if (-not (Test-Path -LiteralPath $SidecarExe)) { throw "Backend sidecar is missing. Run pnpm sidecar:build first." }

if (Test-Path -LiteralPath $Payload) { Remove-Item -LiteralPath $Payload -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Payload, $Artifacts, (Join-Path $Payload "Images") | Out-Null
Copy-Item -LiteralPath $DesktopExe -Destination (Join-Path $Payload "SpEd Packet Studio.exe")
Copy-Item -LiteralPath $SidecarExe -Destination (Join-Path $Payload "sped-packet-backend.exe")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "src-tauri\icons\StoreLogo.png") -Destination (Join-Path $Payload "Images\StoreLogo.png")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "src-tauri\icons\Square44x44Logo.png") -Destination (Join-Path $Payload "Images\Square44x44Logo.png")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "src-tauri\icons\Square150x150Logo.png") -Destination (Join-Path $Payload "Images\Square150x150Logo.png")
Copy-Item -LiteralPath (Join-Path $ProjectRoot "assets") -Destination (Join-Path $Payload "assets") -Recurse
if (Test-Path -LiteralPath (Join-Path $ProjectRoot "templates")) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "templates") -Destination (Join-Path $Payload "templates") -Recurse
}

$Manifest = Get-Content -LiteralPath $ManifestTemplate -Raw
$Manifest = $Manifest.Replace("__IDENTITY_NAME__", [Security.SecurityElement]::Escape($IdentityName))
$Manifest = $Manifest.Replace("__PUBLISHER__", [Security.SecurityElement]::Escape($Publisher))
$Manifest = $Manifest.Replace("__PUBLISHER_DISPLAY_NAME__", [Security.SecurityElement]::Escape($PublisherDisplayName))
$Manifest = $Manifest.Replace("__VERSION__", $Version)
Set-Content -LiteralPath (Join-Path $Payload "AppxManifest.xml") -Value $Manifest -Encoding UTF8

$Msix = Join-Path $Artifacts "SpEd-Packet-Studio-$Version-x64.msix"
& $MakeAppx pack /o /d $Payload /p $Msix
if ($LASTEXITCODE -ne 0) { throw "MakeAppx failed." }

if ($CertificatePath) {
    if (-not (Test-Path -LiteralPath $CertificatePath)) { throw "MSIX certificate was not found: $CertificatePath" }
    $SignArgs = @("sign", "/fd", "SHA256", "/f", $CertificatePath)
    if ($CertificatePassword) { $SignArgs += @("/p", $CertificatePassword) }
    if ($TimestampUrl) { $SignArgs += @("/tr", $TimestampUrl, "/td", "SHA256") }
    $SignArgs += $Msix
    & $SignTool @SignArgs
    if ($LASTEXITCODE -ne 0) { throw "SignTool failed." }
} else {
    Write-Warning "Created an unsigned MSIX. Set MSIX_CERTIFICATE_PATH for sideload distribution; Partner Center applies Store signing."
}
Write-Output $Msix
