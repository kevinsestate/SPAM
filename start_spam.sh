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

# Check if system packages are installed (before creating venv)
CHECK_SYSTEM_PYTHON="python3"
if ! $CHECK_SYSTEM_PYTHON -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1; then
    SYSTEM_PACKAGES_INSTALLED=false
else
    SYSTEM_PACKAGES_INSTALLED=true
    echo "System packages detected."
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    # If system packages are installed, create venv with --system-site-packages
    if [ "$SYSTEM_PACKAGES_INSTALLED" = true ]; then
        echo "Creating venv with system site-packages access..."
        python3 -m venv --system-site-packages venv
    else
        python3 -m venv venv
    fi
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Function to install via system package manager
install_system_packages() {
    echo "Attempting to install via apt-get..."
    sudo apt-get update -qq
    sudo apt-get install -y python3-matplotlib python3-numpy python3-sqlalchemy python3-tk 2>/dev/null
    
    # Check if system packages worked (using system python, not venv)
    if ! $CHECK_SYSTEM_PYTHON -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1; then
        echo ""
        echo "ERROR: Could not install dependencies!"
        echo "Options:"
        echo "1. Configure DNS (see CONFIGURE_DNS.md):"
        echo "   echo 'static domain_name_servers=8.8.8.8 8.8.4.4' | sudo tee -a /etc/dhcpcd.conf"
        echo "   sudo systemctl restart dhcpcd"
        echo ""
        echo "2. Or install manually:"
        echo "   sudo apt-get install python3-matplotlib python3-numpy python3-sqlalchemy python3-tk"
        echo ""
        exit 1
    else
        echo "Dependencies installed via system packages."
        # Recreate venv with system site-packages if it wasn't already
        if [ ! -f "venv/pyvenv.cfg" ] || ! grep -q "include-system-site-packages = true" venv/pyvenv.cfg 2>/dev/null; then
            echo "Recreating venv to use system packages..."
            deactivate 2>/dev/null
            rm -rf venv
            python3 -m venv --system-site-packages venv
            source venv/bin/activate
        fi
    fi
}

# Check if dependencies are already installed (faster startup)
echo "Checking dependencies..."
# Check both in venv and system python
if python3 -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1; then
    DEPS_AVAILABLE=true
elif $CHECK_SYSTEM_PYTHON -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1; then
    DEPS_AVAILABLE=true
    echo "Dependencies found in system Python. Ensuring venv can access them..."
    # Make sure venv uses system packages
    if [ ! -f "venv/pyvenv.cfg" ] || ! grep -q "include-system-site-packages = true" venv/pyvenv.cfg 2>/dev/null; then
        echo "Recreating venv with system site-packages access..."
        deactivate 2>/dev/null
        rm -rf venv
        python3 -m venv --system-site-packages venv
        source venv/bin/activate
    fi
else
    DEPS_AVAILABLE=false
fi

if [ "$DEPS_AVAILABLE" = false ]; then
    echo "Installing dependencies..."
    
    # Check if we have internet/DNS access (test with IP, not DNS)
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        # Test DNS resolution
        if nslookup pypi.org >/dev/null 2>&1; then
            # Try to install via pip
            echo "Installing via pip..."
            pip install --upgrade pip --quiet 2>/dev/null
            pip install -e . --quiet 2>/dev/null || pip install -r requirements.txt --quiet 2>/dev/null
            
            # Check if installation succeeded
            python3 -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1
            if [ $? -ne 0 ]; then
                echo "WARNING: pip installation failed. Trying system packages..."
                install_system_packages
            else
                echo "Dependencies installed via pip."
            fi
        else
            echo "WARNING: DNS resolution failed. Trying system packages..."
            install_system_packages
        fi
    else
        echo "WARNING: No internet connection detected. Trying system packages..."
        install_system_packages
    fi
    
    # Final check after installation attempts
    if ! python3 -c "import matplotlib, numpy, sqlalchemy" >/dev/null 2>&1; then
        echo ""
        echo "ERROR: Dependencies still not available after installation attempts!"
        echo ""
        echo "Troubleshooting:"
        echo "1. Verify packages are installed:"
        echo "   python3 -c 'import matplotlib, numpy, sqlalchemy; print(\"OK\")'"
        echo ""
        echo "2. If that works, the venv may need to be recreated:"
        echo "   rm -rf venv"
        echo "   python3 -m venv --system-site-packages venv"
        echo ""
        echo "3. Or install in venv manually:"
        echo "   source venv/bin/activate"
        echo "   pip install matplotlib numpy sqlalchemy"
        echo ""
        exit 1
    fi
else
    echo "Dependencies already available, skipping installation..."
fi

# Check for display before running GUI
if [ -z "$DISPLAY" ]; then
    echo ""
    echo "WARNING: No display detected!"
    echo "DISPLAY environment variable is not set."
    echo ""
    echo "Options:"
    echo "1. If using VNC, set display: export DISPLAY=:1"
    echo "2. If SSHing, use: ssh -X pi@your-pi-ip"
    echo "3. Install VNC: sudo apt-get install tightvncserver && vncserver :1"
    echo "4. See RUNNING_WITHOUT_DISPLAY.md for detailed instructions"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please set up a display first."
        exit 1
    fi
fi

# Run the application
echo "Launching SPAM GUI..."
python3 GUI.py

# Deactivate virtual environment on exit
deactivate

echo "SPAM Application closed."

