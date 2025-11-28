import React, { useState, useEffect, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart } from 'recharts'

/**
 * Multi-Channel LiveView Component - FIXED
 * Supports 1-16 EEG channels via WebSocket
 * NOW INCLUDES: Signal Quality + Samples Per Second
 */

export default function LiveView({ wsData }) {
  const [channelsData, setChannelsData] = useState({})
  const [channelStats, setChannelStats] = useState({})
  const [timeWindow, setTimeWindow] = useState(500)
  const [isPaused, setIsPaused] = useState(false)
  const [selectedChannels, setSelectedChannels] = useState([0])
  const [numChannels, setNumChannels] = useState(1)
  const [debugInfo, setDebugInfo] = useState('')
  
  // NEW: Signal quality and performance metrics
  const [samplesPerSecond, setSamplesPerSecond] = useState(0)
  const [signalHealth, setSignalHealth] = useState('good')
  const [totalSamplesReceived, setTotalSamplesReceived] = useState(0)
  const [lastCountTime, setLastCountTime] = useState(Date.now())
  const [samplesThisSecond, setSamplesThisSecond] = useState(0)

  const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

  // Parse incoming WebSocket data
  useEffect(() => {
    if (!wsData || isPaused) return

    try {
      const rawData = typeof wsData.data === 'string'
        ? JSON.parse(wsData.data)
        : wsData.data

      console.log('LiveView received:', rawData) // DEBUG

      // Handle multi-channel format from WebSocket
      if (rawData.values && Array.isArray(rawData.values)) {
        const channels = rawData.channels || 1
        setNumChannels(channels)

        // Initialize channel data if needed
        if (Object.keys(channelsData).length === 0) {
          const newData = {}
          for (let ch = 0; ch < channels; ch++) {
            newData[ch] = []
          }
          setChannelsData(newData)
        }

        // NEW: Track samples per second
        const now = Date.now()
        const timeDiff = now - lastCountTime
        
        if (timeDiff >= 1000) {
          // Update every second
          setSamplesPerSecond(samplesThisSecond)
          setSamplesThisSecond(0)
          setLastCountTime(now)
        }

        // Add new samples
        setChannelsData(prev => {
          const updated = { ...prev }
          
          rawData.values.forEach((value, ch) => {
            if (!updated[ch]) updated[ch] = []
            
            updated[ch].push({
              time: updated[ch].length,
              value: parseFloat(value),
              timestamp: Date.now(),
              channel: ch
            })
            
            // Keep only last N samples
            updated[ch] = updated[ch].slice(-timeWindow)
          })
          
          return updated
        })

        // Update counters
        setTotalSamplesReceived(prev => prev + rawData.values.length)
        setSamplesThisSecond(prev => prev + rawData.values.length)
        setDebugInfo(`Channels: ${channels} | Buffer: ${Object.keys(channelsData).length}`)
      }
    } catch (e) {
      console.error('Parse error:', e, wsData)
      setDebugInfo(`Error: ${e.message}`)
    }
  }, [wsData, isPaused, timeWindow, lastCountTime])

  // Calculate stats for each channel
  useEffect(() => {
    const stats = {}
    let allHealthy = true

    Object.keys(channelsData).forEach(ch => {
      const data = channelsData[ch]
      if (data.length === 0) {
        stats[ch] = { empty: true }
        return
      }

      const values = data.map(d => d.value)
      const mean = values.reduce((a, b) => a + b, 0) / values.length
      const rms = Math.sqrt(values.reduce((a, b) => a + b * b, 0) / values.length)
      const power = rms * rms
      const min = Math.min(...values)
      const max = Math.max(...values)
      const range = Math.abs(max - min)

      // Zero crossing rate
      let zcr = 0
      for (let i = 1; i < values.length; i++) {
        if ((values[i - 1] >= 0 && values[i] < 0) || (values[i - 1] < 0 && values[i] >= 0)) {
          zcr++
        }
      }
      zcr = zcr / (values.length - 1)

      stats[ch] = { rms, power, mean, min, max, zcr, range }

      // NEW: Determine signal health per channel
      if (range > 100000) {
        allHealthy = false
      } else if (range < 50) {
        allHealthy = false
      }
    })

    setChannelStats(stats)

    // NEW: Set overall signal health
    if (allHealthy && Object.keys(stats).length > 0) {
      setSignalHealth('good')
    } else if (Object.keys(stats).length > 0) {
      setSignalHealth('warning')
    }
  }, [channelsData])

  // Combine data for chart display
  const displayData = useMemo(() => {
    if (Object.keys(channelsData).length === 0) return []

    const combined = []
    const maxLen = Math.max(...selectedChannels.map(ch => channelsData[ch]?.length || 0))

    for (let i = 0; i < maxLen; i++) {
      const point = { time: i }
      selectedChannels.forEach(ch => {
        if (channelsData[ch] && channelsData[ch][i]) {
          point[`ch${ch}`] = channelsData[ch][i].value
        }
      })
      combined.push(point)
    }

    return combined.slice(-timeWindow)
  }, [channelsData, selectedChannels, timeWindow])

  const signalHealthColor = {
    good: 'bg-green-100 text-green-800 border-green-300',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    error: 'bg-red-100 text-red-800 border-red-300'
  }

  const signalHealthLabel = {
    good: '✅ Good Signal',
    warning: '⚠️ Weak/Noisy Signal',
    error: '❌ No Signal'
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-gray-800">Multi-Channel EEG</h2>
            <p className="text-sm text-gray-600">{numChannels} channel(s) @ 250 Hz WebSocket</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className={`px-4 py-2 rounded-lg font-medium text-white transition ${
                isPaused ? 'bg-green-600 hover:bg-green-700' : 'bg-yellow-600 hover:bg-yellow-700'
              }`}
            >
              {isPaused ? '▶ Resume' : '⏸ Pause'}
            </button>
            <select
              value={timeWindow}
              onChange={(e) => setTimeWindow(Number(e.target.value))}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value={250}>1s</option>
              <option value={500}>2s</option>
              <option value={750}>3s</option>
              <option value={1000}>4s</option>
            </select>
          </div>
        </div>
      </div>

      {/* NEW: Signal Quality & Performance */}
      <div className="grid grid-cols-2 gap-4">
        {/* Signal Health */}
        <div className={`rounded-lg shadow p-4 border-2 ${signalHealthColor[signalHealth]}`}>
          <div className="text-lg font-semibold">{signalHealthLabel[signalHealth]}</div>
          <div className="text-sm mt-1">Overall signal quality</div>
        </div>

        {/* Performance Metrics */}
        <div className="bg-white rounded-lg shadow p-4 border-2 border-blue-300">
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <div className="text-gray-600">Samples/Sec</div>
              <div className="text-lg font-semibold text-blue-600">{samplesPerSecond}</div>
            </div>
            <div>
              <div className="text-gray-600">Total Samples</div>
              <div className="text-lg font-semibold text-purple-600">{totalSamplesReceived}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Channel Selection */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">Select Channels to Display</h3>
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: numChannels }).map((_, ch) => (
            <button
              key={ch}
              onClick={() => {
                setSelectedChannels(prev =>
                  prev.includes(ch)
                    ? prev.filter(c => c !== ch)
                    : [...prev, ch].sort()
                )
              }}
              className={`px-3 py-1 rounded text-sm font-medium transition ${
                selectedChannels.includes(ch)
                  ? `text-white`
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
              style={selectedChannels.includes(ch) ? { backgroundColor: COLORS[ch % COLORS.length] } : {}}
            >
              CH{ch}
            </button>
          ))}
        </div>
      </div>

      {/* Main Chart */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Waveform</h3>
        <div style={{ height: 400, width: '100%' }}>
          {displayData.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-500">Waiting for EEG signal... ({totalSamplesReceived} samples buffered)</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={displayData}
                margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip formatter={(value) => value?.toFixed(2)} />
                <Legend />
                {selectedChannels.map((ch, idx) => (
                  <Line
                    key={ch}
                    type="monotone"
                    dataKey={`ch${ch}`}
                    stroke={COLORS[ch % COLORS.length]}
                    dot={false}
                    isAnimationActive={false}
                    strokeWidth={2}
                    name={`Channel ${ch}`}
                  />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 gap-4">
        {selectedChannels.map(ch => {
          const stats = channelStats[ch] || {}
          return (
            <div key={ch} className="bg-white rounded-lg shadow p-4 border-l-4" style={{ borderColor: COLORS[ch % COLORS.length] }}>
              <h4 className="font-semibold text-gray-800 mb-2">Channel {ch}</h4>
              {stats.empty ? (
                <p className="text-gray-500">No data yet</p>
              ) : (
                <div className="grid grid-cols-5 gap-4 text-sm">
                  <div>
                    <div className="text-gray-600">RMS</div>
                    <div className="text-lg font-semibold text-blue-600">{stats.rms?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">Power</div>
                    <div className="text-lg font-semibold text-purple-600">{stats.power?.toFixed(0)}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">Mean</div>
                    <div className="text-lg font-semibold text-green-600">{stats.mean?.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">ZCR</div>
                    <div className="text-lg font-semibold text-orange-600">{stats.zcr?.toFixed(3)}</div>
                  </div>
                  <div>
                    <div className="text-gray-600">Range</div>
                    <div className="text-lg font-semibold text-red-600">{stats.range?.toFixed(0)}</div>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Debug Info */}
      <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-600 space-y-1">
        <div>Status: {isPaused ? '⏸️ PAUSED' : '🔴 LIVE'}</div>
        <div>Channels: {numChannels} | Selected: {selectedChannels.length}</div>
        <div>Samples/Sec: {samplesPerSecond} | Total: {totalSamplesReceived}</div>
        <div>{debugInfo}</div>
      </div>
    </div>
  )
}