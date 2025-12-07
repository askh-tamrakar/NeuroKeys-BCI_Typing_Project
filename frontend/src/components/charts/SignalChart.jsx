import React, { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

/**
 * SignalChart supports:
 * - single series: pass `data` = [{time, value}, ...]
 * - multi-channel overlay: pass `byChannel` = { 0: [{time, value}, ...], 1: [...] }
 *
 * When byChannel is provided, we merge timestamps into one data array with fields:
 * { time, ch0: val, ch1: val, ... } so Recharts can plot multiple lines.
 *
 * Props:
 * - title
 * - data
 * - byChannel
 * - timeWindowMs (ms)
 * - color (single series) or a palette used for multi channels
 * - channelLabelPrefix: string for legend e.g., 'Ch'
 */

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
  showGrid = true
}) {
  // If byChannel present -> merge into single array
  const merged = useMemo(() => {
    if (!byChannel || typeof byChannel !== 'object') {
      // single series path: simply clip to time window
      const arr = Array.isArray(data) ? data.slice() : []
      if (arr.length === 0) return { dataArray: [], channelKeys: [] }
      const newest = arr[arr.length - 1].time || Date.now()
      const cutoff = newest - timeWindowMs
      const filtered = arr.filter(d => Number(d.time) >= cutoff)
      // sort
      filtered.sort((a, b) => a.time - b.time)
      // map to same shape (time & value)
      return { dataArray: filtered.map(d => ({ time: Number(d.time), value: Number(d.value) })), channelKeys: [] }
    }

    // Multi-channel: get each channel array, filter by time window relative to their newest
    const chKeys = Object.keys(byChannel).map(k => k).sort((a, b) => Number(a) - Number(b))
    if (chKeys.length === 0) return { dataArray: [], channelKeys: [] }

    // Build set of timestamps from all channels (coarse union)
    const allTimestampsSet = new Set()
    const chFiltered = {}
    chKeys.forEach((k) => {
      const arr = Array.isArray(byChannel[k]) ? byChannel[k].slice() : []
      if (arr.length === 0) {
        chFiltered[k] = []
        return
      }
      const newest = arr[arr.length - 1].time || Date.now()
      const cutoff = newest - timeWindowMs
      const filtered = arr.filter(d => Number(d.time) >= cutoff)
      filtered.forEach(p => allTimestampsSet.add(Number(p.time)))
      // sort ascending
      filtered.sort((a, b) => a.time - b.time)
      chFiltered[k] = filtered
    })

    // If there are no timestamps -> empty
    if (allTimestampsSet.size === 0) return { dataArray: [], channelKeys: chKeys }

    // Convert set -> sorted array
    const allTimestamps = Array.from(allTimestampsSet).sort((a, b) => a - b)

    // For each timestamp, pick the nearest sample from each channel (simple nearest-neighbor)
    // Build merged rows: { time, ch0: val, ch1: val, ... }
    const dataArray = allTimestamps.map(ts => {
      const row = { time: ts }
      chKeys.forEach(k => {
        const arr = chFiltered[k]
        if (!arr || arr.length === 0) {
          row[`ch${k}`] = null
          return
        }
        // binary search nearest index (arr sorted by time)
        let lo = 0, hi = arr.length - 1, best = arr[0]
        while (lo <= hi) {
          const mid = Math.floor((lo + hi) / 2)
          const midT = arr[mid].time
          if (midT === ts) { best = arr[mid]; break }
          if (midT < ts) { lo = mid + 1 }
          else { hi = mid - 1 }
          // track nearest by difference
          if (Math.abs(arr[mid].time - ts) < Math.abs(best.time - ts)) best = arr[mid]
        }
        // if nearest is too far (e.g., > half sample interval), we can set null to avoid weird interpolation
        // compute approx sample interval from arr
        const approxInterval = arr.length >= 2 ? Math.abs(arr[arr.length - 1].time - arr[0].time) / (arr.length - 1) : 1000
        const maxAcceptDist = Math.max(approxInterval * 0.6, 1) // accept within ~60% of interval
        row[`ch${k}`] = Math.abs(best.time - ts) <= maxAcceptDist ? Number(best.value) : null
      })
      return row
    })

    return { dataArray, channelKeys: chKeys }
  }, [data, byChannel, timeWindowMs])

  const dataArray = merged.dataArray || []
  const channelKeys = merged.channelKeys || []

  // dynamic y domain (consider all channels)
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

  // Calculate stats
  const min = values.length ? Math.min(...values) : -1
  const max = values.length ? Math.max(...values) : 1
  const mean = values.length ? (values.reduce((a, b) => a + b, 0) / values.length) : 0

  // Determine domain
  const pad = Math.max((max - min) * 0.1, 0.01)
  const calculatedDomain = [min - pad, max + pad]
  const finalYDomain = yDomainProp || calculatedDomain

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
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })}
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
                  stroke={DEFAULT_PALETTE[idx % DEFAULT_PALETTE.length]}
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
                fill={`url(#gradient-${title})`}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
