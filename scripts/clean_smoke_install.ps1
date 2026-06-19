[CmdletBinding()]
param(
    [string]$InstallDir = "D:\CareerCopilotSmoke"
)

$ErrorActionPreference = "SilentlyContinue"
Get-Process -Name "career-copilot" | Stop-Process -Force
if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}
if (Test-Path "D:\installer-smoke.log") {
    Remove-Item "D:\installer-smoke.log" -Force
}
Write-Output "SMOKE_CLEANED"
