@echo off
setlocal

set "ROOT=%~dp0.."
pushd "%ROOT%"

call scripts\build_exe.bat
if errorlevel 1 (
  echo [ERROR] EXE build failed.
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
if exist "%ISCC_PATH%" (
  "%ISCC_PATH%" installers\windows_setup.iss
  if errorlevel 1 (
    echo [ERROR] Installer build failed.
    popd
    exit /b %errorlevel%
  )
) else (
  echo Please install Inno Setup 6 from https://jrsoftware.org/isdl.php
  popd
  exit /b 1
)

popd
exit /b 0