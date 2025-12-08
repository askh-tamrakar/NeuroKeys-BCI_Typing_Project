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
      : `timestamp,EEG,EOG,EMG\\n${Date.now()},0.5,-0.2,0.3\\n`

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
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h2 className="text-2xl font-bold text-text mb-6 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          Signal Recordings
        </h2>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            value={recordingName}
            onChange={(e) => setRecordingName(e.target.value)}
            placeholder="Recording name..."
            className="flex-1 px-4 py-3 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all placeholder:text-muted/50"
            disabled={isRecording}
          />
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className={`px-8 py-3 rounded-xl font-bold transition-all shadow-glow ${isRecording
              ? 'bg-accent text-primary-contrast hover:opacity-90'
              : 'bg-primary text-primary-contrast hover:opacity-90 hover:translate-y-[-2px] active:translate-y-[0px]'
              }`}
          >
            {isRecording ? '⏹ Stop Recording' : '⏺ Start Recording'}
          </button>
        </div>

        {isRecording && (
          <div className="bg-primary/10 border border-primary/30 rounded-xl p-5 mb-6">
            <div className="flex items-center gap-4">
              <div className="w-4 h-4 bg-primary rounded-full animate-pulse"></div>
              <span className="text-primary font-bold text-lg">Recording in progress...</span>
            </div>
          </div>
        )}
      </div>

      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h3 className="text-xl font-bold text-text mb-4">Saved Recordings</h3>
        <div className="space-y-3">
          {recordings.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted space-y-3">
              <div className="w-16 h-16 rounded-full bg-bg border border-border flex items-center justify-center">
                <span className="text-2xl">🎙️</span>
              </div>
              <p>No recordings yet. Start recording to save signal data.</p>
            </div>
          ) : (
            recordings.map(rec => (
              <div key={rec.id} className="flex items-center justify-between p-5 bg-bg rounded-xl border border-border hover:border-primary/50 transition-all">
                <div>
                  <div className="font-bold text-text text-lg">{rec.name}</div>
                  <div className="text-sm text-muted mt-1">
                    {new Date(rec.timestamp).toLocaleString()} • {rec.duration}s • {rec.size}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    className="px-4 py-2 bg-primary text-primary-contrast rounded-lg font-bold hover:opacity-90 transition-all"
                    title="Play"
                  >
                    ▶
                  </button>
                  <button
                    onClick={() => downloadRecording(rec, 'JSON')}
                    className="px-4 py-2 bg-accent text-primary-contrast rounded-lg font-bold hover:opacity-90 transition-all"
                  >
                    JSON
                  </button>
                  <button
                    onClick={() => downloadRecording(rec, 'CSV')}
                    className="px-4 py-2 bg-accent text-primary-contrast rounded-lg font-bold hover:opacity-90 transition-all"
                  >
                    CSV
                  </button>
                  <button
                    onClick={() => deleteRecording(rec.id)}
                    className="px-4 py-2 bg-surface border border-border text-text rounded-lg font-bold hover:border-primary/50 transition-all"
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


// import React, { useState, useEffect } from 'react'

// export default function RecordingsView() {
//   const [recordings, setRecordings] = useState([])
//   const [isRecording, setIsRecording] = useState(false)
//   const [recordingName, setRecordingName] = useState('')
//   const [recordingDuration, setRecordingDuration] = useState(0)
//   const [recordingTimer, setRecordingTimer] = useState(null)
//   const [sessionData, setSessionData] = useState(null)

//   // Load saved recordings from server
//   useEffect(() => {
//     const loadRecordings = async () => {
//       try {
//         const response = await fetch('http://localhost:8000/api/recordings')
//         const data = await response.json()
//         setRecordings(data.recordings || [])
//       } catch (error) {
//         console.error('Error loading recordings:', error)
//       }
//     }
//     loadRecordings()
//   }, [])

//   const startRecording = async () => {
//     try {
//       const response = await fetch('http://localhost:8000/api/recording/start', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           name: recordingName || `Recording ${recordings.length + 1}`,
//           timestamp: new Date().toISOString()
//         })
//       })

//       if (response.ok) {
//         const data = await response.json()
//         setSessionData(data.sessionId)
//         setIsRecording(true)
//         setRecordingDuration(0)

//         // Start timer
//         const timer = setInterval(() => {
//           setRecordingDuration(prev => prev + 1)
//         }, 1000)
//         setRecordingTimer(timer)
//       }
//     } catch (error) {
//       console.error('Failed to start recording:', error)
//     }
//   }

//   const stopRecording = async () => {
//     try {
//       clearInterval(recordingTimer)

//       const response = await fetch('http://localhost:8000/api/recording/stop', {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({
//           sessionId: sessionData,
//           duration: recordingDuration
//         })
//       })

//       if (response.ok) {
//         const data = await response.json()
//         const newRecording = {
//           id: data.sessionId,
//           name: recordingName || `Recording ${recordings.length + 1}`,
//           timestamp: new Date().getTime(),
//           duration: recordingDuration,
//           size: data.fileSize || '0 MB',
//           dataPoints: data.totalPackets || 0,
//           path: data.filePath
//         }

//         setRecordings(prev => [newRecording, ...prev])
//         setIsRecording(false)
//         setRecordingName('')
//         setRecordingDuration(0)
//         setSessionData(null)
//       }
//     } catch (error) {
//       console.error('Failed to stop recording:', error)
//     }
//   }

//   const downloadRecording = async (recording, format) => {
//     try {
//       const response = await fetch(`http://localhost:8000/api/recording/download/${recording.id}`, {
//         method: 'POST',
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({ format: format.toLowerCase() })
//       })

//       if (response.ok) {
//         const blob = await response.blob()
//         const url = URL.createObjectURL(blob)
//         const a = document.createElement('a')
//         a.href = url
//         a.download = `${recording.name}.${format === 'JSON' ? 'json' : 'csv'}`
//         a.click()
//         URL.revokeObjectURL(url)
//       }
//     } catch (error) {
//       console.error('Download failed:', error)
//     }
//   }

//   const deleteRecording = async (id) => {
//     if (!confirm('Delete this recording permanently?')) return

//     try {
//       const response = await fetch(`http://localhost:8000/api/recording/${id}`, {
//         method: 'DELETE'
//       })

//       if (response.ok) {
//         setRecordings(prev => prev.filter(r => r.id !== id))
//       }
//     } catch (error) {
//       console.error('Delete failed:', error)
//     }
//   }

//   const formatDuration = (seconds) => {
//     const hrs = Math.floor(seconds / 3600)
//     const mins = Math.floor((seconds % 3600) / 60)
//     const secs = seconds % 60
//     return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
//   }

//   return (
//     <div className="recordings-container">
//       <div className="card recording-control">
//         <h2>🎙️ Session Recording</h2>

//         {!isRecording ? (
//           <>
//             <div className="form-group">
//               <label>Session Name</label>
//               <input
//                 type="text"
//                 value={recordingName}
//                 onChange={(e) => setRecordingName(e.target.value)}
//                 placeholder="Enter session name (optional)"
//                 className="input"
//               />
//             </div>
//             <button
//               onClick={startRecording}
//               className="btn btn-success btn-lg btn-block"
//             >
//               ⏺️ Start Recording
//             </button>
//           </>
//         ) : (
//           <>
//             <div className="recording-timer">
//               <h3>⏱️ {formatDuration(recordingDuration)}</h3>
//             </div>
//             <button
//               onClick={stopRecording}
//               className="btn btn-danger btn-lg btn-block"
//             >
//               ⏹️ Stop Recording
//             </button>
//           </>
//         )}
//       </div>

//       <div className="recordings-list">
//         <h2>📋 Saved Sessions</h2>
//         {recordings.length === 0 ? (
//           <p className="empty-message">No recordings yet. Start a session to save data.</p>
//         ) : (
//           <div className="recordings-grid">
//             {recordings.map(recording => (
//               <div key={recording.id} className="recording-card">
//                 <div className="recording-header">
//                   <h3>{recording.name}</h3>
//                   <span className="badge">{formatDuration(recording.duration)}</span>
//                 </div>

//                 <div className="recording-details">
//                   <p><strong>Date:</strong> {new Date(recording.timestamp).toLocaleString()}</p>
//                   <p><strong>Size:</strong> {recording.size}</p>
//                   <p><strong>Data Points:</strong> {recording.dataPoints}</p>
//                 </div>

//                 <div className="recording-actions">
//                   <button
//                     onClick={() => downloadRecording(recording, 'JSON')}
//                     className="btn btn-sm btn-primary"
//                   >
//                     📥 JSON
//                   </button>
//                   <button
//                     onClick={() => downloadRecording(recording, 'CSV')}
//                     className="btn btn-sm btn-primary"
//                   >
//                     📥 CSV
//                   </button>
//                   <button
//                     onClick={() => deleteRecording(recording.id)}
//                     className="btn btn-sm btn-danger"
//                   >
//                     🗑️ Delete
//                   </button>
//                 </div>
//               </div>
//             ))}
//           </div>
//         )}
//       </div>
//     </div>
//   )
// }
