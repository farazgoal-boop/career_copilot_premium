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

echo [INFO] Refreshing dist\windows-bundle from the freshly built EXE...
set "PYI_OUT=%ROOT%\dist\Career Copilot Premium"
if not exist "%PYI_OUT%\Career Copilot Premium.exe" (
  echo [ERROR] Expected %PYI_OUT%\Career Copilot Premium.exe
  popd
  exit /b 1
)
if exist "%ROOT%\dist\windows-bundle" rmdir /s /q "%ROOT%\dist\windows-bundle"
mkdir "%ROOT%\dist\windows-bundle"
xcopy /E /I /Y "%PYI_OUT%\*" "%ROOT%\dist\windows-bundle\" >nul
if exist "%ROOT%\.env.example" copy /Y "%ROOT%\.env.example" "%ROOT%\dist\windows-bundle\.env.example" >nul
copy /Y "%ROOT%\dist\windows-bundle\Career Copilot Premium.exe" "%ROOT%\dist\windows-bundle\career-copilot.exe" >nul

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