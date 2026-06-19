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

& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\verify_setup_only.ps1") -ProjectRoot $root -InstallDir $InstallDir
if ($LASTEXITCODE -ne 0) {
    throw "verify_setup_only.ps1 failed"
}

& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\collect_installed_runtime_inventory.ps1") -InstallDir $InstallDir
if ($LASTEXITCODE -ne 0) {
    throw "collect_installed_runtime_inventory.ps1 failed"
}

& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\verify_torch_libs_match.ps1") -ProjectRoot $root -InstallDir $InstallDir
if ($LASTEXITCODE -ne 0) {
    throw "verify_torch_libs_match.ps1 failed"
}

& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\verify_installed_launch_only.ps1") -InstallDir $InstallDir
if ($LASTEXITCODE -ne 0) {
    throw "verify_installed_launch_only.ps1 failed"
}
