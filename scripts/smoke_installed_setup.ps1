$ErrorActionPreference = 'Stop'

$setupPath = Join-Path (Get-Location) 'dist\installer\CareerCopilotPremium_Setup_v1.0.0.exe'
$installDir = 'D:\cc_smoke_install'

if (-not (Test-Path $setupPath)) {
    throw "Setup not found: $setupPath"
}

$tempSetupPath = Join-Path $env:TEMP 'CareerCopilotPremium_Setup_smoke.exe'
if (Test-Path $tempSetupPath) {
    Remove-Item $tempSetupPath -Force -ErrorAction SilentlyContinue
}
Copy-Item $setupPath $tempSetupPath -Force

if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
}

$installer = Start-Process -FilePath $tempSetupPath -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',('/DIR=' + $installDir) -Wait -PassThru
Write-Output ("INSTALL_EXIT={0}" -f $installer.ExitCode)

$mainExe = Get-ChildItem -Path $installDir -File -Filter '*.exe' -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -notlike 'unins*' } |
    Select-Object -First 1
$exePath = if ($mainExe) { $mainExe.FullName } else { '' }
Write-Output ("INSTALLED_EXE={0}" -f $exePath)
Write-Output ("INSTALLED_EXE_EXISTS={0}" -f [bool]$mainExe)
if (-not $mainExe) {
    exit 1
}

$app = Start-Process -FilePath $exePath -PassThru

$healthOk = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/health' -TimeoutSec 2
        if ($health.ok -eq $true) {
            $healthOk = $true
            break
        }
    }
    catch {
    }
}
Write-Output ("HEALTH_OK={0}" -f $healthOk)

$onboardingOk = $false
$sessionId = ''
if ($healthOk) {
    try {
        $headers = @{
            Accept = 'application/json'
            'X-Requested-With' = 'XMLHttpRequest'
        }
        $body = @{
            full_name = 'Smoke User'
            target_name = 'Acme AI'
            current_role = 'Engineer'
            product_description = 'Smoke test session'
        }
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/onboarding?response_format=json' -Method Post -Body $body -ContentType 'application/x-www-form-urlencoded' -Headers $headers -TimeoutSec 30
        $onboardingOk = [bool]$response.ok
        $sessionId = [string]$response.session_id
        Write-Output ("ONBOARDING_PAYLOAD={0}" -f ($response | ConvertTo-Json -Compress))
    }
    catch {
        $onboardingOk = $false
        $sessionId = ''
        Write-Output ("ONBOARDING_ERROR={0}" -f $_.Exception.Message)
    }
}

Write-Output ("ONBOARDING_OK={0}" -f $onboardingOk)
Write-Output ("SESSION_ID={0}" -f $sessionId)

Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
Get-Process -Name 'career-copilot' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
