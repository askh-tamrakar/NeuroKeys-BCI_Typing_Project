import React, { useState } from 'react'

export default function DevicesView() {
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
  
  const testStream = () => {
    setTestStatus('testing')
    setTimeout(() => {
      setTestStatus('success')
      setTimeout(() => setTestStatus(null), 3000)
    }, 2000)
  }
  
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-6">Device Configuration</h2>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">Sensor Selection</label>
            <div className="flex gap-4">
              {['EEG', 'EOG', 'EMG'].map(sensor => (
                <label key={sensor} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedSensors.includes(sensor)}
                    onChange={() => toggleSensor(sensor)}
                    className="w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                  />
                  <span className="font-medium text-gray-700">{sensor}</span>
                </label>
              ))}
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Sampling Rate (Hz)</label>
            <select 
              value={samplingRate}
              onChange={(e) => setSamplingRate(Number(e.target.value))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value={125}>125 Hz</option>
              <option value={250}>250 Hz</option>
              <option value={500}>500 Hz</option>
              <option value={1000}>1000 Hz</option>
            </select>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">High-pass Filter (Hz)</label>
              <input
                type="number"
                value={filterLow}
                onChange={(e) => setFilterLow(Number(e.target.value))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                min="0.1"
                step="0.1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Low-pass Filter (Hz)</label>
              <input
                type="number"
                value={filterHigh}
                onChange={(e) => setFilterHigh(Number(e.target.value))}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                min="1"
                step="1"
              />
            </div>
          </div>
          
          <button 
            onClick={testStream}
            disabled={testStatus === 'testing'}
            className={`w-full py-3 rounded-lg font-semibold transition ${
              testStatus === 'testing' 
                ? 'bg-yellow-500 text-white cursor-wait'
                : testStatus === 'success'
                ? 'bg-green-600 text-white'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {testStatus === 'testing' && '🧪 Testing Stream...'}
            {testStatus === 'success' && '✅ Test Successful!'}
            {!testStatus && '🧪 Test Stream'}
          </button>
        </div>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Current Configuration</h3>
        <div className="bg-gray-50 rounded-lg p-4 space-y-2">
          <div className="flex justify-between">
            <span className="text-gray-600">Active Sensors:</span>
            <span className="font-medium">{selectedSensors.join(', ') || 'None'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Sampling Rate:</span>
            <span className="font-medium">{samplingRate} Hz</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Filter Range:</span>
            <span className="font-medium">{filterLow} - {filterHigh} Hz</span>
          </div>
        </div>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Saved Profiles</h3>
        <p className="text-gray-600">No saved device profiles. Configure and save a profile above.</p>
      </div>
    </div>
  )
}
