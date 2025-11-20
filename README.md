# SPAM - Scanner for Polarized Anisotropic Materials

A full-stack web application for scanning and analyzing polarized anisotropic materials. This application provides real-time measurement visualization, data management, and export capabilities.

## Features

- **Real-time Measurements**: Live data visualization with WebSocket support
- **Data Management**: Store and retrieve measurement data
- **Calibration**: System calibration functionality
- **Data Export**: Export measurements in JSON or CSV format
- **Modern UI**: Responsive web interface matching the original design

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database operations
- **SQLite**: Database (can be upgraded to PostgreSQL)
- **WebSocket**: Real-time data streaming

### Frontend
- **React**: UI framework
- **Vite**: Build tool and dev server
- **Recharts**: Charting library for data visualization
- **Axios**: HTTP client

## Project Structure

```
SPAM/
├── backend/
│   ├── main.py           # FastAPI application
│   ├── database.py       # Database configuration
│   ├── models.py         # SQLAlchemy models
│   ├── schemas.py        # Pydantic schemas
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── services/     # API service
│   │   ├── hooks/        # Custom React hooks
│   │   └── App.jsx       # Main app component
│   ├── package.json      # Node dependencies
│   └── vite.config.js    # Vite configuration
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- npm or yarn

### Backend Setup

1. Navigate to the backend directory:
```bash
cd backend
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the backend server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`
API documentation will be available at `http://localhost:8000/docs`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. Start the backend server first (port 8000)
2. Start the frontend development server (port 3000)
3. Open your browser and navigate to `http://localhost:3000`
4. Use the control panel to:
   - Calibrate the system
   - Start/stop measurements
   - View results
   - Export data

## API Endpoints

- `GET /api/status` - Get system status
- `POST /api/calibrate` - Start calibration
- `POST /api/measurements/start` - Start measurement session
- `POST /api/measurements` - Create a measurement
- `GET /api/measurements` - Get all measurements
- `GET /api/measurements/{id}` - Get specific measurement
- `DELETE /api/measurements/{id}` - Delete measurement
- `GET /api/export` - Export data (format: json or csv)
- `WS /ws` - WebSocket connection for real-time updates

## Development

### Backend Development

The backend uses FastAPI with automatic API documentation. Visit `/docs` for interactive API documentation.

### Frontend Development

The frontend uses Vite for fast development with hot module replacement.

## Production Deployment

### Backend

For production, use a production ASGI server like Gunicorn with Uvicorn workers:

```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### Frontend

Build the frontend for production:

```bash
cd frontend
npm run build
```

The built files will be in the `dist` directory, which can be served by any static file server or integrated with the backend.

## License

This project is provided as-is for educational and development purposes.

