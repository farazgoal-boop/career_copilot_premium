param(
    [string]$StoreFile,
    [string]$KeyAlias,
    [string]$GradlePropertiesPath = "",
    [switch]$ShowStatus
)

$ErrorActionPreference = "Stop"

function ConvertTo-PlainText {
    param(
        [Parameter(Mandatory = $true)]
        [Security.SecureString]$SecureValue
    )

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }
}

function Get-DefaultGradlePropertiesPath {
    return Join-Path $env:USERPROFILE '.gradle\gradle.properties'
}

function Read-PropertiesFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $map = [ordered]@{}
    if (-not (Test-Path $Path)) {
        return $map
    }

    foreach ($line in Get-Content -Path $Path -Encoding UTF8) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) {
            continue
        }

        $separatorIndex = $line.IndexOf('=')
        if ($separatorIndex -lt 0) {
            continue
        }

        $name = $line.Substring(0, $separatorIndex).Trim()
        $value = $line.Substring($separatorIndex + 1).Trim()
        $map[$name] = $value
    }

    return $map
}

function Write-PropertiesFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [hashtable]$Properties
    )

    $directory = Split-Path -Parent $Path
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $existingLines = @()
    if (Test-Path $Path) {
        $existingLines = Get-Content -Path $Path -Encoding UTF8
    }

    $updatedLines = New-Object System.Collections.Generic.List[string]
    $writtenKeys = New-Object System.Collections.Generic.HashSet[string]([System.StringComparer]::OrdinalIgnoreCase)

    foreach ($line in $existingLines) {
        $separatorIndex = $line.IndexOf('=')
        if ($separatorIndex -gt 0) {
            $name = $line.Substring(0, $separatorIndex).Trim()
            if ($Properties.ContainsKey($name)) {
                $updatedLines.Add($name + '=' + $Properties[$name])
                $writtenKeys.Add($name) | Out-Null
                continue
            }
        }
        $updatedLines.Add($line)
    }

    foreach ($entry in $Properties.GetEnumerator()) {
        if (-not $writtenKeys.Contains($entry.Key)) {
            $updatedLines.Add($entry.Key + '=' + $entry.Value)
        }
    }

    Set-Content -Path $Path -Value $updatedLines -Encoding UTF8
}

if (-not $GradlePropertiesPath) {
    $GradlePropertiesPath = Get-DefaultGradlePropertiesPath
}

if (-not $StoreFile) {
    $StoreFile = Read-Host 'Release keystore path'
}
if (-not (Test-Path $StoreFile)) {
    throw "Keystore file not found: $StoreFile"
}

if (-not $KeyAlias) {
    $KeyAlias = Read-Host 'Release key alias'
}
if (-not $KeyAlias) {
    throw 'A release key alias is required.'
}

$storePassword = ConvertTo-PlainText -SecureValue (Read-Host 'Release keystore password' -AsSecureString)
$keyPassword = ConvertTo-PlainText -SecureValue (Read-Host 'Release key password' -AsSecureString)

$properties = Read-PropertiesFile -Path $GradlePropertiesPath
$properties['CCP_UPLOAD_STORE_FILE'] = (Resolve-Path $StoreFile).Path
$properties['CCP_UPLOAD_STORE_PASSWORD'] = $storePassword
$properties['CCP_UPLOAD_KEY_ALIAS'] = $KeyAlias
$properties['CCP_UPLOAD_KEY_PASSWORD'] = $keyPassword

Write-PropertiesFile -Path $GradlePropertiesPath -Properties $properties

Write-Host "Android release signing configured in $GradlePropertiesPath"
Write-Host 'Re-run scripts\validate_mobile_release_env.ps1 to confirm release_signing_ready becomes true.'

if ($ShowStatus) {
    powershell -ExecutionPolicy Bypass -File (Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\validate_mobile_release_env.ps1')
}