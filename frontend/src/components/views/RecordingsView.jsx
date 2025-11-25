import React, { useState } from 'react'

export default function RecordingsView() {
  const [recordings, setRecordings] = useState([])
  const [isRecording, setIsRecording] = useState(false)
  const [recordingName, setRecordingName] = useState('')
  
  const startRecording = () => {
    const name = recordingName || `Recording ${recordings.length + 1}`
    setIsRecording(true)
    console.log('Recording started:', name)
  }
  
  const stopRecording = () => {
    setIsRecording(false)
    const newRecording = {
      id: Date.now(),
      name: recordingName || `Recording ${recordings.length + 1}`,
      timestamp: Date.now(),
      duration: 10,
      size: '2.5 MB'
    }
    setRecordings(prev => [newRecording, ...prev])
    setRecordingName('')
  }
  
  const downloadRecording = (recording, format) => {
    // Mock download
    const data = format === 'JSON' 
      ? JSON.stringify({ recording: recording.name, format }, null, 2)
      : `timestamp,EEG,EOG,EMG\n${Date.now()},0.5,-0.2,0.3\n`
    
    const blob = new Blob([data], { type: format === 'JSON' ? 'application/json' : 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${recording.name}.${format.toLowerCase()}`
    a.click()
    URL.revokeObjectURL(url)
  }
  
  const deleteRecording = (id) => {
    if (confirm('Delete this recording?')) {
      setRecordings(prev => prev.filter(r => r.id !== id))
    }
  }
  
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Signal Recordings</h2>
        
        <div className="flex gap-4 mb-6">
          <input
            type="text"
            value={recordingName}
            onChange={(e) => setRecordingName(e.target.value)}
            placeholder="Recording name..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            disabled={isRecording}
          />
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`px-6 py-2 rounded-lg font-semibold text-white transition ${
              isRecording ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {isRecording ? '⏹ Stop Recording' : '⏺ Start Recording'}
          </button>
        </div>
        
        {isRecording && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center gap-3">
              <div className="w-4 h-4 bg-red-600 rounded-full pulse"></div>
              <span className="text-red-800 font-semibold">Recording in progress...</span>
            </div>
          </div>
        )}
      </div>
      
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Saved Recordings</h3>
        <div className="space-y-3">
          {recordings.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No recordings yet. Start recording to save signal data.</p>
          ) : (
            recordings.map(rec => (
              <div key={rec.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <div className="font-semibold text-gray-800">{rec.name}</div>
                  <div className="text-sm text-gray-600">
                    {new Date(rec.timestamp).toLocaleString()} • {rec.duration}s • {rec.size}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button 
                    className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 transition"
                    title="Play"
                  >
                    ▶
                  </button>
                  <button 
                    onClick={() => downloadRecording(rec, 'JSON')}
                    className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 transition"
                  >
                    JSON
                  </button>
                  <button 
                    onClick={() => downloadRecording(rec, 'CSV')}
                    className="px-3 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 transition"
                  >
                    CSV
                  </button>
                  <button 
                    onClick={() => deleteRecording(rec.id)}
                    className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 transition"
                  >
                    🗑
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
