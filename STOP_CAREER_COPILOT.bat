@echo off

setlocal EnableExtensions

title Stop Career Copilot Premium

cd /d "%~dp0"



echo.

echo Stopping Career Copilot Premium (ports 5000, 5001, 8765)...

echo.



for %%P in (5000 5001 8765) do (

  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (

    echo Killing PID %%A on port %%P

    taskkill /PID %%A /F >nul 2>&1

  )

)



taskkill /IM "career-copilot.exe" /F >nul 2>&1

taskkill /IM "Career Copilot Premium.exe" /F >nul 2>&1



echo.

echo Done. Wait 3 seconds then start the app again.

timeout /t 3 /nobreak >nul

exit /b 0

