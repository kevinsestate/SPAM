import React from 'react'
import './Sidebar.css'

const Sidebar = ({ onCalibrate, onStartMeasurement, onViewResults, onExport, isMeasuring }) => {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-title">SPAM</div>
        <div className="sidebar-subtitle">Control Panel</div>
      </div>
      
      <div className="sidebar-content">
        <div className="controls-label">CONTROLS</div>
        
        <button className="sidebar-button" onClick={onCalibrate}>
          ⚙ Calibrate
        </button>
        
        <button 
          className="sidebar-button" 
          onClick={onStartMeasurement}
        >
          {isMeasuring ? '⏸ Stop Measurement' : '▶ Start Measurement'}
        </button>
        
        <button className="sidebar-button" onClick={onViewResults}>
          📊 View Results
        </button>
        
        <button className="sidebar-button" onClick={onExport}>
          💾 Export Data
        </button>
      </div>
      
      <div className="sidebar-footer">
        <div className="version">Version 1.0.0</div>
      </div>
    </div>
  )
}

export default Sidebar

