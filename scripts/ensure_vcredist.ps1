param(
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
if (-not $Target) {
    $Target = Join-Path (Split-Path $PSScriptRoot -Parent) "installers\windows\assets\vc_redist.x64.exe"
}

$dir = Split-Path $Target -Parent
New-Item -ItemType Directory -Path $dir -Force | Out-Null

if (Test-Path $Target) {
    $size = (Get-Item $Target).Length
    if ($size -gt 10MB) {
        Write-Host "[OK] VC++ redistributable already present: $Target"
        exit 0
    }
}

$url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
Write-Host "Downloading VC++ redistributable..."
Invoke-WebRequest -Uri $url -OutFile $Target -UseBasicParsing
Write-Host "[OK] Saved: $Target"
