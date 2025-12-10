// LiveView.jsx (updated)
import React, { useState, useEffect, useRef, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'

export default function LiveView({ wsData, config, isPaused }) {
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

  const addDataPoint = (dataArray, newPoint, maxAge) => {
    const now = newPoint.time
    const filtered = dataArray.filter(p => (now - p.time) < maxAge)
    return [...filtered, newPoint]
  }

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
  }, [wsData, isPaused, timeWindowMs, channelMapping, samplingRate])

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

  const displayCh0 = activeChannels.length > 0 ? activeChannels[0] : 0
  const displayCh1 = activeChannels.length > 1 ? activeChannels[1] : 1

  const getChannelData = (chIndex) => {
    switch (chIndex) {
      case 0: return ch0Data
      case 1: return ch1Data
      case 2: return ch2Data
      case 3: return ch3Data
      default: return []
    }
  }

  const data1 = getChannelData(displayCh0)
  const data2 = getChannelData(displayCh1)

  const getSensorName = (chIndex) => {
    const chKey = `ch${chIndex}`
    return channelMapping[chKey]?.sensor || `Channel ${chIndex}`
  }

  const sensorName1 = getSensorName(displayCh0)
  const sensorName2 = getSensorName(displayCh1)

  return (
    <div className="w-full h-full flex flex-col gap-4 p-4 bg-slate-900 rounded-lg overflow-auto">
      <div className="flex-1 min-h-0">
        <div className="mb-2 text-sm font-semibold text-slate-300">
          Channel {displayCh0} - {sensorName1}
          <span className="text-slate-500 ml-2">({data1.length} points)</span>
        </div>
        <SignalChart
          title={`Ch${displayCh0} ${sensorName1}`}
          data={data1}
          timeWindowMs={timeWindowMs}
          color="rgb(59, 130, 246)"
          height={250}
          showGrid={showGrid}
          scannerX={scannerX}
        />
      </div>

      <div className="flex-1 min-h-0">
        <div className="mb-2 text-sm font-semibold text-slate-300">
          Channel {displayCh1} - {sensorName2}
          <span className="text-slate-500 ml-2">({data2.length} points)</span>
        </div>
        <SignalChart
          title={`Ch${displayCh1} ${sensorName2}`}
          data={data2}
          timeWindowMs={timeWindowMs}
          color="rgb(16, 185, 129)"
          height={250}
          showGrid={showGrid}
          scannerX={scannerX}
        />
      </div>

      <div className="bg-slate-800 rounded p-3 text-xs text-slate-400 font-mono space-y-1">
        <div>
          <span className="text-blue-400">Ch0</span>: {ch0Data.length} pts{' '}
          <span className="ml-4 text-green-400">Ch1</span>: {ch1Data.length} pts{' '}
          <span className="ml-4 text-yellow-400">Ch2</span>: {ch2Data.length} pts{' '}
          <span className="ml-4 text-red-400">Ch3</span>: {ch3Data.length} pts
        </div>
        <div>
          <span className="text-cyan-400">Scanner (ts)</span>: {scannerX ? new Date(scannerX).toLocaleTimeString() : '—'}{' '}
          <span className="ml-4 text-cyan-300">({scannerPercent.toFixed(1)}%)</span>
          <span className="ml-4"><span className="text-orange-400">Window</span>: {(timeWindowMs / 1000).toFixed(1)}s</span>
        </div>
        <div>
          <span className="text-lime-400">Display Channels</span>: [{displayCh0}, {displayCh1}] <span className="ml-4"><span className="text-pink-400">Active</span>: {activeChannels.join(', ')}</span>
        </div>
        {wsData?.raw?.stream_name && (
          <div><span className="text-violet-400">Stream</span>: {wsData.raw.stream_name}</div>
        )}
      </div>
    </div>
  )
}
