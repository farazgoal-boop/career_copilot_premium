@echo off

setlocal EnableExtensions

title Career Copilot Premium - Playwright Tests

cd /d "%~dp0"



set "LOG=%~dp0playwright_test_result.txt"



echo.

echo ============================================================

echo  Playwright Client Readiness Tests

echo ============================================================

echo.

echo  BEFORE running:

echo    1) STOP_CAREER_COPILOT.bat

echo    2) START_DEV.bat  (keep that window open)

echo  Dashboard must be at http://127.0.0.1:5000

echo.

echo  Saving output to: playwright_test_result.txt

echo.



powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_playwright_client_test.ps1" -BaseUrl "http://127.0.0.1:5000" > "%LOG%" 2>&1

set "RC=%ERRORLEVEL%"

type "%LOG%"



if not "%RC%"=="0" (

  echo.

  echo ============================================================

  echo  TESTS FAILED  (exit code %RC%)

  echo ============================================================

  echo  Full log: %LOG%

  echo.

  echo  Common fix:

  echo    - START_DEV.bat chalao pehle

  echo    - Browser http://127.0.0.1:5000 open ho

  echo    - Phir TEST.bat dubara chalao

  echo.

  pause

  exit /b %RC%

)



echo.

echo ============================================================

echo  ALL TESTS PASSED

echo ============================================================

echo.

pause

exit /b 0

