import { useState, useEffect, useRef } from 'react'

/**
 * useWebSocket Hook - Updated for Flask-SocketIO Backend
 * 
 * Features:
 * - Connects to Flask-SocketIO server at http://localhost:5000
 * - Listens to 'bio_data_update' events for real-time data
 * - Auto-reconnection with exponential backoff
 * - Message sending support
 */

export function useWebSocket(url = 'http://localhost:5000' || 'ws://localhost:5000') {
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [latency, setLatency] = useState(0)
  const socketRef = useRef(null)
  const pingTimer = useRef(null)
  const lastPingTime = useRef(0)

  const connect = () => {
    if (socketRef.current?.connected) return

    console.log(`🔌 Connecting to WebSocket: ${url}`)
    setStatus('connecting')

    // Dynamically load Socket.IO client
    const script = document.createElement('script')
    script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js'
    script.onload = () => {
      const io = window.io

      socketRef.current = io(url, {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
        transports: ['websocket', 'polling']
      })

      // Connection events
      socketRef.current.on('connect', () => {
        setStatus('connected')
        console.log('✅ WebSocket connected')

        // Start ping for latency measurement
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

      // MAIN EVENT: Real-time biosignals from Flask-SocketIO
      socketRef.current.on('bio_data_update', (data) => {
        setLatency(Math.round(performance.now() - lastPingTime.current))

        // Data format from Flask server:
        // {
        //   stream_name: "BioSignals-Processed",
        //   channels: { 0: {label, type, value, timestamp}, 1: {...} },
        //   channel_count: 2,
        //   sample_rate: 512,
        //   sample_count: 1024,
        //   timestamp: 123.456
        // }

        setLastMessage({
          data: JSON.stringify(data),
          timestamp: Date.now(),
          raw: data
        })
      })

      // Status response
      socketRef.current.on('status', (data) => {
        console.log('Server status:', data)
      })

      // Response from server
      socketRef.current.on('response', (data) => {
        console.log('Server response:', data)
      })
    }

    document.head.appendChild(script)
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

  const sendMessage = (data) => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('message', data)
      console.log('📤 Sent message:', data)
    } else {
      console.warn('⚠️ WebSocket not connected, cannot send message:', data)
    }
  }

  const requestStatus = () => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('request_status')
    }
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
    sendMessage,
    requestStatus
  }
}

export default useWebSocket
