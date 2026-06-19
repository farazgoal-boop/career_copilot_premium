Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location 'D:\my apps\career_copilot_premium\career_copilot_premium'

Get-Process -Name ISCC -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$iscc = 'C:\Users\HAROON TRADERS\AppData\Local\Programs\Inno Setup 6\ISCC.exe'
if (-not (Test-Path $iscc)) {
    throw 'ISCC_NOT_FOUND'
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$outBase = "CareerCopilotPremium_Setup_FIXED_$stamp"

& $iscc '/Orelease\installer\current' "/F$outBase" 'installers\windows_setup_current.iss'
if ($LASTEXITCODE -ne 0) {
    throw "ISCC_FAILED_$LASTEXITCODE"
}

$newSetup = "release\installer\current\$outBase.exe"
if (-not (Test-Path $newSetup)) {
    throw 'NEW_SETUP_MISSING'
}

$helpProc = Start-Process -FilePath $newSetup -ArgumentList '/?' -PassThru -Wait

$dest = 'ready to client'
if (-not (Test-Path $dest)) {
    New-Item -ItemType Directory -Path $dest | Out-Null
}

Copy-Item $newSetup (Join-Path $dest 'career-copilot-premium-setup.exe') -Force
if (Test-Path 'release\windows\Career Copilot Premium.exe') {
    Copy-Item 'release\windows\Career Copilot Premium.exe' (Join-Path $dest 'Career Copilot Premium.exe') -Force
}
if (Test-Path 'release\android\CareerCopilotPremium.apk') {
    Copy-Item 'release\android\CareerCopilotPremium.apk' (Join-Path $dest 'career-copilot-premium.apk') -Force
}

$srcHash = (Get-FileHash $newSetup -Algorithm SHA256).Hash
$dstHash = (Get-FileHash (Join-Path $dest 'career-copilot-premium-setup.exe') -Algorithm SHA256).Hash

Write-Output ("NEW_SETUP=" + $newSetup)
Write-Output ("HELP_EXIT=" + $helpProc.ExitCode)
Write-Output ("HASH_MATCH=" + ($srcHash -eq $dstHash))
Get-ChildItem $dest -File | Select-Object Name, Length, LastWriteTime | Sort-Object Name | Format-Table -AutoSize