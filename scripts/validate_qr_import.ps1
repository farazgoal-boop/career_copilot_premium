[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
.\.venv\Scripts\python.exe scripts\benchmark_import_main.py
.\.venv\Scripts\python.exe scripts\check_pairing_qr_route.py
