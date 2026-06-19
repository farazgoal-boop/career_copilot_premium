$ErrorActionPreference = 'Stop'

$exe = 'D:\my\career-copilot.exe'
if (-not (Test-Path $exe)) {
    throw "Installed exe not found at $exe"
}

$app = Start-Process -FilePath $exe -PassThru

$healthOk = $false
for ($i = 0; $i -lt 40; $i++) {
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
        Write-Output ("ONBOARDING_OK={0}" -f [bool]$response.ok)
        Write-Output ("SESSION_ID={0}" -f [string]$response.session_id)
        Write-Output ("ONBOARDING_PAYLOAD={0}" -f ($response | ConvertTo-Json -Compress))
    }
    catch {
        Write-Output 'ONBOARDING_OK=False'
        Write-Output ("ONBOARDING_ERROR={0}" -f $_.Exception.Message)
    }
}
else {
    Write-Output 'ONBOARDING_SKIPPED_NO_HEALTH'
}

Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
Get-Process -Name 'career-copilot' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
