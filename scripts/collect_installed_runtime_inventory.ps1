[CmdletBinding()]
param(
    [string]$InstallDir = "D:\CareerCopilotSmoke"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $InstallDir)) {
    throw "Install directory not found at $InstallDir"
}

$targets = @(
    "career-copilot.exe",
    "_internal\setuptools\_vendor\jaraco\text\Lorem ipsum.txt",
    "_internal\torch\lib\torch.dll",
    "_internal\torch\lib\torch_cpu.dll",
    "_internal\torch\lib\torch_python.dll",
    "_internal\torch\lib\c10.dll",
    "_internal\torch\lib\libiomp5md.dll",
    "_internal\torch\lib\shm.dll"
)

foreach ($relativePath in $targets) {
    $fullPath = Join-Path $InstallDir $relativePath
    Write-Output ($relativePath + "=" + (Test-Path $fullPath))
}
