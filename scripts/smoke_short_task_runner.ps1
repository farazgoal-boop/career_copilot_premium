[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
cmd.exe /c (Join-Path $root "scripts\run_smoke_short_task.cmd")
