import React, { useState, useEffect, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'
// *** CHANGED: Import a simple brain/tech icon for the new visual element ***
import { Brain, Zap, Play, Pause } from 'lucide-react'

/**
 * LiveView (Python-WS streaming) with multi-channel EEG support.
 * - EEG buffer is stored per-channel: eegByChannel = { 0: [{time,value}, ...], 1: [...] }
 * - UI: Single-channel (choose index) or Overlay all channels
 */

export default function LiveView({ wsData }) {
  // per-channel buffers for EEG, single buffers for EOG/EMG
  const [eegByChannel, setEegByChannel] = useState({}) // {chIndex: [{time,value}, ...]}
  const [eogData, setEogData] = useState([])
  const [emgData, setEmgData] = useState([])

  // UI controls
  const [timeWindowMs, setTimeWindowMs] = useState(10000) // 10s
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

  useEffect(() => {
    if (!wsData || isPaused) return

    let payload = null
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
      }
    }
  }, [wsData, isPaused, timeWindowMs]) // eslint-disable-line react-hooks/exhaustive-deps

  // Select data to pass to SignalChart for EEG:
  // - single mode: pass selected channel's array as `data`
  // - overlay mode: pass entire eegByChannel as `byChannel`
  const eegChartProp = useMemo(() => {
    if (displayMode === 'overlay') {
      return { byChannel: eegByChannel }
    } else {
      // ensure selectedChannel exists; if not, pick lowest existing
      const ch = Number(selectedChannel)
      if (eegByChannel[ch]) return { data: eegByChannel[ch] }
      const keys = Object.keys(eegByChannel)
      if (keys.length === 0) return { data: [] }
      const fallback = Number(keys[0])
      return { data: eegByChannel[fallback] ?? [] }
    }
  }, [displayMode, selectedChannel, eegByChannel])

  return (
    // *** CHANGED: Added 'min-h-screen' for better responsiveness on small screens, ensuring content takes full height ***
    <div className="flex flex-col min-h-screen bg-bg gap-6 p-4 md:p-6 overflow-y-auto">
      {/* Top Banner / Controls */}
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-5 sticky top-0 z-20 backdrop-blur-md bg-opacity-95">
        
        {/* *** CHANGED: Flex layout changed to ensure better stacking on small screens *** */}
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">

          {/* *** CHANGED: Tech Brain Icon & Animation *** */}
          <div className="flex items-center gap-4">
            <div className={`bg-primary/10 p-3 rounded-xl border border-primary/20 transition-all duration-300 ${isPaused ? 'opacity-50' : 'opacity-100'}`}>
              <Brain className={`w-6 h-6 ${isPaused ? 'text-accent' : 'text-primary'} ${!isPaused ? 'animate-pulse-fast' : ''}`} />
              {/* Custom animation class (needs to be defined in main CSS, or use Tailwind's `animate-pulse` like I did) */}
              <Zap className={`w-3 h-3 absolute -top-1 -right-1 ${isPaused ? 'text-accent/50' : 'text-primary'} ${!isPaused ? 'animate-ping-slow' : ''}`} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-text tracking-tight">Live Monitoring</h2>
              <p className="text-xs text-muted font-mono uppercase tracking-widest">{isPaused ? 'PAUSED' : 'STREAMING ACTIVE'}</p>
            </div>
          </div>
          {/* *** END CHANGED: Tech Brain Icon & Animation *** */}

          {/* *** CHANGED: Control Group - Added responsive wrap/stack and stylized Pause/Resume button (connecting button) *** */}
          <div className="flex flex-wrap items-center gap-4">
            
            {/* Control Group - Pause/Resume Button (Now stylized and larger) */}
            <div className="flex items-center gap-2 bg-bg/50 p-1.5 rounded-xl border border-border shadow-md">
              <button
                onClick={() => setIsPaused(!isPaused)}
                // *** CHANGED: Increased padding (py-3.5) and font size (text-base) for a larger, more prominent button ***
                className={`flex items-center gap-2 px-5 py-3.5 rounded-xl font-extrabold text-base transition-all duration-300 ${isPaused
                  ? 'bg-accent/20 text-accent hover:bg-accent/30 border border-accent/20 shadow-lg shadow-accent/20'
                  : 'bg-primary text-primary-contrast hover:bg-primary/90 border border-primary shadow-xl shadow-primary/30'
                  }`}
              >
                {isPaused ? <Play className="w-5 h-5" /> : <Pause className="w-5 h-5" />}
                {isPaused ? 'RESUME STREAM' : 'PAUSE STREAM'}
              </button>
            </div>

            <div className="h-10 w-[1px] bg-border mx-2 hidden lg:block"></div> {/* Separator for desktop */}
            
            {/* Time Window (Moved inside the same responsive div) */}
            <div className="flex flex-col gap-1 w-full sm:w-auto"> {/* Added w-full/sm:w-auto for better stacking */}
              <label className="text-[10px] font-bold text-muted uppercase tracking-wider ml-1">Time Window</label>
              <select
                value={timeWindowMs}
                onChange={(e) => setTimeWindowMs(Number(e.target.value))}
                className="px-4 py-3 bg-bg border border-border text-text text-sm rounded-lg focus:ring-2 focus:ring-primary/50 outline-none hover:border-primary/50 transition-colors w-full sm:w-[150px]" // Added responsive width
              >
                <option value={5000}>5 Seconds</option>
                <option value={10000}>10 Seconds</option>
                <option value={30000}>30 Seconds</option>
                <option value={60000}>60 Seconds</option>
              </select>
            </div>
          </div>
          {/* *** END CHANGED: Control Group *** */}
        </div>

        {/* Filters / Toggles Row */}
        {/* *** CHANGED: Added 'flex-col sm:flex-row' and adjusted gap/margin for better responsiveness on smaller screens *** */}
        <div className="mt-6 pt-4 border-t border-border flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
          
          {/* EEG Mode (Single/Overlay) */}
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

          {/* Select Channel Dropdown (only visible in single mode) */}
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
            </div>
          )}

          {/* Pushes EOG/EMG toggles to the right on larger screens */}
          <div className="flex-grow"></div> 

          {/* EOG/EMG Toggles */}
          <div className="flex items-center gap-4 mt-2 sm:mt-0"> {/* Adjusted top margin for mobile stacking */}
            <label className="flex items-center gap-2 cursor-pointer group">
              <div className={`w-10 h-5 rounded-full p-1 transition-colors duration-300 ${showEog ? 'bg-emerald-500/20 ring-1 ring-emerald-500' : 'bg-bg ring-1 ring-border'}`}>
                <div className={`w-3 h-3 rounded-full bg-emerald-500 shadow-sm transform transition-transform duration-300 ${showEog ? 'translate-x-[18px]' : 'translate-x-0'}`}></div>
              </div>
              <input type="checkbox" className="hidden" checked={showEog} onChange={e => setShowEog(e.target.checked)} />
              <span className={`text-xs font-bold transition-colors ${showEog ? 'text-emerald-400' : 'text-muted group-hover:text-text'}`}>Show EOG</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer group">
              <div className={`w-10 h-5 rounded-full p-1 transition-colors duration-300 ${showEmg ? 'bg-amber-500/20 ring-1 ring-amber-500' : 'bg-bg ring-1 ring-border'}`}>
                <div class={`w-3 h-3 rounded-full bg-amber-500 shadow-sm transform transition-transform duration-300 ${showEmg ? 'translate-x-[18px]' : 'translate-x-0'}`}></div>
              </div>
              <input type="checkbox" className="hidden" checked={showEmg} onChange={e => setShowEmg(e.target.checked)} />
              <span className={`text-xs font-bold transition-colors ${showEmg ? 'text-amber-400' : 'text-muted group-hover:text-text'}`}>Show EMG</span>
            </label>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      {/* *** CHANGED: Chart height increased on large screens, grid layout adjusted to 1-column on mobile and 2-column on xl *** */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 pb-10">

        {/* Main EEG Chart */}
        <div className="col-span-1 xl:col-span-2 h-[350px] md:h-[450px]">
          <SignalChart
            title={displayMode === 'single' ? `EEG Channel ${selectedChannel}` : 'EEG Overlay (All Channels)'}
            color="#3b82f6"
            timeWindowMs={timeWindowMs}
            {...eegChartProp}
            channelLabelPrefix="Ch"
            // *** CHANGED: Increased height property for the chart component itself ***
            height={400} 
            showGrid={true}
          />
        </div>

        {/* Secondary Charts (EOG and EMG now share a column on XL screens) */}
        {showEog && (
          <div className="col-span-1 h-[250px] lg:h-[300px]"> {/* Increased height for better look */}
            <SignalChart
              title="EOG - Eye Movement"
              data={eogData}
              color="#10b981"
              timeWindowMs={timeWindowMs}
              // *** CHANGED: Increased height property for the chart component itself ***
              height={250}
            />
          </div>
        )}

        {showEmg && (
          <div className="col-span-1 h-[250px] lg:h-[300px]"> {/* Increased height for better look */}
            <SignalChart
              title="EMG - Muscle Activity"
              data={emgData}
              color="#f59e0b"
              timeWindowMs={timeWindowMs}
              // *** CHANGED: Increased height property for the chart component itself ***
              height={250}
            />
          </div>
        )}
        {/* *** END CHANGED: Chart Grid *** */}
      </div>
    </div>
  )
}