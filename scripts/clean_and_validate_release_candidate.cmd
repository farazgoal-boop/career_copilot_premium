@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0clean_smoke_install.ps1" -InstallDir "D:\CareerCopilotSmoke"
if errorlevel 1 exit /b %errorlevel%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0validate_release_candidate.ps1"
