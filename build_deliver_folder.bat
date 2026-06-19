@echo off
setlocal EnableExtensions
title Career Copilot Premium - DELIVER_TO_CLIENT Builder
cd /d "%~dp0"

echo.
echo Building DELIVER_TO_CLIENT folder...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_deliver_folder.ps1" -Root "%CD%"
if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  exit /b 1
)
exit /b 0
