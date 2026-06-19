@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify_setup_only.ps1" -ProjectRoot "%~dp0.." -InstallDir "D:\CareerCopilotSmoke"
