param(
    [ValidateSet("connect", "install", "update", "clean", "pro")]
    [string]$Mode = "connect",
    [string]$UsbDeviceId = "",
    [int]$Port = 5555,
    [string]$ApkPath = "dist/mobile/career-copilot-premium.apk",
    [switch]$LaunchApp
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

    $candidates += (Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe")

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }

    $adbCmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($adbCmd) {
        return $adbCmd.Source
    }

    throw "adb not found. Install Android platform-tools first."
}

function Get-OnlineDevices {
    param([string]$AdbExe)

    $lines = & $AdbExe devices | Select-Object -Skip 1
    $devices = @()

    foreach ($line in $lines) {
        if ($line -match "^([\w\.:\-]+)\s+device$") {
            $devices += $Matches[1]
        }
    }

    return $devices
}

function Resolve-UsbDevice {
    param(
        [string]$AdbExe,
        [string]$RequestedUsbDeviceId
    )

    $devices = Get-OnlineDevices -AdbExe $AdbExe
    if (-not $devices -or $devices.Count -eq 0) {
        throw "No Android device detected over USB. Connect phone with USB and allow USB debugging."
    }

    if ($RequestedUsbDeviceId) {
        if ($devices -contains $RequestedUsbDeviceId) {
            return $RequestedUsbDeviceId
        }
        throw "USB device '$RequestedUsbDeviceId' not found. Detected: $($devices -join ', ')"
    }

    $usbOnly = $devices | Where-Object { $_ -notmatch ':' -and $_ -notlike 'emulator-*' }
    if ($usbOnly -and $usbOnly.Count -gt 0) {
        return $usbOnly[0]
    }

    return $devices[0]
}

function Get-DeviceWifiIp {
    param(
        [string]$AdbExe,
        [string]$DeviceId
    )

    $addrOutput = (& $AdbExe -s $DeviceId shell ip -f inet addr show wlan0 2>$null | Out-String)
    if ($addrOutput -match "inet\s+(\d+\.\d+\.\d+\.\d+)/") {
        return $Matches[1]
    }

    $routeOutput = (& $AdbExe -s $DeviceId shell ip route 2>$null | Out-String)
    if ($routeOutput -match "src\s+(\d+\.\d+\.\d+\.\d+)") {
        return $Matches[1]
    }

    throw "Could not resolve device Wi-Fi IP. Ensure phone is connected to Wi-Fi."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$adbExe = Resolve-AdbExecutable
& $adbExe start-server | Out-Null

$usbDevice = Resolve-UsbDevice -AdbExe $adbExe -RequestedUsbDeviceId $UsbDeviceId
Write-Host "USB device: $usbDevice"

Write-Host "Switching device ADB to TCP/IP on port $Port..." -ForegroundColor Cyan
& $adbExe -s $usbDevice tcpip $Port | Out-Null

$wifiIp = Get-DeviceWifiIp -AdbExe $adbExe -DeviceId $usbDevice
$wirelessDevice = "$wifiIp`:$Port"

Write-Host "Connecting to wireless ADB target: $wirelessDevice" -ForegroundColor Cyan
$connectOutput = (& $adbExe connect $wirelessDevice | Out-String).Trim()
Write-Host $connectOutput

if ($Mode -eq "connect") {
    Write-Host ""
    Write-Host "Wireless ADB is ready: $wirelessDevice" -ForegroundColor Green
    Write-Host "Now you can unplug USB and run install/update commands with -DeviceId $wirelessDevice"
    return
}

$installScript = Join-Path $repoRoot "scripts\install_update_mobile_apk_adb.ps1"
if (-not (Test-Path $installScript)) {
    throw "Installer wrapper script not found: $installScript"
}

$resolvedInstallMode = $Mode
if ($Mode -eq "pro") {
    $resolvedInstallMode = "update"
}

$argsList = @(
    "-ExecutionPolicy", "Bypass",
    "-File", $installScript,
    "-Mode", $resolvedInstallMode,
    "-ApkPath", $ApkPath,
    "-DeviceId", $wirelessDevice
)

if ($LaunchApp) {
    $argsList += "-LaunchApp"
}

Write-Host ""
Write-Host "Running APK $resolvedInstallMode over wireless ADB..." -ForegroundColor Cyan
& powershell @argsList

if ($Mode -eq "pro") {
    $desktopProScript = Join-Path $repoRoot "scripts\start_mobile_pro_mode.ps1"
    if (-not (Test-Path $desktopProScript)) {
        throw "Desktop pro launcher script not found: $desktopProScript"
    }

    Write-Host "" 
    Write-Host "Starting desktop pro mode in a new terminal window..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", $desktopProScript
    ) | Out-Null

    Write-Host "Pro mode complete:" -ForegroundColor Green
    Write-Host "1) Phone app installed/updated and launched"
    Write-Host "2) Desktop session + worker + bridge launching in new PowerShell window"
}
