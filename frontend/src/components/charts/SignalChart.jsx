import React, { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function SignalChart({ title, data, color, timeWindow }) {
  const displayData = useMemo(() => {
    return data.slice(-timeWindow)
  }, [data, timeWindow])
  
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        <div className="text-sm text-gray-600">
          {displayData.length > 0 && (
            <>
              <span>Min: {Math.min(...displayData.map(d => d.value)).toFixed(3)}</span>
              <span className="mx-2">|</span>
              <span>Max: {Math.max(...displayData.map(d => d.value)).toFixed(3)}</span>
              <span className="mx-2">|</span>
              <span>Mean: {(displayData.reduce((a, b) => a + b.value, 0) / displayData.length).toFixed(3)}</span>
            </>
          )}
        </div>
      </div>
      
      <div className="chart-container">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={displayData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="time" 
              domain={['dataMin', 'dataMax']}
              tickFormatter={(t) => new Date(t).toLocaleTimeString()}
            />
            <YAxis domain={[-1, 1]} />
            <Tooltip 
              labelFormatter={(t) => new Date(t).toLocaleTimeString()}
              formatter={(value) => value.toFixed(4)}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="value" 
              stroke={color} 
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
