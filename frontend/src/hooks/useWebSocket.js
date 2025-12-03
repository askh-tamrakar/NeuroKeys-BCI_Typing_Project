import { useState, useEffect, useRef } from 'react'

export function useWebSocket(url) {
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [latency, setLatency] = useState(0)

  const wsRef = useRef(null)
  const pingTimer = useRef(null)

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    setStatus('connecting')

    wsRef.current = new WebSocket(url)

    wsRef.current.onopen = () => {
      setStatus('connected')

      // Send ping every 1 sec
      pingTimer.current = setInterval(() => {
        const id = Math.random().toString(36).slice(2, 10)
        const t0 = performance.now()

        wsRef.current.send(JSON.stringify({
          type: "ping",
          id,
          t0
        }))
      }, 1000)
    }

    wsRef.current.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === "pong") {
        const rtt = performance.now() - msg.t0
        setLatency(rtt.toFixed(2)) 
        return
      }

      setLastMessage({ data: event.data, timestamp: Date.now() })
    }

    wsRef.current.onerror = () => setStatus('error')

    wsRef.current.onclose = () => {
      setStatus('disconnected')
      clearInterval(pingTimer.current)
    }
  }

  const disconnect = () => {
    wsRef.current?.close()
  }

  useEffect(() => {
    return () => disconnect()
  }, [])

  return {
    status,
    lastMessage,
    latency,
    connect,
    disconnect,
    ws: wsRef.current
  }
}
