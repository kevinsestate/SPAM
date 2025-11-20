import React, { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import CenterPanel from './components/CenterPanel'
import InfoPanel from './components/InfoPanel'
import StatusBar from './components/StatusBar'
import MenuBar from './components/MenuBar'
import SettingsModal from './components/SettingsModal'
import HelpModal from './components/HelpModal'
import { useWebSocket } from './hooks/useWebSocket'
import { api } from './services/api'
import './App.css'

function App() {
  const [status, setStatus] = useState({
    angle: 0.0,
    permittivity: 2.00,
    permeability: 1.50,
    status: 'Ready'
  })
  const [systemStatus, setSystemStatus] = useState('All Systems Operational')
  const [statusMessage, setStatusMessage] = useState('System Ready')
  const [statusType, setStatusType] = useState('success')
  const [measurements, setMeasurements] = useState([])
  const [isMeasuring, setIsMeasuring] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [helpView, setHelpView] = useState('about')
  const [settings, setSettings] = useState({
    measurementInterval: 500,
    angleRange: { min: 0, max: 180 },
    autoSave: false,
    connectionPort: 'COM1',
    connectionBaudRate: 9600,
    apiEndpoint: 'http://localhost:8000',
    chartUpdateRate: 100
  })
  const intervalRef = useRef(null)

  // Load settings from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('spamSettings')
    if (saved) {
      try {
        const loadedSettings = JSON.parse(saved)
        setSettings(loadedSettings)
      } catch (e) {
        console.error('Failed to load settings:', e)
      }
    }
  }, [])

  // WebSocket connection for real-time updates
  const ws = useWebSocket('ws://localhost:8000/ws')

  useEffect(() => {
    if (ws) {
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.type === 'measurement' && data.data) {
          setStatus({
            angle: data.data.angle,
            permittivity: data.data.permittivity,
            permeability: data.data.permeability,
            status: 'Measuring...'
          })
          // Add to measurements for graph
          setMeasurements(prev => [...prev, data.data])
        } else if (data.type === 'calibration') {
          setStatusMessage('Calibration completed successfully')
          setStatusType('success')
          setStatus(prev => ({ ...prev, status: 'Ready' }))
        }
      }
    }
  }, [ws])

  // Cleanup interval on unmount or when measurement stops
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  const handleCalibrate = async () => {
    try {
      setStatus(prev => ({ ...prev, status: 'Calibrating...' }))
      setStatusMessage('Calibration in progress...')
      setStatusType('warning')
      await api.calibrate()
    } catch (error) {
      console.error('Calibration error:', error)
      setStatusMessage('Calibration failed')
      setStatusType('error')
    }
  }

  const startMeasurementInterval = () => {
    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }
    
    // Simulate measurement data (in real app, this would come from hardware)
    intervalRef.current = setInterval(async () => {
      const minAngle = settings.angleRange.min || 0
      const maxAngle = settings.angleRange.max || 180
      const angle = minAngle + Math.random() * (maxAngle - minAngle)
      const permittivity = 2.0 + 0.1 * Math.sin(angle * Math.PI / 90) + (Math.random() - 0.5) * 0.05
      const permeability = 1.5 + 0.08 * Math.cos(angle * Math.PI / 90) + (Math.random() - 0.5) * 0.05
      
      try {
        await api.createMeasurement({
          angle,
          permittivity,
          permeability
        })
      } catch (error) {
        console.error('Measurement error:', error)
      }
    }, settings.measurementInterval || 500)
  }

  const handleStartMeasurement = async () => {
    try {
      setIsMeasuring(true)
      setStatus(prev => ({ ...prev, status: 'Measuring...' }))
      setStatusMessage('Measurement started')
      setStatusType('info')
      await api.startMeasurement()
      startMeasurementInterval()
    } catch (error) {
      console.error('Start measurement error:', error)
      setStatusMessage('Failed to start measurement')
      setStatusType('error')
      setIsMeasuring(false)
    }
  }

  const handleStopMeasurement = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsMeasuring(false)
    setStatus(prev => ({ ...prev, status: 'Ready' }))
    setStatusMessage('Measurement stopped')
    setStatusType('info')
  }

  const handleViewResults = async () => {
    try {
      const data = await api.getMeasurements()
      setMeasurements(data)
      setStatusMessage('Results displayed')
      setStatusType('success')
    } catch (error) {
      console.error('View results error:', error)
      setStatusMessage('Failed to load results')
      setStatusType('error')
    }
  }

  const handleExport = async () => {
    try {
      setStatusMessage('Exporting data...')
      setStatusType('warning')
      const response = await api.exportData('json')
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `spam-data-${new Date().toISOString()}.json`
      a.click()
      URL.revokeObjectURL(url)
      setStatusMessage('Data exported successfully')
      setStatusType('success')
    } catch (error) {
      console.error('Export error:', error)
      setStatusMessage('Export failed')
      setStatusType('error')
    }
  }

  const handleSettings = (view) => {
    setSettingsOpen(true)
  }

  const handleSettingsSave = (newSettings) => {
    setSettings(newSettings)
    // If measurement is running, restart interval with new settings
    if (isMeasuring) {
      startMeasurementInterval()
    }
    setStatusMessage('Settings saved successfully')
    setStatusType('success')
  }

  const handleHelp = (view) => {
    setHelpView(view || 'about')
    setHelpOpen(true)
  }

  return (
    <div className="app">
      <MenuBar 
        onExport={handleExport}
        onSettings={handleSettings}
        onHelp={handleHelp}
      />
      <div className="app-content">
        <Sidebar
          onCalibrate={handleCalibrate}
          onStartMeasurement={isMeasuring ? handleStopMeasurement : handleStartMeasurement}
          onViewResults={handleViewResults}
          onExport={handleExport}
          isMeasuring={isMeasuring}
        />
        <CenterPanel measurements={measurements} />
        <InfoPanel status={status} systemStatus={systemStatus} />
      </div>
      <StatusBar
        message={statusMessage}
        type={statusType}
      />
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSave={handleSettingsSave}
      />
      <HelpModal
        isOpen={helpOpen}
        onClose={() => setHelpOpen(false)}
        view={helpView}
      />
    </div>
  )
}

export default App

