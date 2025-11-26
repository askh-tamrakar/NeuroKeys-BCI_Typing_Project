import React, { useState, useEffect } from 'react'

export default function CommandVisualizer({ wsData }) {
  const [commands, setCommands] = useState([])
  const [liveText, setLiveText] = useState('')
  const [activeKey, setActiveKey] = useState(null)
  
  const keyboard = [
    ['A', 'B', 'C', 'D', 'E'],
    ['F', 'G', 'H', 'I', 'J'],
    ['K', 'L', 'M', 'N', 'O'],
    ['P', 'Q', 'R', 'S', 'T'],
    ['U', 'V', 'W', 'X', 'Y', 'Z']
  ]
  
  useEffect(() => {
    if (!wsData) return
    
    try {
      const parsed = JSON.parse(wsData.data)
      if (parsed.type !== 'command') return
      
      const cmd = { ...parsed, id: Date.now() }
      setCommands(prev => [cmd, ...prev].slice(0, 20))
      
      setActiveKey(parsed.command)
      setTimeout(() => setActiveKey(null), 300)
      
      if (parsed.command === 'ENTER') {
        // Trigger enter animation
      } else if (parsed.command === 'BACKSPACE') {
        setLiveText(prev => prev.slice(0, -1))
      } else {
        setLiveText(prev => prev + parsed.command)
      }
    } catch (e) {
      console.error('Command parse error:', e)
    }
  }, [wsData])
  
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Command Recognition</h2>
        
        <div className="bg-gray-100 rounded-lg p-4 mb-4">
          <div className="text-sm text-gray-600 mb-2">Live Text Preview:</div>
          <div className="text-2xl font-mono min-h-[3rem] bg-white rounded p-3">
            {liveText || <span className="text-gray-400">Waiting for input...</span>}
          </div>
        </div>
        
        <div className="space-y-2 mb-4">
          {keyboard.map((row, i) => (
            <div key={i} className="flex justify-center gap-2">
              {row.map(key => (
                <div
                  key={key}
                  className={`command-key w-12 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                    ${activeKey === key 
                      ? 'bg-blue-600 border-blue-500 text-white scale-110' 
                      : 'border-gray-300 bg-white text-gray-700'}`}
                >
                  {key}
                </div>
              ))}
            </div>
          ))}
          <div className="flex justify-center gap-2 mt-4">
            <div 
              className={`command-key px-6 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                ${activeKey === 'BACKSPACE' 
                  ? 'bg-blue-600 border-blue-500 text-white scale-110' 
                  : 'border-gray-300 bg-white text-gray-700'}`}
            >
              ⌫ BACK
            </div>
            <div 
              className={`command-key px-12 h-12 flex items-center justify-center rounded-lg border-2 font-semibold transition-all
                ${activeKey === 'ENTER' 
                  ? 'bg-green-600 border-green-500 text-white scale-110' 
                  : 'border-gray-300 bg-white text-gray-700'}`}
            >
              ↵ ENTER
            </div>
          </div>
        </div>
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Command Timeline</h3>
        <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-hide">
          {commands.length === 0 ? (
            <p className="text-gray-500 text-center py-8">Waiting for recognized commands...</p>
          ) : (
            commands.map(cmd => (
              <div key={cmd.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-2xl font-bold text-blue-600">{cmd.command}</span>
                  <span className="text-sm text-gray-600">
                    {new Date(cmd.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-sm font-medium text-gray-700">
                  {(cmd.confidence * 100).toFixed(1)}%
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
