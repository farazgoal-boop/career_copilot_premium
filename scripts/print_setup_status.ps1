[CmdletBinding()]
param(
    [string]$InstallDir = "D:\CareerCopilotSmoke"
)

$ErrorActionPreference = "Stop"
Write-Output ("SETUP_EXISTS=" + (Test-Path "D:\my apps\career_copilot_premium\career_copilot_premium\dist\installer\career-copilot-premium-setup.exe"))
Write-Output ("INSTALL_DIR_EXISTS=" + (Test-Path $InstallDir))
Write-Output ("SMOKE_LOG_EXISTS=" + (Test-Path "D:\installer-smoke.log"))
