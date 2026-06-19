@echo off
setlocal EnableExtensions
title Career Copilot Premium - Client Package Builder
cd /d "%~dp0"

set "ROOT=%CD%"
if exist "%ROOT%\venv311\Scripts\python.exe" (
  set "PYTHON=%ROOT%\venv311\Scripts\python.exe"
  set "PIP=%ROOT%\venv311\Scripts\pip.exe"
) else (
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
  set "PIP=%ROOT%\.venv\Scripts\pip.exe"
)

echo.
echo ============================================================
echo  Career Copilot Premium - Full Client Package Build
echo ============================================================
echo  Project folder: %ROOT%
echo.

if not exist "%PYTHON%" (
  echo [1/7] Creating virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERROR: Could not create .venv. Install Python 3.11+ from python.org
    goto :fail
  )
  set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
  set "PIP=%ROOT%\.venv\Scripts\pip.exe"
)

echo [2/7] Installing Python packages...
"%PYTHON%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [2b/7] Verifying speech-to-text runtime...
"%PYTHON%" -c "import speech_recognition; print('SpeechRecognition OK')"
if errorlevel 1 (
  echo ERROR: SpeechRecognition is missing. Listen/F2 will not work until this package is installed.
  goto :fail
)

echo [3/7] Building Windows app (PyInstaller + premium_launcher)...
"%PYTHON%" -m PyInstaller career-copilot.spec --clean --noconfirm
if errorlevel 1 goto :fail

set "PYI_OUT=%ROOT%\dist\Career Copilot Premium"
if not exist "%PYI_OUT%\Career Copilot Premium.exe" (
  echo ERROR: Expected %PYI_OUT%\Career Copilot Premium.exe
  goto :fail
)

echo [4/7] Preparing dist\windows-bundle...
if exist "%ROOT%\dist\windows-bundle" rmdir /s /q "%ROOT%\dist\windows-bundle"
mkdir "%ROOT%\dist\windows-bundle"
xcopy /E /I /Y "%PYI_OUT%\*" "%ROOT%\dist\windows-bundle\" >nul
if exist "%ROOT%\portable.flag" copy /Y "%ROOT%\portable.flag" "%ROOT%\dist\windows-bundle\" >nul
if exist "%ROOT%\.env.example" copy /Y "%ROOT%\.env.example" "%ROOT%\dist\windows-bundle\.env.example" >nul
if exist "%ROOT%\dist\windows-bundle\Career Copilot Premium.exe" (
  copy /Y "%ROOT%\dist\windows-bundle\Career Copilot Premium.exe" "%ROOT%\dist\windows-bundle\career-copilot.exe" >nul
)

echo [4b/7] Ensuring VC++ redistributable for installer...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\ensure_vcredist.ps1"
if errorlevel 1 (
  echo WARNING: VC++ redistributable download failed. Installer will still build.
)

echo [5/7] Building Setup.exe (Inno Setup 6+)...
set "ISCC="
for %%I in (
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  "C:\Program Files\Inno Setup 6\ISCC.exe"
  "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
  "C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
  "C:\Program Files\Inno Setup 7\ISCC.exe"
  "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
) do if exist %%I set "ISCC=%%~I"
if not defined ISCC (
  echo WARNING: Inno Setup not installed. Skip Setup.exe.
  echo Download: https://jrsoftware.org/isdl.php
  goto :skip_inno
)
"%ISCC%" "%ROOT%\installers\windows_setup.iss"
if errorlevel 1 goto :fail
:skip_inno

echo [6/7] Assembling ready to client package...
if exist "%ROOT%\ready to client" rmdir /s /q "%ROOT%\ready to client"
mkdir "%ROOT%\ready to client"
mkdir "%ROOT%\ready to client\windows"
mkdir "%ROOT%\ready to client\installer"
mkdir "%ROOT%\ready to client\android"
mkdir "%ROOT%\ready to client\requirements"
mkdir "%ROOT%\ready to client\docs"
mkdir "%ROOT%\ready to client\security"
mkdir "%ROOT%\ready to client\mac"
mkdir "%ROOT%\ready to client\linux"

