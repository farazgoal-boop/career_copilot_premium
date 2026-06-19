@echo off
setlocal
title Career Copilot Premium
set "ROOT=%~dp0"
cd /d "%ROOT%"
set CAREER_COPILOT_PORTABLE=1
call START_PREMIUM.bat
endlocal
