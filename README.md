# SPAM - Scanner for Polarized Anisotropic Materials

A local desktop application for scanning and analyzing polarized anisotropic materials. Designed to run on Raspberry Pi and other local systems without requiring a web server.

## Features

- **Real-time Measurements**: Live data visualization with automatic updates
- **Data Management**: Store and retrieve measurement data using SQLite
- **Calibration**: System calibration functionality
- **Data Export**: Export measurements in JSON or CSV format
- **Modern GUI**: Desktop interface built with Tkinter and Matplotlib

## Tech Stack

- **Python 3.8+**: Core application language
- **Tkinter**: GUI framework (included with Python)
- **Matplotlib**: Data visualization and graphing
- **SQLAlchemy**: ORM for database operations
- **SQLite**: Local database (no server required)

## Project Structure

```
SPAM/
├── GUI.py                 # Main application (standalone desktop app)
├── requirements.txt       # Python dependencies
├── start_spam.sh         # Startup script for Linux/Raspberry Pi
├── start_spam.bat        # Startup script for Windows
├── backend/
│   ├── database.py       # Database configuration
│   ├── models.py         # SQLAlchemy models
│   └── schemas.py        # Data schemas (for reference)
└── README.md
```

## Installation

### Prerequisites

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Tkinter** (GUI framework - usually included with Python)
  - On Raspberry Pi/Linux: `sudo apt-get install python3-tk`
  - On Windows/Mac: Usually pre-installed with Python

### Windows Installation

#### Option 1: Quick Start (Recommended)

1. **Download or clone the repository:**
   ```powershell
   git clone https://github.com/kevinsestate/SPAM.git
   cd SPAM
   ```

2. **Run the startup script:**
   ```powershell
   .\start_spam.bat
   ```
   
   The script will automatically:
   - Check if Python is installed
   - Create a virtual environment (if needed)
   - Install all dependencies (only if not already installed)
   - Launch the GUI application

#### Option 2: Manual Installation

1. **Navigate to the project directory:**
   ```powershell
   cd SPAM
   ```

2. **Create a virtual environment:**
   ```powershell
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   ```powershell
   .\venv\Scripts\activate
   ```
   
   If you get an execution policy error:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Run the application:**
   ```powershell
   python GUI.py
   ```

### Linux / Raspberry Pi Installation

#### Option 1: Quick Start (Recommended)

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/kevinsestate/SPAM.git
   cd SPAM
   ```

2. **Make the startup script executable:**
   ```bash
   chmod +x start_spam.sh
   ```

3. **Run the application:**
   ```bash
   ./start_spam.sh
   ```
   
   The script will automatically:
   - Check if Python 3 is installed
   - Create a virtual environment (if needed)
   - Install all dependencies (only if not already installed)
   - Launch the GUI application

#### Option 2: Manual Installation

1. **Install Tkinter (if not already installed):**
   ```bash
   sudo apt-get update
   sudo apt-get install python3-tk
   ```

2. **Navigate to the project directory:**
   ```bash
   cd SPAM
   ```

3. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   ```

4. **Activate the virtual environment:**
   ```bash
   source venv/bin/activate
   ```

5. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

6. **Run the application:**
   ```bash
   python3 GUI.py
   ```

## Usage Guide

### First Time Setup

1. **Configure Connection Settings** (if using hardware):
   - Go to **Settings → Connection Setup**
   - Enter VNA IP address and port (if using VNA)
   - Configure serial port settings (if using serial connection)
   - Click **"Save"** to store settings

2. **Adjust Measurement Parameters** (optional):
   - Go to **Settings → Adjust Parameters**
   - Set frequency, power level, angle step, and measurement interval
   - Click **"Save"** to apply changes

### Calibration Process

Before taking measurements, you must calibrate the system:

1. Click the **"Calibrate"** button in the sidebar
2. **Step 1 - Empty Measurement:**
   - Ensure NO material is in the measurement fixture
   - Click **OK** to begin empty calibration
   - Wait for calibration to complete (~2 seconds)
3. **Step 2 - Material Placement:**
   - Place your material sample in the measurement fixture
   - Ensure it is properly positioned and secured
   - Click **OK** to continue with material calibration
   - Wait for calibration to complete (~2 seconds)
4. Calibration complete! The system is now ready for measurements

### Taking Measurements

1. **Start a Measurement Session:**
   - Click **"Start Measurement"** in the sidebar
   - The system will automatically sweep through angles from 0° to 90°
   - Measurements are taken at each angle step (default: 5°)
   - Data is saved to the database in real-time

2. **Monitor Progress:**
   - Watch the real-time graphs in the center panel
   - Check the right panel for current values:
     - Current Angle
     - Permittivity (ε)
     - Permeability (μ)
     - S-Parameters (S₁₁, S₁₂, S₂₁, S₂₂)
   - View system status at the bottom

3. **Stop Measurement:**
   - Click **"Stop Measurement"** to halt the current session
   - Data collected up to that point is saved

### Viewing Results

- **Real-Time Graphs:**
  - Center panel shows permittivity and permeability vs angle
  - Graphs update automatically every second
  - Scroll to view control parameters and non-idealities sections

- **Measurement Data Panel:**
  - Right panel displays latest measurement values
  - S-Parameters show magnitude and phase
  - System status indicates current state

- **View Results Summary:**
  - Click **"View Results"** to see statistics
  - Shows total measurements, angle range, min/max/average values

### Managing Data

1. **Clear Measurements:**
   - Click **"Clear Measurements"** to delete all data
   - Confirmation dialog will appear
   - **Warning:** This action cannot be undone

2. **Export Data:**
   - Click **"Export Data"** or use **File → Export Data**
   - Choose file location and format:
     - **JSON**: Structured data format
     - **CSV**: Spreadsheet-compatible format
   - All measurements will be exported

### Understanding the Interface

**Left Sidebar:**
- Action buttons for calibration, measurement control, and data management
- Version information at the bottom

**Center Panel:**
- Real-time measurement graphs (Permittivity and Permeability)
- Control Parameters section (frequency, power, angle step, interval)
- Non-Idealities & Compensation section (calibration error, noise, temperature, humidity)

**Right Panel:**
- Current measurement values
- S-Parameter display
- System status

**Status Bar (Bottom):**
- Current system status
- Last update timestamp

### Database

- All measurements are stored in a local SQLite database (`spam.db`)
- The database is created automatically on first run
- No database server is required - everything runs locally
- Database file is stored in the project directory

## Hardware Integration

The current implementation includes simulated measurement data for demonstration. To integrate with actual hardware:

### VNA Integration

1. **Configure Connection:**
   - Go to **Settings → Connection Setup**
   - Enter your VNA IP address and port (typically port 5025 for SCPI)
   - Save settings

2. **Modify Measurement Worker:**
   - Locate the `_measurement_worker` method in `GUI.py` (around line 1025)
   - Replace the simulated S-parameter generation with actual VNA readings:
   ```python
   # Example VNA integration
   import pyvisa
   
   def _measurement_worker(self):
       rm = pyvisa.ResourceManager()
       vna = rm.open_resource(f"TCPIP::{self.connection_settings['vna_address']}::{self.connection_settings['vna_port']}::SOCKET")
       
       while self.is_measuring:
           # Read S-parameters from VNA
           s11 = vna.query("S11")
           s12 = vna.query("S12")
           s21 = vna.query("S21")
           s22 = vna.query("S22")
           
           # Convert S-parameters to material properties
           permittivity, permeability = convert_s_to_material_props(s11, s12, s21, s22)
           
           # Save to database
           self._create_measurement(self.current_angle, permittivity, permeability)
   ```

3. **S-Parameter to Material Properties:**
   - Implement conversion formulas based on your measurement setup
   - Consider calibration corrections and non-idealities
   - The GUI displays S-parameters in real-time for verification

### Serial Device Integration

1. **Configure Serial Connection:**
   - Go to **Settings → Connection Setup**
   - Set serial port (e.g., COM1, /dev/ttyUSB0)
   - Set baud rate and timeout
   - Save settings

2. **Modify for Serial Communication:**
   ```python
   import serial
   
   def _measurement_worker(self):
       ser = serial.Serial(
           port=self.connection_settings['serial_port'],
           baudrate=int(self.connection_settings['baud_rate']),
           timeout=float(self.connection_settings['timeout'])
       )
       
       while self.is_measuring:
           # Read data from serial device
           data = ser.readline().decode().strip()
           # Parse and convert to permittivity/permeability
           # Save to database
   ```

### Key Integration Points

- **Connection Settings:** Stored in `self.connection_settings` dictionary
- **Measurement Parameters:** Adjustable via Settings → Adjust Parameters
- **S-Parameter Display:** Already implemented in the GUI
- **Database:** Automatically handles all measurement storage
- **Real-time Updates:** GUI updates automatically as data arrives

## Troubleshooting

### Tkinter not found (Linux/Raspberry Pi)
```bash
sudo apt-get update
sudo apt-get install python3-tk
```

### Permission denied on startup script
```bash
chmod +x start_spam.sh
```

### Database errors
- The database file (`spam.db`) is created automatically
- If you encounter errors, try deleting `spam.db` and restarting the application

### Display issues on Raspberry Pi
- If the GUI doesn't appear, make sure you're running in a graphical environment
- For headless setups, you may need to set up X11 forwarding or use a VNC server

## Development

### Adding New Features

The application is structured with clear separation:
- `GUI.py`: Main application and UI logic
- `backend/models.py`: Database models
- `backend/database.py`: Database configuration

### Testing

Run the application and test:
- Calibration functionality
- Measurement start/stop
- Data export (JSON and CSV)
- Graph updates with real data

## Notes

- This is a **local-only** application - no web server or network access required
- All data is stored locally in SQLite
- The application is designed to run standalone on a Raspberry Pi
- The web frontend (React) and FastAPI backend are no longer needed for local operation

## License

This project is provided as-is for educational and development purposes.
