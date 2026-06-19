@echo off
setlocal

set "ROOT=%~dp0.."
set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
set "PATH=%ANDROID_HOME%\platform-tools;%ANDROID_HOME%\cmdline-tools\latest\bin;%PATH%"
set "KEYSTORE_FILE=%ROOT%\release\android\career_copilot.keystore"
set "KEYSTORE_PASSWORD=CareerCopilot123!"
set "KEY_ALIAS=career_copilot"
set "KEY_PASSWORD=CareerCopilot123!"

pushd "%ROOT%\mobile_app\react_native"

call npm.cmd install
if errorlevel 1 (
  echo [ERROR] npm install failed.
  popd
  exit /b %errorlevel%
)

if not exist "android\app\src\main\assets\" mkdir "android\app\src\main\assets"

if not exist "%KEYSTORE_FILE%" (
  if not exist "%ROOT%\release\android\" mkdir "%ROOT%\release\android"
  keytool -genkeypair -v -storetype PKCS12 -keystore "%KEYSTORE_FILE%" -alias career_copilot -keyalg RSA -keysize 2048 -validity 10000 -storepass CareerCopilot123! -keypass CareerCopilot123! -dname "CN=Career Copilot, OU=Dev, O=Career Copilot, L=Local, S=Local, C=US"
  if errorlevel 1 (
    echo [ERROR] Keystore generation failed.
    popd
    exit /b %errorlevel%
  )
)

call npx.cmd react-native bundle --platform android --dev false --entry-file index.js --bundle-output android/app/src/main/assets/index.android.bundle --assets-dest android/app/src/main/res/
if errorlevel 1 (
  echo [ERROR] React Native bundle generation failed.
  popd
  exit /b %errorlevel%
)

pushd android
set "GRADLE_CMD=gradlew.bat"
if not exist "%GRADLE_CMD%" set "GRADLE_CMD=%ROOT%\.tools\gradle-8.7\bin\gradle.bat"
if not exist "%GRADLE_CMD%" set "GRADLE_CMD=%ROOT%\.tools\gradle-8.7\bin\gradle"
call "%GRADLE_CMD%" assembleRelease
if errorlevel 1 (
  echo [ERROR] Gradle release build failed.
  popd
  popd
  exit /b %errorlevel%
)
popd

set "SRC=android\app\build\outputs\apk\release\app-release.apk"
set "DST_DIR=%ROOT%\release\android"
set "DST=%DST_DIR%\CareerCopilotPremium.apk"

if not exist "%SRC%" (
  echo [ERROR] Release APK not found at %SRC%
  popd
  exit /b 1
)

if not exist "%DST_DIR%\" mkdir "%DST_DIR%"
copy /Y "%SRC%" "%DST%" >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy APK to %DST%
  popd
  exit /b %errorlevel%
)

echo [OK] Release APK copied to %DST%
popd
exit /b 0