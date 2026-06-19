[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [switch]$InstallBrowsers
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$runnerDir = Join-Path $resolvedProjectRoot ".playwright-smoke-runner"
$runnerScript = Join-Path $runnerDir "playwright_smoke_test.mjs"
$sourceScript = Join-Path $resolvedProjectRoot "scripts\playwright_smoke_test.mjs"
$playwrightCacheDir = Join-Path $env:LOCALAPPDATA "ms-playwright"

New-Item -ItemType Directory -Path $runnerDir -Force | Out-Null

if (-not (Test-Path (Join-Path $runnerDir "package.json"))) {
    Set-Content -Path (Join-Path $runnerDir "package.json") -Encoding utf8 -Value @'
{
  "name": "career-copilot-playwright-smoke-runner",
  "private": true
}
'@
}

Push-Location $resolvedProjectRoot
try {
    if (-not (Test-Path (Join-Path $runnerDir "node_modules\playwright"))) {
        Push-Location $runnerDir
        try {
            & npm.cmd install playwright --no-save
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install Playwright into $runnerDir"
            }
        }
        finally {
            Pop-Location
        }
    }

    $hasChromium = (Test-Path $playwrightCacheDir) -and (@(Get-ChildItem $playwrightCacheDir -Directory -Filter "chromium*" -ErrorAction SilentlyContinue).Count -gt 0)
    if ($InstallBrowsers -or -not $hasChromium) {
        Push-Location $runnerDir
        try {
            & npx.cmd playwright install chromium
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install Playwright Chromium browser."
            }
        }
        finally {
            Pop-Location
        }
    }

    Copy-Item -Path $sourceScript -Destination $runnerScript -Force
    $env:CAREER_COPILOT_BASE_URL = $BaseUrl
    & node.exe $runnerScript
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright smoke test failed."
    }
    Write-Host "Playwright smoke passed against $BaseUrl"
}
finally {
    Pop-Location
}