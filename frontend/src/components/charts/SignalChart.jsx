// SignalChart.jsx
import React, { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, ReferenceDot, ReferenceArea } from 'recharts'

const DEFAULT_PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f97316', '#06d6a0'
]

export default function SignalChart({
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
  annotations = [], // New Prop [{ x: timestamp, y: value, label: string, color: string }]
  channelColors = null, // New Prop { [key]: colorString }
  markedWindows = [],
  activeWindow = null
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

  // If timestamps have almost no variance (dataMin === dataMax or tiny range), synthesize an even timescale
  const xTimes = dataArray.map(d => Number(d.time)).filter(t => Number.isFinite(t))
  let dataMin = xTimes.length ? Math.min(...xTimes) : null
  let dataMax = xTimes.length ? Math.max(...xTimes) : null

  const tinyThreshold = Math.max(1, timeWindowMs * 0.001) // e.g., 1ms or 0.1% of window
  if (dataMin === null || dataMax === null || (dataMax - dataMin) < tinyThreshold) {
    // synthesize times evenly spaced across the timeWindowMs so chart can render smoothly
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

  return (
    <div className="bg-card surface-panel border border-border shadow-sm rounded-xl overflow-hidden flex flex-col h-full bg-surface">
      <div className="px-5 py-3 border-b border-border bg-bg/50 backdrop-blur-sm flex justify-between items-center">
        <h3 className="font-bold text-text flex items-center gap-2">
          <span className="w-2 h-6 rounded-full" style={{ backgroundColor: color }}></span>
          {title}
        </h3>

        <div className="flex gap-4 text-xs font-mono text-muted">
          {dataArray.length > 0 && (
            <>
              <div className="flex flex-col items-end">
                <span className="opacity-50 text-[10px] uppercase tracking-wider">Min</span>
                <span className="font-medium text-text">{min.toFixed(2)}</span>
              </div>
              <div className="w-[1px] h-6 bg-border/50"></div>
              <div className="flex flex-col items-end">
                <span className="opacity-50 text-[10px] uppercase tracking-wider">Max</span>
                <span className="font-medium text-text">{max.toFixed(2)}</span>
              </div>
              <div className="w-[1px] h-6 bg-border/50"></div>
              <div className="flex flex-col items-end">
                <span className="opacity-50 text-[10px] uppercase tracking-wider">Mean</span>
                <span className="font-medium text-text">{mean.toFixed(2)}</span>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="relative w-full p-2 flex-grow" style={{ height: height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={dataArray}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.3} />}
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
              tickFormatter={(v) => v.toFixed(1)}
              width={40}
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
                  type="monotone"
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
                type="monotone"
                dataKey="value"
                name="Signal"
                stroke={color}
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
