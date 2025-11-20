import React, { useState } from 'react'
import './HelpModal.css'

const HelpModal = ({ isOpen, onClose, view }) => {
  const [currentView, setCurrentView] = useState(view || 'about')

  if (!isOpen) return null

  const AboutContent = () => (
    <div className="help-content">
      <div className="help-header-section">
        <h2>SPAM</h2>
        <p className="subtitle">Scanner for Polarized Anisotropic Materials</p>
        <p className="version">Version 1.0.0</p>
      </div>
      
      <div className="help-section">
        <h3>About</h3>
        <p>
          SPAM is a full-stack web application designed for scanning and analyzing 
          polarized anisotropic materials. The application provides real-time measurement 
          visualization, data management, and export capabilities.
        </p>
      </div>

      <div className="help-section">
        <h3>Features</h3>
        <ul>
          <li>Real-time measurement visualization</li>
          <li>System calibration</li>
          <li>Data export (JSON/CSV)</li>
          <li>WebSocket-based live updates</li>
          <li>Configurable measurement parameters</li>
        </ul>
      </div>

      <div className="help-section">
        <h3>Technology Stack</h3>
        <ul>
          <li><strong>Backend:</strong> FastAPI, SQLAlchemy, SQLite</li>
          <li><strong>Frontend:</strong> React, Vite, Recharts</li>
          <li><strong>Real-time:</strong> WebSocket</li>
        </ul>
      </div>

      <div className="help-section">
        <h3>Contact & Support</h3>
        <p>
          For technical support or questions, please refer to the User Guide 
          or contact your system administrator.
        </p>
      </div>
    </div>
  )

  const UserGuideContent = () => (
    <div className="help-content">
      <div className="help-section">
        <h3>Getting Started</h3>
        <ol>
          <li>Ensure the backend server is running on port 8000</li>
          <li>Start the frontend application</li>
          <li>Calibrate the system before taking measurements</li>
          <li>Start a measurement session to begin data collection</li>
        </ol>
      </div>

      <div className="help-section">
        <h3>Controls</h3>
        <dl>
          <dt>⚙ Calibrate</dt>
          <dd>Calibrates the measurement system. Run this before starting measurements for accurate results.</dd>
          
          <dt>▶ Start Measurement</dt>
          <dd>Begins a new measurement session. Data will be collected and displayed in real-time on the graphs.</dd>
          
          <dt>📊 View Results</dt>
          <dd>Loads and displays all stored measurement data in the graphs.</dd>
          
          <dt>💾 Export Data</dt>
          <dd>Exports all measurement data in JSON format for external analysis.</dd>
        </dl>
      </div>

      <div className="help-section">
        <h3>Measurement Data</h3>
        <p>The application displays three key metrics:</p>
        <ul>
          <li><strong>Current Angle:</strong> The current measurement angle in degrees (0-180°)</li>
          <li><strong>Permittivity (ε):</strong> The electric permittivity of the material</li>
          <li><strong>Permeability (μ):</strong> The magnetic permeability of the material</li>
        </ul>
      </div>

      <div className="help-section">
        <h3>Graphs</h3>
        <p>
          The center panel displays two real-time graphs showing how permittivity and 
          permeability vary with angle. These graphs update automatically as measurements 
          are taken.
        </p>
      </div>

      <div className="help-section">
        <h3>Settings</h3>
        <p>
          Access settings from the menu bar to configure:
        </p>
        <ul>
          <li>Measurement interval</li>
          <li>Angle range</li>
          <li>Connection parameters</li>
          <li>API endpoint</li>
        </ul>
      </div>

      <div className="help-section">
        <h3>Troubleshooting</h3>
        <dl>
          <dt>No data appearing in graphs</dt>
          <dd>Ensure measurements have been started and the backend is running.</dd>
          
          <dt>Connection errors</dt>
          <dd>Check that the backend server is running on port 8000 and verify the API endpoint in settings.</dd>
          
          <dt>Export not working</dt>
          <dd>Ensure you have measurement data stored. Try viewing results first.</dd>
        </dl>
      </div>
    </div>
  )

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content help-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="help-tabs">
            <button
              className={currentView === 'about' ? 'tab-active' : 'tab'}
              onClick={() => setCurrentView('about')}
            >
              About SPAM
            </button>
            <button
              className={currentView === 'guide' ? 'tab-active' : 'tab'}
              onClick={() => setCurrentView('guide')}
            >
              User Guide
            </button>
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body help-body">
          {currentView === 'about' ? <AboutContent /> : <UserGuideContent />}
        </div>

        <div className="modal-footer">
          <button className="btn-primary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

export default HelpModal

