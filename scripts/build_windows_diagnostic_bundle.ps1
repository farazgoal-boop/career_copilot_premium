[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$PythonCommand = ".\.venv\Scripts\python.exe"
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

$resolvedProjectRoot = (Resolve-Path $ProjectRoot).Path
$pythonExecutable = Resolve-RequiredCommandPath -CommandName $PythonCommand -InstallHint "Create the virtual environment or pass -PythonCommand with a valid interpreter path."
$buildDir = Join-Path $resolvedProjectRoot "build"
$diagWorkDir = Join-Path $buildDir "pyinstaller-diagnostic-work"
$diagDistDir = Join-Path $buildDir "pyinstaller-diagnostic-dist"
$diagSpecDir = Join-Path $buildDir "pyinstaller-diagnostic-spec"
$configDir = Join-Path $resolvedProjectRoot "config"

foreach ($path in @($diagWorkDir, $diagDistDir, $diagSpecDir)) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force
    }
}

Push-Location $resolvedProjectRoot
try {
    & $pythonExecutable -m PyInstaller --noconfirm --clean --name career-copilot-diagnostic --paths . --collect-data desktop_app --collect-data web_app --add-data ($configDir + ";config") --workpath $diagWorkDir --distpath $diagDistDir --specpath $diagSpecDir desktop_launcher.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller diagnostic build failed"
    }
}
finally {
    Pop-Location
}

Write-Host "Diagnostic bundle ready at: $diagDistDir"