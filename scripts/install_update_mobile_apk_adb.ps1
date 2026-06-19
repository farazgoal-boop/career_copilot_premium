param(
    [ValidateSet("install", "update", "clean")]
    [string]$Mode = "update",
    [string]$ApkPath = "dist/mobile/career-copilot-premium.apk",
    [string]$DeviceId = "",
    [switch]$LaunchApp
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$baseScript = Join-Path $repoRoot "scripts\install_mobile_apk_adb.ps1"

if (-not (Test-Path $baseScript)) {
    throw "Base ADB installer script not found: $baseScript"
}

$argsList = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $baseScript,
    "-ApkPath", $ApkPath
)

if ($DeviceId) {
    $argsList += @("-DeviceId", $DeviceId)
}

if ($LaunchApp) {
    $argsList += "-LaunchApp"
}

switch ($Mode) {
    "install" {
        # Install mode uses reinstall flag for first-time and repeated deploys.
        $argsList += "-ReinstallClean"
    }
    "clean" {
        $argsList += "-ReinstallClean"
    }
    "update" {
        # Update mode keeps user data when signatures are compatible.
    }
}

Write-Host "ADB mode: $Mode" -ForegroundColor Cyan
Write-Host "APK path: $ApkPath"
if ($DeviceId) {
    Write-Host "Target device: $DeviceId"
}

& powershell @argsList
