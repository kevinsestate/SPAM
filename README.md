# SPAM - Scanner for Polarized Anisotropic Materials

A local desktop application for scanning and analyzing polarized anisotropic materials. Designed to run on Raspberry Pi and other local systems without requiring a web server.

## Features

- **Real-time Measurements**: Live data visualization with automatic updates
- **Data Management**: Store and retrieve measurement data using SQLite
- **Calibration**: System calibration functionality
- **Data Export**: Export measurements in JSON or CSV format
- **Modern GUI**: Desktop interface built with Tkinter and Matplotlib

## Current Implementation Status

- **AD7193 on Raspberry Pi**: SPI bring-up is working (`ID=0xA2` and finite I/Q reads).
- **GUI ADC-only flow**: Operational for measurement runs without motor/RF switch control.
- **Motor dependency**: Optional for ADC bring-up; missing motor libs do not block ADC validation.
- **Extraction boundary (important)**: Voltage-to-calibrated-S-parameter math is still pending teammate implementation.
- **ADC output rate**: Configurable via **Data Rate (Hz)** in **Settings → Connection Setup** (also `adc_data_rate` in `spam_config.json`). Default `96` Hz is conservative; increase (e.g. `4800`) for faster conversions at the cost of noise / filter notches (see `hardware/ad7193.py` FS mapping).
- **Measured I/Q pair rate**: With default `data_rate=96` and stream mode, **Python and C++** both achieve on the order of **~12 complete I/Q pairs per second** on a Pi 4 — the limit matches between languages, so the bottleneck is **ADC filter / two-channel sequencer / read pattern**, not Python alone. Raw SPI throughput is much higher (`scripts/pi/spi_ad7193_benchmark`).

### What Is Provisional vs Final

- **Final/validated now**
  - AD7193 low-level SPI communication and channel reads.
  - End-to-end GUI acquisition path using live ADC values.
- **Provisional for now**
  - Mapping ADC voltage I/Q directly into S-parameter values for extraction.
  - Material extraction quality until calibrated voltage->S conversion is merged.

## Tech Stack

- **Python 3.9+**: Core application language
- **Tkinter**: GUI framework (included with Python)
- **Matplotlib**: Data visualization and graphing
- **SQLAlchemy**: ORM for database operations
- **SQLite**: Local database (no server required)

## Project Structure

```
SPAM/
├── GUI.py                  # Thin entry point (backward compat)
├── app.py                  # Application assembly (SPAMGui from mixins)
├── __main__.py             # Enables: python -m spam
├── pyproject.toml          # Python packaging config
├── requirements.txt        # Legacy dependency list
├── start_spam.sh           # Startup script for Linux/Raspberry Pi
├── start_spam.bat          # Startup script for Windows
├── spam_calc.py            # Backward-compat shim -> core/
├── spam_optimizer.py       # Backward-compat shim -> core/
├── core/
│   ├── spam_calc.py        # Transmission-matrix math (forward + S->T)
│   └── spam_optimizer.py   # Progressive inverse extraction
├── gui/
│   ├── themes.py           # Theme palettes and fonts
│   ├── widgets.py          # Styled widget factory
│   ├── config.py           # Config persistence
│   ├── hardware_mixin.py   # Hardware init and motor control
│   ├── db_helpers.py       # Database CRUD helpers
│   ├── measurement.py      # Measurement sweep worker
│   ├── extraction.py       # Material extraction worker
│   ├── graphs.py           # Center panel graphs
│   ├── callbacks.py        # Status, calibrate, export, help
│   ├── debug_console.py    # Debug console window
│   ├── panels/             # Menu, status bar, sidebar, detail panel
│   └── dialogs/            # Extraction, parameters, connection dialogs
├── backend/
│   ├── database.py         # Database configuration
│   └── models.py           # SQLAlchemy models
├── hardware/
│   ├── ad7193.py           # AD7193 ADC driver
│   └── rf_switch.py        # RF switch controller
├── tests/
│   ├── test_spam_calc.py   # T-matrix validation tests
│   └── test_optimizer.py   # Extraction validation tests
├── scripts/pi/             # Raspberry Pi ADC / SPI utilities (see below)
├── Simulated Spam Calculations/
│   ├── *.mat               # Simulated validation datasets
│   └── *.m                 # MATLAB reference scripts
├── archive/
│   └── legacy/             # Non-active archived artifacts
└── README.md
```

### Raspberry Pi ADC scripts (`scripts/pi/`)

