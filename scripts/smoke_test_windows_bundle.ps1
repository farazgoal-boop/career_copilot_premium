[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$bundleDir = Join-Path $resolvedProjectRoot "dist\windows-bundle"
$exePath = Join-Path $bundleDir "career-copilot.exe"

if (-not (Test-Path $exePath)) {
    throw "Packaged executable not found at $exePath"
}

Stop-Process -Name "career-copilot" -Force -ErrorAction SilentlyContinue

$process = Start-Process -FilePath $exePath -WorkingDirectory $bundleDir -PassThru
$process.WaitForExit()

Write-Output ("EXIT=" + $process.ExitCode)