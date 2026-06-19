param(
    [switch]$Bundle,
    [switch]$InstallDependencies,
    [string]$GradleCommand = "gradle"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$reactNativeRoot = Join-Path $projectRoot "mobile_app\react_native"
$androidRoot = Join-Path $reactNativeRoot "android"
$gradlew = Join-Path $androidRoot "gradlew.bat"
$minimumGradleVersion = [version]"8.7"

function Resolve-PortableGradlePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,
        [string]$PreferredVersion
    )

    $portableRoot = Join-Path $ProjectRoot "tools\gradle"
    if (-not (Test-Path $portableRoot)) {
        return $null
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
        return $null
    }

    return $gradleBats[0].FullName
}

function Get-PreferredGradleVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot
    )

    $wrapperProperties = Join-Path $ProjectRoot 'mobile_app\react_native\node_modules\react-native\template\android\gradle\wrapper\gradle-wrapper.properties'
    if (-not (Test-Path $wrapperProperties)) {
        return $null
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

function Test-RequiredCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

function Resolve-ExecutablePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName,
        [Parameter()]
        [string[]]$FallbackPaths = @()
    )

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    foreach ($path in $FallbackPaths) {
        if (Test-Path $path) {
            return $path
        }
    }

    return $null
}

function Get-NodeCandidatePaths {
    return @(
        'C:\Program Files\nodejs\node.exe',
        'C:\Program Files (x86)\nodejs\node.exe',
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe')
    )
}

function Get-NpmCandidatePaths {
    return @(
        'C:\Program Files\nodejs\npm.cmd',
        'C:\Program Files (x86)\nodejs\npm.cmd',
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\npm.cmd')
    )
}

function Get-JavaCandidatePaths {
    $patterns = @(
        'C:\Program Files\Microsoft\jdk-*\bin\java.exe',
        'C:\Program Files\Eclipse Adoptium\jdk-*\bin\java.exe',
        'C:\Program Files\Android\Android Studio\jbr\bin\java.exe'
    )

    $results = @()
    foreach ($pattern in $patterns) {
        $results += Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName
    }
    return $results
}

function Resolve-AndroidSdkPath {
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
    return $null
}

function Sync-AndroidLocalProperties {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetSdkRoot,
        [Parameter(Mandatory = $true)]
        [string]$AndroidProjectRoot
    )

    $localPropertiesPath = Join-Path $AndroidProjectRoot 'local.properties'
    $sdkDir = $TargetSdkRoot -replace '\\', '/'
    Set-Content -Path $localPropertiesPath -Value ("sdk.dir=" + $sdkDir) -Encoding ASCII
}

function Add-PathEntry {
    param([Parameter(Mandatory = $true)][string]$PathEntry)

    if (-not $PathEntry) {
        return
    }

    $currentEntries = @($env:PATH -split ';')
    if ($currentEntries -notcontains $PathEntry) {
        $env:PATH = ($currentEntries + $PathEntry) -join ';'
    }
}

function Ensure-DebugKeystore {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AndroidProjectRoot,
        [Parameter(Mandatory = $true)]
        [string]$JavaHome
    )

    $debugKeystorePath = Join-Path $AndroidProjectRoot 'app\debug.keystore'
    if (Test-Path $debugKeystorePath) {
        return
    }

    $keytoolPath = Join-Path $JavaHome 'bin\keytool.exe'
    if (-not (Test-Path $keytoolPath)) {
        throw "keytool.exe was not found under JAVA_HOME. Unable to create the Android debug keystore."
    }

    & $keytoolPath -genkeypair -v -storetype PKCS12 -keystore $debugKeystorePath -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Android Debug,O=Android,C=US'
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the Android debug keystore at $debugKeystorePath"
    }
}

if (-not (Test-Path $reactNativeRoot)) {
    throw "React Native mobile shell not found at $reactNativeRoot"
}

$resolvedNodePath = Resolve-ExecutablePath -CommandName "node" -FallbackPaths (Get-NodeCandidatePaths)
if (-not $resolvedNodePath) {
    throw "Node.js is required for the React Native Android build. Install Node.js 20+ and retry."
}

$resolvedJavaPath = Resolve-ExecutablePath -CommandName "java" -FallbackPaths (Get-JavaCandidatePaths)
if (-not $resolvedJavaPath) {
    throw "Java is required for the Android build. Install a supported JDK and retry."
}

$androidSdkPath = Resolve-AndroidSdkPath
if (-not $androidSdkPath) {
    throw "ANDROID_SDK_ROOT or ANDROID_HOME must point to an installed Android SDK."
}

$env:JAVA_HOME = Split-Path (Split-Path $resolvedJavaPath -Parent) -Parent
$env:ANDROID_SDK_ROOT = $androidSdkPath
$env:ANDROID_HOME = $androidSdkPath
$env:NODE_BINARY = $resolvedNodePath
Add-PathEntry -PathEntry (Split-Path $resolvedNodePath -Parent)
Add-PathEntry -PathEntry (Split-Path $resolvedJavaPath -Parent)
Add-PathEntry -PathEntry (Join-Path $androidSdkPath 'platform-tools')

Sync-AndroidLocalProperties -TargetSdkRoot $androidSdkPath -AndroidProjectRoot $androidRoot
Ensure-DebugKeystore -AndroidProjectRoot $androidRoot -JavaHome $env:JAVA_HOME

if ($InstallDependencies) {
    Push-Location $reactNativeRoot
    try {
        if (-not (Test-RequiredCommand -Name "npm")) {
            $npmPath = Resolve-ExecutablePath -CommandName "npm" -FallbackPaths (Get-NpmCandidatePaths)
            if (-not $npmPath) {
                throw "npm is required when -InstallDependencies is used. Install Node.js/npm and retry."
            }
            & $npmPath install
        }
        else {
            npm install
        }
    }
    finally {
        Pop-Location
    }
}

$taskName = if ($Bundle) { "bundleRelease" } else { "assembleRelease" }
$preferredGradleVersion = Get-PreferredGradleVersion -ProjectRoot $projectRoot
$portableGradle = Resolve-PortableGradlePath -ProjectRoot $projectRoot -PreferredVersion $preferredGradleVersion

Push-Location $androidRoot
try {
    if (Test-Path $gradlew) {
        & $gradlew $taskName
    }
    elseif ($portableGradle) {
        & $portableGradle $taskName
    }
    else {
        $resolvedGradle = Get-Command $GradleCommand -ErrorAction SilentlyContinue
        if ($null -eq $resolvedGradle) {
            throw "Gradle wrapper not found, no portable Gradle was bootstrapped, and '$GradleCommand' is unavailable. Run scripts\\install_portable_gradle.ps1 or install Gradle first."
        }
        & $resolvedGradle.Source $taskName
    }
}
finally {
    Pop-Location
}