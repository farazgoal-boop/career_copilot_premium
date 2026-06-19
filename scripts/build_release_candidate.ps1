[CmdletBinding()]
param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = (Resolve-Path $ProjectRoot).Path
$buildBat = Join-Path $root "BUILD_CLIENT_PACKAGE.bat"

if (-not (Test-Path $buildBat)) {
    throw "BUILD_CLIENT_PACKAGE.bat not found at $buildBat"
}

Push-Location $root
try {
    & cmd.exe /c "`"$buildBat`""
    if ($LASTEXITCODE -ne 0) {
        throw "BUILD_CLIENT_PACKAGE.bat failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}

Write-Output "RELEASE_CANDIDATE_READY"
