param(
    [string]$InputPath = "vscode-extensions.txt"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $InputPath)) {
    throw "Extensions file not found: $InputPath"
}

if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
    throw "VS Code 'code' command is not available in PATH. Open VS Code once and enable the command line integration if needed."
}

Get-Content $InputPath | ForEach-Object {
    $extensionId = $_.Trim()
    if ($extensionId) {
        code --install-extension $extensionId --force | Out-Null
        Write-Host "Installed extension: $extensionId"
    }
}