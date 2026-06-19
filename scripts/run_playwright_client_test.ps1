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
$runnerScript = Join-Path $runnerDir "playwright_client_test.mjs"
$sourceScript = Join-Path $resolvedProjectRoot "scripts\playwright_client_test.mjs"
$playwrightCacheDir = Join-Path $env:LOCALAPPDATA "ms-playwright"

Write-Host ""
Write-Host "============================================================"
Write-Host " Career Copilot Premium - Playwright Client Test"
Write-Host "============================================================"
Write-Host " App URL: $BaseUrl"
Write-Host " Make sure the app is running before this test."
Write-Host ""

# Quick reachability check
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 5
    if ($health.status -ne "ok") {
        throw "Health status not ok"
    }
    Write-Host "[OK] Dashboard reachable at $BaseUrl"
} catch {
    Write-Host "[FAIL] Cannot reach $BaseUrl/api/health"
    Write-Host "       Start the app first: START_DEV.bat (keep console open)"
    exit 1
}

New-Item -ItemType Directory -Path $runnerDir -Force | Out-Null

if (-not (Test-Path (Join-Path $runnerDir "package.json"))) {
    Set-Content -Path (Join-Path $runnerDir "package.json") -Encoding utf8 -Value @'
{
  "name": "career-copilot-playwright-runner",
  "private": true
}
'@
}

Push-Location $resolvedProjectRoot
try {
    if (-not (Test-Path (Join-Path $runnerDir "node_modules\playwright"))) {
        Write-Host "[1/3] Installing Playwright..."
        Push-Location $runnerDir
        try {
            & npm.cmd install playwright --no-save
            if ($LASTEXITCODE -ne 0) { throw "npm install playwright failed" }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[1/3] Playwright already installed"
    }

    $hasChromium = (Test-Path $playwrightCacheDir) -and (@(Get-ChildItem $playwrightCacheDir -Directory -Filter "chromium*" -ErrorAction SilentlyContinue).Count -gt 0)
    if ($InstallBrowsers -or -not $hasChromium) {
        Write-Host "[2/3] Installing Chromium browser..."
        Push-Location $runnerDir
        try {
            & npx.cmd playwright install chromium
            if ($LASTEXITCODE -ne 0) { throw "playwright install chromium failed" }
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[2/3] Chromium already installed"
    }

    Copy-Item -Path $sourceScript -Destination $runnerScript -Force
    $env:CAREER_COPILOT_BASE_URL = $BaseUrl
    Write-Host "[3/3] Running client-readiness tests..."
    & node.exe $runnerScript
    if ($LASTEXITCODE -ne 0) {
        throw "Playwright client test failed."
    }
    Write-Host ""
    Write-Host "ALL PLAYWRIGHT CLIENT TESTS PASSED"
}
finally {
    Pop-Location
}
