@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3 -m venv .venv
)

echo Installing from requirements.txt...
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pyinstaller

echo.
echo Done. Next: run BUILD_CLIENT_PACKAGE.bat to create Setup.exe for client.
pause
