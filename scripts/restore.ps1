[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupZip,
    [string]$DestinationDir,
    [string]$EnvFilePath,
    [string]$ExtensionsFile,
    [string]$PythonCommand = "python",
    [switch]$SkipVenv,
    [switch]$SkipPip,
    [switch]$OpenFolder
)

$ErrorActionPreference = "Stop"

function Resolve-RequiredCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName,
        [Parameter(Mandatory = $true)]
        [string]$InstallHint
    )

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command '$CommandName' was not found. $InstallHint"
    }

    return $command.Source
}

$resolvedBackupZip = (Resolve-Path $BackupZip).Path
if (-not $DestinationDir) {
    $zipName = [System.IO.Path]::GetFileNameWithoutExtension($resolvedBackupZip)
    $DestinationDir = Join-Path (Split-Path $resolvedBackupZip -Parent) $zipName
}

if (Test-Path $DestinationDir) {
    throw "Destination already exists: $DestinationDir"
}

New-Item -ItemType Directory -Path $DestinationDir -Force | Out-Null
Expand-Archive -Path $resolvedBackupZip -DestinationPath $DestinationDir -Force

if ($EnvFilePath) {
    $resolvedEnvFilePath = (Resolve-Path $EnvFilePath).Path
    Copy-Item -Path $resolvedEnvFilePath -Destination (Join-Path $DestinationDir ".env") -Force
}

$requirementsPath = Join-Path $DestinationDir "requirements.txt"
if (-not (Test-Path $requirementsPath)) {
    throw "requirements.txt not found in restored project: $requirementsPath"
}

$pythonExecutable = $null
if (-not $SkipVenv -or -not $SkipPip) {
    $pythonExecutable = Resolve-RequiredCommand -CommandName $PythonCommand -InstallHint "Install Python and ensure it is on PATH, or rerun with -PythonCommand set to the full interpreter path."
}

if (-not $SkipVenv) {
    $venvPath = Join-Path $DestinationDir ".venv"
    & $pythonExecutable -m venv $venvPath
}

if (-not $SkipPip) {
    $pythonInVenv = Join-Path $DestinationDir ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonInVenv)) {
        throw "Virtual environment Python not found: $pythonInVenv"
    }

    & $pythonInVenv -m pip install --upgrade pip
    & $pythonInVenv -m pip install -r $requirementsPath
}

if ($ExtensionsFile) {
    $resolvedExtensionsFile = (Resolve-Path $ExtensionsFile).Path
    if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
        Write-Warning "VS Code 'code' command is not available, so extensions were not installed."
    } else {
        Get-Content $resolvedExtensionsFile | ForEach-Object {
            $extensionId = $_.Trim()
            if ($extensionId) {
                code --install-extension $extensionId --force | Out-Null
            }
        }
    }
}

Write-Host "Restore completed at: $DestinationDir"
Write-Host "Activate the environment with: .venv\Scripts\Activate.ps1"
Write-Host "Run the app with: .venv\Scripts\python.exe -m desktop_app.main"

if ($OpenFolder) {
    Invoke-Item $DestinationDir
}