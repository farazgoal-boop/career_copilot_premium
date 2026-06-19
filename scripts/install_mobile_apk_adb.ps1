param(
    [string]$ApkPath = "dist/mobile/career-copilot-premium.apk",
    [string]$PackageName = "com.careercopilot.premium",
    [string]$DeviceId = "",
    [switch]$LaunchApp,
    [switch]$ReinstallClean
)

$ErrorActionPreference = "Stop"

function Resolve-AdbExecutable {
    $candidates = @()

    if ($env:ANDROID_SDK_ROOT) {
        $candidates += (Join-Path $env:ANDROID_SDK_ROOT "platform-tools\adb.exe")
    }
    if ($env:ANDROID_HOME) {
        $candidates += (Join-Path $env:ANDROID_HOME "platform-tools\adb.exe")
    }

    $localSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
    $candidates += $localSdk

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $adbCmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($adbCmd) {
        return $adbCmd.Source
    }

    throw "adb not found. Install Android platform-tools and add adb to PATH."
}

function Get-ConnectedDeviceId {
    param(
        [string]$AdbExe,
        [string]$RequestedDeviceId
    )

    $lines = & $AdbExe devices | Select-Object -Skip 1
    $online = @()
    foreach ($line in $lines) {
        if ($line -match "^([\w\.:\-]+)\s+device$") {
            $online += $Matches[1]
        }
    }

    if (-not $online -or $online.Count -eq 0) {
        throw "No Android device detected. Enable USB debugging and connect phone via USB."
    }

    if ($RequestedDeviceId) {
        if ($online -contains $RequestedDeviceId) {
            return $RequestedDeviceId
        }
        throw "Requested device '$RequestedDeviceId' not found. Connected devices: $($online -join ', ')"
    }

    return $online[0]
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$resolvedApk = Join-Path $repoRoot $ApkPath
if (-not (Test-Path $resolvedApk)) {
    throw "APK not found: $resolvedApk"
}

$adbExe = Resolve-AdbExecutable
& $adbExe start-server | Out-Null

$targetDevice = Get-ConnectedDeviceId -AdbExe $adbExe -RequestedDeviceId $DeviceId

Write-Host "Installing APK via ADB bypass..." -ForegroundColor Cyan
Write-Host "Device: $targetDevice"
Write-Host "APK:    $resolvedApk"

if ($ReinstallClean) {
    Write-Host "Cleaning old app (if exists)..." -ForegroundColor Yellow
    & $adbExe -s $targetDevice uninstall $PackageName | Out-Null
}

$installOutput = & $adbExe -s $targetDevice install -r $resolvedApk 2>&1
$installText = ($installOutput | Out-String).Trim()

if ($LASTEXITCODE -ne 0 -or $installText -match "Failure") {
    if ($installText -match "INSTALL_FAILED_UPDATE_INCOMPATIBLE") {
        Write-Host "Update incompatible detected. Trying uninstall + clean install..." -ForegroundColor Yellow
        & $adbExe -s $targetDevice uninstall $PackageName | Out-Null
        $installOutput = & $adbExe -s $targetDevice install $resolvedApk 2>&1
        $installText = ($installOutput | Out-String).Trim()
    }
}

if ($LASTEXITCODE -ne 0 -or $installText -match "Failure") {
    Write-Host $installText
    throw "ADB install failed. See output above."
}

Write-Host "Install success." -ForegroundColor Green

if ($LaunchApp) {
    Write-Host "Launching app..." -ForegroundColor Cyan
    & $adbExe -s $targetDevice shell monkey -p $PackageName -c android.intent.category.LAUNCHER 1 | Out-Null
    Write-Host "App launch command sent." -ForegroundColor Green
}

Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "1) Run desktop helper: powershell -ExecutionPolicy Bypass -File scripts/start_mobile_pro_mode.ps1"
Write-Host "2) In phone app, tap Fetch Sessions -> Use Latest Session -> Refresh"