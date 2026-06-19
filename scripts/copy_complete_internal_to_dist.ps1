[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = (Resolve-Path $ProjectRoot).Path
$src = Join-Path $root "build\pyinstaller-dist\career-copilot\_internal"
$dst = Join-Path $root "dist\windows-bundle\_internal"

if (-not (Test-Path $src)) {
    throw "Source _internal folder not found at $src"
}

if (Test-Path $dst) {
    Remove-Item $dst -Recurse -Force
}

Copy-Item -Path $src -Destination $dst -Recurse -Force

Write-Output ("DIST_INTERNAL_READY=" + (Test-Path $dst))
Write-Output ("LOREM_EXISTS=" + (Test-Path (Join-Path $dst "setuptools\_vendor\jaraco\text\Lorem ipsum.txt")))
Write-Output ("TORCH_C10_EXISTS=" + (Test-Path (Join-Path $dst "torch\lib\c10.dll")))
