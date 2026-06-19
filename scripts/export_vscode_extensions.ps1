param(
    [string]$OutputPath = "vscode-extensions.txt"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
    throw "VS Code 'code' command is not available in PATH. Open VS Code once and enable the command line integration if needed."
}

code --list-extensions | Set-Content -Path $OutputPath -Encoding UTF8
Write-Host "Extensions exported to: $OutputPath"