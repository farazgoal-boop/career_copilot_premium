[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
cmd.exe /c (Join-Path $root "scripts\final_smoke_wrapper.cmd")
