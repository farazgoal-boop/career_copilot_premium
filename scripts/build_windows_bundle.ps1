[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$PythonCommand = ".\\.venv\\Scripts\\python.exe",
    [string]$OutputDir = "dist\\windows-bundle",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-RequiredCommandPath {
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

function Stop-RunningBundleProcess {
    cmd /c "taskkill /F /T /IM career-copilot.exe >nul 2>nul" | Out-Null

    $runningProcesses = @(Get-Process -Name "career-copilot" -ErrorAction SilentlyContinue)
    if (-not $runningProcesses) {
        return
    }

    $runningProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    foreach ($process in $runningProcesses) {
        try {
            $process.WaitForExit(5000)
        }
        catch {
        }
    }
}

function Sync-DirectoryContents {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDirectory,
        [Parameter(Mandatory = $true)]
        [string]$DestinationDirectory
    )

    if (Test-Path $DestinationDirectory) {
        Remove-Item $DestinationDirectory -Recurse -Force
    }

    New-Item -ItemType Directory -Path $DestinationDirectory -Force | Out-Null
    Copy-Item -Path (Join-Path $SourceDirectory '*') -Destination $DestinationDirectory -Recurse -Force
}

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$pythonExecutable = Resolve-RequiredCommandPath -CommandName $PythonCommand -InstallHint "Create the virtual environment or pass -PythonCommand with a valid interpreter path."

$resolvedOutputDir = Join-Path $resolvedProjectRoot $OutputDir
$buildDir = Join-Path $resolvedProjectRoot "build"
$pyInstallerWorkDir = Join-Path $buildDir "pyinstaller-work"
$pyInstallerDistDir = Join-Path $buildDir "pyinstaller-dist"
$pyInstallerAppDir = Join-Path $pyInstallerDistDir "career-copilot"
$specFile = Join-Path $buildDir "career-copilot.spec"
$configDir = Join-Path $resolvedProjectRoot "config"

if ($Clean) {
    foreach ($path in @($resolvedOutputDir, $pyInstallerWorkDir, $pyInstallerDistDir, $specFile)) {
        if (Test-Path $path) {
            Remove-Item $path -Recurse -Force
        }
    }
}

Push-Location $resolvedProjectRoot
try {
    Stop-RunningBundleProcess

    & $pythonExecutable -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not available in the selected Python environment. Install PyInstaller into that environment before building the Windows bundle."
    }

    & $pythonExecutable -m PyInstaller --noconfirm --clean career-copilot.spec --workpath $pyInstallerWorkDir --distpath $pyInstallerDistDir --specpath $buildDir
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build the career-copilot Windows bundle"
    }

    New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null
    foreach ($bundlePath in @((Join-Path $resolvedOutputDir "career-copilot.exe"), (Join-Path $resolvedOutputDir "_internal"))) {
        if (Test-Path $bundlePath) {
            Stop-RunningBundleProcess
            Remove-Item $bundlePath -Recurse -Force
        }
    }

    Copy-Item -Path (Join-Path $pyInstallerAppDir "career-copilot.exe") -Destination (Join-Path $resolvedOutputDir "career-copilot.exe") -Force
    Copy-Item -Path (Join-Path $pyInstallerAppDir "_internal") -Destination (Join-Path $resolvedOutputDir "_internal") -Recurse -Force
    Copy-Item -Path (Join-Path $resolvedProjectRoot "config") -Destination (Join-Path $resolvedOutputDir "config") -Recurse -Force
    Copy-Item -Path (Join-Path $resolvedProjectRoot "docs") -Destination (Join-Path $resolvedOutputDir "docs") -Recurse -Force
    Copy-Item -Path (Join-Path $resolvedProjectRoot "README.md") -Destination (Join-Path $resolvedOutputDir "README.md") -Force
    $sourceProfilesDir = Join-Path $resolvedProjectRoot "data\user_profiles"
    if (Test-Path $sourceProfilesDir) {
        Sync-DirectoryContents -SourceDirectory $sourceProfilesDir -DestinationDirectory (Join-Path $resolvedOutputDir "data\user_profiles")
    }

    $requiredBundleFiles = @(
        (Join-Path $resolvedOutputDir "career-copilot.exe"),
        (Join-Path $resolvedOutputDir "_internal\base_library.zip"),
        (Join-Path $resolvedOutputDir "_internal\python314.dll"),
        (Join-Path $resolvedOutputDir "_internal\setuptools\_vendor\jaraco\text\Lorem ipsum.txt"),
        (Join-Path $resolvedOutputDir "_internal\torch\lib\torch.dll"),
        (Join-Path $resolvedOutputDir "_internal\torch\lib\torch_cpu.dll"),
        (Join-Path $resolvedOutputDir "_internal\torch\lib\torch_python.dll"),
        (Join-Path $resolvedOutputDir "_internal\torch\lib\c10.dll"),
        (Join-Path $resolvedOutputDir "_internal\torch\lib\libiomp5md.dll"),
        (Join-Path $resolvedOutputDir "_internal\torch\lib\shm.dll")
    )
    foreach ($requiredFile in $requiredBundleFiles) {
        if (-not (Test-Path $requiredFile)) {
            throw "Windows bundle is incomplete. Missing required runtime artifact: $requiredFile"
        }
    }

    # Ensure packaged web control-room assets always match latest source edits.
    $packagedWebRoot = Join-Path $resolvedOutputDir "_internal\web_app"
    if (-not (Test-Path $packagedWebRoot)) {
        New-Item -ItemType Directory -Path $packagedWebRoot -Force | Out-Null
    }
    Sync-DirectoryContents -SourceDirectory (Join-Path $resolvedProjectRoot "web_app\templates") -DestinationDirectory (Join-Path $packagedWebRoot "templates")
    Sync-DirectoryContents -SourceDirectory (Join-Path $resolvedProjectRoot "web_app\static") -DestinationDirectory (Join-Path $packagedWebRoot "static")

    foreach ($directoryName in @("data", "logs", "backups")) {
        New-Item -ItemType Directory -Path (Join-Path $resolvedOutputDir $directoryName) -Force | Out-Null
    }
}
finally {
    Pop-Location
}

Write-Host "Windows bundle ready at: $resolvedOutputDir"
Write-Host "Next step: compile installers\\windows\\setup.iss with Inno Setup."