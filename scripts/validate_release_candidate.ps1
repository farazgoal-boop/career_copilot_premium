[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\build_release_candidate.ps1") -ProjectRoot $root
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\verify_setup_only.ps1") -ProjectRoot $root -InstallDir "D:\CareerCopilotSmoke"
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\collect_installed_runtime_inventory.ps1") -InstallDir "D:\CareerCopilotSmoke"
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\verify_torch_libs_match.ps1") -ProjectRoot $root -InstallDir "D:\CareerCopilotSmoke"
& "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\verify_installed_launch_only.ps1") -InstallDir "D:\CareerCopilotSmoke"
