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
  channelLabelPrefix = 'Ch'
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
      return { dataArray: filtered.map(d => ({ time: Number(d.time), value: Number(d.value) })) , channelKeys: [] }
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
  const min = values.length ? Math.min(...values) : -1
  const max = values.length ? Math.max(...values) : 1
  const pad = Math.max((max - min) * 0.1, 0.01)
  const yDomain = [min - pad, max + pad]
  const mean = values.length ? (values.reduce((a, b) => a + b, 0) / values.length) : 0

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        <div className="text-sm text-gray-600">
          {dataArray.length > 0 && (
            <>
              <span>Min: {min.toFixed(3)}</span>
              <span className="mx-2">|</span>
              <span>Max: {max.toFixed(3)}</span>
              <span className="mx-2">|</span>
              <span>Mean: {mean.toFixed(3)}</span>
            </>
          )}
        </div>
      </div>

      <div className="chart-container" style={{ width: '100%', height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={dataArray}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tickFormatter={(t) => {
                const n = Number(t)
                return Number.isFinite(n) ? new Date(n).toLocaleTimeString() : String(t)
              }}
            />
            <YAxis domain={yDomain} />
            <Tooltip
              labelFormatter={(t) => {
                const n = Number(t)
                return Number.isFinite(n) ? new Date(n).toLocaleTimeString() : String(t)
              }}
              formatter={(v) => (Number.isFinite(Number(v)) ? Number(v).toFixed(4) : v)}
            />
            <Legend />
            {byChannel && channelKeys.length ? (
              channelKeys.map((k, idx) => (
                <Line
                  key={`ch-${k}`}
                  type="monotone"
                  dataKey={`ch${k}`}
                  name={`${channelLabelPrefix ?? 'Ch'} ${k}`}
                  stroke={DEFAULT_PALETTE[idx % DEFAULT_PALETTE.length]}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              ))
            ) : (
              <Line
                type="monotone"
                dataKey="value"
                stroke={color}
                dot={false}
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
