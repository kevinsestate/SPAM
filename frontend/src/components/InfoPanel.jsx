import React from 'react'
import './InfoPanel.css'

const InfoPanel = ({ status, systemStatus }) => {
  const infoItems = [
    { label: 'Current Angle', value: `${status.angle.toFixed(1)}°`, icon: '🔄' },
    { label: 'Permittivity (ε)', value: status.permittivity.toFixed(2), icon: '⚡' },
    { label: 'Permeability (μ)', value: status.permeability.toFixed(2), icon: '🧲' },
    { label: 'Status', value: status.status, icon: '●' }
  ]

  return (
    <div className="info-panel">
      <div className="info-header">Measurement Data</div>
      
      <div className="info-content">
        {infoItems.map((item, index) => (
          <div key={index} className="info-card">
            <div className="info-card-border"></div>
            <div className="info-card-content">
              <div className="info-card-header">
                <span className="info-icon">{item.icon}</span>
                <span className="info-label">{item.label}</span>
              </div>
              <div className="info-value">{item.value}</div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="info-footer">
        <div className="system-card">
          <div className="system-card-border"></div>
          <div className="system-card-content">
            <div className="system-label">System Status</div>
            <div className="system-value">{systemStatus}</div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default InfoPanel

