@echo off
cd /d "D:\my apps\career_copilot_premium\career_copilot_premium"
for %%f in ("ready to client\career-copilot-premium-setup.exe" "ready to client\career-copilot-premium.apk" "release\installer\current\CareerCopilotPremium_Setup_CURRENT.exe") do (
 if exist %%~f echo %%~tf^|%%~zf^|%%~f
 if not exist %%~f echo MISSING^|%%~f
)
