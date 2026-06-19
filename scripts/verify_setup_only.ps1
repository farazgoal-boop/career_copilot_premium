[CmdletBinding()]
param(
    [string]$ProjectRoot = "",
    [string]$InstallDir = "D:\CareerCopilotSmoke"
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$root = (Resolve-Path $ProjectRoot).Path
$setupExe = Join-Path $root "dist\installer\career-copilot-premium-setup.exe"
if (-not (Test-Path $setupExe)) {
    throw "Setup executable not found at $setupExe"
}

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

$setupLog = "D:\installer-smoke.log"
if (Test-Path $setupLog) {
    Remove-Item $setupLog -Force
}

$tempSetupExe = Join-Path $env:TEMP ("career-copilot-setup-only-" + [Guid]::NewGuid().ToString("N") + ".exe")
Copy-Item -Path $setupExe -Destination $tempSetupExe -Force

$installArgs = @(
    "/VERYSILENT",
    "/SUPPRESSMSGBOXES",
    "/NORESTART",
    "/SP-",
    ("/DIR=" + $InstallDir),
    ("/LOG=" + $setupLog)
)

$setup = Start-Process -FilePath $tempSetupExe -ArgumentList $installArgs -PassThru -Wait

Write-Output ("SETUP_EXIT=" + $setup.ExitCode)
Write-Output ("INSTALL_DIR_EXISTS=" + (Test-Path $InstallDir))
Write-Output ("LOG_EXISTS=" + (Test-Path $setupLog))
Write-Output ("EXE_EXISTS=" + (Test-Path (Join-Path $InstallDir "career-copilot.exe")))
Write-Output ("LOREM_EXISTS=" + (Test-Path (Join-Path $InstallDir "_internal\setuptools\_vendor\jaraco\text\Lorem ipsum.txt")))
Remove-Item $tempSetupExe -Force -ErrorAction SilentlyContinue
