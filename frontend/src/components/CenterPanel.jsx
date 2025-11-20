import React from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import './CenterPanel.css'

const CenterPanel = ({ measurements }) => {
  // Prepare data for charts
  const chartData = measurements.map(m => ({
    angle: m.angle,
    permittivity: m.permittivity,
    permeability: m.permeability
  }))

  // If no measurements, show placeholder data
  const displayData = chartData.length > 0 ? chartData : Array.from({ length: 100 }, (_, i) => ({
    angle: (i * 180) / 100,
    permittivity: 2.0 + 0.1 * Math.sin((i * 180) / 100 * Math.PI / 90),
    permeability: 1.5 + 0.08 * Math.cos((i * 180) / 100 * Math.PI / 90)
  }))

  return (
    <div className="center-panel">
      <div className="center-header">
        <div className="center-title">Real-Time Measurements</div>
      </div>
      
      <div className="charts-container">
        <div className="chart-card">
          <div className="chart-title">Permittivity (ε) vs Angle</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displayData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#BDC3C7" opacity={0.3} />
              <XAxis 
                dataKey="angle" 
                stroke="#2C3E50"
                label={{ value: 'Angle (degrees)', position: 'insideBottom', offset: -5 }}
              />
              <YAxis 
                stroke="#2C3E50"
                label={{ value: 'Permittivity (ε)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="permittivity" 
                stroke="#3498DB" 
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        <div className="chart-card">
          <div className="chart-title">Permeability (μ) vs Angle</div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displayData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#BDC3C7" opacity={0.3} />
              <XAxis 
                dataKey="angle" 
                stroke="#2C3E50"
                label={{ value: 'Angle (degrees)', position: 'insideBottom', offset: -5 }}
              />
              <YAxis 
                stroke="#2C3E50"
                label={{ value: 'Permeability (μ)', angle: -90, position: 'insideLeft' }}
              />
              <Tooltip />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="permeability" 
                stroke="#1ABC9C" 
                strokeWidth={2.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

export default CenterPanel

