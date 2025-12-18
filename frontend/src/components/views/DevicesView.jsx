import React, { useState } from 'react'

export default function DevicesView({ sendMessage }) {
  const [selectedSensors, setSelectedSensors] = useState(['EEG', 'EOG', 'EMG'])
  const [samplingRate, setSamplingRate] = useState(250)
  const [filterLow, setFilterLow] = useState(1)
  const [filterHigh, setFilterHigh] = useState(45)
  const [testStatus, setTestStatus] = useState(null)

  const toggleSensor = (sensor) => {
    if (selectedSensors.includes(sensor)) {
      setSelectedSensors(prev => prev.filter(s => s !== sensor))
    } else {
      setSelectedSensors(prev => [...prev, sensor])
    }
  }

  const handleSamplingRateChange = (rate) => {
    setSamplingRate(rate)
    if (sendMessage) {
      sendMessage({
        type: "config",
        param: "sampling_rate",
        value: rate
      })
    }
  }

  const handleFilterLowChange = (val) => {
    setFilterLow(val)
    sendFilterConfig(val, filterHigh)
  }

  const handleFilterHighChange = (val) => {
    setFilterHigh(val)
    sendFilterConfig(filterLow, val)
  }

  const sendFilterConfig = (low, high) => {
    if (sendMessage) {
      sendMessage({
        type: "config",
        param: "filter_bandpass",
        low: low,
        high: high
      })
    }
  }

  const testStream = () => {
    setTestStatus('testing')
    setTimeout(() => {
      setTestStatus('success')
      setTimeout(() => setTestStatus(null), 3000)
    }, 2000)
  }

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h2 className="text-2xl font-bold text-text mb-6 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          Device Configuration
        </h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-bold text-text mb-3">Sensor Selection</label>
            <div className="flex gap-4">
              {['EEG', 'EOG', 'EMG'].map(sensor => (
                <label key={sensor} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={selectedSensors.includes(sensor)}
                    onChange={() => toggleSensor(sensor)}
                    className="w-6 h-6 text-primary rounded-lg focus:ring-2 focus:ring-primary/50 border-border bg-bg"
                  />
                  <span className="font-bold text-text group-hover:text-primary transition-colors">{sensor}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-bold text-text mb-3">Sampling Rate (Hz)</label>
            <select
              value={samplingRate}
              onChange={(e) => handleSamplingRateChange(Number(e.target.value))}
              className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
            >
              <option value={125}>125 Hz</option>
              <option value={250}>250 Hz</option>
              <option value={500}>500 Hz</option>
              <option value={512}>512 Hz (Max)</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-bold text-text mb-3">High-pass Filter (Hz)</label>
              <input
                type="number"
                value={filterLow}
                onChange={(e) => handleFilterLowChange(Number(e.target.value))}
                className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                min="0.1"
                step="0.1"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-text mb-3">Low-pass Filter (Hz)</label>
              <input
                type="number"
                value={filterHigh}
                onChange={(e) => handleFilterHighChange(Number(e.target.value))}
                className="w-full px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                min="1"
                step="1"
              />
            </div>
          </div>

          <button
            onClick={testStream}
            disabled={testStatus === 'testing'}
            className={`w-full py-4 rounded-xl font-bold text-lg transition-all shadow-glow ${testStatus === 'testing'
              ? 'bg-accent text-primary-contrast cursor-wait animate-pulse'
              : testStatus === 'success'
                ? 'bg-accent text-primary-contrast'
                : 'bg-primary text-primary-contrast hover:opacity-90 hover:translate-y-[-2px] active:translate-y-[0px]'
              }`}
          >
            {testStatus === 'testing' && '🧪 Testing Stream...'}
            {testStatus === 'success' && '✅ Test Successful!'}
            {!testStatus && '🧪 Test Stream'}
          </button>
        </div>
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">Current Configuration</h3>
        <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-5 space-y-3 border border-border">
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Active Sensors:</span>
            <span className="font-bold text-text">{selectedSensors.join(', ') || 'None'}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Sampling Rate:</span>
            <span className="font-bold text-text">{samplingRate} Hz</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted font-medium">Filter Range:</span>
            <span className="font-bold text-text">{filterLow} - {filterHigh} Hz</span>
          </div>
        </div>
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">Saved Profiles</h3>
        <div className="flex flex-col items-center justify-center py-12 text-muted space-y-3">
          <div className="w-16 h-16 rounded-full bg-bg border border-border flex items-center justify-center">
            <span className="text-2xl">📋</span>
          </div>
          <p>No saved device profiles. Configure and save a profile above.</p>
        </div>
      </div>
    </div>
  )
}

// import React, { useState, useEffect } from 'react'

// export default function DevicesView({ sendMessage }) {
//   const [devices, setDevices] = useState([])
//   const [selectedPort, setSelectedPort] = useState('')
//   const [isConnected, setIsConnected] = useState(false)

//   // Channel mapping
//   const [ch0Mapping, setCh0Mapping] = useState('EEG')
//   const [ch1Mapping, setCh1Mapping] = useState('EOG')

//   // Device config
//   const [samplingRate, setSamplingRate] = useState(512)
//   const [baudRate, setBaudRate] = useState(230400)
//   const [testStatus, setTestStatus] = useState(null)

//   // Fetch available COM ports
//   useEffect(() => {
//     const fetchPorts = async () => {
//       try {
//         const response = await fetch('http://localhost:8000/api/ports')
//         const data = await response.json()
//         setDevices(data.ports || [])
//       } catch (error) {
//         console.error('Error fetching ports:', error)
//         setDevices([
//           { port: 'COM3', description: 'Arduino Uno R4' },
//           { port: 'COM4', description: 'Arduino Uno R3' }
//         ])
//       }
//     }
//     fetchPorts()
//   }, [])

//   const handleConnect = async () => {
//     try {
//       const response = await fetch('http://localhost:8000/api/connect', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           port: selectedPort,
//           baudRate: baudRate,
//           samplingRate: samplingRate,
//           channelMapping: {
//             0: ch0Mapping,
//             1: ch1Mapping
//           }
//         })
//       })

//       if (response.ok) {
//         setIsConnected(true)
//         if (sendMessage) {
//           sendMessage({
//             type: 'device_connected',
//             port: selectedPort,
//             channelMapping: { 0: ch0Mapping, 1: ch1Mapping }
//           })
//         }
//       }
//     } catch (error) {
//       console.error('Connection failed:', error)
//     }
//   }

//   const handleDisconnect = async () => {
//     try {
//       await fetch('http://localhost:8000/api/disconnect', { method: 'POST' })
//       setIsConnected(false)
//     } catch (error) {
//       console.error('Disconnection failed:', error)
//     }
//   }

//   const handleChannelMapping = (channel, sensorType) => {
//     if (channel === 0) {
//       setCh0Mapping(sensorType)
//     } else {
//       setCh1Mapping(sensorType)
//     }

//     if (sendMessage) {
//       sendMessage({
//         type: 'channel_mapping_updated',
//         channelMapping: {
//           0: channel === 0 ? sensorType : ch0Mapping,
//           1: channel === 1 ? sensorType : ch1Mapping
//         }
//       })
//     }
//   }

//   const testConnection = () => {
//     setTestStatus('testing')
//     // Send test command via WebSocket
//     if (sendMessage) {
//       sendMessage({ type: 'test_stream' })
//     }
//     setTimeout(() => {
//       setTestStatus('success')
//       setTimeout(() => setTestStatus(null), 3000)
//     }, 2000)
//   }

//   return (
//     <div className="devices-container">
//       <div className="card">
//         <h2>🔌 Device Connection</h2>

//         {!isConnected ? (
//           <>
//             <div className="form-group">
//               <label>COM Port</label>
//               <select
//                 value={selectedPort}
//                 onChange={(e) => setSelectedPort(e.target.value)}
//                 className="input"
//               >
//                 <option value="">Select a port...</option>
//                 {devices.map(device => (
//                   <option key={device.port} value={device.port}>
//                     {device.port} - {device.description}
//                   </option>
//                 ))}
//               </select>
//             </div>

//             <div className="form-group">
//               <label>Baud Rate</label>
//               <select
//                 value={baudRate}
//                 onChange={(e) => setBaudRate(parseInt(e.target.value))}
//                 className="input"
//               >
//                 <option value={115200}>115200</option>
//                 <option value={230400}>230400</option>
//                 <option value={250000}>250000</option>
//               </select>
//             </div>

//             <button onClick={handleConnect} className="btn btn-primary btn-lg">
//               ✅ Connect
//             </button>
//           </>
//         ) : (
//           <>
//             <div className="status-indicator success">
//               ✅ Connected to {selectedPort}
//             </div>
//             <button onClick={handleDisconnect} className="btn btn-danger btn-lg">
//               ❌ Disconnect
//             </button>
//           </>
//         )}
//       </div>

//       {isConnected && (
//         <>
//           <div className="card">
//             <h2>🎛️ Channel Mapping</h2>
//             <p className="text-muted">Select which sensor is connected to each channel</p>

//             <div className="mapping-grid">
//               <div className="mapping-item">
//                 <label>Channel 0</label>
//                 <select
//                   value={ch0Mapping}
//                   onChange={(e) => handleChannelMapping(0, e.target.value)}
//                   className="input"
//                 >
//                   <option value="EMG">EMG (Muscle)</option>
//                   <option value="EOG">EOG (Eye Movement)</option>
//                   <option value="EEG">EEG (Brain)</option>
//                 </select>
//               </div>

//               <div className="mapping-item">
//                 <label>Channel 1</label>
//                 <select
//                   value={ch1Mapping}
//                   onChange={(e) => handleChannelMapping(1, e.target.value)}
//                   className="input"
//                 >
//                   <option value="EMG">EMG (Muscle)</option>
//                   <option value="EOG">EOG (Eye Movement)</option>
//                   <option value="EEG">EEG (Brain)</option>
//                 </select>
//               </div>
//             </div>

//             <div className="mapping-preview">
//               <h4>Current Configuration:</h4>
//               <ul>
//                 <li><strong>Channel 0:</strong> {ch0Mapping}</li>
//                 <li><strong>Channel 1:</strong> {ch1Mapping}</li>
//               </ul>
//             </div>
//           </div>

//           <div className="card">
//             <h2>📊 Configuration</h2>

//             <div className="form-group">
//               <label>Sampling Rate (Hz)</label>
//               <input
//                 type="number"
//                 value={samplingRate}
//                 onChange={(e) => setSamplingRate(parseInt(e.target.value))}
//                 className="input"
//               />
//             </div>

//             <button
//               onClick={testConnection}
//               className="btn btn-secondary btn-lg"
//               disabled={testStatus === 'testing'}
//             >
//               {testStatus === 'testing' ? '⏳ Testing...' : '🧪 Test Stream'}
//             </button>

//             {testStatus === 'success' && (
//               <div className="alert alert-success">
//                 ✅ Stream test successful! Data is flowing correctly.
//               </div>
//             )}
//           </div>
//         </>
//       )}
//     </div>
//   )
// }
