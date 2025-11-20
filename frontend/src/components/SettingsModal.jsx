import React, { useState, useEffect } from 'react'
import './SettingsModal.css'

const SettingsModal = ({ isOpen, onClose, onSave }) => {
  const [settings, setSettings] = useState({
    measurementInterval: 500,
    angleRange: { min: 0, max: 180 },
    autoSave: false,
    connectionPort: 'COM1',
    connectionBaudRate: 9600,
    apiEndpoint: 'http://localhost:8000',
    chartUpdateRate: 100
  })

  useEffect(() => {
    // Load settings from localStorage
    const saved = localStorage.getItem('spamSettings')
    if (saved) {
      try {
        setSettings(JSON.parse(saved))
      } catch (e) {
        console.error('Failed to load settings:', e)
      }
    }
  }, [])

  const handleChange = (key, value) => {
    setSettings(prev => ({
      ...prev,
      [key]: value
    }))
  }

  const handleNestedChange = (parentKey, childKey, value) => {
    setSettings(prev => ({
      ...prev,
      [parentKey]: {
        ...prev[parentKey],
        [childKey]: value
      }
    }))
  }

  const handleSave = () => {
    localStorage.setItem('spamSettings', JSON.stringify(settings))
    if (onSave) {
      onSave(settings)
    }
    onClose()
  }

  const handleReset = () => {
    const defaultSettings = {
      measurementInterval: 500,
      angleRange: { min: 0, max: 180 },
      autoSave: false,
      connectionPort: 'COM1',
      connectionBaudRate: 9600,
      apiEndpoint: 'http://localhost:8000',
      chartUpdateRate: 100
    }
    setSettings(defaultSettings)
    localStorage.setItem('spamSettings', JSON.stringify(defaultSettings))
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Settings</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          <div className="settings-section">
            <h3>Measurement Parameters</h3>
            <div className="setting-item">
              <label>Measurement Interval (ms)</label>
              <input
                type="number"
                value={settings.measurementInterval}
                onChange={(e) => handleChange('measurementInterval', parseInt(e.target.value) || 500)}
                min="100"
                max="5000"
                step="100"
              />
            </div>
            <div className="setting-item">
              <label>Angle Range</label>
              <div className="range-inputs">
                <input
                  type="number"
                  value={settings.angleRange.min}
                  onChange={(e) => handleNestedChange('angleRange', 'min', parseFloat(e.target.value) || 0)}
                  min="0"
                  max="180"
                  step="1"
                />
                <span>to</span>
                <input
                  type="number"
                  value={settings.angleRange.max}
                  onChange={(e) => handleNestedChange('angleRange', 'max', parseFloat(e.target.value) || 180)}
                  min="0"
                  max="180"
                  step="1"
                />
              </div>
            </div>
            <div className="setting-item">
              <label>
                <input
                  type="checkbox"
                  checked={settings.autoSave}
                  onChange={(e) => handleChange('autoSave', e.target.checked)}
                />
                Auto-save measurements
              </label>
            </div>
          </div>

          <div className="settings-section">
            <h3>Connection Setup</h3>
            <div className="setting-item">
              <label>Port</label>
              <select
                value={settings.connectionPort}
                onChange={(e) => handleChange('connectionPort', e.target.value)}
              >
                <option value="COM1">COM1</option>
                <option value="COM2">COM2</option>
                <option value="COM3">COM3</option>
                <option value="COM4">COM4</option>
                <option value="/dev/ttyUSB0">/dev/ttyUSB0</option>
                <option value="/dev/ttyUSB1">/dev/ttyUSB1</option>
              </select>
            </div>
            <div className="setting-item">
              <label>Baud Rate</label>
              <select
                value={settings.connectionBaudRate}
                onChange={(e) => handleChange('connectionBaudRate', parseInt(e.target.value))}
              >
                <option value="9600">9600</option>
                <option value="19200">19200</option>
                <option value="38400">38400</option>
                <option value="57600">57600</option>
                <option value="115200">115200</option>
              </select>
            </div>
          </div>

          <div className="settings-section">
            <h3>API Configuration</h3>
            <div className="setting-item">
              <label>API Endpoint</label>
              <input
                type="text"
                value={settings.apiEndpoint}
                onChange={(e) => handleChange('apiEndpoint', e.target.value)}
                placeholder="http://localhost:8000"
              />
            </div>
            <div className="setting-item">
              <label>Chart Update Rate (ms)</label>
              <input
                type="number"
                value={settings.chartUpdateRate}
                onChange={(e) => handleChange('chartUpdateRate', parseInt(e.target.value) || 100)}
                min="50"
                max="1000"
                step="50"
              />
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={handleReset}>Reset to Defaults</button>
          <div>
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button className="btn-primary" onClick={handleSave}>Save</button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SettingsModal

