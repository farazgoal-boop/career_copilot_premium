@echo off
setlocal

set "JAVA_HOME=C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot"
set "ANDROID_SDK_ROOT=C:\Users\HAROON TRADERS\AppData\Local\Android\Sdk"
set "ANDROID_HOME=C:\Users\HAROON TRADERS\AppData\Local\Android\Sdk"
set "NODE_BINARY=C:\Program Files\nodejs\node.exe"
set "PATH=%PATH%;C:\Program Files\nodejs;C:\Program Files\Microsoft\jdk-17.0.19.10-hotspot\bin;C:\Users\HAROON TRADERS\AppData\Local\Android\Sdk\platform-tools"
set "APP_DEBUG_KEYSTORE=D:\my apps\career_copilot_premium\career_copilot_premium\mobile_app\react_native\android\app\debug.keystore"

if not exist "%APP_DEBUG_KEYSTORE%" (
	if not exist "%JAVA_HOME%\bin\keytool.exe" (
		echo keytool.exe not found under JAVA_HOME. Unable to create debug.keystore.
		exit /b 1
	)

	"%JAVA_HOME%\bin\keytool.exe" -genkeypair -v -storetype PKCS12 -keystore "%APP_DEBUG_KEYSTORE%" -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US"
	if errorlevel 1 exit /b %ERRORLEVEL%
)

cd /d "D:\my apps\career_copilot_premium\career_copilot_premium\mobile_app\react_native\android"
call "D:\my apps\career_copilot_premium\career_copilot_premium\tools\gradle\gradle-8.7\bin\gradle.bat" :app:assembleRelease --stacktrace --console=plain --no-daemon
exit /b %ERRORLEVEL%