import React, { useState, useEffect, useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ComposedChart } from 'recharts'

/**
 * Multi-Channel LiveView Component - FIXED
 * Supports 1-16 EEG channels via WebSocket
 * NOW INCLUDES: Signal Quality + Samples Per Second
 */

/**
 * LiveView (Python-WS streaming) with multi-channel EEG support.
 * - EEG buffer is stored per-channel: eegByChannel = { 0: [{time,value}, ...], 1: [...] }
 * - UI: Single-channel (choose index) or Overlay all channels
 */

export default function LiveView({ wsData }) {
  const [channelsData, setChannelsData] = useState({})
  const [channelStats, setChannelStats] = useState({})
  const [timeWindow, setTimeWindow] = useState(500)
  const [isPaused, setIsPaused] = useState(false)
  const [displayMode, setDisplayMode] = useState('single') // 'single' | 'overlay'
  const [selectedChannel, setSelectedChannel] = useState(0)
  const [showEog, setShowEog] = useState(true)
  const [showEmg, setShowEmg] = useState(true)

  // limits
  const MAX_POINTS_PER_MESSAGE = 120
  const MAX_POINTS_PER_CHANNEL = 50000

  // helper to push per-channel and trim by time window
  const pushChannelPoints = (chIdx, pts) => {
    setEegByChannel(prev => {
      const current = prev[chIdx] ?? []
      const merged = [...current, ...pts]
      const lastTs = merged.length ? merged[merged.length - 1].time : Date.now()
      const cutoff = lastTs - timeWindowMs
      const trimmed = merged.filter(p => p.time >= cutoff)
      if (trimmed.length > MAX_POINTS_PER_CHANNEL) return { ...prev, [chIdx]: trimmed.slice(-MAX_POINTS_PER_CHANNEL) }
      return { ...prev, [chIdx]: trimmed }
    })
  }

  const pushSingleByTimeWindow = (setter, pts) => {
    setter(prev => {
      if (!pts || pts.length === 0) return prev
      const merged = [...prev, ...pts]
      const lastTs = merged.length ? merged[merged.length - 1].time : Date.now()
      const cutoff = lastTs - timeWindowMs
      const sliced = merged.filter(p => p.time >= cutoff)
      if (sliced.length > MAX_POINTS_PER_CHANNEL) return sliced.slice(-MAX_POINTS_PER_CHANNEL)
      return sliced
    })
  }

  // compute known EEG channel count from buffer keys
  const knownEegChannels = useMemo(() => {
    return Object.keys(eegByChannel).map(k => Number(k)).sort((a, b) => a - b)
  }, [eegByChannel])

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
      // wsData might be string or object
      if (typeof wsData === 'object' && wsData !== null) {
        payload = wsData.data ? JSON.parse(wsData.data) : wsData;
      } else if (typeof wsData === 'string') {
        payload = JSON.parse(wsData);
      }
    } catch (err) {
      console.error('LiveView: failed to parse wsData', err, wsData)
      return
    }

    if (!payload || !payload.window || !Array.isArray(payload.window)) return
    const source = (payload.source || '').toUpperCase()
    const fs = Number(payload.fs) || 250
    const endTs = Number(payload.timestamp) || Date.now()
    const channels = payload.window
    const nChannels = channels.length
    const samples = Array.isArray(channels[0]) ? channels[0] : []
    const n = samples.length
    if (n === 0) return

    // limit points per message
    const stride = Math.max(1, Math.floor(n / MAX_POINTS_PER_MESSAGE))

    // Build per-sample timestamps (common for all channels)
    // sample i offset from end: (i - (n - 1))*(1000/fs)
    const timestamps = []
    for (let i = 0; i < n; i += stride) {
      const offsetMs = Math.round((i - (n - 1)) * (1000 / fs))
      timestamps.push(endTs + offsetMs)
    }

    // For EEG (multi-channel), create points per channel and push to per-channel buffers
    if (source === 'EEG' || nChannels >= 8) {
      // ensure we handle all channels even if some are missing
      for (let ch = 0; ch < nChannels; ch++) {
        const chSamples = Array.isArray(channels[ch]) ? channels[ch] : []
        if (!chSamples || chSamples.length === 0) continue
        const pts = []
        for (let i = 0, idx = 0; i < chSamples.length; i += stride, idx++) {
          const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)))
          const v = Number(chSamples[i])
          pts.push({ time: t, value: Number.isFinite(v) ? v : 0 })
        }
        pushChannelPoints(ch, pts)
      }
    } else {
      // non-EEG: pick first channel only
      const samples0 = samples
      const pts = []
      for (let i = 0, idx = 0; i < samples0.length; i += stride, idx++) {
        const t = timestamps[idx] ?? (endTs - Math.round((n - 1 - i) * (1000 / fs)))
        const v = Number(samples0[i])
        pts.push({ time: t, value: Number.isFinite(v) ? v : 0 })
      }

      if (source === 'EOG') pushSingleByTimeWindow(setEogData, pts)
      else if (source === 'EMG') pushSingleByTimeWindow(setEmgData, pts)
      else {
        // heuristics: if 2 channels try EOG, else EMG fallback
        if (nChannels === 2) pushSingleByTimeWindow(setEogData, pts)
        else pushSingleByTimeWindow(setEmgData, pts)
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
    <div className="flex flex-col h-full bg-bg gap-6 p-4 md:p-6 overflow-y-auto">
      {/* Top Banner / Controls */}
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-5 sticky top-0 z-20 backdrop-blur-md bg-opacity-95">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">

          <div className="flex items-center gap-4">
            <div className="bg-primary/10 p-3 rounded-xl border border-primary/20">
              <div className={`status-dot w-4 h-4 ${isPaused ? 'bg-accent' : 'bg-primary'} animate-pulse shadow-[0_0_10px_currentColor]`}></div>
            </div>
            <div>
              <h2 className="text-xl font-bold text-text tracking-tight">Live Monitoring</h2>
              <p className="text-xs text-muted font-mono uppercase tracking-widest">{isPaused ? 'PAUSED' : 'STREAMING ACTIVE'}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Control Group */}
            <div className="flex items-center gap-2 bg-bg/50 p-1.5 rounded-xl border border-border">
              <button
                onClick={() => setIsPaused(!isPaused)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-bold text-sm transition-all duration-200 ${isPaused
                  ? 'bg-accent/20 text-accent hover:bg-accent/30 border border-accent/20'
                  : 'bg-primary/20 text-primary hover:bg-primary/30 border border-primary/20 shadow-glow'
                  }`}
              >
                {isPaused ? '▶ Resume Stream' : '⏸ Pause Stream'}
              </button>
            </div>

            <div className="h-8 w-[1px] bg-border mx-1"></div>

            {/* Time Window */}
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-bold text-muted uppercase tracking-wider ml-1">Time Window</label>
              <select
                value={timeWindowMs}
                onChange={(e) => setTimeWindowMs(Number(e.target.value))}
                className="px-3 py-2 bg-bg border border-border text-text text-sm rounded-lg focus:ring-2 focus:ring-primary/50 outline-none hover:border-primary/50 transition-colors"
              >
                <option value={5000}>5 Seconds</option>
                <option value={10000}>10 Seconds</option>
                <option value={30000}>30 Seconds</option>
                <option value={60000}>60 Seconds</option>
              </select>
            </div>
          </div>
        </div>
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
                  className={`px-4 py-2 rounded-lg font-medium text-white transition ${isPaused ? 'bg-green-600 hover:bg-green-700' : 'bg-yellow-600 hover:bg-yellow-700'
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

            {/* Filters / Toggles Row */}
            <div className="mt-6 pt-4 border-t border-border flex flex-wrap items-center gap-6">
              <div className="flex items-center gap-4">
                <span className="text-xs font-bold text-text uppercase tracking-wider bg-bg/50 px-2 py-1 rounded">EEG Mode:</span>
                <div className="flex bg-bg/50 p-1 rounded-lg border border-border">
                  <button
                    onClick={() => setDisplayMode('single')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${displayMode === 'single' ? 'bg-primary text-primary-contrast shadow-sm' : 'text-muted hover:text-text'}`}
                  >
                    Single Ch
                  </button>
                  <button
                    onClick={() => setDisplayMode('overlay')}
                    className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${displayMode === 'overlay' ? 'bg-primary text-primary-contrast shadow-sm' : 'text-muted hover:text-text'}`}
                  >
                    Overlay All
                  </button>
                </div>
              </div>

              {displayMode === 'single' && (
                <div className="flex items-center gap-2 animate-in fade-in slide-in-from-left-4 duration-300">
                  <span className="text-xs font-bold text-muted uppercase">Select Channel:</span>
                  <select
                    value={selectedChannel}
                    onChange={(e) => setSelectedChannel(Number(e.target.value))}
                    className="px-3 py-1.5 bg-bg border border-border text-text text-xs rounded-lg outline-none cursor-pointer hover:border-primary/50"
                  >
                    {knownEegChannels.length === 0 && <option value={0}>Waiting for data...</option>}
                    {knownEegChannels.map(ch => (
                      <option key={ch} value={ch}>Channel {ch}</option>
                    ))}
                  </select>
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
          )}

                      <div className="flex-grow"></div>

                      <div className="flex items-center gap-4">
                        <label className="flex items-center gap-2 cursor-pointer group">
                          <div className={`w-10 h-5 rounded-full p-1 transition-colors duration-300 ${showEog ? 'bg-emerald-500/20 ring-1 ring-emerald-500' : 'bg-bg ring-1 ring-border'}`}>
                            <div className={`w-3 h-3 rounded-full bg-emerald-500 shadow-sm transform transition-transform duration-300 ${showEog ? 'translate-x-[18px]' : 'translate-x-0'}`}></div>
                          </div>
                          <input type="checkbox" className="hidden" checked={showEog} onChange={e => setShowEog(e.target.checked)} />
                          <span className={`text-xs font-bold transition-colors ${showEog ? 'text-emerald-400' : 'text-muted group-hover:text-text'}`}>Show EOG</span>
                        </label>

                        <label className="flex items-center gap-2 cursor-pointer group">
                          <div className={`w-10 h-5 rounded-full p-1 transition-colors duration-300 ${showEmg ? 'bg-amber-500/20 ring-1 ring-amber-500' : 'bg-bg ring-1 ring-border'}`}>
                            <div className={`w-3 h-3 rounded-full bg-amber-500 shadow-sm transform transition-transform duration-300 ${showEmg ? 'translate-x-[18px]' : 'translate-x-0'}`}></div>
                          </div>
                          <input type="checkbox" className="hidden" checked={showEmg} onChange={e => setShowEmg(e.target.checked)} />
                          <span className={`text-xs font-bold transition-colors ${showEmg ? 'text-amber-400' : 'text-muted group-hover:text-text'}`}>Show EMG</span>
                        </label>
                      </div>
                    </div>
                  </div>

                  {/* Charts Grid */}
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 pb-10">

                    {/* Main EEG Chart */}
                    <div className="col-span-1 xl:col-span-2 h-[350px] md:h-[400px]">
                      <SignalChart
                        title={displayMode === 'single' ? `EEG Channel ${selectedChannel}` : 'EEG Overlay (All Channels)'}
                        color="#3b82f6"
                        timeWindowMs={timeWindowMs}
                        {...eegChartProp}
                        channelLabelPrefix="Ch"
                        height={320}
                        showGrid={true}
                      />
                    </div>

                    {/* Secondary Charts */}
                    {showEog && (
                      <div className="col-span-1 h-[250px]">
                        <SignalChart
                          title="EOG - Eye Movement"
                          data={eogData}
                          color="#10b981"
                          timeWindowMs={timeWindowMs}
                          height={200}
                        />
                      </div>
                    )}

                    {showEmg && (
                      <div className="col-span-1 h-[250px]">
                        <SignalChart
                          title="EMG - Muscle Activity"
                          data={emgData}
                          color="#f59e0b"
                          timeWindowMs={timeWindowMs}
                          height={200}
                        />
                      </div>
                    )}

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
                          className={`px-3 py-1 rounded text-sm font-medium transition ${selectedChannels.includes(ch)
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
