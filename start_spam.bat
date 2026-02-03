<<<<<<< Updated upstream
@echo off
REM Startup script for SPAM on Windows (for testing)

echo Starting SPAM Application...
echo ============================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)

REM Get the directory where this script is located
cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo If you get an execution policy error, run this command in PowerShell:
    echo Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    pause
    exit /b 1
)

REM Install/update dependencies
echo Installing dependencies...
python -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo WARNING: Failed to upgrade pip, continuing anyway...
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    echo Please check that requirements.txt exists and contains valid packages
    pause
    exit /b 1
)

REM Upgrade SQLAlchemy to latest version (fixes Python 3.14 compatibility)
echo Upgrading SQLAlchemy for Python 3.14 compatibility...
pip install --upgrade sqlalchemy --quiet

REM Verify matplotlib is installed (critical dependency)
python -c "import matplotlib" >nul 2>&1
if errorlevel 1 (
    echo ERROR: matplotlib is not installed correctly
    echo Attempting to reinstall...
    pip install matplotlib numpy sqlalchemy --force-reinstall
    if errorlevel 1 (
        echo ERROR: Failed to install matplotlib
        pause
        exit /b 1
    )
)

REM Run the application
echo.
echo Launching SPAM GUI...
echo.
python GUI.py
if errorlevel 1 (
    echo.
    echo ERROR: Application crashed. Check the error message above.
    pause
    exit /b 1
)

REM Deactivate virtual environment on exit
deactivate

echo.
echo SPAM Application closed.
pause

=======
@echo off
REM Startup script for SPAM on Windows (for testing)

echo Starting SPAM Application...
echo ============================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)

REM Get the directory where this script is located
cd /d "%~dp0"

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo If you get an execution policy error, run this command in PowerShell:
    echo Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    pause
    exit /b 1
)

REM Check if dependencies are already installed (faster startup)
echo Checking dependencies...
python -c "import matplotlib, numpy, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install --upgrade pip --quiet
    if errorlevel 1 (
        echo WARNING: Failed to upgrade pip, continuing anyway...
    )
    
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        echo Please check that requirements.txt exists and contains valid packages
        pause
        exit /b 1
    )
    
    REM Upgrade SQLAlchemy to latest version (fixes Python 3.14 compatibility)
    pip install --upgrade sqlalchemy --quiet
) else (
    echo Dependencies already installed, skipping...
)

REM Run the application
echo.
echo Launching SPAM GUI...
echo.
python GUI.py
if errorlevel 1 (
    echo.
    echo ERROR: Application crashed. Check the error message above.
    pause
    exit /b 1
)

REM Deactivate virtual environment on exit
deactivate

echo.
echo SPAM Application closed.
pause

>>>>>>> Stashed changes
