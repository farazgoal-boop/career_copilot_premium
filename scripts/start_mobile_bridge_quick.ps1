param(
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

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return "$($py.Source) -3"
    }

    throw "Python not found. Install Python 3 or create .venv first."
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
        $entry = $item.Value
        $updatedAt = ""
        if ($entry -and $entry.PSObject.Properties.Name -contains "updated_at") {
            $updatedAt = [string]$entry.updated_at
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
            UpdatedAt = $updatedAt
            SortTicks = $sortTicks
        }
    }

    if (-not $entries) {
        return $null
    }

    return ($entries | Sort-Object SortTicks -Descending | Select-Object -First 1).SessionId
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
    $deepLink = "careercopilot://connect?baseUrl=$([uri]::EscapeDataString($baseUrl))"
    if ($SessionId) {
        $deepLink += "&sessionId=$([uri]::EscapeDataString($SessionId))"
    }

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

$pythonExecutable = Resolve-PythonExecutable
$registryPath = Join-Path $repoRoot "data\cache\session_registry.json"
$latestSessionId = Get-LatestSessionId -RegistryPath $registryPath
$lanIps = Get-LanAddresses

Write-Host ""
Write-Host "Career Copilot Mobile Bridge Launcher" -ForegroundColor Cyan
Write-Host "Repo root: $repoRoot"
Write-Host "Bridge host: $BridgeHost"
Write-Host "Bridge port: $Port"

if ($lanIps -and $lanIps.Count -gt 0) {
    Write-Host ""
    Write-Host "Use one of these URLs in your phone app:" -ForegroundColor Yellow
    foreach ($ip in $lanIps) {
        Write-Host "  http://$ip`:$Port"
    }
}

if ($latestSessionId) {
    Write-Host ""
    Write-Host "Latest Session ID (auto-use in mobile app):" -ForegroundColor Green
    Write-Host "  $latestSessionId"
} else {
    Write-Host ""
    Write-Host "No saved session found." -ForegroundColor Yellow
    Write-Host "Start a desktop session first, then tap 'Fetch Sessions' in mobile app."
}

Show-DeepLinkQr -LanIps $lanIps -BridgePort $Port -SessionId $latestSessionId

Write-Host ""
Write-Host "Starting live bridge... Press Ctrl+C to stop." -ForegroundColor Cyan

if ($pythonExecutable -like "* -3") {
    & py -3 -m desktop_app.main --serve-mobile-bridge --mobile-bridge-host $BridgeHost --mobile-bridge-port $Port --session-registry-path $registryPath
} else {
    & $pythonExecutable -m desktop_app.main --serve-mobile-bridge --mobile-bridge-host $BridgeHost --mobile-bridge-port $Port --session-registry-path $registryPath
}