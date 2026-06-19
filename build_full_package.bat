@echo off
setlocal

set "ROOT=%~dp0"
pushd "%ROOT%"

call scripts\build_full_package.bat
set "EXIT_CODE=%ERRORLEVEL%"

popd
exit /b %EXIT_CODE%
