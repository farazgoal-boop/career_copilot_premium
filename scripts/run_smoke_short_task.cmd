@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0clean_smoke_install.ps1" -InstallDir "D:\CareerCopilotSmoke" >nul 2>nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_setup_only.ps1" -ProjectRoot "%~dp0.." -InstallDir "D:\CareerCopilotSmoke"
if errorlevel 1 exit /b %errorlevel%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0collect_installed_runtime_inventory.ps1" -InstallDir "D:\CareerCopilotSmoke"
if errorlevel 1 exit /b %errorlevel%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_torch_libs_match.ps1" -ProjectRoot "%~dp0.." -InstallDir "D:\CareerCopilotSmoke"
if errorlevel 1 exit /b %errorlevel%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_installed_launch_only.ps1" -InstallDir "D:\CareerCopilotSmoke"
