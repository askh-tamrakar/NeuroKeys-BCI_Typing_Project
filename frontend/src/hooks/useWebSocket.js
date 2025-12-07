import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Custom React hook for WebSocket connection
 * Handles connection lifecycle, message parsing, and latency monitoring
 */
export function useWebSocket(url) {
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [latency, setLatency] = useState(0)

  const wsRef = useRef(null)
  const pingTimer = useRef(null)
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    // Don't reconnect if already connecting or connected
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return
    }

    console.log(`🔌 Connecting to WebSocket: ${url}`)
    setStatus('connecting')

    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('✅ WebSocket connected')
        setStatus('connected')

        // Send ping every 1 second to measure latency
        pingTimer.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            const id = Math.random().toString(36).slice(2, 10)
            const t0 = performance.now()

            wsRef.current.send(
              JSON.stringify({
                type: 'ping',
                id,
                t0
              })
            )
          }
        }, 1000)
      }

      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)

          // Handle pong responses (ping/pong for latency)
          if (msg.type === 'pong') {
            const rtt = performance.now() - msg.t0
            setLatency(parseFloat(rtt.toFixed(2)))
            return
          }

          // Handle actual EMG data
          setLastMessage({
            data: event.data,
            parsed: msg,
            timestamp: Date.now()
          })

          // Log EMG data for debugging
          if (msg.source === 'EMG') {
            console.log('📨 Received EMG packet:', msg)
          }
        } catch (e) {
          console.error('❌ Failed to parse WebSocket message:', e)
          console.log('Raw message:', event.data)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('❌ WebSocket error:', error)
        setStatus('error')
      }

      wsRef.current.onclose = (event) => {
        console.log(`🔌 WebSocket closed: Code=${event.code}, Reason=${event.reason}`)
        setStatus('disconnected')
        clearInterval(pingTimer.current)

        // Auto-reconnect after 3 seconds
        reconnectTimer.current = setTimeout(() => {
          console.log('🔄 Attempting to reconnect...')
          connect()
        }, 3000)
      }
    } catch (e) {
      console.error('❌ Failed to create WebSocket:', e)
      setStatus('error')
    }
  }, [url])

  const disconnect = useCallback(() => {
    console.log('🛑 Disconnecting WebSocket')
    clearInterval(pingTimer.current)
    clearTimeout(reconnectTimer.current)
    wsRef.current?.close()
    wsRef.current = null
    setStatus('disconnected')
  }, [])

  const sendMessage = useCallback(
    (data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify(data))
          console.log('📤 Sent message:', data)
        } catch (e) {
          console.error('❌ Failed to send message:', e)
        }
      } else {
        console.warn('⚠️  WebSocket not connected, cannot send message:', data)
      }
    },
    []
  )

  // Auto-connect on mount, cleanup on unmount
  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    status,           // 'disconnected' | 'connecting' | 'connected' | 'error'
    lastMessage,      // { data: string, parsed: object, timestamp: number }
    latency,          // Ping-pong latency in ms
    connect,          // Manual connect function
    disconnect,       // Manual disconnect function
    sendMessage,      // Send data to server
    ws: wsRef.current // Raw WebSocket reference (if needed)
  }
}
