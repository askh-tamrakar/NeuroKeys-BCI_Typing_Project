import React, { useState } from 'react'

export default function SettingsView() {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000')
  const [wsUrl, setWsUrl] = useState('ws://localhost:8000/ws')
  const [useMock, setUseMock] = useState(true)
  const [theme, setTheme] = useState('light')
  
  const handleSave = () => {
    // Save settings to localStorage
    localStorage.setItem('bci_settings', JSON.stringify({
      apiUrl,
      wsUrl,
      useMock,
      theme
    }))
    alert('Settings saved!')
  }
  
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Settings</h2>
        
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-4">API Configuration</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">API Base URL</label>
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="http://localhost:8000"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">WebSocket URL</label>
                <input
                  type="text"
                  value={wsUrl}
                  onChange={(e) => setWsUrl(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="ws://localhost:8765"
                />
              </div>
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={useMock}
                  onChange={(e) => setUseMock(e.target.checked)}
                  className="w-5 h-5 text-blue-600 rounded"
                />
                <label className="ml-2 text-sm text-gray-700">Use Mock Data (for testing without hardware)</label>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Appearance</h3>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Theme</label>
              <select
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              >
                <option value="light">Light</option>
                <option value="dark">Dark</option>
                <option value="auto">Auto</option>
              </select>
            </div>
          </div>
          
          <button
            onClick={handleSave}
            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 transition"
          >
            💾 Save Settings
          </button>
        </div>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">About</h3>
        <div className="text-gray-600 space-y-2">
          <p><strong>Version:</strong> 1.0.0</p>
          <p><strong>Mode:</strong> {useMock ? 'Mock/Demo' : 'Hardware Connected'}</p>
          <p><strong>WebSocket:</strong> {wsUrl}</p>
        </div>
      </div>
    </div>
  )
}
