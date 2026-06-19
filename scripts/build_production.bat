@echo off
title Career Copilot Premium - Production Build
cd /d "D:\my apps\career_copilot_premium\career_copilot_premium"

echo.
echo ===== Installing dependencies =====
.venv\Scripts\pip install pyinstaller segno sounddevice soundfile numpy sqlalchemy pillow qrcode cryptography flask werkzeug --quiet
if errorlevel 1 goto :fail

echo.
echo ===== Building Windows EXE =====
.venv\Scripts\pyinstaller career-copilot.spec --clean --noconfirm
if errorlevel 1 goto :fail

echo.
echo ===== Creating ready-to-client folder =====
if not exist "ready to client" mkdir "ready to client"
if not exist "ready to client\windows" mkdir "ready to client\windows"
if not exist "ready to client\android" mkdir "ready to client\android"
if not exist "ready to client\installer" mkdir "ready to client\installer"

echo.
echo ===== Copying EXE files =====
xcopy /E /I /Y "dist\windows-bundle\*" "ready to client\windows\"
if errorlevel 1 goto :fail

echo.
echo ===== Building Setup.exe installer =====
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Users\HAROON TRADERS\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Users\HAROON TRADERS\AppData\Local\Programs\Inno Setup 7\ISCC.exe"
if not exist "%ISCC_PATH%" (
    echo ERROR: ISCC.exe not found.
    goto :fail
)
"%ISCC_PATH%" "installers\windows_setup.iss"
if errorlevel 1 goto :fail
xcopy /Y "dist\installer\*.exe" "ready to client\installer\"
if errorlevel 1 goto :fail

echo.
echo ===== Copying APK =====
if exist "dist\mobile\*.apk" (
    xcopy /Y "dist\mobile\*.apk" "ready to client\android\"
) else if exist "dist\*.apk" (
    xcopy /Y "dist\*.apk" "ready to client\android\"
) else if exist "release\android\*.apk" (
    xcopy /Y "release\android\*.apk" "ready to client\android\"
) else (
    echo WARNING: No APK found in dist\mobile, dist, or release\android.
)

echo.
echo ===== BUILD COMPLETE =====
echo.
echo ready to client folder contents:
dir "ready to client" /s /b
pause
exit /b 0

:fail
echo.
echo ===== BUILD FAILED =====
echo Check the output above for details.
pause
exit /b 1
