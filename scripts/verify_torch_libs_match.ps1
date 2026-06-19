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
$src = Join-Path $root "build\pyinstaller-dist\career-copilot\_internal\torch\lib"
$dst = Join-Path $InstallDir "_internal\torch\lib"

$srcNames = @(Get-ChildItem $src -File | Select-Object -ExpandProperty Name)
$dstNames = @(Get-ChildItem $dst -File | Select-Object -ExpandProperty Name)
$missing = @($srcNames | Where-Object { $_ -notin $dstNames })

Write-Output ("SRC_COUNT=" + $srcNames.Count)
Write-Output ("DST_COUNT=" + $dstNames.Count)
Write-Output ("MISSING_COUNT=" + $missing.Count)
if ($missing.Count -gt 0) {
    foreach ($item in ($missing | Sort-Object)) {
        Write-Output ("MISSING=" + $item)
    }
}
