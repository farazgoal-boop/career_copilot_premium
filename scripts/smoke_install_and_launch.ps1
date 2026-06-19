[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$InstallDir = "D:\CareerCopilotSmoke",
    [int]$WaitSeconds = 25
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = (Resolve-Path $ProjectRoot).Path
$setupExe = Join-Path $root "dist\installer\career-copilot-premium-setup.exe"
if (-not (Test-Path $setupExe)) {
    throw "Setup executable not found at $setupExe"
}

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

$setupLog = "D:\installer-smoke.log"
if (Test-Path $setupLog) {
    Remove-Item $setupLog -Force
}

$tempSetupExe = Join-Path $env:TEMP ("career-copilot-setup-smoke-" + [Guid]::NewGuid().ToString("N") + ".exe")

$copied = $false
for ($attempt = 1; $attempt -le 10; $attempt++) {
    try {
        Copy-Item -Path $setupExe -Destination $tempSetupExe -Force
        $copied = $true
        break
    }
    catch {
        if ($attempt -eq 10) {
            throw
        }
        [System.Threading.Thread]::Sleep(400)
    }
}

if (-not $copied) {
    throw "Could not copy setup executable for smoke validation."
}

$installArgs = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/SP-",
    ("/DIR=" + $InstallDir),
    ("/LOG=" + $setupLog)
)

$setup = Start-Process -FilePath $tempSetupExe -ArgumentList $installArgs -PassThru -Wait

$exePath = Join-Path $InstallDir "career-copilot.exe"
$loremPath = Join-Path $InstallDir "_internal\setuptools\_vendor\jaraco\text\Lorem ipsum.txt"

$ready = $false
$launchError = ""
$processId = 0
if (Test-Path $exePath) {
    try {
        $app = Start-Process -FilePath $exePath -WorkingDirectory $InstallDir -PassThru
        $processId = $app.Id
        $deadline = (Get-Date).AddSeconds($WaitSeconds)
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
            [System.Threading.Thread]::Sleep(300)
        }
    }
    catch {
        $launchError = $_.Exception.Message
    }
}

Get-Process -Name "career-copilot" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item $tempSetupExe -Force -ErrorAction SilentlyContinue

Write-Output ("SETUP_EXIT=" + $setup.ExitCode)
Write-Output ("INSTALL_DIR_EXISTS=" + (Test-Path $InstallDir))
Write-Output ("EXE_EXISTS=" + (Test-Path $exePath))
Write-Output ("LOREM_EXISTS=" + (Test-Path $loremPath))
Write-Output ("APP_READY=" + $ready)
Write-Output ("APP_PID=" + $processId)
Write-Output ("LAUNCH_ERROR=" + $launchError)
Write-Output ("SETUP_LOG_PATH=" + $setupLog)
