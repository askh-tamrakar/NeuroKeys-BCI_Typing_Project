import React, { useEffect, useRef, useState } from 'react'
import LiveView from './LiveView'
import { MockWebSocket } from '../../services/MockWebSocket'

const USE_MOCK = true
const WS_URL = 'ws://localhost:8000/ws'

export default function TestView() {
  const [wsData, setWsData] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    const ws = USE_MOCK ? new MockWebSocket(WS_URL) : new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => console.log('WS open')
    ws.onmessage = (evt) => {
      // The MockWebSocket sends { data: JSON.stringify(...) } just like a real WebSocket MessageEvent
      // but some mocks may send objects directly. Handle both.
      try {
        if (typeof evt.data === 'string') {
          setWsData({ data: evt.data }) // keep as MessageEvent-like so LiveView.parse handles it
        } else if (evt.data && typeof evt.data === 'object') {
          // sometimes mock already sends object
          setWsData(evt.data)
        } else {
          // fallback: try to stringify and save
          setWsData({ data: JSON.stringify(evt) })
        }
      } catch (e) {
        console.error('App onmessage parse error', e, evt)
      }
    }
    ws.onerror = (e) => console.error('WS error', e)
    ws.onclose = () => console.log('WS closed')

    return () => { if (ws && ws.close) ws.close() }
  }, [])

  return (
    <div style={{ padding: 20 }}>
      <h1>Test LiveView</h1>
      <LiveView wsData={wsData} />
    </div>
  )
}
