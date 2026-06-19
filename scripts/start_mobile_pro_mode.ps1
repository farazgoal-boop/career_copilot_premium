param(
    [string]$ProfileDir = "data/user_profiles/amina-khan",
    [string]$Company = "Acme AI",
    [string]$Role = "Staff Backend Engineer",
    [int]$Port = 8765,
    [string]$BridgeHost = "0.0.0.0"
)

$ErrorActionPreference = "Stop"

function Resolve-PythonExecutable {
    $repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
    $candidatePaths = @(
        (Join-Path $repoRoot ".venv\Scripts\python.exe"),
        (Join-Path $repoRoot "temp_restore\.venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidatePaths) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Python executable not found."
}

function Get-LatestSessionId {
    param([string]$RegistryPath)

    if (-not (Test-Path $RegistryPath)) {
        return $null
    }

    $jsonText = Get-Content -Path $RegistryPath -Raw -Encoding UTF8
    if (-not $jsonText.Trim()) {
        return $null
    }

    $registry = ConvertFrom-Json -InputObject $jsonText
    if (-not $registry) {
        return $null
    }

    $entries = @()
    foreach ($item in $registry.PSObject.Properties) {
        $sessionId = $item.Name
        $updatedAt = ""
        if ($item.Value -and $item.Value.PSObject.Properties.Name -contains "updated_at") {
            $updatedAt = [string]$item.Value.updated_at
        }

        $sortTicks = [DateTimeOffset]::MinValue.UtcTicks
        try {
            if ($updatedAt) {
                $sortTicks = ([DateTimeOffset]::Parse($updatedAt)).UtcTicks
            }
        } catch {
            $sortTicks = [DateTimeOffset]::MinValue.UtcTicks
        }

        $entries += [PSCustomObject]@{
            SessionId = $sessionId
            SortTicks = $sortTicks
        }
    }

    if (-not $entries) {
        return $null
    }

    return ($entries | Sort-Object SortTicks -Descending | Select-Object -First 1).SessionId
}

function Get-LanAddresses {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike '127.*' -and
            $_.IPAddress -notlike '169.254.*' -and
            $_.PrefixOrigin -ne 'WellKnown'
        } |
        Select-Object -ExpandProperty IPAddress -Unique
}

function Show-DeepLinkQr {
    param(
        [string[]]$LanIps,
        [int]$BridgePort,
        [string]$SessionId
    )

    if (-not $LanIps -or $LanIps.Count -eq 0) {
        return
    }

    $targetIp = $LanIps[0]
    $baseUrl = "http://$targetIp`:$BridgePort"
    $deepLink = "careercopilot://connect?baseUrl=$([uri]::EscapeDataString($baseUrl))&sessionId=$([uri]::EscapeDataString($SessionId))"

    Write-Host ""
    Write-Host "Mobile QR Deep Link:" -ForegroundColor Green
    Write-Host "  $deepLink"

    try {
        $qrUrl = "https://api.qrserver.com/v1/create-qr-code/?size=320x320&data=$([uri]::EscapeDataString($deepLink))"
        Write-Host "Opening QR in browser for instant scan..." -ForegroundColor Cyan
        Start-Process $qrUrl | Out-Null
    }
    catch {
        Write-Host "Could not auto-open QR link. Use the deep link above in any QR generator." -ForegroundColor Yellow
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$pythonExe = Resolve-PythonExecutable
$registryPath = Join-Path $repoRoot "data\cache\session_registry.json"
$resolvedProfileDir = Join-Path $repoRoot $ProfileDir

if (-not (Test-Path $resolvedProfileDir)) {
    throw "Profile directory not found: $resolvedProfileDir"
}

Write-Host "Creating/updating session..." -ForegroundColor Cyan
& $pythonExe -m desktop_app.main --profile-dir $resolvedProfileDir --company $Company --role $Role --start-session --session-registry-path $registryPath

$latestSessionId = Get-LatestSessionId -RegistryPath $registryPath
if (-not $latestSessionId) {
    throw "Could not resolve latest session ID from registry."
}

Write-Host "Starting worker in background window..." -ForegroundColor Cyan
$workerCmd = "Set-Location '$repoRoot'; & '$pythonExe' -m desktop_app.main --session-id '$latestSessionId' --run-session-worker --session-registry-path '$registryPath'"
Start-Process powershell -ArgumentList '-NoExit', '-Command', $workerCmd | Out-Null

$lanIps = Get-LanAddresses
Write-Host ""
Write-Host "Mobile setup" -ForegroundColor Green
if ($lanIps -and $lanIps.Count -gt 0) {
    foreach ($ip in $lanIps) {
        Write-Host "Bridge URL: http://$ip`:$Port"
    }
}
Write-Host "Session ID: $latestSessionId"

Show-DeepLinkQr -LanIps $lanIps -BridgePort $Port -SessionId $latestSessionId

Write-Host ""
Write-Host "Starting live bridge in this window (Ctrl+C to stop)..." -ForegroundColor Cyan

& $pythonExe -m desktop_app.main --serve-mobile-bridge --mobile-bridge-host $BridgeHost --mobile-bridge-port $Port --session-registry-path $registryPath