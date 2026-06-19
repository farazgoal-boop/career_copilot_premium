@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%"

set "PYINSTALLER_CMD=pyinstaller"
where pyinstaller >nul 2>nul
if errorlevel 1 (
  set "PYTHON_EXE=%ROOT%\.startup-check-venv\Scripts\python.exe"
  if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%ROOT%\temp_restore\.venv\Scripts\python.exe"
  if not exist "%PYTHON_EXE%" (
    echo [ERROR] Could not find pyinstaller or a local build Python runtime.
    popd
    exit /b 1
  )
  set "PYINSTALLER_CMD=%PYTHON_EXE% -m PyInstaller"
)

call %PYINSTALLER_CMD% career-copilot.spec --clean --noconfirm
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

set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 7\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files\Inno Setup 7\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Users\%USERNAME%\AppData\Local\Programs\Inno Setup 7\ISCC.exe"

if not exist "%ISCC_PATH%" (
  echo [ERROR] Inno Setup ISCC.exe not found.
  popd
  exit /b 1
)

"%ISCC_PATH%" installers\windows_setup.iss
if errorlevel 1 (
  echo [ERROR] Inno Setup build failed.
  popd
  exit /b %errorlevel%
)

set "FINAL_INSTALLER=release\installer\v1.0.0\CareerCopilotPremium_Setup_v1.0.0.exe"
set "DUPLICATE_INSTALLER=release\installer\v1.0.0\CareerCopilotPremium_Setup_v1.0.0.exe.exe"

if exist "%DUPLICATE_INSTALLER%" del /f /q "%DUPLICATE_INSTALLER%"
if exist "release\installer\CareerCopilotPremium_Setup_v1.0.0.exe.exe" del /f /q "release\installer\CareerCopilotPremium_Setup_v1.0.0.exe.exe"

if not exist "%FINAL_INSTALLER%" (
  echo [ERROR] Final installer not found at %FINAL_INSTALLER%
  popd
  exit /b 1
)

copy /Y "%FINAL_INSTALLER%" "CareerCopilotPremium_Setup_v1.0.0.exe" >nul
if errorlevel 1 (
  echo [WARN] Could not copy installer to project root.
) else (
  echo [OK] Root copy updated: CareerCopilotPremium_Setup_v1.0.0.exe
)

echo [OK] Full package built: %FINAL_INSTALLER%
popd
exit /b 0
