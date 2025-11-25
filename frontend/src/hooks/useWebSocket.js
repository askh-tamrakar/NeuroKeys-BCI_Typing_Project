import { useState, useEffect, useRef } from 'react'
import { MockWebSocket } from '../services/MockWebSocket'

export function useWebSocket(url) {
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [latency, setLatency] = useState(0)
  const wsRef = useRef(null)
  const pingRef = useRef(null)
  
  const connect = () => {
    if (wsRef.current?.readyState === 1) return
    
    setStatus('connecting')
    
    // Use MockWebSocket if VITE_USE_MOCK is true
    const useMock = import.meta.env.VITE_USE_MOCK === 'true'
    wsRef.current = useMock ? new MockWebSocket(url) : new WebSocket(url)
    
    wsRef.current.onopen = () => {
      setStatus('connected')
      pingRef.current = setInterval(() => {
        setLatency(Math.random() * 30 + 10) // Mock 10-40ms
      }, 1000)
    }
    
    wsRef.current.onmessage = (event) => {
      setLastMessage({ data: event.data, timestamp: Date.now() })
    }
    
    wsRef.current.onerror = () => setStatus('error')
    wsRef.current.onclose = () => {
      setStatus('disconnected')
      clearInterval(pingRef.current)
    }
  }
  
  const disconnect = () => {
    wsRef.current?.close()
  }
  
  useEffect(() => {
    return () => disconnect()
  }, [])
  
  return { status, lastMessage, latency, connect, disconnect, ws: wsRef.current }
}
