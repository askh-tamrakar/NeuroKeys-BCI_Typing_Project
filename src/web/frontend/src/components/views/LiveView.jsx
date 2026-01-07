import React, { useState, useEffect, useRef, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'
import { DataService } from '../../services/DataService'
import { Radio, Square, Settings2, Wifi, Circle } from 'lucide-react'
import '../../styles/live/LiveView.css'

export default function LiveView({ wsData, wsEvent, config, isPaused }) {
  // Global default for initialization, but now each channel has its own
  const defaultTimeWindowMs = config?.display?.timeWindowMs || 10000
  const samplingRate = config?.sampling_rate || 250
  const showGrid = config?.display?.showGrid ?? true
  const channelMapping = config?.channel_mapping || {}
  const numChannels = 2 // Hardcoded for strict 2-channel mode

  const [ch0Data, setCh0Data] = useState([])
  const [ch1Data, setCh1Data] = useState([])
  const [ch2Data, setCh2Data] = useState([])
  const [ch3Data, setCh3Data] = useState([])
  const [scannerX, setScannerX] = useState(null)
  const [scannerPercent, setScannerPercent] = useState(0)

  // -- MOVED UP TO FIX TDZ --
  const getActiveChannels = () => {
    const active = []
    for (let i = 0; i < numChannels; i++) {
      const key = `ch${i}`
      const chConfig = channelMapping[key]
      if (chConfig?.enabled !== false) active.push(i)
    }
    return active
  }

  const activeChannels = useMemo(() => getActiveChannels(), [channelMapping, numChannels])

  // Channel Configuration State (Zoom & Range)
  const [channelConfig, setChannelConfig] = useState({})
  const BASE_AMPLITUDE = 1500 // uV assumed base range
  // -- END MOVED UP --

  // Recording State
  const [isRecording, setIsRecording] = useState(false)
  const [recordingStartTime, setRecordingStartTime] = useState(null)
  const [recordingTime, setRecordingTime] = useState(0)
  const [recordedData, setRecordedData] = useState([]) // Array of { timestamp, channels: { ch0: val, ch1: val, ... } }
  const [recordingChannels, setRecordingChannels] = useState([0, 1]) // Default to 2 channels
  const [isSaving, setIsSaving] = useState(false)

  // Optimized batch adder
  // Assumes newPoints are sorted by time (guaranteed by backend/websocket logic)
  const addDataPoints = (dataArray, newPoints, maxAge) => {
    if (!newPoints || newPoints.length === 0) return dataArray

    // 1. Append new points (cheap)
    const combined = dataArray.concat(newPoints)

    // 2. Prune old points from the FRONT (cheap-ish)
    // Since data is monotonic, we just need to find the first index that is valid
    // Binary search would be O(log N), but linear scan from start is also fine if we assume we remove small chunks.
    // However, binary search is safer for potentially large buffers.

    const latestTime = newPoints[newPoints.length - 1].time
    const cutoff = latestTime - maxAge

    // Optimization: If the oldest point is already newer than cutoff, do nothing
    if (combined.length > 0 && combined[0].time > cutoff) {
      return combined
    }

    // Binary search to find cut index
    let low = 0
    let high = combined.length - 1
    let cutIndex = 0

    while (low <= high) {
      const mid = (low + high) >>> 1
      if (combined[mid].time < cutoff) {
        cutIndex = mid + 1 // This point is too old, potential cut is after it
        low = mid + 1
      } else {
        high = mid - 1
      }
    }

    // Slice is O(K) copy, but unavoidable for immutable update. 
    // It is much faster than filter() which allocates closures and checks every element.
    return cutIndex > 0 ? combined.slice(cutIndex) : combined
  }

  // Update recording timer
  useEffect(() => {
    let interval = null
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingTime(Math.floor((Date.now() - recordingStartTime) / 1000))
      }, 1000)
    } else {
      setRecordingTime(0)
    }
    return () => clearInterval(interval)
  }, [isRecording, recordingStartTime])

  useEffect(() => {
    if (!wsData || isPaused) return

    let basePayload = null
    try {
      basePayload = wsData.raw ?? (typeof wsData === 'string' ? JSON.parse(wsData) : wsData)
    } catch (e) {
      console.warn('[LiveView] Failed to parse wsData:', e)
      return
    }

    if (!basePayload) return

    // Handle Batch or Single Sample
    const samples = basePayload._batch || (basePayload.channels ? [basePayload] : [])
    if (samples.length === 0) return

    const sampleIntervalMs = Math.round(1000 / (samplingRate || 250))

    // Temporary buffers for this update
    const batchUpdates = { 0: [], 1: [], 2: [], 3: [] }
    const recordingUpdates = []

    samples.forEach(payload => {
      if (!payload.channels) return

      let incomingTs = Number(payload.timestamp)
      // Fix timestamp if needed
      if (!incomingTs || incomingTs < 1e9) incomingTs = Date.now()

      // Monotonic timestamp logic
      if (!window.__lastTs) window.__lastTs = incomingTs
      if (incomingTs <= window.__lastTs) {
        incomingTs = window.__lastTs + sampleIntervalMs
      }
      window.__lastTs = incomingTs

      // Recording accumulation
      if (isRecording) {
        const recordPoint = { timestamp: incomingTs, channels: {} }
        let hasData = false
        recordingChannels.forEach(chNum => {
          const chKey = `ch${chNum}` // payload might use integer keys, check Object.entries below
          // Search in payload.channels (which might be object with keys '0','1'...)
          Object.entries(payload.channels).forEach(([chIdx, chData]) => {
            if (parseInt(chIdx) === chNum) {
              let val = 0
              if (typeof chData === 'number') val = chData
              else if (typeof chData === 'object') val = chData.value ?? chData.val ?? 0
              recordPoint.channels[`ch${chNum}`] = val
              hasData = true
            }
          })
        })
        if (hasData) recordingUpdates.push(recordPoint)
      }

      // View Buffers accumulation
      Object.entries(payload.channels).forEach(([chIdx, chData]) => {
        const chNum = parseInt(chIdx)
        const chKey = `ch${chNum}`

        // Skip disabled
        const chConfig = channelMapping[chKey]
        if (chConfig?.enabled === false) return

        let value = 0
        if (typeof chData === 'number') value = chData
        else if (typeof chData === 'object') value = chData.value ?? chData.val ?? 0

        if (!Number.isFinite(value)) return

        // Push to temp buffer
        if (batchUpdates[chNum]) {
          batchUpdates[chNum].push({ time: incomingTs, value: Number(value) })
        }
      })
    })

    // Commit State Updates - using channel specific or default windows is not critical for *accumulation*, 
    // but strict buffer management might want to use the largest window to be safe. 
    // For now, using a safe upper bound (e.g. 30s) or just keeping the old default for buffering is fine 
    // as long as we don't prune too aggressively.
    // Let's use a safe large buffer (30s) for addDataPoints to avoid cutting off data needed for a large custom window.
    const safeBufferMs = 30000
    if (batchUpdates[0].length) setCh0Data(prev => addDataPoints(prev, batchUpdates[0], safeBufferMs))
    if (batchUpdates[1].length) setCh1Data(prev => addDataPoints(prev, batchUpdates[1], safeBufferMs))
    if (batchUpdates[2].length) setCh2Data(prev => addDataPoints(prev, batchUpdates[2], safeBufferMs))
    if (batchUpdates[3].length) setCh3Data(prev => addDataPoints(prev, batchUpdates[3], safeBufferMs))

    if (recordingUpdates.length > 0) {
      setRecordedData(prev => [...prev, ...recordingUpdates])
    }

  }, [wsData, isPaused, channelMapping, samplingRate, isRecording, recordingChannels])

  useEffect(() => {
    const allData = [ch0Data, ch1Data, ch2Data, ch3Data].filter(d => d && d.length)
    if (allData.length === 0) {
      setScannerX(null)
      setScannerPercent(0)
      return
    }

    const oldestTs = Math.min(...allData.map(d => d[0].time))
    const newestTs = Math.max(...allData.map(d => d[d.length - 1].time))
    // Use the maximum time window of any active channel for the global scanner/progress bar (if we even keep it)
    // or just default to 10s if complex. For now, let's use the first active channel's window or default.
    const refWindow = channelConfig[activeChannels[0]]?.timeWindowMs || defaultTimeWindowMs
    const duration = Math.max(refWindow, newestTs - oldestTs || 1)

    // place scanner at newestTs (right edge of visible range)
    setScannerX(newestTs)

    const posRatio = Math.min((newestTs - oldestTs) / duration, 1.0)
    setScannerPercent(posRatio * 100)
  }, [ch0Data, ch1Data, ch2Data, ch3Data, channelConfig, defaultTimeWindowMs, activeChannels])

  // Initialize config for channels when they appear
  useEffect(() => {
    setChannelConfig(prev => {
      const next = { ...prev }
      let changed = false
      activeChannels.forEach((chIdx, i) => {
        if (!next[chIdx]) {
          const defaultColor = ['#3b82f6', '#10b981', '#f59e0b', '#a855f7'][i % 4]
          next[chIdx] = { zoom: 1, manualRange: "", timeWindowMs: defaultTimeWindowMs, color: defaultColor }
          changed = true
        }
      })
      return changed ? next : prev
    })
  }, [activeChannels, defaultTimeWindowMs])

  const updateChannelConfig = (chIdx, key, value) => {
    setChannelConfig(prev => ({
      ...prev,
      [chIdx]: { ...prev[chIdx], [key]: value }
    }))
  }

  const getChannelYDomain = (chIdx) => {
    const cfg = channelConfig[chIdx]
    if (!cfg) return [-BASE_AMPLITUDE, BASE_AMPLITUDE]

    if (cfg.manualRange && !isNaN(parseFloat(cfg.manualRange))) {
      const r = parseFloat(cfg.manualRange)
      return [-r, r]
    }
    return [-BASE_AMPLITUDE / cfg.zoom, BASE_AMPLITUDE / cfg.zoom]
  }

  // Handle Annotations (Blinks)
  const [annotations, setAnnotations] = useState([])

  useEffect(() => {
    if (!wsEvent) return
    if (wsEvent.event === 'BLINK') {
      const ts = wsEvent.timestamp ? wsEvent.timestamp * 1000 : Date.now()
      const chKey = wsEvent.channel
      let targetData = []
      if (chKey === 'ch0') targetData = ch0Data
      if (chKey === 'ch1') targetData = ch1Data
      if (chKey === 'ch2') targetData = ch2Data
      if (chKey === 'ch3') targetData = ch3Data

      const point = targetData.length > 0 ? targetData[targetData.length - 1] : { value: 0 }

      setAnnotations(prev => [
        ...prev,
        {
          x: ts, // absolute time, will be mapped later
          y: point.value,
          label: 'BLINK',
          color: '#ef4444',
          channel: chKey
        }
      ].slice(-20))
    }
  }, [wsEvent, ch0Data, ch1Data, ch2Data, ch3Data])

  useEffect(() => {
    const now = Date.now()
    // Use a safe large window for cleaning up annotations
    setAnnotations(prev => prev.filter(a => (now - a.x) < 30000))
  }, [ch0Data]) // Clean up

  const getChannelData = (chIndex) => {
    switch (chIndex) {
      case 0: return ch0Data
      case 1: return ch1Data
      case 2: return ch2Data
      case 3: return ch3Data
      default: return []
    }
  }

  // --- SWEEP TRANSFORM LOGIC (Dual Segment) ---
  const processSweep = (data, windowMs) => {
    if (!data || data.length === 0) return { active: [], history: [], scanner: null, latestTs: 0 }
    const latestTs = data[data.length - 1].time
    const scannerPos = latestTs % windowMs

    const active = []  // Newest data (0 -> Scanner)
    const history = [] // Oldest data (Scanner -> Window)

    const cycleStartTs = latestTs - scannerPos // The time corresponding to X=0 in the current sweep

    data.forEach(d => {
      const mappedTime = d.time % windowMs
      // We only care about data within [latestTs - windowMs, latestTs]
      if (d.time > (latestTs - windowMs)) {
        if (d.time >= cycleStartTs) {
          active.push({ ...d, time: mappedTime })
        } else {
          history.push({ ...d, time: mappedTime })
        }
      }
    })

    // Sort each segment by X (mappedTime) for correct line drawing
    active.sort((a, b) => a.time - b.time)
    history.sort((a, b) => a.time - b.time)

    return { active, history, scanner: scannerPos, latestTs }
  }

  // Map annotations to sweep

  const mapAnn = (anns, windowMs) => anns.map(a => ({
    ...a,
    origX: a.x,
    x: a.x % windowMs
  }))

  const toggleRecording = async () => {
    if (!isRecording) {
      // Start
      setRecordedData([])
      setRecordingStartTime(Date.now())
      setIsRecording(true)
    } else {
      // Stop & Save
      setIsRecording(false)
      setIsSaving(true)

      try {
        const now = new Date()
        const day = String(now.getDate()).padStart(2, '0')
        const month = String(now.getMonth() + 1).padStart(2, '0')
        const year = now.getFullYear()
        const hours = String(now.getHours()).padStart(2, '0')
        const mins = String(now.getMinutes()).padStart(2, '0')
        const secs = String(now.getSeconds()).padStart(2, '0')

        // Use first sensor type in recording channels for filename
        const firstCh = recordingChannels[0]
        const sensorType = channelMapping[`ch${firstCh}`]?.sensor || 'DATA'

        const filename = `${sensorType}__${day}-${month}-${year}__${hours}-${mins}-${secs}.json`

        const payload = {
          metadata: {
            sensorType,
            channels: recordingChannels,
            samplingRate,
            startTime: recordingStartTime,
            endTime: Date.now(),
            duration: recordingTime
          },
          data: recordedData
        }

        await DataService.saveSession(filename, payload)
        alert(`Session saved successfully as ${filename}`)
      } catch (err) {
        console.error('Failed to save session:', err)
        alert('Failed to save session. Check console for details.')
      } finally {
        setIsSaving(false)
        setRecordedData([])
      }
    }
  }

  const toggleChannelSelection = (chIdx) => {
    setRecordingChannels(prev =>
      prev.includes(chIdx) ? prev.filter(c => c !== chIdx) : [...prev, chIdx]
    )
  }

  return (
    <div className="live-view-container">
      <div className="h-[94px] shrink-0" />
      {/* Controls */}
      <div className="controls-container flex flex-row justify-between">
        {/* Zoom controls removed from here, moved to per-channel */}

        {/* Recording Controls */}
        <div className="flex flex-row gap-2">
          <div className="record-controls">
            <button
              onClick={toggleRecording}
              disabled={isSaving || (activeChannels.length === 0 && !isRecording)}
              className={`record-btn ${isRecording ? 'recording' : 'idle'}`}
            >
              {isRecording ? <Square size={16} fill="currentColor" /> : <Radio size={16} />}
              {isRecording ? `STOP (${recordingTime}s)` : 'REC'}
            </button>
            {isSaving && <div className="saving-indicator">SAVING...</div>}
          </div>
          <div>
            {isRecording && <div className="recording-status">● RECORDING IN PROGRESS</div>}
          </div>
        </div>

        <div className="flex flex-row gap-2">
          <div className="mode-indicator">
            {/* Global range indicator removed or can be replaced with something else */}
            <span className="text-primary font-bold flex items-center gap-2 w-auto"><Settings2 size={16} /> MODE:</span>
            INDEPENDENT SCALING
            <span className='separator'></span>
            <div className="flex items-center gap-2"><span className="text-purple-400 flex items-center gap-1"><Wifi size={16} /> Stream</span>: {wsData?.raw?.stream_name || 'Disconnected'}</div>
          </div>
        </div>

      </div>

      {Array.from({ length: 2 }).map((_, chIdx) => {
        const isEnabled = activeChannels.includes(chIdx);
        const rawData = getChannelData(chIdx)
        const sensorName = channelMapping[`ch${chIdx}`]?.sensor

        // --- DEFINE VARIABLES IN CORRECT ORDER ---
        const currentZoom = channelConfig[chIdx]?.zoom || 1
        const currentManual = channelConfig[chIdx]?.manualRange || ""
        const currentTimeWindow = channelConfig[chIdx]?.timeWindowMs || defaultTimeWindowMs
        const currentChColor = channelConfig[chIdx]?.color || ['rgb(59, 130, 246)', 'rgb(16, 185, 129)', 'rgb(245, 158, 11)', 'rgb(168, 85, 247)'][chIdx % 4]

        // Now it is safe to use currentChColor
        const chColorHist = currentChColor + '4D'

        const chDomain = getChannelYDomain(chIdx)

        // Moved sweep processing down to have access to currentTimeWindow
        const sweep = processSweep(rawData, currentTimeWindow)

        return (
          <div key={chIdx} className="channel-wrapper">
            <SignalChart
              graphNo={`Graph ${chIdx + 1}`}
              title={`${sensorName}`}
              disabled={!isEnabled}
              byChannel={{ active: sweep.active, history: sweep.history }}
              channelColors={{ active: currentChColor, history: chColorHist }} // Pass dynamic color
              timeWindowMs={currentTimeWindow}
              color={currentChColor} // Main color prop
              height="100%"
              showGrid={showGrid}
              scannerX={sweep.scanner}
              annotations={mapAnn(annotations.filter(a => a.channel === `ch${chIdx}`), currentTimeWindow)}
              yDomainProp={chDomain}
              tickCount={7}
              curveType="natural"
              // New props for controls
              currentZoom={currentZoom}
              currentManual={currentManual}
              onZoomChange={(z) => { updateChannelConfig(chIdx, 'zoom', z); updateChannelConfig(chIdx, 'manualRange', ""); }}
              onRangeChange={(val) => updateChannelConfig(chIdx, 'manualRange', val)}
              onTimeWindowChange={(val) => updateChannelConfig(chIdx, 'timeWindowMs', val)}
              onColorChange={(val) => updateChannelConfig(chIdx, 'color', val)}
            />
          </div>
        )
      })}
    </div>
  )
}
