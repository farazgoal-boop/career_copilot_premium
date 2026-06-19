param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path $PSScriptRoot -Parent
}
$Root = (Resolve-Path $Root).Path

$Deliver = Join-Path $Root "DELIVER_TO_CLIENT"
$ZipPath = Join-Path $Root "DELIVER_TO_CLIENT.zip"

Write-Host ""
Write-Host "============================================================"
Write-Host " Career Copilot Premium - DELIVER_TO_CLIENT Builder"
Write-Host "============================================================"
Write-Host " Root: $Root"
Write-Host ""

function Copy-EnvExample {
    param([string]$TargetDir)
    $source = Join-Path $Root ".env.example"
    if (Test-Path $source) {
        Copy-Item $source (Join-Path $TargetDir ".env.example") -Force
    }
}

function Copy-SourcePayload {
    param([string]$TargetDir)
    $files = @(
        "premium_launcher.py",
        "runtime_paths.py",
        "app_licensing.py",
        "requirements.txt",
        "install_mac.sh",
        "install_linux.sh",
        "START_PREMIUM.sh"
    )
    foreach ($name in $files) {
        $src = Join-Path $Root $name
        if (Test-Path $src) {
            Copy-Item $src (Join-Path $TargetDir $name) -Force
        }
    }
    foreach ($dir in @("desktop_app", "web_app", "mobile_app", "data")) {
        $srcDir = Join-Path $Root $dir
        if (-not (Test-Path $srcDir)) { continue }
        $destDir = Join-Path $TargetDir $dir
        if (Test-Path $destDir) { Remove-Item $destDir -Recurse -Force }
        Copy-Item $srcDir $destDir -Recurse -Force
        Get-ChildItem $destDir -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem $destDir -Recurse -Directory -Filter "node_modules" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        Get-ChildItem $destDir -Recurse -Directory -Filter ".git" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    $rn = Join-Path $TargetDir "mobile_app\react_native"
    if (Test-Path $rn) { Remove-Item $rn -Recurse -Force -ErrorAction SilentlyContinue }
    $cacheDir = Join-Path $TargetDir "data\cache"
    if (Test-Path $cacheDir) { Remove-Item $cacheDir -Recurse -Force -ErrorAction SilentlyContinue }
    $profilesDir = Join-Path $TargetDir "data\user_profiles"
    if (Test-Path $profilesDir) { Remove-Item $profilesDir -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Path (Join-Path $TargetDir "data\user_profiles") -Force | Out-Null
}

function Convert-HtmlToPdf {
    param(
        [string]$HtmlPath,
        [string]$PdfPath
    )
    if (-not (Test-Path $HtmlPath)) {
        Write-Warning "USER_MANUAL.html not found - skipping PDF."
        return $false
    }
    $edgeCandidates = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
    )
    $edge = $edgeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($edge) {
        $resolvedHtml = (Resolve-Path $HtmlPath).Path
        $uri = "file:///" + ($resolvedHtml -replace '\\', '/')
        if (Test-Path $PdfPath) { Remove-Item $PdfPath -Force }
        Start-Process -FilePath $edge -ArgumentList @(
            "--headless", "--disable-gpu", "--no-pdf-header-footer",
            "--print-to-pdf=$PdfPath", $uri
        ) -Wait -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 3
        if (Test-Path $PdfPath) { return $true }
    }
    Write-Warning "Edge PDF export failed - trying Python fallback."
    $python = Join-Path $Root "venv311\Scripts\python.exe"
    if (-not (Test-Path $python)) { $python = Join-Path $Root ".venv\Scripts\python.exe" }
    if (-not (Test-Path $python)) { return $false }
    $converter = Join-Path $Root "scripts\html_to_pdf.py"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $python -m pip install xhtml2pdf -q 2>&1 | Out-Null
    & $python $converter $HtmlPath $PdfPath 2>&1 | Out-Null
    $ErrorActionPreference = $prevEap
    return (Test-Path $PdfPath)
}

if (Test-Path $Deliver) { Remove-Item $Deliver -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

$winDir = Join-Path $Deliver "Windows"
$macDir = Join-Path $Deliver "Mac"
$linuxDir = Join-Path $Deliver "Linux"
$androidDir = Join-Path $Deliver "Android"
$deliverSrc = Join-Path $Root "client_package\deliver"

New-Item -ItemType Directory -Path $winDir, $macDir, $linuxDir, $androidDir -Force | Out-Null

$setupCandidates = @(
    (Join-Path $Root "dist\installer\CareerCopilotPremium_Setup_v1.0.0.exe"),
    (Join-Path $Root "ready to client\installer\CareerCopilotPremium_Setup_v1.0.0.exe"),
    (Join-Path $Root "CareerCopilotPremium_Setup_v1.0.0.exe")
)
$setup = $setupCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($setup) {
    Copy-Item $setup (Join-Path $winDir "CareerCopilotPremium_Setup_v1.0.0.exe") -Force
    Write-Host "[OK] Windows Setup.exe"
} else {
    Write-Warning "Windows Setup.exe not found. Run BUILD_CLIENT_PACKAGE.bat first."
}
Copy-EnvExample $winDir
Copy-Item (Join-Path $deliverSrc "SETUP_WINDOWS.txt") (Join-Path $winDir "SETUP_WINDOWS.txt") -Force

Copy-SourcePayload $macDir
Copy-EnvExample $macDir
Copy-Item (Join-Path $deliverSrc "SETUP_MAC.txt") (Join-Path $macDir "SETUP_MAC.txt") -Force
Write-Host "[OK] Mac source package"

Copy-SourcePayload $linuxDir
Copy-EnvExample $linuxDir
Copy-Item (Join-Path $deliverSrc "SETUP_LINUX.txt") (Join-Path $linuxDir "SETUP_LINUX.txt") -Force
Write-Host "[OK] Linux source package"

$apkCandidates = @(
    (Join-Path $Root "release\android\CareerCopilotPremium.apk"),
    (Join-Path $Root "ready to client\android\CareerCopilotPremium.apk"),
    (Join-Path $Root "dist\mobile\career-copilot-premium.apk")
)
$apk = $apkCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($apk) {
    Copy-Item $apk (Join-Path $androidDir "CareerCopilotPremium.apk") -Force
    Write-Host "[OK] Android APK"
} else {
    Write-Warning "Android APK not found. Run scripts/build_apk.bat first."
}
Copy-Item (Join-Path $deliverSrc "SETUP_ANDROID.txt") (Join-Path $androidDir "SETUP_ANDROID.txt") -Force

Copy-Item (Join-Path $deliverSrc "README.txt") (Join-Path $Deliver "README.txt") -Force
Copy-Item (Join-Path $deliverSrc "VIRUSTOTAL-LINK.txt") (Join-Path $Deliver "VIRUSTOTAL-LINK.txt") -Force

$htmlManual = Join-Path $Root "docs\USER_MANUAL.html"
$pdfManual = Join-Path $Deliver "USER_MANUAL.pdf"
$pdfOk = $false
try {
    $pdfOk = Convert-HtmlToPdf -HtmlPath $htmlManual -PdfPath $pdfManual
} catch {
    $pdfOk = $false
}
if ($pdfOk) {
    Write-Host "[OK] USER_MANUAL.pdf"
    $htmlFallback = Join-Path $Deliver "USER_MANUAL.html"
    if (Test-Path $htmlFallback) { Remove-Item $htmlFallback -Force }
} else {
    Write-Warning "Could not create USER_MANUAL.pdf - USER_MANUAL.html copied as fallback."
    if (Test-Path $htmlManual) {
        Copy-Item $htmlManual (Join-Path $Deliver "USER_MANUAL.html") -Force
    }
}

Compress-Archive -Path (Join-Path $Deliver "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "============================================================"
Write-Host " DELIVER_TO_CLIENT READY"
Write-Host "============================================================"
Write-Host " Folder: $Deliver"
Write-Host " ZIP:    $ZipPath"
Write-Host ""
Write-Host " File sizes:"
Get-ChildItem $Deliver -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($Deliver.Length).TrimStart('\')
    $sizeMb = [math]::Round($_.Length / 1MB, 2)
    if ($sizeMb -ge 0.01 -or $_.Extension -match '\.(exe|apk|pdf|zip)$') {
        Write-Host ("  {0,-50} {1,8} MB" -f $rel, $sizeMb)
    }
}
if (Test-Path $ZipPath) {
    $zipMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 2)
    Write-Host ""
    Write-Host ("  DELIVER_TO_CLIENT.zip (total)                    {0,8} MB" -f $zipMb)
}
Write-Host ""
