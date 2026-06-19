@echo off
setlocal EnableExtensions
title Career Copilot Premium
cd /d "%~dp0"

set "ROOT=%CD%"
set "CAREER_COPILOT_PORTABLE=1"

echo.
echo ============================================================
echo  Career Copilot Premium  (USB / portable — nothing installed on PC)
echo ============================================================
echo  Folder: %ROOT%
echo.

REM --- 1) Built EXE (skip when developing — use START_DEV.bat instead) ---
if "%CAREER_COPILOT_USE_SOURCE%"=="1" goto :use_python
if exist "%ROOT%dist\windows-bundle\career-copilot.exe" (
  echo Starting packaged app from dist\windows-bundle...
  echo For latest source code testing, use START_DEV.bat instead.
  start "" "%ROOT%dist\windows-bundle\career-copilot.exe"
  exit /b 0
)
if exist "%ROOT%ready to client\windows\career-copilot.exe" (
  echo Starting client package...
  start "" "%ROOT%ready to client\windows\career-copilot.exe"
  exit /b 0
)

:use_python
REM --- 2) Python from USB venv only (never system Python) ---
set "PYTHON="
if exist "%ROOT%.venv\Scripts\pythonw.exe" set "PYTHON=%ROOT%.venv\Scripts\pythonw.exe"
if not defined PYTHON if exist "%ROOT%venv311\Scripts\pythonw.exe" set "PYTHON=%ROOT%venv311\Scripts\pythonw.exe"
if not defined PYTHON if exist "%ROOT%python\pythonw.exe" set "PYTHON=%ROOT%python\pythonw.exe"

if not defined PYTHON (
  echo.
  echo [ERROR] No runnable app found in this folder.
  echo.
  echo On the BUILD machine run once:
  echo   install_deps.bat
  echo   BUILD_CLIENT_PACKAGE.bat
  echo Then copy this whole folder to USB, OR copy "ready to client\windows" here.
  echo.
  echo For dev on USB without EXE, copy the .venv folder from the build PC too.
  echo.
  pause
  exit /b 1
)

echo Starting dashboard + mobile bridge + overlay...
start "Career Copilot Premium" "%PYTHON%" "%ROOT%premium_launcher.py"
echo.
echo Launched. Browser and overlay will open shortly.
echo All data stays in: %ROOT%
timeout /t 4 /nobreak >nul
exit /b 0
