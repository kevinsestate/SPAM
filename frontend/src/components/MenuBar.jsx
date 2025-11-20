import React, { useState, useRef, useEffect } from 'react'
import './MenuBar.css'

const MenuBar = ({ onExport, onSettings, onHelp }) => {
  const [activeMenu, setActiveMenu] = useState(null)
  const menuRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setActiveMenu(null)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleMenuClick = (menuName) => {
    setActiveMenu(activeMenu === menuName ? null : menuName)
  }

  const handleMenuItemClick = (action) => {
    if (action === 'export') {
      onExport()
    } else if (action === 'adjust-params' || action === 'connection') {
      onSettings('adjust-params')
    } else if (action === 'about') {
      onHelp('about')
    } else if (action === 'guide') {
      onHelp('guide')
    }
    setActiveMenu(null)
  }

  return (
    <div className="menu-bar" ref={menuRef}>
      <div className="menu-section">
        <div className="menu-item-container">
          <span className="menu-item" onClick={() => handleMenuClick('file')}>
            File
          </span>
          {activeMenu === 'file' && (
            <div className="menu-dropdown">
              <div className="menu-dropdown-item" onClick={() => handleMenuItemClick('export')}>
                Export Data
              </div>
            </div>
          )}
        </div>

        <div className="menu-item-container">
          <span className="menu-item" onClick={() => handleMenuClick('settings')}>
            Settings
          </span>
          {activeMenu === 'settings' && (
            <div className="menu-dropdown">
              <div className="menu-dropdown-item" onClick={() => handleMenuItemClick('adjust-params')}>
                Adjust Parameters
              </div>
              <div className="menu-dropdown-item" onClick={() => handleMenuItemClick('connection')}>
                Connection Setup
              </div>
            </div>
          )}
        </div>

        <div className="menu-item-container">
          <span className="menu-item" onClick={() => handleMenuClick('help')}>
            Help
          </span>
          {activeMenu === 'help' && (
            <div className="menu-dropdown">
              <div className="menu-dropdown-item" onClick={() => handleMenuItemClick('about')}>
                About SPAM
              </div>
              <div className="menu-dropdown-item" onClick={() => handleMenuItemClick('guide')}>
                User Guide
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default MenuBar

