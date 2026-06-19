[CmdletBinding()]
param(
    [string]$InstallDir = "D:\CareerCopilotSmoke",
    [int]$WaitSeconds = 25
)

$ErrorActionPreference = "Stop"

$exePath = Join-Path $InstallDir "career-copilot.exe"
if (-not (Test-Path $exePath)) {
    throw "Installed executable not found at $exePath"
}

Get-Process -Name "career-copilot" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$ready = $false
$launchError = ""
$processId = 0

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

Write-Output ("APP_READY=" + $ready)
Write-Output ("APP_PID=" + $processId)
Write-Output ("LAUNCH_ERROR=" + $launchError)
