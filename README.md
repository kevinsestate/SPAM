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

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Tkinter (usually included with Python)
  - On Raspberry Pi/Linux: `sudo apt-get install python3-tk`
  - On Windows/Mac: Usually pre-installed

### Quick Start (Raspberry Pi)

1. Clone or download this repository to your Raspberry Pi

2. Make the startup script executable:
```bash
chmod +x start_spam.sh
```

3. Run the application:
```bash
./start_spam.sh
```

The script will automatically:
- Create a virtual environment (if needed)
- Install all dependencies
- Launch the GUI application

### Manual Setup

1. Navigate to the project directory:
```bash
cd SPAM
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
```

3. Activate the virtual environment:
   - Linux/Raspberry Pi: `source venv/bin/activate`
   - Windows: `venv\Scripts\activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the application:
```bash
python3 GUI.py
```

## Usage

### Starting Measurements

1. Click **"Calibrate"** to calibrate the system before taking measurements
2. Click **"Start Measurement"** to begin a measurement session
   - The application will automatically take measurements at different angles
   - Data is saved to the database in real-time
   - Graphs update automatically as new data arrives
3. Click **"Start Measurement"** again to stop an ongoing measurement

### Viewing Results

- The center panel displays real-time graphs of permittivity and permeability vs angle
- The right panel shows the latest measurement values
- Graphs automatically update every second with the latest data

### Exporting Data

1. Click **"Export Data"** or use the File menu
2. Choose a file location and format (JSON or CSV)
3. All measurements will be exported to the selected file

### Database

- All measurements are stored in a local SQLite database (`spam.db`)
- The database is created automatically on first run
- No database server is required - everything runs locally

## Hardware Integration

The current implementation includes simulated measurement data. To integrate with actual hardware:

1. Locate the `_measurement_worker` method in `GUI.py`
2. Replace the simulated data generation with your hardware reading code
3. The database and GUI will automatically handle the real data

Example hardware integration:
```python
def _measurement_worker(self):
    """Background thread for continuous measurements."""
    while self.is_measuring:
        # Replace this with actual hardware reading:
        permittivity = read_permittivity_from_hardware()
        permeability = read_permeability_from_hardware()
        
        # Save to database
        self._create_measurement(self.current_angle, permittivity, permeability)
        
        # Increment angle and continue...
```

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
