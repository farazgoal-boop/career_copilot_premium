param(
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
$minimumGradleVersion = [version]"8.7"

function Get-GradlePropertiesCandidatePaths {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    return @(
        (Join-Path $env:USERPROFILE '.gradle\gradle.properties'),
        (Join-Path $projectRoot 'mobile_app\react_native\android\gradle.properties')
    )
}

function Get-GradlePropertyOrEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $escapedName = [regex]::Escape($Name)
    foreach ($path in Get-GradlePropertiesCandidatePaths) {
        if (-not (Test-Path $path)) {
            continue
        }

        $match = Select-String -Path $path -Pattern ("^\s*" + $escapedName + "\s*=\s*(.*)$") -CaseSensitive:$false | Select-Object -First 1
        if ($match -and $match.Matches.Count -gt 0) {
            return $match.Matches[0].Groups[1].Value.Trim()
        }
    }

    return ""
}

function Get-SigningSettingOrEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [switch]$MaskValue
    )

    $value = [Environment]::GetEnvironmentVariable($Name)
    if (-not $value) {
        $value = Get-GradlePropertyOrEmpty -Name $Name
    }
    if (-not $value) {
        return ""
    }
    if ($MaskValue) {
        return "configured"
    }
    return $value
}

function Get-CommandPathOrEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return ""
    }
    return $command.Source
}

function Get-FirstExistingPathOrEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Paths
    )

    foreach ($path in $Paths) {
        if (Test-Path $path) {
            return $path
        }
    }

    return ""
}

function Get-NodePathOrEmpty {
    $resolved = Get-CommandPathOrEmpty -Name "node"
    if ($resolved) {
        return $resolved
    }
    return Get-FirstExistingPathOrEmpty -Paths @(
        'C:\Program Files\nodejs\node.exe',
        'C:\Program Files (x86)\nodejs\node.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe')
    )
}

function Get-NpmPathOrEmpty {
    $resolved = Get-CommandPathOrEmpty -Name "npm"
    if ($resolved) {
        return $resolved
    }
    return Get-FirstExistingPathOrEmpty -Paths @(
        'C:\Program Files\nodejs\npm.cmd',
        'C:\Program Files (x86)\nodejs\npm.cmd',
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\npm.cmd')
    )
}

function Get-JavaPathOrEmpty {
    $resolved = Get-CommandPathOrEmpty -Name "java"
    if ($resolved) {
        return $resolved
    }

    $patterns = @(
        'C:\Program Files\Microsoft\jdk-*\bin\java.exe',
        'C:\Program Files\Eclipse Adoptium\jdk-*\bin\java.exe',
        'C:\Program Files\Android\Android Studio\jbr\bin\java.exe'
    )
    foreach ($pattern in $patterns) {
        $match = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
        if ($match) {
            return $match
        }
    }

    return ""
}

function Get-AndroidSdkPathOrEmpty {
    if ($env:ANDROID_SDK_ROOT) {
        return $env:ANDROID_SDK_ROOT
    }
    if ($env:ANDROID_HOME) {
        return $env:ANDROID_HOME
    }
    $defaultSdkRoot = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
    if (Test-Path $defaultSdkRoot) {
        return $defaultSdkRoot
    }
    return ""
}

function Get-PortableGradlePathOrEmpty {
    param(
        [string]$PreferredVersion
    )

    $projectRoot = Split-Path -Parent $PSScriptRoot
    $portableRoot = Join-Path $projectRoot "tools\gradle"
    if (-not (Test-Path $portableRoot)) {
        return ""
    }

    if ($PreferredVersion) {
        $preferredPath = Join-Path $portableRoot ("gradle-" + $PreferredVersion + "\bin\gradle.bat")
        if (Test-Path $preferredPath) {
            return $preferredPath
        }
    }

    $gradleBats = Get-ChildItem -Path $portableRoot -Filter "gradle.bat" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($null -eq $gradleBats -or $gradleBats.Count -eq 0) {
        return ""
    }

    return $gradleBats[0].FullName
}

