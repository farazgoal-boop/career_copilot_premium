@echo off
setlocal

set "PYTHON_CMD="
where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    where py >nul 2>nul && set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo Python 3 was not found on PATH.
    echo Install Python and rerun this script.
    exit /b 1
)

if not exist .venv (
    call %PYTHON_CMD% -m venv .venv
    if errorlevel 1 exit /b %errorlevel%
)

call .venv\Scripts\activate.bat
call python -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%

call pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

echo Environment ready.
echo Run tests with: python -m unittest discover -s tests -p "test_*.py" -v

endlocal