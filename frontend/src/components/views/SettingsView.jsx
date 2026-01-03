import React, { useState } from 'react'

export default function SettingsView() {
  const [apiUrl, setApiUrl] = useState('http://localhost:8000')
  const [wsUrl, setWsUrl] = useState('ws://localhost:8765')
  const [useMock, setUseMock] = useState(true)
  const [theme, setTheme] = useState('rose')

  const themes = [
    { value: 'rose', label: 'Rose' },
    { value: 'violet', label: 'Violet' },
    { value: 'olive', label: 'Olive' },
    { value: 'ocean', label: 'Ocean' },
    { value: 'sunset', label: 'Sunset' },
    { value: 'forest', label: 'Forest' },
    { value: 'slate', label: 'Slate' },
    { value: 'mint', label: 'Mint' },
    { value: 'blush', label: 'Blush' },
    { value: 'vibrant', label: 'Vibrant' },
    { value: 'plum', label: 'Plum' },
    { value: 'yellow', label: 'Golden Ember' },
    { value: 'yellow-dark', label: 'Golden Eclipse' },
    { value: 'crimson', label: 'Crimson Blaze' },
    { value: 'inferno', label: 'Inferno Burst' },
    { value: 'rosewood', label: 'Rosewood Velvet' },
    { value: 'ember', label: 'Ember Noir' },
    { value: 'amethyst', label: 'Amethyst Dream' }
  ]

  const handleSave = () => {
    // Save settings to localStorage
    localStorage.setItem('bci_settings', JSON.stringify({
      apiUrl,
      wsUrl,
      useMock,
      theme
    }))

    // Apply theme
    const root = document.documentElement
    root.className = `root theme-${theme}`

    alert('Settings saved!')
  }

  const applyTheme = (themeValue) => {
    setTheme(themeValue)
    const root = document.documentElement
    root.className = `root theme-${themeValue}`
  }

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h2 className="text-2xl font-bold text-text mb-6 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          Settings
        </h2>

        <div className="space-y-8">
          <div>
            <h3 className="text-xl font-bold text-text mb-4">API Configuration</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-bold text-text mb-3">API Base URL</label>
                <input
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                  placeholder="http://localhost:8000"
                />
              </div>

              <div>
                <label className="block text-sm font-bold text-text mb-3">WebSocket URL</label>
                <input
                  type="text"
                  value={wsUrl}
                  onChange={(e) => setWsUrl(e.target.value)}
                  className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                  placeholder="ws://localhost:8765"
                />
              </div>

              <div className="flex items-center gap-3 p-4 bg-bg rounded-xl border border-border">
                <input
                  type="checkbox"
                  checked={useMock}
                  onChange={(e) => setUseMock(e.target.checked)}
                  className="w-6 h-6 text-primary rounded-lg"
                />
                <label className="text-sm font-medium text-text">Use Mock Data (for testing without hardware)</label>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-xl font-bold text-text mb-4">Appearance</h3>

            <div>
              <label className="block text-sm font-bold text-text mb-3">Theme</label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {themes.map(t => (
                  <button
                    key={t.value}
                    onClick={() => applyTheme(t.value)}
                    className={`px-4 py-3 rounded-xl font-bold transition-all ${theme === t.value
                      ? 'bg-primary text-primary-contrast shadow-glow'
                      : 'bg-bg border border-border text-text hover:border-primary/50'
                      }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <button
            onClick={handleSave}
            className="w-full bg-primary text-primary-contrast py-4 rounded-xl font-bold text-lg hover:opacity-90 transition-all shadow-glow hover:translate-y-[-2px] active:translate-y-[0px]"
          >
            💾 Save Settings
          </button>
        </div>
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">About</h3>
        <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-5 space-y-3 border border-border">
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Version:</span>
            <span className="font-bold text-text">1.0.0</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Mode:</span>
            <span className="font-bold text-text">{useMock ? 'Mock/Demo' : 'Hardware Connected'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">WebSocket:</span>
            <span className="font-bold text-text text-sm">{wsUrl}</span>
          </div>
        </div>
      </div>
    </div>
  )
}


// import React, { useState, useEffect } from 'react'

// export default function SettingsView({ sendMessage }) {
//   const [apiUrl, setApiUrl] = useState('http://localhost:8000')
//   const [wsUrl, setWsUrl] = useState('ws://localhost:8765')
//   const [useMock, setUseMock] = useState(false)
//   const [theme, setTheme] = useState('rose')
//   const [filterSettings, setFilterSettings] = useState({
//     emgHighPass: 70,
//     eogLowFreq: 0.5,
//     eogHighFreq: 50,
//     eegLowFreq: 0.1,
//     eegHighFreq: 40
//   })

//   const themes = [
//     { value: 'rose', label: 'Rose' },
//     { value: 'violet', label: 'Violet' },
//     { value: 'ocean', label: 'Ocean' },
//     { value: 'forest', label: 'Forest' },
//   ]

//   const handleSaveSettings = () => {
//     const settings = {
//       apiUrl,
//       wsUrl,
//       useMock,
//       theme,
//       filters: filterSettings
//     }
//     localStorage.setItem('bci_settings', JSON.stringify(settings))

//     if (sendMessage) {
//       sendMessage({
//         type: 'settings_updated',
//         settings: settings
//       })
//     }

//     const root = document.documentElement
//     root.className = `root theme-${theme}`
//     alert('Settings saved!')
//   }

//   const applyTheme = (themeValue) => {
//     setTheme(themeValue)
//     const root = document.documentElement
//     root.className = `root theme-${themeValue}`
//   }

//   const handleFilterChange = (key, value) => {
//     setFilterSettings(prev => ({
//       ...prev,
//       [key]: parseFloat(value)
//     }))
//   }

//   return (
//     <div className="settings-container">
//       <div className="card">
//         <h2>🔌 Server Configuration</h2>

//         <div className="form-group">
//           <label>API URL</label>
//           <input
//             type="text"
//             value={apiUrl}
//             onChange={(e) => setApiUrl(e.target.value)}
//             className="input"
//           />
//           <p className="help-text">Base URL for HTTP API calls</p>
//         </div>

//         <div className="form-group">
//           <label>WebSocket URL</label>
//           <input
//             type="text"
//             value={wsUrl}
//             onChange={(e) => setWsUrl(e.target.value)}
//             className="input"
//           />
//           <p className="help-text">WebSocket endpoint for live data streaming</p>
//         </div>

//         <div className="form-group">
//           <label>
//             <input
//               type="checkbox"
//               checked={useMock}
//               onChange={(e) => setUseMock(e.target.checked)}
//             />
//             Use Mock Data (for testing without hardware)
//           </label>
//         </div>
//       </div>

//       <div className="card">
//         <h2>🎨 Display Settings</h2>

//         <div className="form-group">
//           <label>Theme</label>
//           <div className="theme-grid">
//             {themes.map(t => (
//               <button
//                 key={t.value}
//                 onClick={() => applyTheme(t.value)}
//                 className={`theme-button ${theme === t.value ? 'active' : ''}`}
//               >
//                 {t.label}
//               </button>
//             ))}
//           </div>
//         </div>
//       </div>

//       <div className="card">
//         <h2>🔧 Filter Settings</h2>

//         <h4>EMG Filter</h4>
//         <div className="form-group">
//           <label>High-Pass Frequency (Hz)</label>
//           <input
//             type="number"
//             value={filterSettings.emgHighPass}
//             onChange={(e) => handleFilterChange('emgHighPass', e.target.value)}
//             className="input"
//           />
//         </div>

//         <h4>EOG Filter (Band-Pass)</h4>
//         <div className="form-row">
//           <div className="form-group">
//             <label>Low Frequency (Hz)</label>
//             <input
//               type="number"
//               value={filterSettings.eogLowFreq}
//               onChange={(e) => handleFilterChange('eogLowFreq', e.target.value)}
//               className="input"
//             />
//           </div>
//           <div className="form-group">
//             <label>High Frequency (Hz)</label>
//             <input
//               type="number"
//               value={filterSettings.eogHighFreq}
//               onChange={(e) => handleFilterChange('eogHighFreq', e.target.value)}
//               className="input"
//             />
//           </div>
//         </div>

//         <h4>EEG Filter (Band-Pass)</h4>
//         <div className="form-row">
//           <div className="form-group">
//             <label>Low Frequency (Hz)</label>
//             <input
//               type="number"
//               value={filterSettings.eegLowFreq}
//               onChange={(e) => handleFilterChange('eegLowFreq', e.target.value)}
//               className="input"
//             />
//           </div>
//           <div className="form-group">
//             <label>High Frequency (Hz)</label>
//             <input
//               type="number"
//               value={filterSettings.eegHighFreq}
//               onChange={(e) => handleFilterChange('eegHighFreq', e.target.value)}
//               className="input"
//             />
//           </div>
//         </div>
//       </div>

//       <button
//         onClick={handleSaveSettings}
//         className="btn btn-primary btn-lg btn-block"
//       >
//         ✅ Save All Settings
//       </button>
//     </div>
//   )
// }