Build and run on the Pi (Linux only; requires SPI enabled and `g++` for C++ tools):

| Script / binary | Purpose |
|-----------------|--------|
| `check_adc_lowlevel.py` | Short I/Q sanity check; optional `--benchmark-raw`, `--binary-out`, `--result-json` |
| `live_adc_view.py` | Live plot and/or benchmark; use `--data-rate`, `--spi-speed`, `--mode max-rate`, `--acq-mode stream`, `--benchmark-raw`, `--result-json` (do not pass literal `...` on the command line) |
| `adc_fast_capture.py` | Optional native fast path hook + Python fallback |
| `spi_ad7193_benchmark.cpp` | Raw SPI throughput vs clock (not full ADC protocol) |
| `ad7193_cpp_benchmark.cpp` | Full AD7193 driver in C++ + **pair/s** benchmark (compare to `live_adc_view.py`) |

Example (high output rate, benchmark only):

```bash
cd SPAM && source venv/bin/activate
python scripts/pi/live_adc_view.py --data-rate 4800 --spi-speed 2000000 \
  --mode max-rate --acq-mode stream --benchmark-raw --no-plot --duration 30 --result-json
```

Compile C++ tools:

```bash
cd SPAM/scripts/pi
g++ -O3 -std=c++17 spi_ad7193_benchmark.cpp -o spi_ad7193_benchmark
g++ -O3 -std=c++17 ad7193_cpp_benchmark.cpp -o ad7193_cpp_benchmark
```

(`-O3` uses the letter **O**, not zero.)

### Active vs Archive

- **Active runtime/test path**: `app.py`, `GUI.py`, `core/`, `gui/`, `backend/`, `hardware/`, `tests/`, startup scripts.
- **Archive path**: `archive/legacy/` contains non-active or superseded artifacts kept for reference (not used by launch scripts).

## Installation

### Prerequisites

- **Python 3.9 or higher**
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
   - Install the project and all dependencies
   - Launch the GUI application

#### Option 2: pip install (Standard Python)

1. **Clone and install:**
   ```powershell
   git clone https://github.com/kevinsestate/SPAM.git
   cd SPAM
   pip install -e .
   ```

2. **Launch (any of these work):**
   ```powershell
   spam                # CLI entry point
   python -m spam      # Module entry point
   python GUI.py       # Direct script
   ```

#### Option 3: Manual Installation

1. **Navigate to the project directory:**
   ```powershell
   cd SPAM
   ```

2. **Create a virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
   
   If you get an execution policy error:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **Install:**
   ```powershell
   pip install -e .
   ```

4. **Run:**
   ```powershell
   spam
   ```

### Linux / Raspberry Pi Installation

#### Option 1: Quick Start (Recommended)

1. **Clone or download the repository:**
   ```bash
   git clone https://github.com/kevinsestate/SPAM.git
   cd SPAM
   chmod +x start_spam.sh
   ```

2. **Run the application:**
   ```bash
   ./start_spam.sh
   ```
   
   The script will automatically:
   - Check if Python 3 is installed
   - Create a virtual environment (if needed)
   - Install the project and all dependencies
   - Launch the GUI application

#### Option 2: pip install (Standard Python)

1. **Clone and install:**
   ```bash
   git clone https://github.com/kevinsestate/SPAM.git
   cd SPAM
   pip install -e .
   ```

   For Raspberry Pi with hardware support:
   ```bash
   pip install -e ".[rpi]"
   ```

2. **Launch:**
   ```bash
   spam                # CLI entry point
   python -m spam      # Module entry point
   python3 GUI.py      # Direct script
   ```

#### Option 3: Manual Installation

1. **Install Tkinter (if not already installed):**
   ```bash
   sudo apt-get update
   sudo apt-get install python3-tk
   ```

