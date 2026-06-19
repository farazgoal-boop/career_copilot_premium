[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$InstallDir = "D:\CareerCopilotSmoke"
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = (Resolve-Path $ProjectRoot).Path

& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\build_release_candidate.ps1") -ProjectRoot $root
if ($LASTEXITCODE -ne 0) {
    throw "build_release_candidate.ps1 failed"
}

& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\test_setup_and_launch_end_to_end.ps1") -ProjectRoot $root -InstallDir $InstallDir
if ($LASTEXITCODE -ne 0) {
    throw "test_setup_and_launch_end_to_end.ps1 failed"
}
