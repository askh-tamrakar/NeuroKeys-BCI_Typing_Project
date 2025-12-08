import React, { useState, useEffect, useRef, useMemo } from 'react'
import SignalChart from '../charts/SignalChart'

/**
 * LiveView (Oscilloscope Mode)
 * - Renders EEG data with a "stationary grid".
 * - Vertical "scanner bar" moves left to right.
 * - Data overwrites old values.
 * - Config is passed from parent (LiveDashboard).
 */
export default function LiveView({ wsData, config, isPaused }) {
  // Config extracts
  const timeWindowMs = config?.display?.timeWindowMs || 10000
  const samplingRate = config?.sampling_rate || 512
  const showGrid = config?.display?.showGrid ?? true
  const channelMapping = config?.channel_mapping || {}

  // Display Mode
  // If multiple channels enabled -> Overlay or Single?
  // For this demo, let's stick to "Overlay" if multi-channel, or allow user mapped "Single"
  // But the requirement says "two vertically stacked graphs". 
  // Let's interpret "channel selection mapping for each of the two graphs" 
  // as: Graph 1 shows Channel X, Graph 2 shows Channel Y.
  // We need state for "Graph 1 Channel" and "Graph 2 Channel".
  // Actually sidebar has channel mapping "ch0: {sensor: 'EEG'}"... 
  // The requirement "channel selection mapping for each of the two graphs" implies the USER selects which channel goes to Graph 1 and 2.
  // Sidebar just maps sensors.
  // Let's add local state for "Graph 1 Source" and "Graph 2 Source" or assume Sidebar handles it.
  // "Sidebar Functionality: ... channel selection mapping for each of the two graphs"
  // Okay, keeping it simple: I will render TWO graphs. I need to know WHICH channel to show on each.
  // I will make default: Graph 1 = Ch 0, Graph 2 = Ch 1.
  // Ideally these should be in `config` or local state controlled by Sidebar. 
  // Since `config` has `channel_mapping`, maybe I add `graph_mapping` to config? or just use local state here?
  // Requirement: "Sidebar Functionality: ... channel mapping ..." -> implies Sidebar controls this.
  // I'll assume config has `graph_sources: { graph1: 'ch0', graph2: 'ch1' }` or similar.
  // If not, I'll default to 0 and 1.

  const [graphSources, setGraphSources] = useState({
    top: 'ch0',
    bottom: 'ch1'
  })

  // We can let the user change this? Or assume Sidebar does?
  // The Sidebar I built updates `config.channel_mapping`, but didn't explicitly have "Graph 1 Source Selector".
  // I will treat `config.channel_mapping` as "What is on Ch0?" 
  // and I will add selectors in this view or just picking the first two enabled channels.
  // Let's pick first two enabled.

  // State for data buffers
  // We need a fixed grid of X points.
  // To keep 60fps with Recharts, fewer points is better. 
  // 10s @ 512Hz = 5000 points. Recharts might struggle. 
  // We will downsample for display. e.g. 500 points (10s window -> 50Hz display res).
  const DISPLAY_POINTS = 500

  const initBuffer = () => {
    const arr = new Array(DISPLAY_POINTS).fill(0).map((_, i) => ({
      time: (i / DISPLAY_POINTS) * timeWindowMs, // 0..10000
      val: 0
    }))
    return arr
  }

  // Refs to store the "Live" data without triggering re-renders on every sample
  // structure: { [chKey]: [{time, val}, ...] }
  // We store the full resolution or display resolution? 
  // Let's store display resolution for performance.
  const buffersRef = useRef({})

  // We also track the "Scanner Cursor" position (0..timeWindowMs)
  const cursorRef = useRef(0)

  // Force update trigger
  const [tick, setTick] = useState(0)

  // Initialize buffers for all possible channels
  useEffect(() => {
    Object.keys(channelMapping).forEach(key => {
      if (!buffersRef.current[key]) {
        buffersRef.current[key] = initBuffer()
      }
    })
    // Also re-init if timeWindow changes
    // (Existing buffers would be invalid scale)
    buffersRef.current = {} // clear to force re-init

    // Animation loop
    let animId
    const loop = () => {
      if (!isPaused) {
        setTick(t => t + 1)
      }
      animId = requestAnimationFrame(loop)
    }
    animId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(animId)
  }, [timeWindowMs, isPaused]) // eslint-disable-line

  // Handle incoming data
  useEffect(() => {
    if (!wsData || isPaused) return

    let payload = null
    try {
      payload = typeof wsData === 'string' ? JSON.parse(wsData) : wsData
      if (wsData.data && typeof wsData.data === 'string') payload = JSON.parse(wsData.data)
    } catch { return }

    if (!payload?.window) return

    const channels = payload.window
    const endTs = Number(payload.timestamp) || Date.now()
    // const fs = Number(payload.fs) || samplingRate // Use payload FS if available
    const fs = samplingRate // Use config FS to match time window logic consistently
    const dt = 1000 / fs

    // For each channel
    channels.forEach((samples, chIdx) => {
      // Map index to key
      const chKey = `ch${chIdx}`
      // Ensure buffer exists
      if (!buffersRef.current[chKey]) {
        buffersRef.current[chKey] = initBuffer()
      }

      const buffer = buffersRef.current[chKey]
      const nSamples = samples.length

      for (let i = 0; i < nSamples; i++) {
        // Absolute time of this sample
        // timestamp is end of packet?
        // "timestamp": 12345.678
        // Sample i time = endTs - (N - 1 - i) * dt
        const tAbs = endTs - (nSamples - 1 - i) * dt

        // Map to window [0, timeWindowMs]
        // We align 0 to some arbitrary start or just mod?
        // Scanner mode usually implies: x = t % T
        const posMs = tAbs % timeWindowMs
        // handle negative mod
        const safePos = posMs < 0 ? posMs + timeWindowMs : posMs

        cursorRef.current = safePos // Update global cursor (shared)

        // Map safePos to index 0..DISPLAY_POINTS
        const idx = Math.floor((safePos / timeWindowMs) * DISPLAY_POINTS)

        if (idx >= 0 && idx < buffer.length) {
          // Update value
          buffer[idx].val = samples[i]
          // Also clear slightly ahead to create a "gap" or "scanner bar" affect? 
          // Just overwriting is fine for bar.
        }
      }
    })

  }, [wsData, isPaused, timeWindowMs, samplingRate])

  // Prepare data for rendering
  // We render the two selected mapped channels
  // graphSources could be controlled by UI, for now hardcoded to first 2 enabled or just ch0/ch1
  const activeKeys = Object.keys(channelMapping).filter(k => channelMapping[k].enabled)
  const key1 = activeKeys[0] || 'ch0'
  const key2 = activeKeys[1] || 'ch1'

  // Get data slices
  const data1 = buffersRef.current[key1] ? [...buffersRef.current[key1]] : []
  const data2 = buffersRef.current[key2] ? [...buffersRef.current[key2]] : []

  // To make chart render "scanner bar", we pass `scannerX` to SignalChart ref line
  // And `data` is just static X axis points with updated Ys.

  // Recharts needs `time` for XAxis. Our buffer has `time` 0..window.

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Graph 1 */}
      <div className="flex-1 min-h-0 bg-surface rounded-xl border border-border overflow-hidden p-2 relative">
        <div className="absolute top-3 left-4 z-10 flex gap-2">
          <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-1 rounded">
            {channelMapping[key1]?.sensor || 'Sensor'} ({key1})
          </span>
        </div>
        <SignalChart
          title=""
          data={data1.map(d => ({ time: d.time, value: d.val }))} // Map 'val' to 'value'
          color="#3b82f6"
          timeWindowMs={timeWindowMs}
          height="100%"
          showGrid={showGrid}
          scannerX={cursorRef.current}
          yDomainProp={['auto', 'auto']} // Auto scale? Or fixed?
        />
      </div>

      {/* Graph 2 */}
      <div className="flex-1 min-h-0 bg-surface rounded-xl border border-border overflow-hidden p-2 relative">
        <div className="absolute top-3 left-4 z-10 flex gap-2">
          <span className="text-xs font-bold text-emerald-500 bg-emerald-500/10 px-2 py-1 rounded">
            {channelMapping[key2]?.sensor || 'Sensor'} ({key2})
          </span>
        </div>
        <SignalChart
          title=""
          data={data2.map(d => ({ time: d.time, value: d.val }))}
          color="#10b981"
          timeWindowMs={timeWindowMs}
          height="100%"
          showGrid={showGrid}
          scannerX={cursorRef.current}
          yDomainProp={['auto', 'auto']}
        />
      </div>
    </div>
  )
}
