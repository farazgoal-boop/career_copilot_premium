@echo off

setlocal EnableExtensions

title Career Copilot Premium - Dev Start (visible console)

cd /d "%~dp0"



echo.

echo ============================================================

echo  Career Copilot Premium - DEV START

echo ============================================================

echo  Use this for testing + Playwright (latest source code).

echo.



call "%~dp0STOP_CAREER_COPILOT.bat"



set "PYTHON="

if exist "%~dp0venv311\Scripts\python.exe" set "PYTHON=%~dp0venv311\Scripts\python.exe"

if not defined PYTHON if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"



if not defined PYTHON (

  echo [ERROR] No venv found. Run: install_deps.bat

  pause

  exit /b 1

)



REM Dev mode: use project folder data, not packaged EXE

set "CAREER_COPILOT_PORTABLE=1"

set "CAREER_COPILOT_USE_SOURCE=1"



echo Starting with: %PYTHON%

echo Dashboard will open at http://127.0.0.1:5000

echo Keep this window open. Close it to stop the app.

echo.



"%PYTHON%" "%~dp0premium_launcher.py"

set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (

  echo.

  echo App exited with error code %RC%

  echo Check logs\startup_error.log

  pause

)

exit /b %RC%

