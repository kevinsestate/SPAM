import React from 'react'
import './StatusBar.css'

const StatusBar = ({ message, type }) => {
  const getStatusColor = () => {
    switch (type) {
      case 'success': return '#27AE60'
      case 'warning': return '#F39C12'
      case 'error': return '#E74C3C'
      default: return '#3498DB'
    }
  }

  return (
    <div className="status-bar">
      <div className="status-left">
        <span className="status-indicator" style={{ color: getStatusColor() }}>●</span>
        <span className="status-text">{message}</span>
      </div>
      <div className="status-right">
        <span className="status-time">
          Last Update: {new Date().toLocaleString()}
        </span>
      </div>
    </div>
  )
}

export default StatusBar

