@echo off
setlocal

set "ROOT=%~dp0.."
set "EXE=%ROOT%\dist\windows-bundle\career-copilot.exe"

taskkill /F /IM career-copilot.exe >nul 2>nul
taskkill /F /IM python.exe >nul 2>nul

if not exist "%EXE%" (
  echo {"error":"missing_exe","path":"%EXE%"}
  exit /b 1
)

start "" "%EXE%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$live = @(); foreach ($i in 1..24) { foreach ($port in 5000..5025) { try { $resp = Invoke-WebRequest -UseBasicParsing (\"http://127.0.0.1:{0}/api/health\" -f $port) -TimeoutSec 1; if ($resp.StatusCode -eq 200 -and -not ($live -contains $port)) { $live += $port } } catch {} }; if ($live.Count -gt 0) { break }; Start-Sleep -Milliseconds 500 }; $proc = Get-Process career-copilot -ErrorAction SilentlyContinue | Select-Object -First 1; [pscustomobject]@{ pid = $(if ($proc) { $proc.Id } else { $null }); livePorts = $live } | ConvertTo-Json -Depth 4"

exit /b %ERRORLEVEL%