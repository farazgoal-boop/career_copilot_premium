[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$InstallDir = "D:\CareerCopilotInstallerSmoke",
    [int]$AppTimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$setupExe = Join-Path $resolvedProjectRoot "dist\installer\career-copilot-premium-setup.exe"

if (-not (Test-Path $setupExe)) {
    throw "Setup executable not found at $setupExe"
}

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

$setupLog = Join-Path $resolvedProjectRoot "logs\installer-smoke.log"
$tempSetupExe = Join-Path $env:TEMP ("career-copilot-premium-setup-smoke-" + [Guid]::NewGuid().ToString("N") + ".exe")
Copy-Item -Path $setupExe -Destination $tempSetupExe -Force

$setupArgs = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/SP-",
    ('/DIR="' + $InstallDir + '"'),
    ('/LOG="' + $setupLog + '"')
)

$setupProcess = Start-Process -FilePath $tempSetupExe -ArgumentList $setupArgs -Wait -PassThru
if ($setupProcess.ExitCode -ne 0) {
    throw "Installer exited with code $($setupProcess.ExitCode). See $setupLog"
}

$installedExe = Join-Path $InstallDir "career-copilot.exe"
if (-not (Test-Path $installedExe)) {
    throw "Installed executable not found at $installedExe"
}

Get-Process -Name "career-copilot" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$appProcess = Start-Process -FilePath $installedExe -WorkingDirectory $InstallDir -PassThru
$deadline = (Get-Date).AddSeconds($AppTimeoutSeconds)
$ready = $false

while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:5000/api/health" -UseBasicParsing -TimeoutSec 1
        if ($response.StatusCode -eq 200 -and $response.Content -match '"ok"\s*:\s*true') {
            $ready = $true
            break
        }
    }
    catch {
    }

    [System.Threading.Thread]::Sleep(250)
}

$sw.Stop()
Get-Process -Name "career-copilot" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Output ("INSTALL_EXIT=" + $setupProcess.ExitCode)
Write-Output ("INSTALLED_EXE=" + $installedExe)
Write-Output ("APP_READY=" + $ready)
Write-Output ("APP_SECONDS=" + [Math]::Round($sw.Elapsed.TotalSeconds, 2))
Write-Output ("SETUP_LOG=" + $setupLog)

Remove-Item $tempSetupExe -Force -ErrorAction SilentlyContinue
