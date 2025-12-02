@echo off
REM Startup script for SPAM on Windows (for testing)

echo Starting SPAM Application...
echo ============================

REM Get the directory where this script is located
cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate

REM Install/update dependencies
echo Installing dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

REM Run the application
echo Launching SPAM GUI...
python GUI.py

REM Deactivate virtual environment on exit
deactivate

echo SPAM Application closed.
pause

