# SPAM — Scanner for Polarized Anisotropic Materials

A local desktop application for scanning and extracting electromagnetic material tensors (ε, μ) from polarized RF measurements. Runs standalone on Raspberry Pi — no web server required.

## Features

- **Dual-polarization sweep**: Two full 0°–80° arm sweeps per run — horn at 0° (horizontal) then 90° (vertical) — servo-controlled automatically
- **Real-time S-parameter display**: Live S₂₁/S₁₁ magnitude and phase at each angle
- **T-matrix extraction**: Progressive inverse solver extracts diagonal ε/μ tensors from the full dual-pol S-matrix
- **Calibrated measurements**: Through + Reflect calibration sweep stores per-angle reference voltages
- **Live ADC oscilloscope**: Background I/Q stream at ~300 samp/s displayed in GUI
- **Data export**: JSON and CSV with all S-param fields + extraction results appended
- **Debug log**: All events written to `~/SPAM/spam_run.log` (survives crashes)
- **Remote access**: VNC-capable (x11vnc on X11 session) for headless operation

## Current Implementation Status (2026-04-13)

- **AD7193 SPI**: Operational — `ID=0xA2`, finite I/Q at 4800 Hz data rate, 4 MHz SPI
- **Motor control**: I2C polling of MCU status register (GPIO ISR not available on this kernel)
- **Servo**: HPS-2518MG on GPIO 18 — calibrated 850 µs = 0° (H), 1800 µs = 90° (V); jitter-free (PWM released after each move)
- **Dual-pol sweep**: Sweep 1 at horn 0°, servo rotates to 90°, Sweep 2 at horn 90°, returns home
- **RF switch**: Code complete — enable in Settings → Connection Setup once switch is physically wired
- **Calibration**: Through + Reflect sweep at pol-0 implemented; pol-90 cal deferred
- **Extraction**: Fires automatically after dual sweep if calibration data is loaded; builds 4×4 S-matrix from paired pol-0/pol-90 measurements

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
├── spam_config.json        # GUI / ADC connection defaults (local)
├── spam_calc.py            # Backward-compat shim -> core/
├── spam_optimizer.py       # Backward-compat shim -> core/
├── core/
│   ├── spam_calc.py        # Transmission-matrix math (forward + S->T)
│   └── spam_optimizer.py   # Progressive inverse extraction
├── docs/                   # Handoff, benchmarks, integration notes, hardware PDFs (see docs/README.md)
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
│   ├── ad7193.py           # AD7193 ADC driver (SPI)
│   ├── rf_switch.py        # RF switch controller (GPIO)
│   └── servo.py            # HPS-2518MG servo driver (pigpio/RPi.GPIO)
├── tests/
│   ├── test_spam_calc.py   # T-matrix validation tests
│   └── test_optimizer.py   # Extraction validation tests
├── scripts/pi/             # Raspberry Pi utilities (ADC, servo calibration)
├── Simulated Spam Calculations/
│   ├── *.mat               # Simulated validation datasets
│   └── *.m                 # MATLAB reference scripts
├── archive/
│   └── legacy/             # Non-active archived artifacts (includes old GUI snapshots)
└── README.md
```

Local runtime files (often gitignored): `spam.db`, `venv/`, `__pycache__/`, `spam_scanner.egg-info/`.

### Raspberry Pi ADC scripts (`scripts/pi/`)

Build and run on the Pi (Linux only; requires SPI enabled and `g++` for C++ tools):

| Script / binary | Purpose |
|-----------------|--------|
| `check_adc_lowlevel.py` | Short I/Q sanity check; optional `--benchmark-raw`, `--binary-out`, `--result-json` |
| `live_adc_view.py` | Live plot and/or benchmark; use `--data-rate`, `--spi-speed`, `--mode max-rate`, `--acq-mode stream`, `--benchmark-raw`, `--result-json` |
| `adc_fast_capture.py` | Optional native fast path hook + Python fallback |
| `servo_test.py` | **Interactive servo calibration** — `scan`, `sweep`, `min<us>`, `max<us>`, angle commands |
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

Before taking measurements, calibrate the system to convert raw ADC voltages to S-parameters:

1. Click **"Calibrate"** in the sidebar
2. **Step 1 — Through (empty fixture):**
   - Remove ALL material from the fixture
   - Click **OK** — arm sweeps 0°→80°, records per-angle transmitted voltage
3. **Step 2 — Reflect (metal sheet):**
   - Place a metal sheet in the fixture
   - Click **OK** — arm sweeps again, records reflected voltage
4. Calibration stored in DB — loaded automatically on next launch

> **Note:** Set `cal_d_m` and `cal_d_sheet_m` in **Settings → Connection Setup** to your physical rig geometry (metres) for accurate phase correction. Default is 0.0 (phase correction disabled).

### Taking Measurements

1. **Start a Measurement Session:**
   - Click **"Start Measurement"** in the sidebar
   - **Sweep 1**: arm sweeps 0°→80° at 5° steps with horn at 0° (horizontal)
   - Servo automatically rotates horn to 90°
   - **Sweep 2**: arm sweeps 0°→80° with horn at 90° (vertical)
   - Servo returns horn to 0° and extraction fires automatically
   - All data saved to DB in real-time

2. **Monitor Progress:**
   - Right panel shows: Angle, Polarization, Sweep progress (e.g. `Sweep 1/2 — 8/17 pts`), Cal Data status, live S₂₁/S₁₁
   - Center graphs: S-parameter plots with pol-0 (blue) and pol-90 (orange) colour coding, live ADC oscilloscope

3. **Stop Measurement:**
   - Click **"Stop Measurement"** — motors return home, servo resets to 0°

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
   - Choose format:
     - **JSON**: measurements array + extraction result block (ε tensor, μ tensor, fit error)
     - **CSV**: one row per measurement point with all S-param fields; extraction result appended as footer
   - Data exported in chronological order (angle 0 = row 1)

### Understanding the Interface

**Left Sidebar:**
- Action buttons for calibration, measurement control, and data management
- Version information at the bottom

**Center Panel:**
- Real-time measurement graphs (Permittivity and Permeability)
- Control Parameters section (frequency, power, angle step, interval)
- Non-Idealities & Compensation section (calibration error, noise, temperature, humidity)

**Right Panel:**
- Measurement section: Angle, Polarization, Sweep progress, Cal Data status, Status
- Extracted Material: εr diagonal, μr diagonal, Fit Error
- Motor: status and position
- S-Parameters: live S₁₁, S₁₂, S₂₁, S₂₂
- Extraction Config: status, thickness, tensor type
- Parameters: frequency, power, angle step, interval

**Status Bar (Bottom):**
- Current system status
- Last update timestamp

### Database

- All measurements are stored in a local SQLite database (`spam.db`)
- The database is created automatically on first run
- No database server is required - everything runs locally
- Database file is stored in the project directory

## Hardware Integration

### System Architecture

**RF Chain (24 GHz):**
- **Gunn Diode Oscillator** → Amplifier → Splitter
  - TX path → TX Horn Antenna (radiates into free space through sample)
  - LO path → Mixer
- **RX Horn Antennas**: Transmitted (RXT) and Reflected (RXp)
- **SP2T RF Switch** (GPIO 22): selects TX or RX antenna path → Mixer input
- **Mixer**: downconverts to IF — produces IF-I and IF-Q
- **AD7193 (Pmod AD5)**: 24-bit SPI ADC reads IF-I and IF-Q at 4800 Hz

**Control System (Raspberry Pi):**
- **AD7193** via SPI (`/dev/spidev0.0`, 4 MHz)
- **Motor controller MCU** via I2C (address `0x55`) — 2-axis arm + material rotation
- **HPS-2518MG Servo** via GPIO 18 PWM (pigpio) — rotates horn antenna for polarization
- **SP2T RF Switch** via GPIO 22 (optional, enable in settings)

### Connection Setup

All hardware parameters are in **Settings → Connection Setup**:

| Setting | Default | Notes |
|---|---|---|
| SPI Bus / CS | 0 / 0 | AD7193 on SPI0.0 |
| SPI Speed | 4000000 | 4 MHz |
| ADC Gain | 1 | Increase for weak signals |
| Data Rate (Hz) | 4800 | Higher = faster, more noise |
| Samples/Point | 8 | Averaged per angle |
| Enable RF Switch | 0 | Set to 1 once switch is wired |
| Switch GPIO Pin | 22 | BCM numbering |
| Servo GPIO Pin | 18 | BCM numbering |
| MCU Address | 0x55 | I2C motor controller |
| ISR Pin | 17 | Motor position interrupt |
| Coupler Sep. d (m) | 0.0 | **Measure and set for calibration** |
| Ref Plane d_sheet (m) | 0.0 | **Measure and set for calibration** |

### Servo Calibration

To recalibrate the horn servo (e.g. after mechanical adjustment):

```bash
cd ~/SPAM
python3 scripts/pi/servo_test.py
```

Use `scan` to find physical stops, `min<us>` / `max<us>` to set endpoints, `sweep` to verify, `q` to print final values. Update `_PULSE_MIN_US` / `_PULSE_MAX_US` in `hardware/servo.py`.

### Remote Access (VNC)

Enable x11vnc on the Pi (X11 session required — run `sudo raspi-config nonint do_wayland W1` first if on Wayland):

```bash
x11vnc -display :0 -nopw -forever -bg -noxdamage
# Connects on port 5901
```

Connect from Windows using RealVNC Viewer: `<pi-ip>:5901`

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

**Automated math checks** (from repo root):

```bash
python tests/test_spam_calc.py
python tests/test_optimizer.py
```

**Manual / GUI:** calibration, measurement start/stop, export (JSON/CSV), live graphs.

## Notes

- This is a **local-only** application - no web server or network access required
- All data is stored locally in SQLite
- The application is designed to run standalone on a Raspberry Pi
- The web frontend (React) and FastAPI backend are no longer needed for local operation

## Integration testing and reports

- **Transmission-matrix / extraction (simulation):** [docs/integration/TRANSMISSION_MATRIX_INTEGRATION_TEST_RESULTS.md](docs/integration/TRANSMISSION_MATRIX_INTEGRATION_TEST_RESULTS.md)
- **ADC / RF switch software bring-up (hardware scope):** [docs/integration/INTEGRATION_TEST_RESULTS.md](docs/integration/INTEGRATION_TEST_RESULTS.md)
- **Benchmark summary + LaTeX report:** [docs/benchmarks/benchmark_results.md](docs/benchmarks/benchmark_results.md), [docs/benchmarks/benchmark_report.tex](docs/benchmarks/benchmark_report.tex)
- **Index of all docs:** [docs/README.md](docs/README.md)

## License

This project is provided as-is for educational and development purposes.
