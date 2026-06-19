param(
    [string]$SourceApk = "dist/mobile/career-copilot-premium.apk",
    [string]$OutputDir = "dist/mobile/transfer"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$resolvedSourceApk = Join-Path $repoRoot $SourceApk
if (-not (Test-Path $resolvedSourceApk)) {
    throw "APK not found at $resolvedSourceApk. Build APK first."
}

$resolvedOutputDir = Join-Path $repoRoot $OutputDir
New-Item -Path $resolvedOutputDir -ItemType Directory -Force | Out-Null

$timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
$friendlyApkName = "career-copilot-premium-$timestamp.apk"
$friendlyApkPath = Join-Path $resolvedOutputDir $friendlyApkName

Copy-Item -Path $resolvedSourceApk -Destination $friendlyApkPath -Force

$hash = (Get-FileHash -Path $friendlyApkPath -Algorithm SHA256).Hash
$hashFilePath = "$friendlyApkPath.sha256.txt"
$hash | Out-File -FilePath $hashFilePath -Encoding ascii -Force

$installGuidePath = Join-Path $resolvedOutputDir "INSTALL-ANDROID.txt"
$installGuide = @(
    "Career Copilot Android Install Guide",
    "",
    "APK file:",
    $friendlyApkPath,
    "",
    "SHA256:",
    $hash,
    "",
    "Install steps:",
    "1) Copy APK to phone using USB cable (recommended).",
    "2) Open phone Files app and browse to the copied APK.",
    "3) Allow 'Install unknown apps' for Files app if prompted.",
    "4) Install the app.",
    "",
    "If phone shows 'Unable to open document':",
    "1) Re-copy APK via USB (avoid social media messengers).",
    "2) Confirm file extension is .apk.",
    "3) Try a different file manager app.",
    "4) Ensure enough free storage on phone."
)
$installGuide | Out-File -FilePath $installGuidePath -Encoding utf8 -Force

Write-Host "Transfer package prepared:" -ForegroundColor Green
Write-Host "APK:   $friendlyApkPath"
Write-Host "HASH:  $hash"
Write-Host "HASH FILE: $hashFilePath"
Write-Host "GUIDE: $installGuidePath"