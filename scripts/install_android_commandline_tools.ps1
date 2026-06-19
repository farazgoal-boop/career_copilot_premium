[CmdletBinding()]
param(
    [string]$SdkRoot,
    [string]$ToolsZipUrl = "https://dl.google.com/android/repository/commandlinetools-win-14742923_latest.zip",
    [string]$AndroidPlatform = "platforms;android-34",
    [string]$BuildToolsVersion = "34.0.0",
    [switch]$SkipPackageInstall,
    [switch]$PersistEnvironment
)

$ErrorActionPreference = "Stop"

function Resolve-SdkRoot {
    param([string]$ConfiguredPath)

    if ($ConfiguredPath) {
        return $ConfiguredPath
    }
    if ($env:ANDROID_SDK_ROOT) {
        return $env:ANDROID_SDK_ROOT
    }
    if ($env:ANDROID_HOME) {
        return $env:ANDROID_HOME
    }
    return Join-Path $env:LOCALAPPDATA 'Android\Sdk'
}

function Install-CommandLineTools {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetSdkRoot,
        [Parameter(Mandatory = $true)]
        [string]$DownloadUrl
    )

    $cmdlineToolsRoot = Join-Path $TargetSdkRoot 'cmdline-tools'
    $latestRoot = Join-Path $cmdlineToolsRoot 'latest'
    $sdkManagerPath = Join-Path $latestRoot 'bin\sdkmanager.bat'
    if (Test-Path $sdkManagerPath) {
        return $sdkManagerPath
    }

    New-Item -ItemType Directory -Path $cmdlineToolsRoot -Force | Out-Null

    $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("ccp-android-tools-" + [guid]::NewGuid().ToString("N"))
    $archivePath = Join-Path $tempDirectory 'commandlinetools.zip'
    $extractPath = Join-Path $tempDirectory 'extract'

    try {
        New-Item -ItemType Directory -Path $extractPath -Force | Out-Null
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $archivePath
        Expand-Archive -Path $archivePath -DestinationPath $extractPath -Force

        $expandedRoot = Join-Path $extractPath 'cmdline-tools'
        if (-not (Test-Path $expandedRoot)) {
            throw "Downloaded Android command-line tools archive is missing the expected cmdline-tools folder."
        }

        if (Test-Path $latestRoot) {
            Remove-Item -Path $latestRoot -Recurse -Force
        }
        New-Item -ItemType Directory -Path $latestRoot -Force | Out-Null
        Get-ChildItem -Path $expandedRoot -Force | ForEach-Object {
            Move-Item -Path $_.FullName -Destination $latestRoot -Force
        }

        if (-not (Test-Path $sdkManagerPath)) {
            throw "Android sdkmanager.bat was not found after extracting the command-line tools."
        }

        return $sdkManagerPath
    }
    finally {
        if (Test-Path $tempDirectory) {
            Remove-Item -Path $tempDirectory -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Install-AndroidPackages {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SdkManagerPath,
        [Parameter(Mandatory = $true)]
        [string]$TargetSdkRoot,
        [Parameter(Mandatory = $true)]
        [string]$PlatformPackage,
        [Parameter(Mandatory = $true)]
        [string]$BuildTools
    )

    $packageArgs = @(
        "--sdk_root=$TargetSdkRoot",
        'platform-tools',
        $PlatformPackage,
        "build-tools;$BuildTools"
    )

    $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("ccp-android-licenses-" + [guid]::NewGuid().ToString("N"))
    $licenseAnswersPath = Join-Path $tempDirectory 'licenses.txt'

    try {
        New-Item -ItemType Directory -Path $tempDirectory -Force | Out-Null
        Set-Content -Path $licenseAnswersPath -Value ((1..200 | ForEach-Object { 'y' }) -join [Environment]::NewLine) -Encoding ASCII
        $licenseCommand = 'type "' + $licenseAnswersPath + '" | "' + $SdkManagerPath + '" --licenses --sdk_root="' + $TargetSdkRoot + '"'
        cmd.exe /d /c $licenseCommand | Out-Null
    }
    finally {
        if (Test-Path $tempDirectory) {
            Remove-Item -Path $tempDirectory -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    & $SdkManagerPath @packageArgs
}

function Persist-SdkEnvironment {
    param([Parameter(Mandatory = $true)][string]$TargetSdkRoot)

    [Environment]::SetEnvironmentVariable('ANDROID_SDK_ROOT', $TargetSdkRoot, 'User')
    [Environment]::SetEnvironmentVariable('ANDROID_HOME', $TargetSdkRoot, 'User')
}

$resolvedSdkRoot = Resolve-SdkRoot -ConfiguredPath $SdkRoot
New-Item -ItemType Directory -Path $resolvedSdkRoot -Force | Out-Null

$sdkManager = Install-CommandLineTools -TargetSdkRoot $resolvedSdkRoot -DownloadUrl $ToolsZipUrl

if (-not $SkipPackageInstall) {
    Install-AndroidPackages -SdkManagerPath $sdkManager -TargetSdkRoot $resolvedSdkRoot -PlatformPackage $AndroidPlatform -BuildTools $BuildToolsVersion
}

if ($PersistEnvironment) {
    Persist-SdkEnvironment -TargetSdkRoot $resolvedSdkRoot
}

[pscustomobject]@{
    sdk_root = $resolvedSdkRoot
    sdkmanager = $sdkManager
    platform_tools = Join-Path $resolvedSdkRoot 'platform-tools'
    android_platform = Join-Path $resolvedSdkRoot 'platforms\android-34'
    build_tools = Join-Path $resolvedSdkRoot ("build-tools\\" + $BuildToolsVersion)
    environment_persisted = [bool]$PersistEnvironment
} | ConvertTo-Json -Depth 3