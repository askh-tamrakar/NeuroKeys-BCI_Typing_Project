import { useState, useEffect, useRef } from 'react'
import io from 'socket.io-client'

/**
 * WebSocket Hook for Multi-Channel EEG Streaming
 * Much lower latency than HTTP polling
 */
export function useWebSocket(url) {
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [latency, setLatency] = useState(0)
  const [channels, setChannels] = useState(1)

  const socketRef = useRef(null)
  const pingTimer = useRef(null)
  const lastPingTime = useRef(0)

  const connect = () => {
    if (socketRef.current?.connected) return

    console.log(`🔌 Connecting to WebSocket: ${url}`)
    setStatus('connecting')

    // Extract base URL (remove /api/stream if present)
    const baseUrl = url.replace(/\/api\/.*/, '')

    socketRef.current = io(baseUrl, {
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
      transports: ['websocket', 'polling']
    })

    socketRef.current.on('connect', () => {
      setStatus('connected')
      console.log('✅ WebSocket connected')

      // Start ping/pong for latency measurement
      pingTimer.current = setInterval(() => {
        lastPingTime.current = performance.now()
        socketRef.current.emit('ping')
      }, 1000)
    })

    socketRef.current.on('disconnect', () => {
      setStatus('disconnected')
      if (pingTimer.current) clearInterval(pingTimer.current)
      console.log('❌ WebSocket disconnected')
    })

    socketRef.current.on('error', (error) => {
      setStatus('error')
      console.error('WebSocket error:', error)
    })

    // Receive EEG data (realtime @ 250 Hz)
    socketRef.current.on('eeg_data', (data) => {
      setLatency(Math.round(performance.now() - lastPingTime.current))
      setChannels(data.channels)

      setLastMessage({
        data: JSON.stringify(data),
        timestamp: Date.now()
      })
    })

    // Receive buffered data
    socketRef.current.on('buffer_data', (data) => {
      setLastMessage({
        data: JSON.stringify(data),
        timestamp: Date.now()
      })
    })

    // Receive all channels data
    socketRef.current.on('all_channels_data', (data) => {
      setLastMessage({
        data: JSON.stringify(data),
        timestamp: Date.now()
      })
    })

    // Response from server
    socketRef.current.on('response', (data) => {
      console.log('Server response:', data)
      setChannels(data.channels)
    })
  }

  const disconnect = () => {
    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
    }
    if (pingTimer.current) {
      clearInterval(pingTimer.current)
    }
    setStatus('disconnected')
  }

  const requestBuffer = (channel = 0, n = 500) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('request_buffer', { channel, n })
    }
  }

  const requestAllChannels = (n = 500) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('request_all_channels', { n })
    }
  }

  useEffect(() => {
    return () => disconnect()
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
    status,
    lastMessage,
    latency,
    channels,
    connect,
    disconnect,
    requestBuffer,
    requestAllChannels
  }
}

export default useWebSocket