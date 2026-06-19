@echo off
setlocal

cd /d "%~dp0"

echo [INFO] Closing running Career Copilot processes...
taskkill /F /IM "Career Copilot Premium.exe" >nul 2>nul
taskkill /F /IM "career-copilot.exe" >nul 2>nul
taskkill /F /IM "career_copilot_launcher.exe" >nul 2>nul

echo [INFO] Starting installer...
if exist "CareerCopilotPremium_Setup_CURRENT.exe" (
  start "" /wait "CareerCopilotPremium_Setup_CURRENT.exe"
  exit /b %ERRORLEVEL%
)

if exist "CareerCopilotPremium_Setup_v1.0.0.exe" (
  start "" /wait "CareerCopilotPremium_Setup_v1.0.0.exe"
  exit /b %ERRORLEVEL%
)

echo [ERROR] Setup file not found in project root.
echo Place setup exe in this folder and run again.
exit /b 1
