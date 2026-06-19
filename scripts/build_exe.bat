@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%"

set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  set "PYTHON_EXE=%ROOT%\.startup-check-venv\Scripts\python.exe"
)
if not exist "%PYTHON_EXE%" (
  set "PYTHON_EXE=%ROOT%\temp_restore\.venv\Scripts\python.exe"
)

if not exist "%PYTHON_EXE%" (
  echo [ERROR] No build Python environment found.
  popd
  exit /b 1
)

"%PYTHON_EXE%" -c "import PySide6, cryptography, sqlalchemy, flask_socketio" 1>nul 2>nul
if errorlevel 1 (
  echo [ERROR] Build environment is missing required packages: PySide6, cryptography, sqlalchemy, flask_socketio.
  echo [ERROR] Active build python: %PYTHON_EXE%
  popd
  exit /b 1
)

"%PYTHON_EXE%" -m PyInstaller career-copilot.spec --clean --noconfirm
if errorlevel 1 (
  echo [ERROR] PyInstaller build failed.
  popd
  exit /b %errorlevel%
)

set "SRC=dist\Career Copilot Premium"
set "DST=release\windows"

if not exist "%SRC%\" (
  echo [ERROR] Expected build output not found: %SRC%
  popd
  exit /b 1
)

if exist "%DST%\" rmdir /s /q "%DST%"
mkdir "%DST%"

robocopy "%SRC%" "%DST%" /E /NFL /NDL /NJH /NJS /NC /NS
if errorlevel 8 (
  echo [ERROR] Copy to %DST% failed.
  popd
  exit /b %errorlevel%
)

echo [OK] Build output copied to %DST%
popd
exit /b 0