xcopy /E /I /Y "%ROOT%\client_package\*" "%ROOT%\ready to client\" >nul
if exist "%ROOT%\client_package\SETUP_GUIDE_WINDOWS.txt" copy /Y "%ROOT%\client_package\SETUP_GUIDE_WINDOWS.txt" "%ROOT%\ready to client\" >nul
if exist "%ROOT%\client_package\SETUP_GUIDE_MAC.txt" copy /Y "%ROOT%\client_package\SETUP_GUIDE_MAC.txt" "%ROOT%\ready to client\mac\" >nul
if exist "%ROOT%\client_package\SETUP_GUIDE_LINUX.txt" copy /Y "%ROOT%\client_package\SETUP_GUIDE_LINUX.txt" "%ROOT%\ready to client\linux\" >nul
if exist "%ROOT%\install_mac.sh" copy /Y "%ROOT%\install_mac.sh" "%ROOT%\ready to client\mac\" >nul
if exist "%ROOT%\install_linux.sh" copy /Y "%ROOT%\install_linux.sh" "%ROOT%\ready to client\linux\" >nul
if exist "%ROOT%\START_PREMIUM.sh" (
  copy /Y "%ROOT%\START_PREMIUM.sh" "%ROOT%\ready to client\mac\" >nul
  copy /Y "%ROOT%\START_PREMIUM.sh" "%ROOT%\ready to client\linux\" >nul
)
if exist "%ROOT%\requirements.txt" (
  copy /Y "%ROOT%\requirements.txt" "%ROOT%\ready to client\mac\" >nul
  copy /Y "%ROOT%\requirements.txt" "%ROOT%\ready to client\linux\" >nul
)
if exist "%ROOT%\.env.example" (
  copy /Y "%ROOT%\.env.example" "%ROOT%\ready to client\mac\" >nul
  copy /Y "%ROOT%\.env.example" "%ROOT%\ready to client\linux\" >nul
)
for %%D in (desktop_app web_app mobile_app data) do (
  if exist "%ROOT%\%%D" (
    xcopy /E /I /Y "%ROOT%\%%D" "%ROOT%\ready to client\mac\%%D\" >nul
    xcopy /E /I /Y "%ROOT%\%%D" "%ROOT%\ready to client\linux\%%D\" >nul
  )
)
if exist "%ROOT%\premium_launcher.py" (
  copy /Y "%ROOT%\premium_launcher.py" "%ROOT%\ready to client\mac\" >nul
  copy /Y "%ROOT%\premium_launcher.py" "%ROOT%\ready to client\linux\" >nul
)
if exist "%ROOT%\runtime_paths.py" (
  copy /Y "%ROOT%\runtime_paths.py" "%ROOT%\ready to client\mac\" >nul
  copy /Y "%ROOT%\runtime_paths.py" "%ROOT%\ready to client\linux\" >nul
)
if exist "%ROOT%\app_licensing.py" (
  copy /Y "%ROOT%\app_licensing.py" "%ROOT%\ready to client\mac\" >nul
  copy /Y "%ROOT%\app_licensing.py" "%ROOT%\ready to client\linux\" >nul
)
if exist "%ROOT%\ready to client\mac\mobile_app\react_native" rmdir /s /q "%ROOT%\ready to client\mac\mobile_app\react_native"
if exist "%ROOT%\ready to client\linux\mobile_app\react_native" rmdir /s /q "%ROOT%\ready to client\linux\mobile_app\react_native"
if exist "%ROOT%\.env.example" copy /Y "%ROOT%\.env.example" "%ROOT%\ready to client\.env.example" >nul
if exist "%ROOT%\dist\windows-bundle" (
  if exist "%ROOT%\ready to client\windows" rmdir /s /q "%ROOT%\ready to client\windows"
  mkdir "%ROOT%\ready to client\windows"
  xcopy /E /I /Y "%ROOT%\dist\windows-bundle\*" "%ROOT%\ready to client\windows\" >nul
  if exist "%ROOT%\ready to client\windows\_internal\mobile_app\react_native" rmdir /s /q "%ROOT%\ready to client\windows\_internal\mobile_app\react_native"
)
if exist "%ROOT%\dist\installer\CareerCopilotPremium_Setup_v1.0.0.exe" (
  copy /Y "%ROOT%\dist\installer\CareerCopilotPremium_Setup_v1.0.0.exe" "%ROOT%\ready to client\installer\" >nul
  copy /Y "%ROOT%\dist\installer\CareerCopilotPremium_Setup_v1.0.0.exe" "%ROOT%\CareerCopilotPremium_Setup_v1.0.0.exe" >nul
)
if exist "%ROOT%\release\android\CareerCopilotPremium.apk" (
  copy /Y "%ROOT%\release\android\CareerCopilotPremium.apk" "%ROOT%\ready to client\android\" >nul
) else if exist "%ROOT%\dist\mobile\career-copilot-premium.apk" (
  copy /Y "%ROOT%\dist\mobile\career-copilot-premium.apk" "%ROOT%\ready to client\android\CareerCopilotPremium.apk" >nul
)
if exist "%ROOT%\docs\USER_GUIDE.md" copy /Y "%ROOT%\docs\USER_GUIDE.md" "%ROOT%\ready to client\docs\" >nul
if exist "%ROOT%\docs\INSTALL.md" copy /Y "%ROOT%\docs\INSTALL.md" "%ROOT%\ready to client\docs\" >nul
if exist "%ROOT%\docs\USER_MANUAL.html" copy /Y "%ROOT%\docs\USER_MANUAL.html" "%ROOT%\ready to client\docs\" >nul
if exist "%ROOT%\installers\windows\assets\user_manual.html" copy /Y "%ROOT%\installers\windows\assets\user_manual.html" "%ROOT%\ready to client\docs\" >nul

echo [7/7] SHA256 manifest + final ZIP...
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\build_client_manifest.ps1" -PackageDir "%ROOT%\ready to client"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  BUILD FINISHED
echo ============================================================
echo  Client folder: %ROOT%\ready to client
echo  Client ZIP:    %ROOT%\CareerCopilotPremium-v1.0.0-CLIENT.zip
echo.
echo  Dev run: START_PREMIUM.bat
echo  Upload VIRUSTOTAL-LINK.txt after scanning Setup.exe
echo.
dir /s /b "%ROOT%\ready to client" 2>nul
echo.
exit /b 0

:fail
echo.
echo BUILD FAILED - read errors above.
exit /b 1
