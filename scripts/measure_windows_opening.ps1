[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [int]$AppTimeoutSeconds = 90,
    [int]$SetupTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path

function Resolve-AppExePath {
    param([string]$Root)

    $candidates = @(
        (Join-Path $Root "dist\windows-bundle\career-copilot.exe"),
        (Join-Path $Root "build\pyinstaller-dist\career-copilot\career-copilot.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    throw "App executable not found in expected locations."
}

function Resolve-SetupExePath {
    param([string]$Root)

    $candidate = Join-Path $Root "dist\installer\career-copilot-premium-setup.exe"
    if (Test-Path $candidate) {
        return (Resolve-Path $candidate).Path
    }

    throw "Setup executable not found at $candidate"
}

function Measure-AppReadyTime {
    param(
        [string]$ExePath,
        [int]$TimeoutSeconds
    )

    Get-Process -Name "career-copilot" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path $ExePath -Parent) -PassThru
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
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

    return [PSCustomObject]@{
        Ready = $ready
        Seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 2)
        ProcessId = $process.Id
    }
}

function Measure-SetupWindowTime {
    param(
        [string]$SetupExePath,
        [int]$TimeoutSeconds
    )

    $tempSetupExe = Join-Path $env:TEMP ("career-copilot-setup-timing-" + [Guid]::NewGuid().ToString("N") + ".exe")
    Copy-Item -Path $SetupExePath -Destination $tempSetupExe -Force

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $process = Start-Process -FilePath $tempSetupExe -WorkingDirectory (Split-Path $SetupExePath -Parent) -PassThru

    $appeared = $false
    try {
        $appeared = $process.WaitForInputIdle($TimeoutSeconds * 1000)
    }
    catch {
        $appeared = $false
    }

    $sw.Stop()

    try {
        if (-not $process.HasExited) {
            $process.Kill()
            $process.WaitForExit(5000)
        }
    }
    catch {
    }

    Remove-Item $tempSetupExe -Force -ErrorAction SilentlyContinue

    return [PSCustomObject]@{
        WindowReady = $appeared
        Seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 2)
        ProcessId = $process.Id
    }
}

$appExe = Resolve-AppExePath -Root $resolvedProjectRoot
$setupExe = Resolve-SetupExePath -Root $resolvedProjectRoot

Write-Output ("APP_EXE=" + $appExe)
Write-Output ("SETUP_EXE=" + $setupExe)

$appTiming = Measure-AppReadyTime -ExePath $appExe -TimeoutSeconds $AppTimeoutSeconds
$setupTiming = Measure-SetupWindowTime -SetupExePath $setupExe -TimeoutSeconds $SetupTimeoutSeconds

Write-Output ("APP_READY=" + $appTiming.Ready)
Write-Output ("APP_SECONDS=" + $appTiming.Seconds)
Write-Output ("SETUP_WINDOW_READY=" + $setupTiming.WindowReady)
Write-Output ("SETUP_SECONDS=" + $setupTiming.Seconds)
