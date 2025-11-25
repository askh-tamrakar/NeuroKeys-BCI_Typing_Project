import React, { useState, useEffect } from 'react'
import SignalChart from '../charts/SignalChart'

export default function LiveView({ wsData }) {
  const [eegData, setEegData] = useState([])
  const [eogData, setEogData] = useState([])
  const [emgData, setEmgData] = useState([])
  const [timeWindow, setTimeWindow] = useState(250)
  const [isPaused, setIsPaused] = useState(false)
  
  useEffect(() => {
    if (!wsData || isPaused) return
    
    try {
      const parsed = JSON.parse(wsData.data)
      if (parsed.type !== 'signal') return
      
      const timestamp = parsed.timestamp
      
      setEegData(prev => [...prev, { time: timestamp, value: parsed.channels.EEG[0] }].slice(-500))
      setEogData(prev => [...prev, { time: timestamp, value: parsed.channels.EOG[0] }].slice(-500))
      setEmgData(prev => [...prev, { time: timestamp, value: parsed.channels.EMG[0] }].slice(-500))
    } catch (e) {
      console.error('Parse error:', e)
    }
  }, [wsData, isPaused])
  
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-800">Live Signal Monitoring</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className={`px-4 py-2 rounded-lg font-medium ${isPaused ? 'bg-green-600' : 'bg-yellow-600'} text-white`}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>
            <select
              value={timeWindow}
              onChange={(e) => setTimeWindow(Number(e.target.value))}
              className="px-4 py-2 border border-gray-300 rounded-lg"
            >
              <option value={125}>5s</option>
              <option value={250}>10s</option>
              <option value={750}>30s</option>
            </select>
          </div>
        </div>
      </div>
      
      <SignalChart title="EEG - Brain Waves" data={eegData} color="#3b82f6" timeWindow={timeWindow} />
      <SignalChart title="EOG - Eye Movement" data={eogData} color="#10b981" timeWindow={timeWindow} />
      <SignalChart title="EMG - Muscle Activity" data={emgData} color="#f59e0b" timeWindow={timeWindow} />
    </div>
  )
}
