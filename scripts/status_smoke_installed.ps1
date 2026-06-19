[CmdletBinding()]
param(
    [string]$InstallDir = "D:\CareerCopilotSmoke"
)

$ErrorActionPreference = "Stop"
Write-Output ("INSTALL_DIR_EXISTS=" + (Test-Path $InstallDir))
if (Test-Path $InstallDir) {
    Write-Output ("EXE_EXISTS=" + (Test-Path (Join-Path $InstallDir "career-copilot.exe")))
    Write-Output ("LOREM_EXISTS=" + (Test-Path (Join-Path $InstallDir "_internal\setuptools\_vendor\jaraco\text\Lorem ipsum.txt")))
    Write-Output ("C10_EXISTS=" + (Test-Path (Join-Path $InstallDir "_internal\torch\lib\c10.dll")))
    Write-Output ("LIBIOMP_EXISTS=" + (Test-Path (Join-Path $InstallDir "_internal\torch\lib\libiomp5md.dll")))
    Write-Output ("SHM_EXISTS=" + (Test-Path (Join-Path $InstallDir "_internal\torch\lib\shm.dll")))
}
