@echo off
setlocal

set "ROOT=%~dp0"
set "SETUP=%ROOT%release\installer\CareerCopilotPremium_Setup_v1.0.0.exe"

if not exist "%SETUP%" (
  echo [ERROR] Setup not found at:
  echo %SETUP%
  exit /b 1
)

start "" "%SETUP%"
exit /b 0
