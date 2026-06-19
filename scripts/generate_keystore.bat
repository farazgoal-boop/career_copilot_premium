@echo off
setlocal

set "ROOT=%~dp0.."
if not exist "%ROOT%\release\android\" mkdir "%ROOT%\release\android"

pushd "%ROOT%"
keytool -genkeypair -v -storetype PKCS12 -keystore release\android\career_copilot.keystore -alias career_copilot -keyalg RSA -keysize 2048 -validity 10000
set "KEYTOOL_EXIT=%errorlevel%"
popd

if not "%KEYTOOL_EXIT%"=="0" (
  echo [ERROR] Keystore generation failed.
  exit /b %KEYTOOL_EXIT%
)

echo [OK] Keystore created at release\android\career_copilot.keystore
echo Save the keystore password safely. Store it in a secure password manager and back it up securely.
exit /b 0