2. **Set up and install:**
   ```bash
   cd SPAM
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

3. **Run:**
   ```bash
   spam
   ```

## Usage Guide

### First Time Setup

1. **Configure Connection Settings** (if using hardware):
   - Go to **Settings → Connection Setup**
   - Configure signal input settings (ADC channels, sampling rate, etc.)
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
- S-Parameter display (derived from signal measurements)
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

The project now includes live **AD7193 (Pmod AD5) SPI** integration on Raspberry Pi for bring-up and GUI measurement flow. (Older docs may mention I2C for a generic ADC; the shipped driver uses **`/dev/spidev*`**.) The remaining hardware-math integration task is calibrated voltage-to-S-parameter conversion for extraction quality.

### System Architecture

The SPAM system uses a custom RF measurement setup with the following components:

**RF Chain:**
- **Gunn Diode Oscillator**: Generates the RF signal
- **Amplifier**: Boosts the RF signal power
- **Splitter**: Divides signal into two paths:
  - **TX Path**: Transmit signal to TX Horn Antenna (radiates RF into free space)
  - **LO Path**: Local Oscillator signal to Mixer
- **RX Horn Antennas**: Two receive antennas (RXp and RXT) receive reflected/transmitted RF
- **Switch**: Selects between the two RX antennas
- **Mixer**: Downconverts RF signal to baseband, producing:
  - **IF-I** (In-phase component)
  - **IF-Q** (Quadrature component)
- **ADCs**: Convert analog IF-I and IF-Q signals to digital data

**Control System:**
- **Raspberry Pi**: Central processing unit
  - Reads I/Q data from ADCs via **I2C**
  - Controls motors via **Microcontroller** (I2C)
  - Receives encoder feedback for angle position
- **Microcontroller**: Motor controller (I2C interface)
  - Controls motor rotation
  - Reads encoder position feedback

### I2C/ADC Integration

The system reads two signals (IF-I and IF-Q) from ADCs connected via I2C to determine permittivity (ε) and permeability (μ).

1. **Configure Connection:**
   - Go to **Settings → Connection Setup**
   - Configure I2C bus number (typically 1 on Raspberry Pi)
   - Set ADC I2C address (default: 0x48)
   - Configure IF-I and IF-Q ADC channels
   - Set sampling rate
   - Configure microcontroller I2C address for motor control
   - Save settings

2. **Modify Measurement Worker:**
   - Locate the `_measurement_worker` method in `GUI.py` (around line 760)
   - Replace the simulated data generation with actual I/Q readings:
   ```python
   def _measurement_worker(self):
       """Read IF-I and IF-Q from ADCs and convert to permittivity/permeability."""
       import smbus
       
       # Initialize I2C bus
       bus = smbus.SMBus(int(self.connection_settings['i2c_bus']))
       adc_addr = int(self.connection_settings['adc_address'], 16)
       
       while self.is_measuring:
           # Read IF-I and IF-Q from ADCs via I2C
           if_i = read_adc_channel(bus, adc_addr, 
                                   int(self.connection_settings['if_i_channel']))
           if_q = read_adc_channel(bus, adc_addr, 
                                   int(self.connection_settings['if_q_channel']))
           
           # Process I/Q signals to extract material properties
           # This conversion depends on your specific RF measurement setup
           permittivity, permeability = process_iq_signals(if_i, if_q, self.current_angle)
           
           # Optionally calculate S-parameters from I/Q for display
           s11, s12, s21, s22 = iq_to_s_parameters(if_i, if_q)
           
           # Save to database
           self._create_measurement(self.current_angle, permittivity, permeability)
           
           # Control motor to next angle (via microcontroller I2C)
           set_motor_angle(bus, int(self.connection_settings['microcontroller_address'], 16), 
                          self.current_angle + angle_step)
           
           # Wait for motor to reach position and stabilize
           time.sleep(self.measurement_interval)
   ```

3. **I/Q to Material Properties Conversion:**
   - Implement conversion algorithms based on your RF measurement setup
   - The I/Q components represent the complex baseband signal
   - Process I/Q to extract magnitude and phase information
   - Apply calibration corrections and non-ideality compensation
   - Convert to permittivity and permeability using your measurement model
   - S-parameters can be derived from I/Q for display purposes

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

The application uses a mixin-based architecture:
- `app.py`: Assembles `SPAMGui` from mixin classes
- `gui/`: Mixin modules (widgets, config, hardware, measurement, extraction, graphs, etc.)
- `core/`: Scientific computation (T-matrix math, inverse solver)
- `backend/`: Database models and configuration
- `hardware/`: ADC and RF switch drivers
- `tests/`: Validation test suites

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

## Integration Testing

For detailed integration test plans and rubrics, see [INTEGRATION_TEST_PLAN.md](INTEGRATION_TEST_PLAN.md).

The integration test plan includes:
- Motor control and measurement sweep integration tests
- Calibration process integration tests
- Manual motor control and I2C communication verification
- Quantitative success criteria for each test
- Test execution logs and assessment rubrics

## License

This project is provided as-is for educational and development purposes.
