// LiveView.jsx (updated)
import React, { useState, useEffect, useRef, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'
import { DataService } from '../../services/DataService'

export default function LiveView({ wsData, wsEvent, config, isPaused }) {
  const timeWindowMs = config?.display?.timeWindowMs || 10000
  const samplingRate = config?.sampling_rate || 250
  const showGrid = config?.display?.showGrid ?? true
  const channelMapping = config?.channel_mapping || {}
  const numChannels = config?.num_channels || 2

  const [ch0Data, setCh0Data] = useState([])
  const [ch1Data, setCh1Data] = useState([])
  const [ch2Data, setCh2Data] = useState([])
  const [ch3Data, setCh3Data] = useState([])
  const [scannerX, setScannerX] = useState(null)
  const [scannerPercent, setScannerPercent] = useState(0)

  // Recording State
  const [isRecording, setIsRecording] = useState(false)
  const [recordingStartTime, setRecordingStartTime] = useState(null)
  const [recordingTime, setRecordingTime] = useState(0)
  const [recordedData, setRecordedData] = useState([]) // Array of { timestamp, channels: { ch0: val, ch1: val, ... } }
  const [recordingChannels, setRecordingChannels] = useState([0, 1, 2, 3]) // Default to all channels
  const [isSaving, setIsSaving] = useState(false)

  const addDataPoint = (dataArray, newPoint, maxAge) => {
    const now = newPoint.time
    const filtered = dataArray.filter(p => (now - p.time) < maxAge)
    return [...filtered, newPoint]
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

    let payload = null
    try {
      payload = wsData.raw ?? (typeof wsData === 'string' ? JSON.parse(wsData) : wsData)
    } catch (e) {
      console.warn('[LiveView] Failed to parse wsData:', e)
      return
    }

    if (!payload?.channels) {
      console.warn('[LiveView] No channels in payload')
      return
    }

    // normalize timestamp (ms)
    let incomingTs = Number(payload.timestamp)

    if (!incomingTs || incomingTs < 1e9) {
      incomingTs = Date.now()
    }

    // sample interval used to bump monotonic timestamps (in ms)
    const sampleIntervalMs = Math.round(1000 / (samplingRate || 250))

    // global incremental timestamp
    if (!window.__lastTs) window.__lastTs = incomingTs
    if (incomingTs <= window.__lastTs) {
      incomingTs = window.__lastTs + sampleIntervalMs
    }
    window.__lastTs = incomingTs

    // If recording, accumulate data
    if (isRecording) {
      const recordPoint = {
        timestamp: incomingTs,
        channels: {}
      }

      Object.entries(payload.channels).forEach(([chIdx, chData]) => {
        const chNum = parseInt(chIdx)
        if (recordingChannels.includes(chNum)) {
          let value = 0
          if (typeof chData === 'number') value = chData
          else if (typeof chData === 'object') value = chData.value ?? chData.val ?? 0
          recordPoint.channels[`ch${chNum}`] = value
        }
      })

      if (Object.keys(recordPoint.channels).length > 0) {
        setRecordedData(prev => [...prev, recordPoint])
      }
    }

    Object.entries(payload.channels).forEach(([chIdx, chData]) => {
      const chNum = parseInt(chIdx)
      const chKey = `ch${chNum}`
      const chConfig = channelMapping[chKey]
      if (chConfig?.enabled === false) return

      let value = 0
      if (typeof chData === 'number') value = chData
      else if (typeof chData === 'object') value = chData.value ?? chData.val ?? 0

      if (!Number.isFinite(value)) return

      // ensure monotonic timestamp per channel: if incomingTs <= lastTs -> bump
      const newPointFactory = (ts) => ({ time: ts, value: Number(value) })

      switch (chNum) {
        case 0:
          setCh0Data(prev => {
            const lastTs = prev.length ? prev[prev.length - 1].time : (incomingTs - sampleIntervalMs)
            const ts = incomingTs <= lastTs ? lastTs + sampleIntervalMs : incomingTs
            return addDataPoint(prev, newPointFactory(ts), timeWindowMs)
          })
          break
        case 1:
          setCh1Data(prev => {
            const lastTs = prev.length ? prev[prev.length - 1].time : (incomingTs - sampleIntervalMs)
            const ts = incomingTs <= lastTs ? lastTs + sampleIntervalMs : incomingTs
            return addDataPoint(prev, newPointFactory(ts), timeWindowMs)
          })
          break
        case 2:
          setCh2Data(prev => {
            const lastTs = prev.length ? prev[prev.length - 1].time : (incomingTs - sampleIntervalMs)
            const ts = incomingTs <= lastTs ? lastTs + sampleIntervalMs : incomingTs
            return addDataPoint(prev, newPointFactory(ts), timeWindowMs)
          })
          break
        case 3:
          setCh3Data(prev => {
            const lastTs = prev.length ? prev[prev.length - 1].time : (incomingTs - sampleIntervalMs)
            const ts = incomingTs <= lastTs ? lastTs + sampleIntervalMs : incomingTs
            return addDataPoint(prev, newPointFactory(ts), timeWindowMs)
          })
          break
        default:
          console.warn(`[LiveView] Ch${chNum}: Unknown channel index`)
      }
    })
  }, [wsData, isPaused, timeWindowMs, channelMapping, samplingRate, isRecording, recordingChannels])

  useEffect(() => {
    const allData = [ch0Data, ch1Data, ch2Data, ch3Data].filter(d => d && d.length)
    if (allData.length === 0) {
      setScannerX(null)
      setScannerPercent(0)
      return
    }

    const oldestTs = Math.min(...allData.map(d => d[0].time))
    const newestTs = Math.max(...allData.map(d => d[d.length - 1].time))
    const duration = Math.max(timeWindowMs, newestTs - oldestTs || 1)

    // place scanner at newestTs (right edge of visible range)
    setScannerX(newestTs)

    const posRatio = Math.min((newestTs - oldestTs) / duration, 1.0)
    setScannerPercent(posRatio * 100)
  }, [ch0Data, ch1Data, ch2Data, ch3Data, timeWindowMs])

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

  // Initialize config for channels when they appear
  useEffect(() => {
    setChannelConfig(prev => {
      const next = { ...prev }
      let changed = false
      activeChannels.forEach(chIdx => {
        if (!next[chIdx]) {
          next[chIdx] = { zoom: 1, manualRange: "" }
          changed = true
        }
      })
      return changed ? next : prev
    })
  }, [activeChannels])

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
    setAnnotations(prev => prev.filter(a => (now - a.x) < timeWindowMs))
  }, [timeWindowMs, ch0Data]) // Clean up

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
    <div className="w-full h-full flex flex-col gap-4 p-4 bg-bg rounded-lg overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 bg-surface border border-border p-3 rounded-lg backdrop-blur-sm">
        <div className="h-4 w-[1px] bg-border mx-2"></div>
        {/* Zoom controls removed from here, moved to per-channel */}

        {/* Recording Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="text-xs font-bold text-muted uppercase tracking-wider">Record Ch:</div>
            <div className="flex gap-1">
              {activeChannels.map(chIdx => (
                <button
                  key={chIdx}
                  disabled={isRecording}
                  onClick={() => toggleChannelSelection(chIdx)}
                  className={`w-6 h-6 flex items-center justify-center rounded text-[10px] font-bold border transition-all ${recordingChannels.includes(chIdx)
                    ? 'bg-primary/20 border-primary text-primary'
                    : 'bg-surface/50 border-border text-muted hover:text-text opacity-50'
                    }`}
                >
                  {chIdx}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={toggleRecording}
            disabled={isSaving || (activeChannels.length === 0 && !isRecording)}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg font-bold text-xs transition-all shadow-lg ${isRecording
              ? 'bg-red-500 text-white animate-pulse'
              : 'bg-emerald-500 text-emerald-contrast hover:translate-y-[-1px]'
              }`}
          >
            <div className={`w-2 h-2 rounded-full ${isRecording ? 'bg-white' : 'bg-white/50'}`}></div>
            {isRecording ? `STOP (${recordingTime}s)` : 'REC'}
          </button>

          {isSaving && <div className="text-[10px] text-primary animate-pulse font-bold">SAVING...</div>}
        </div>

        <div className="text-[10px] text-muted ml-auto font-mono bg-bg/50 px-2 py-1 rounded border border-border">
          {/* Global range indicator removed or can be replaced with something else */}
          <span className="text-primary font-bold">MODE:</span> INDEPENDENT SCALING
        </div>
      </div>

      {activeChannels.map((chIdx) => {
        const sensorName = channelMapping[`ch${chIdx}`]?.sensor
        const rawData = getChannelData(chIdx)
        const sweep = processSweep(rawData, timeWindowMs)
        const chColor = ['rgb(59, 130, 246)', 'rgb(16, 185, 129)', 'rgb(245, 158, 11)', 'rgb(168, 85, 247)'][chIdx % 4]
        const chColorHist = ['rgba(59, 130, 246, 0.3)', 'rgba(16, 185, 129, 0.3)', 'rgba(245, 158, 11, 0.3)', 'rgba(168, 85, 247, 0.3)'][chIdx % 4]

        const currentZoom = channelConfig[chIdx]?.zoom || 1
        const currentManual = channelConfig[chIdx]?.manualRange || ""
        const chDomain = getChannelYDomain(chIdx)

        return (
          <div key={chIdx} className="shrink-0 flex flex-col gap-1">

            {/* Per-Channel Controls Header */}
            <div className="flex items-center justify-between bg-surface/50 p-1 rounded border border-border/50">
              <div className="mb-0 text-sm font-semibold text-muted flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: chColor }}></span>
                Graph {chIdx + 1}
              </div>

              <div className="flex items-center gap-4">
                {/* Zoom Buttons */}
                <div className="flex gap-1 items-center">
                  <span className="text-[9px] font-bold text-muted uppercase">ZOOM</span>
                  {[1, 5, 20, 50].map(z => (
                    <button
                      key={z}
                      onClick={() => { updateChannelConfig(chIdx, 'zoom', z); updateChannelConfig(chIdx, 'manualRange', ""); }}
                      className={`px-1.5 py-0.5 text-[9px] rounded font-bold transition-all ${currentZoom === z && !currentManual
                        ? 'bg-primary text-white shadow-sm'
                        : 'bg-surface hover:bg-white/10 text-muted hover:text-text border border-border'
                        }`}
                    >
                      {z}x
                    </button>
                  ))}
                </div>

                <div className="w-[1px] h-3 bg-border"></div>

                {/* Manual Range Input */}
                <div className="flex gap-1 items-center">
                  <span className="text-[9px] font-bold text-muted uppercase">RANGE</span>
                  <input
                    type="number"
                    placeholder="+/-"
                    value={currentManual}
                    onChange={(e) => updateChannelConfig(chIdx, 'manualRange', e.target.value)}
                    className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-[9px] text-text focus:outline-none focus:border-primary"
                  />
                </div>

                <div className="w-[1px] h-3 bg-border"></div>

                <div className="text-[9px] font-mono text-muted">
                  +/-{(Math.abs(chDomain[1])).toFixed(0)} uV
                </div>
              </div>
            </div>

            <SignalChart
              title={`${sensorName}`}
              byChannel={{ active: sweep.active, history: sweep.history }}
              channelColors={{ active: chColor, history: chColorHist }}
              timeWindowMs={timeWindowMs}
              color={chColor}
              height={300}
              showGrid={showGrid}
              scannerX={sweep.scanner}
              annotations={mapAnn(annotations.filter(a => a.channel === `ch${chIdx}`), timeWindowMs)}
              yDomainProp={chDomain}
              tickCount={7}
            />
          </div>
        )
      })}

      <div className="bg-surface/50 border border-border rounded p-3 text-xs text-muted font-mono space-y-1">
        {/* Footer Info */}
        <div className="flex justify-between">
          <div><span className="text-primary font-bold">MODE:</span> INDEPENDENT SCALING</div>
          {isRecording && <div className="text-red-400 animate-pulse font-bold">● RECORDING IN PROGRESS</div>}
        </div>
        <div><span className="text-purple-400">Stream</span>: {wsData?.raw?.stream_name || 'Disconnected'}</div>
      </div>
    </div>
  )
}
