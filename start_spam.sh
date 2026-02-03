#!/bin/bash
# Startup script for SPAM on Raspberry Pi

echo "Starting SPAM Application..."
echo "============================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are already installed (faster startup)
echo "Checking dependencies..."
python3 -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
else
    echo "Dependencies already installed, skipping..."
fi

# Run the application
echo "Launching SPAM GUI..."
python3 GUI.py

# Deactivate virtual environment on exit
deactivate

echo "SPAM Application closed."

