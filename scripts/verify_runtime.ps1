[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$AppBaseUrl = "http://127.0.0.1:5000",
    [string]$OllamaBaseUrl = "http://127.0.0.1:11434",
    [string]$OllamaModel = "llama3.2:1b",
    [switch]$LaunchBundle,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$bundleDir = Join-Path $resolvedProjectRoot "dist\windows-bundle"
$exePath = Join-Path $bundleDir "career-copilot.exe"

function Invoke-JsonGet {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSec = 10
    )

    $response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec $TimeoutSec
    return ($response.Content | ConvertFrom-Json)
}

function Get-ErrorMessage {
    param(
        [Parameter(Mandatory = $true)]
        [System.Management.Automation.ErrorRecord]$ErrorRecord
    )

    $exceptionMessage = [string]$ErrorRecord.Exception.Message
    if ($ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        return [string]$ErrorRecord.ErrorDetails.Message
    }
    return $exceptionMessage
}

function Wait-ForHttpOk {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$Attempts = 20,
        [int]$TimeoutSec = 5
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec $TimeoutSec
            if ($response.StatusCode -eq 200) {
                return ($response.Content | ConvertFrom-Json)
            }
        }
        catch {
        }
        Start-Sleep -Milliseconds 500
    }

    throw "Runtime endpoint did not become ready: $Url"
}

if ($LaunchBundle) {
    if (-not (Test-Path $exePath)) {
        throw "Packaged executable not found at $exePath"
    }

    Stop-Process -Name "career-copilot" -Force -ErrorAction SilentlyContinue
    Start-Process -FilePath $exePath -WorkingDirectory $bundleDir | Out-Null
}

$appError = $null
$healthPayload = $null
$recentPayload = @{ sessions = @() }
$briefingPayload = @{ microphone = @{ can_capture = $false } }

try {
    $healthPayload = Wait-ForHttpOk -Url "$AppBaseUrl/api/health"
    $recentPayload = Invoke-JsonGet -Url "$AppBaseUrl/api/sessions/recent"
    $briefingPayload = Invoke-JsonGet -Url "$AppBaseUrl/api/briefing"
}
catch {
    $appError = Get-ErrorMessage -ErrorRecord $_
}

$ollamaRequest = @{
    model = $OllamaModel
    prompt = "Reply with exactly: OK"
    stream = $false
} | ConvertTo-Json -Compress

$ollamaPayload = $null
$ollamaError = $null
try {
    $ollamaPayload = Invoke-RestMethod "$OllamaBaseUrl/api/generate" -Method Post -ContentType "application/json" -Body $ollamaRequest -TimeoutSec 30
}
catch {
    $ollamaError = Get-ErrorMessage -ErrorRecord $_
}

$appOk = [bool]($healthPayload -and $healthPayload.ok)
$ollamaOk = [bool]($ollamaPayload -and $ollamaPayload.done -and -not [string]::IsNullOrWhiteSpace([string]$ollamaPayload.response))

$results = [ordered]@{
    checked_at = (Get-Date).ToString("o")
    app_base_url = $AppBaseUrl
    ollama_base_url = $OllamaBaseUrl
    bundle_path = $exePath
    app_ok = $appOk
    app_error = $appError
    microphone_runtime_available = [bool]($healthPayload -and $healthPayload.microphone.runtime_available)
    microphone_input_available = [bool]($healthPayload -and $healthPayload.microphone.input_available)
    microphone_can_capture = [bool]($healthPayload -and $healthPayload.microphone.can_capture)
    microphone_message = [string]($(if ($healthPayload) { $healthPayload.microphone.message } else { "" }))
    recent_session_count = @($recentPayload.sessions).Count
    briefing_microphone_can_capture = [bool]($briefingPayload.microphone.can_capture)
    ollama_model = [string]($(if ($ollamaPayload) { $ollamaPayload.model } else { $OllamaModel }))
    ollama_response = [string]($(if ($ollamaPayload) { $ollamaPayload.response } else { "" }))
    ollama_done = [bool]($ollamaPayload -and $ollamaPayload.done)
    ollama_error = $ollamaError
    passed = [bool]($appOk -and $ollamaOk)
}

if ($Json) {
    $results | ConvertTo-Json -Depth 5
    exit ($(if ($results.passed) { 0 } else { 1 }))
}

Write-Host "Career Copilot Runtime Verification"
Write-Host "App URL: $($results.app_base_url)"
Write-Host "Ollama URL: $($results.ollama_base_url)"
Write-Host "App health: $($results.app_ok)"
Write-Host "Microphone runtime available: $($results.microphone_runtime_available)"
Write-Host "Microphone input available: $($results.microphone_input_available)"
Write-Host "Microphone can capture: $($results.microphone_can_capture)"
Write-Host "Microphone message: $($results.microphone_message)"
Write-Host "Recent sessions: $($results.recent_session_count)"
Write-Host "Briefing microphone can capture: $($results.briefing_microphone_can_capture)"
Write-Host "Ollama model: $($results.ollama_model)"
Write-Host "Ollama response: $($results.ollama_response)"
Write-Host "PASS: $($results.passed)"

exit ($(if ($results.passed) { 0 } else { 1 }))