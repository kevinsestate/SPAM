# SPAM Setup Guide - Fresh Windows Installation

Since you've reset your PC and only have Python and Git installed, follow these steps to set up the SPAM project.

## Step 1: Install Node.js (Required for Frontend)

1. Download Node.js from: https://nodejs.org/
   - Download the LTS (Long Term Support) version
   - Choose the Windows Installer (.msi) for your system (64-bit recommended)

2. Run the installer:
   - Accept the license agreement
   - Use default installation settings
   - Make sure "Add to PATH" is checked (should be by default)
   - Complete the installation

3. Verify installation:
   - Open a new PowerShell/Command Prompt window
   - Run: `node --version` (should show version number)
   - Run: `npm --version` (should show version number)

## Step 2: Set Up Python Backend

1. Open PowerShell in the project directory

2. Navigate to the backend folder:
   ```powershell
   cd backend
   ```

3. Create a virtual environment:
   ```powershell
   python -m venv venv
   ```

4. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   (If you get an execution policy error, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)

5. Install backend dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## Step 3: Set Up Frontend

1. Open a new PowerShell window in the project directory

2. Navigate to the frontend folder:
   ```powershell
   cd frontend
   ```

3. Install frontend dependencies:
   ```powershell
   npm install
   ```

## Step 4: Set Up Standalone GUI (Alternative)

If you want to use the standalone GUI application instead of the web interface:

1. Open PowerShell in the project root directory

2. Create a virtual environment:
   ```powershell
   python -m venv venv
   ```

3. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

4. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

## Running the Application

### Option 1: Web Application (Backend + Frontend)

**Terminal 1 - Backend:**
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python main.py
```
Backend will run on: http://localhost:8000

**Terminal 2 - Frontend:**
```powershell
cd frontend
npm run dev
```
Frontend will run on: http://localhost:5173

### Option 2: Standalone GUI

```powershell
python GUI.py
```
Or use the batch file:
```powershell
.\start_spam.bat
```

## Quick Start Scripts

After setup, you can use:
- `start_backend.bat` - Starts the FastAPI backend
- `start_frontend.bat` - Starts the React frontend
- `start_spam.bat` - Starts the standalone GUI application

## Troubleshooting

### PowerShell Execution Policy Error
If you get an error about execution policy when activating venv:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Node.js Not Found
- Make sure Node.js is installed and added to PATH
- Restart your terminal after installing Node.js
- Verify with: `node --version`

### Python Virtual Environment Issues
- Make sure you're using Python 3.8 or higher
- Check Python version: `python --version`
- If `python` doesn't work, try `python3` or `py`

### Port Already in Use
- Backend uses port 8000
- Frontend uses port 5173
- If ports are in use, close other applications or change ports in the configuration files
