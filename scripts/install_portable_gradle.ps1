param(
    [string]$Version = "8.7"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Join-Path $projectRoot "tools"
$gradleRoot = Join-Path $toolsRoot "gradle"
$versionRoot = Join-Path $gradleRoot ("gradle-" + $Version)
$distributionZip = Join-Path $gradleRoot ("gradle-" + $Version + "-bin.zip")
$distributionUrl = "https://services.gradle.org/distributions/gradle-" + $Version + "-bin.zip"

New-Item -Path $gradleRoot -ItemType Directory -Force | Out-Null

if (Test-Path (Join-Path $versionRoot "bin\gradle.bat")) {
    Write-Host "Portable Gradle already installed at $versionRoot"
    exit 0
}

Write-Host "Downloading Gradle $Version from $distributionUrl"
Invoke-WebRequest -Uri $distributionUrl -OutFile $distributionZip

Write-Host "Extracting portable Gradle to $gradleRoot"
Expand-Archive -Path $distributionZip -DestinationPath $gradleRoot -Force

if (-not (Test-Path (Join-Path $versionRoot "bin\gradle.bat"))) {
    throw "Gradle download completed, but gradle.bat was not found under $versionRoot"
}

Write-Host "Portable Gradle installed at $versionRoot"