function Get-PreferredGradleVersionOrEmpty {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $wrapperProperties = Join-Path $projectRoot 'mobile_app\react_native\node_modules\react-native\template\android\gradle\wrapper\gradle-wrapper.properties'
    if (-not (Test-Path $wrapperProperties)) {
        return ""
    }

    $distributionLine = Select-String -Path $wrapperProperties -Pattern 'distributionUrl=.*gradle-([0-9.]+)-' | Select-Object -First 1
    if ($distributionLine -and $distributionLine.Matches.Count -gt 0) {
        $templateVersion = [version]$distributionLine.Matches[0].Groups[1].Value
        if ($templateVersion -lt $minimumGradleVersion) {
            return $minimumGradleVersion.ToString()
        }
        return $templateVersion.ToString()
    }

    return $minimumGradleVersion.ToString()
}

$preferredGradleVersion = Get-PreferredGradleVersionOrEmpty
$portableGradle = Get-PortableGradlePathOrEmpty -PreferredVersion $preferredGradleVersion
$releaseStoreFile = Get-SigningSettingOrEmpty -Name 'CCP_UPLOAD_STORE_FILE'
$releaseStorePassword = Get-SigningSettingOrEmpty -Name 'CCP_UPLOAD_STORE_PASSWORD' -MaskValue
$releaseKeyAlias = Get-SigningSettingOrEmpty -Name 'CCP_UPLOAD_KEY_ALIAS'
$releaseKeyPassword = Get-SigningSettingOrEmpty -Name 'CCP_UPLOAD_KEY_PASSWORD' -MaskValue
$releaseStoreFileExists = $false
if ($releaseStoreFile) {
    $releaseStoreFileExists = Test-Path $releaseStoreFile
}

$result = [ordered]@{
    node = Get-NodePathOrEmpty
    npm = Get-NpmPathOrEmpty
    java = Get-JavaPathOrEmpty
    gradle = Get-CommandPathOrEmpty -Name "gradle"
    portable_gradle = $portableGradle
    preferred_gradle_version = $preferredGradleVersion
    android_sdk = Get-AndroidSdkPathOrEmpty
    ccp_upload_store_file = $releaseStoreFile
    ccp_upload_store_password = $releaseStorePassword
    ccp_upload_key_alias = $releaseKeyAlias
    ccp_upload_key_password = $releaseKeyPassword
    release_signing_store_file_exists = $releaseStoreFileExists
}

$missing = @()
if (-not $result.node) { $missing += "node" }
if (-not $result.npm) { $missing += "npm" }
if (-not $result.java) { $missing += "java" }
if (-not $result.gradle -and -not $result.portable_gradle) { $missing += "gradle-or-gradlew" }
if (-not $result.android_sdk) { $missing += "android-sdk" }

$result["missing_requirements"] = $missing
$result["release_signing_ready"] = [bool]($releaseStoreFile -and $releaseStoreFileExists -and $releaseStorePassword -and $releaseKeyAlias -and $releaseKeyPassword)

if ($AsJson) {
    $result | ConvertTo-Json -Depth 4
    exit 0
}

Write-Host "Mobile release environment validation"
Write-Host "- Node: $($result.node)"
Write-Host "- npm: $($result.npm)"
Write-Host "- Java: $($result.java)"
Write-Host "- Gradle: $($result.gradle)"
Write-Host "- Portable Gradle: $($result.portable_gradle)"
Write-Host "- Preferred Gradle: $($result.preferred_gradle_version)"
Write-Host "- Android SDK: $($result.android_sdk)"
Write-Host "- Signing ready: $($result.release_signing_ready)"

if ($missing.Count -gt 0) {
    Write-Host "Missing requirements: $($missing -join ', ')"
    exit 1
}

exit 0