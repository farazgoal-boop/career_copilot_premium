@echo off

setlocal EnableExtensions

title Create Client Test ZIP (Setup.exe only)

cd /d "%~dp0"



set "EXE=dist\installer\CareerCopilotPremium_Setup_v1.0.0.exe"

set "OUT=CLIENT_TEST_ONLY.zip"



if not exist "%EXE%" (

  echo ERROR: Build first with BUILD_CLIENT_PACKAGE.bat

  echo Missing: %EXE%

  exit /b 1

)



if exist "%OUT%" del /f /q "%OUT%"



powershell -NoProfile -Command "Compress-Archive -Path '%EXE%' -DestinationPath '%OUT%' -Force"



echo.

echo Created: %CD%\%OUT%

for %%F in ("%OUT%") do echo Size: %%~zF bytes

echo.

echo Send this ZIP to client for testing. They unzip and run Setup.exe only.

exit /b 0

