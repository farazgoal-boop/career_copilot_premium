param(
    [string]$PackageDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $PackageDir) {
    $PackageDir = Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..")).Path "ready to client"
}
$PackageDir = (Resolve-Path $PackageDir).Path
$projectRoot = Split-Path $PackageDir -Parent
$securityDir = Join-Path $PackageDir "security"
New-Item -Path $securityDir -ItemType Directory -Force | Out-Null

$manifestPath = Join-Path $securityDir "SHA256-MANIFEST.txt"
$vtPath = Join-Path $securityDir "VIRUSTOTAL-LINK.txt"

$includeRoots = @(
    (Join-Path $PackageDir "installer"),
    (Join-Path $PackageDir "android"),
    (Join-Path $PackageDir "mac"),
    (Join-Path $PackageDir "linux"),
    (Join-Path $PackageDir "requirements"),
    (Join-Path $PackageDir "docs"),
    (Join-Path $PackageDir "README-START-HERE.txt"),
    (Join-Path $PackageDir "SETUP_GUIDE_WINDOWS.txt"),
    (Join-Path $PackageDir ".env.example")
)

$lines = @("Career Copilot Premium - SHA256 Manifest", "Generated: $(Get-Date -Format o)", "")
$files = @()
foreach ($root in $includeRoots) {
    if (-not (Test-Path $root)) { continue }
    if ((Get-Item $root).PSIsContainer) {
        $files += Get-ChildItem -Path $root -Recurse -File
    } else {
        $files += Get-Item $root
    }
}

foreach ($file in $files) {
    $hash = (Get-FileHash -Path $file.FullName -Algorithm SHA256).Hash
    $relative = $file.FullName.Substring($PackageDir.Length).TrimStart('\')
    $lines += "$relative"
    $lines += "  SHA256: $hash"
    $lines += ""
}

$lines | Out-File -FilePath $manifestPath -Encoding utf8

if (-not (Test-Path $vtPath)) {
    @(
        "VirusTotal Scan",
        "===============",
        "",
        "Upload this file to https://www.virustotal.com :",
        "  installer/CareerCopilotPremium_Setup_v1.0.0.exe",
        "",
        "Paste the public scan link below after upload:",
        "LINK: (pending - upload Setup.exe and paste link here)",
        "",
        "Note: Unsigned PyInstaller apps may show 2-5 false positives."
    ) | Out-File -FilePath $vtPath -Encoding utf8
}

$zipPath = Join-Path $projectRoot "CareerCopilotPremium-v1.0.0-CLIENT.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$staging = Join-Path $projectRoot "dist\client-zip-staging"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

foreach ($name in @("installer", "android", "mac", "linux", "requirements", "docs")) {
    $source = Join-Path $PackageDir $name
    if (Test-Path $source) {
        Copy-Item -Path $source -Destination (Join-Path $staging $name) -Recurse -Force
    }
}
if (Test-Path (Join-Path $PackageDir "README-START-HERE.txt")) {
    Copy-Item (Join-Path $PackageDir "README-START-HERE.txt") (Join-Path $staging "README-START-HERE.txt") -Force
}
if (Test-Path (Join-Path $PackageDir ".env.example")) {
    Copy-Item (Join-Path $PackageDir ".env.example") (Join-Path $staging ".env.example") -Force
} elseif (Test-Path (Join-Path $projectRoot ".env.example")) {
    Copy-Item (Join-Path $projectRoot ".env.example") (Join-Path $staging ".env.example") -Force
}
$stagingSecurity = Join-Path $staging "security"
New-Item -ItemType Directory -Path $stagingSecurity -Force | Out-Null
Copy-Item $manifestPath (Join-Path $stagingSecurity "SHA256-MANIFEST.txt") -Force
Copy-Item $vtPath (Join-Path $stagingSecurity "VIRUSTOTAL-LINK.txt") -Force

Compress-Archive -Path (Join-Path $staging "*") -DestinationPath $zipPath -Force
$zipSizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host "Manifest: $manifestPath"
Write-Host "ZIP: $zipPath ($zipSizeMb MB)"
