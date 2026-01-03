// SignalChart.jsx
import React, { useMemo, useRef } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, ReferenceDot, ReferenceArea } from 'recharts'
import { ChartSpline, ZoomIn, ArrowUpDown, ArrowDown, ArrowUp, Sigma, Clock, Minus, Plus, Ban } from 'lucide-react'
import ElasticSlider from '../ui/ElasticSlider'
import '../../styles/live/SignalChart.css'

const DEFAULT_PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f97316', '#06d6a0'
]

export default function SignalChart({
  graphNo,
  title,
  data = [],
  byChannel = null,
  color = '#3b82f6',
  timeWindowMs = 10000,
  channelLabelPrefix = 'Ch',
  height = 300,
  yDomainProp = null,
  showGrid = true,
  scannerX = null,
  annotations = [],
  channelColors = null,
  markedWindows = [],
  activeWindow = null,
  tickCount = 7,
  curveType = "monotone",
  currentZoom = 1,
  currentManual = "",
  onZoomChange = null,
  onRangeChange = null,
  onTimeWindowChange = null,
  onColorChange = null,
  disabled = false
}) {
  const merged = useMemo(() => {
    if (!byChannel || typeof byChannel !== 'object') {
      const arr = Array.isArray(data) ? data.slice() : []
      if (arr.length === 0) return { dataArray: [], channelKeys: [] }
      // ensure numeric times/values
      arr.forEach(d => {
        d.time = Number(d.time);
        d.value = (d.value === null || d.value === undefined) ? null : Number(d.value)
      })
      // sort ascending
      arr.sort((a, b) => a.time - b.time)
      const newest = arr[arr.length - 1]?.time || Date.now()
      const cutoff = newest - timeWindowMs
      const filtered = arr.filter(d => Number(d.time) >= cutoff)
      return { dataArray: filtered.map(d => ({ time: Number(d.time), value: Number(d.value) })), channelKeys: [] }
    }

    const chKeys = Object.keys(byChannel).map(k => k).sort((a, b) => Number(a) - Number(b))
    if (chKeys.length === 0) return { dataArray: [], channelKeys: [] }

    const allTimestampsSet = new Set()
    const chFiltered = {}
    chKeys.forEach((k) => {
      const arr = Array.isArray(byChannel[k]) ? byChannel[k].slice() : []
      arr.forEach(d => { if (d) { d.time = Number(d.time); d.value = Number(d.value) } })
      if (arr.length === 0) { chFiltered[k] = []; return }
      const newest = arr[arr.length - 1].time || Date.now()
      const cutoff = newest - timeWindowMs
      const filtered = arr.filter(d => Number(d.time) >= cutoff)
      filtered.forEach(p => allTimestampsSet.add(Number(p.time)))
      filtered.sort((a, b) => a.time - b.time)
      chFiltered[k] = filtered
    })

    if (allTimestampsSet.size === 0) return { dataArray: [], channelKeys: chKeys }

    const allTimestamps = Array.from(allTimestampsSet).sort((a, b) => a - b)

    const dataArray = allTimestamps.map(ts => {
      const row = { time: ts }
      chKeys.forEach(k => {
        const arr = chFiltered[k]
        if (!arr || arr.length === 0) {
          row[`ch${k}`] = null
          return
        }
        let lo = 0, hi = arr.length - 1, best = arr[0]
        while (lo <= hi) {
          const mid = Math.floor((lo + hi) / 2)
          const midT = arr[mid].time
          if (midT === ts) { best = arr[mid]; break }
          if (midT < ts) lo = mid + 1
          else hi = mid - 1
          if (Math.abs(arr[mid].time - ts) < Math.abs(best.time - ts)) best = arr[mid]
        }
        const approxInterval = arr.length >= 2 ? Math.abs(arr[arr.length - 1].time - arr[0].time) / (arr.length - 1) : 1000
        const maxAcceptDist = Math.max(approxInterval * 0.6, 1)
        row[`ch${k}`] = Math.abs(best.time - ts) <= maxAcceptDist ? Number(best.value) : null
      })
      return row
    })

    return { dataArray, channelKeys: chKeys }
  }, [data, byChannel, timeWindowMs])

  let dataArray = merged.dataArray || []
  const channelKeys = merged.channelKeys || []

  const xTimes = dataArray.map(d => Number(d.time)).filter(t => Number.isFinite(t))
  let dataMin = xTimes.length ? Math.min(...xTimes) : null
  let dataMax = xTimes.length ? Math.max(...xTimes) : null

  const tinyThreshold = Math.max(1, timeWindowMs * 0.001) // e.g., 1ms or 0.1% of window
  if (dataMin === null || dataMax === null || (dataMax - dataMin) < tinyThreshold) {
    const now = Date.now()
    const n = Math.max(1, dataArray.length)
    const base = now - timeWindowMs
    const stride = timeWindowMs / Math.max(1, n)
    dataArray = dataArray.map((row, i) => {
      return { ...row, time: Math.round(base + (i + 1) * stride) }
    })
    // recompute min/max
    const newTimes = dataArray.map(d => d.time)
    dataMin = Math.min(...newTimes)
    dataMax = Math.max(...newTimes)
  }

  // collect values for Y domain
  const values = []
  if (byChannel && channelKeys.length) {
    dataArray.forEach(row => {
      channelKeys.forEach(k => {
        const v = row[`ch${k}`]
        if (Number.isFinite(v)) values.push(v)
      })
    })
  } else {
    dataArray.forEach(d => {
      const v = d.value
      if (Number.isFinite(v)) values.push(v)
    })
  }

  const min = values.length ? Math.min(...values) : -1
  const max = values.length ? Math.max(...values) : 1
  const mean = values.length ? (values.reduce((a, b) => a + b, 0) / values.length) : 0

  const pad = Math.max((max - min) * 0.1, 0.01)
  const calculatedDomain = [min - pad, max + pad]
  const finalYDomain = yDomainProp || calculatedDomain

  // compute scannerXValue robustly (if scannerX is null it stays null)
  let scannerXValue = null
  if (scannerX !== null && scannerX !== undefined) {
    // if scannerX is percent 0..100
    if (typeof scannerX === 'number' && scannerX >= 0 && scannerX <= 100 && dataMin !== null && dataMax !== null) {
      scannerXValue = dataMin + (dataMax - dataMin) * (scannerX / 100)
    } else {
      // otherwise assume timestamp / x coordinate; ensure it's numeric
      const n = Number(scannerX)
      if (Number.isFinite(n)) scannerXValue = n
    }
    // clamp into dataMin..dataMax to avoid drawing outside visible domain
    if (scannerXValue !== null && dataMin !== null && dataMax !== null) {
      if (scannerXValue < dataMin) scannerXValue = dataMin
      if (scannerXValue > dataMax) scannerXValue = dataMax
    }
  }

  // Helper to get color for window status (Synchronized with TimeSeriesZoomChart)
  const getWindowColor = (status, isMissed) => {
    if (isMissed) return 'rgba(239, 68, 68, 0.2)'; // Red
    if (status === 'correct') return 'rgba(16, 185, 129, 0.2)'; // Green
    if (status === 'incorrect') return 'rgba(245, 158, 11, 0.2)'; // Orange
    return 'rgba(156, 163, 175, 0.1)'; // Gray
  };

  // Calculate explicit ticks if tickCount is provided to enforce exact number of lines
  const ticks = useMemo(() => {
    if (!tickCount || tickCount < 2) return null
    const [min, max] = finalYDomain
    const step = (max - min) / (tickCount - 1)
    const result = []
    for (let i = 0; i < tickCount; i++) {
      result.push(min + (i * step))
    }
    return result
  }, [finalYDomain, tickCount])

  const colorInputRef = useRef(null)

  return (
    <div className={`signal-chart-container ${disabled ? 'signal-chart-disabled' : ''}`}>

      <div className="chart-header">
        <h3 className="chart-title">
          <button
            onClick={() => colorInputRef.current?.click()}
            className="p-1 hover:bg-muted/10 rounded-full transition-colors cursor-pointer group"
            title="Change Graph Color"
          >
            <ChartSpline size={32} strokeWidth={3} style={{ color: color }} className="mr-2 group-hover:scale-110 transition-transform" />
          </button>

          {/* Hidden Color Input */}
          <input
            type="color"
            ref={colorInputRef}
            value={color.length === 7 ? color : "#3b82f6"} // Ensure valid hex code if possible, though browser handles rgb usually
            onChange={(e) => onColorChange && onColorChange(e.target.value)}
            style={{ display: 'none' }}
          />

          {graphNo}
          <span className="channel-color-dot" style={{ backgroundColor: color }}></span>
          {title}
        </h3>

        <div className="channel-controls">
          {/* Time Window Control (New) */}
          <div className="time-window-control">
            <span className="control-label"><Clock size={24} /> Time</span>
            <div className="w-64">
              <ElasticSlider
                defaultValue={(timeWindowMs || 10000) / 1000}
                startingValue={1}
                maxValue={30}
                stepSize={1}
                isStepped={true}
                onChange={(val) => onTimeWindowChange && onTimeWindowChange(val * 1000)}
                leftIcon={<Minus size={18} className="text-muted" />}
                rightIcon={<Plus size={18} className="text-muted" />}
                className="w-full h-6"
              />
            </div>
          </div>

          {/* Zoom Buttons */}
          <div className="zoom-controls">
            <span className="control-label flex items-center gap-1"><ZoomIn size={24} /> ZOOM</span>
            {[1, 2, 3, 5, 10, 25, 50].map(z => (
              <button
                key={z}
                onClick={() => onZoomChange && onZoomChange(z)}
                className={`zoom-btn ${currentZoom === z && !currentManual ? 'active' : 'inactive'}`}
              >
                {z}x
              </button>
            ))}
          </div>

          <div className="separator-small"></div>

          {/* Manual Range Input */}
          <div className="range-input-container">
            <span className="control-label flex items-center gap-1"><ArrowUpDown size={24} /> RANGE</span>
            <input
              type="number"
              placeholder="+/-"
              value={currentManual}
              onChange={(e) => onRangeChange && onRangeChange(e.target.value)}
              className="range-input"
            />
          </div>

          <div className="separator-small"></div>

          <div className="range-display">
            +/-{(Math.abs(finalYDomain[1])).toFixed(0)} uV
          </div>
        </div>

        {/* Stats */}
        <div className="chart-stats">
          {dataArray.length > 0 && (
            <>
              <div className="stat-item">
                <span className="stat-label-chart"><ArrowDown size={18} /> Min</span>
                <span className="stat-value">{min.toFixed(2)}</span>
              </div>
              <div className="stat-separator"></div>
              <div className="stat-item">
                <span className="stat-label-chart"><ArrowUp size={18} /> Max</span>
                <span className="stat-value">{max.toFixed(2)}</span>
              </div>
              <div className="stat-separator"></div>
              <div className="stat-item">
                <span className="stat-label-chart"><Sigma size={18} /> Mean</span>
                <span className="stat-value">{mean.toFixed(2)}</span>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="chart-area" style={{ height: height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={dataArray}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.3} vertical={false} />}
            <ReferenceLine y={0} stroke="var(--border)" strokeOpacity={0.5} />
            {scannerXValue !== null && (
              <ReferenceLine x={scannerXValue} stroke="var(--accent)" strokeOpacity={0.9} strokeWidth={1.5} />
            )}

            {/* Render Marked Windows */}
            {markedWindows.map((win) => {
              const x1 = win.startTime % timeWindowMs;
              const x2 = win.endTime % timeWindowMs;
              if (isNaN(x1) || isNaN(x2)) return null;
              return (
                <ReferenceArea
                  key={win.id}
                  x1={x1}
                  x2={x2}
                  fill={getWindowColor(win.status, win.isMissedActual)}
                  stroke={win.isMissedActual ? '#ef4444' : (win.status === 'correct' ? '#10b981' : '#9ca3af')}
                  strokeOpacity={0.5}
                  label={{ position: 'top', value: win.label, fill: 'var(--muted)', fontSize: 10 }}
                />
              );
            })}

            {activeWindow && !isNaN(activeWindow.startTime) && !isNaN(activeWindow.endTime) && (
              <ReferenceArea
                x1={activeWindow.startTime % timeWindowMs}
                x2={activeWindow.endTime % timeWindowMs}
                fill="var(--primary)"
                fillOpacity={0.1}
                stroke="var(--primary)"
                strokeDasharray="3 3"
              />
            )}

            {/* Render Annotations (Blinks) */}
            {annotations.map((ann, idx) => (
              <ReferenceDot
                key={`ann-${idx}`}
                x={ann.x}
                y={ann.y}
                r={6}
                fill={ann.color || "red"}
                stroke="white"
                strokeWidth={2}
                label={{ position: 'top', value: ann.label, fill: ann.color || "red", fontSize: 12, fontWeight: 'bold' }}
                isFront={true}
              />
            ))}

            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(t) => (Number.isFinite(t) && t < 86400000) ? (t / 1000).toFixed(1) + 's' : new Date(t).toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })}
              stroke="var(--muted)"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              dy={10}
            />
            <YAxis
              domain={finalYDomain}
              stroke="var(--muted)"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => v.toFixed(0)}
              width={40}
              ticks={ticks}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--surface)',
                borderColor: 'var(--border)',
                borderRadius: '8px',
                color: 'var(--text)',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
              }}
              labelStyle={{ color: 'var(--muted)', marginBottom: '0.5rem', fontSize: '12px' }}
              itemStyle={{ fontSize: '12px', padding: '2px 0' }}
              labelFormatter={(t) => new Date(Number(t)).toLocaleTimeString() + `.${new Date(Number(t)).getMilliseconds()}`}
              formatter={(v) => [Number(v).toFixed(3), '']}
            />
            <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />

            {byChannel && channelKeys.length ? (
              channelKeys.map((k, idx) => (
                <Line
                  key={`ch-${k}`}
                  type={curveType}
                  dataKey={`ch${k}`}
                  name={`${channelLabelPrefix ?? 'Ch'} ${k}`}
                  stroke={channelColors?.[k] || DEFAULT_PALETTE[idx % DEFAULT_PALETTE.length]}
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              ))
            ) : (
              <Line
                type={curveType}
                dataKey="value"
                name="Signal"
                stroke={color}
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
                connectNulls={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
