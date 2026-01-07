/**
 * useWebSocket.js - OFFLINE CAPABLE VERSION
 * 
 * Uses 'socket.io-client' npm package instead of CDN for offline support.
 */

import { useState, useEffect, useRef } from 'react'
import { io } from 'socket.io-client'

export function useWebSocket(url = 'http://localhost:1972') {
  const [status, setStatus] = useState('disconnected')
  const [lastMessage, setLastMessage] = useState(null)
  const [lastConfig, setLastConfig] = useState(null)
  const [lastEvent, setLastEvent] = useState(null)
  const [latency, setLatency] = useState(0)

  const socketRef = useRef(null)
  const pingTimer = useRef(null)
  const lastPingTime = useRef(0)

  const [currentUrl, setCurrentUrl] = useState(url)

  const connect = (connectUrl) => {
    const endpoint = connectUrl || currentUrl || url

    // Don't reconnect if already connected to same endpoint
    if (socketRef.current?.connected && endpoint === currentUrl) {
      console.log('⚠️ Already connected')
      return
    }

    console.log(`🔌 Connecting to WebSocket: ${endpoint} (Offline Mode)`)
    setStatus('connecting')
    setCurrentUrl(endpoint)

    try {
      // Connect directly using the imported 'io' function
      socketRef.current = io(endpoint, {
        reconnection: false, // User requested manual retry only
        timeout: 3000,       // Fail after 3 seconds
        transports: ['websocket', 'polling']
      })

      setupSocketListeners()

    } catch (e) {
      console.error('❌ Failed to initialize Socket.IO:', e)
      setStatus('error')
    }
  }

  const setupSocketListeners = () => {
    if (!socketRef.current) return

    // === CONNECTION EVENT ===
    socketRef.current.on('connect', () => {
      console.log('✅ WebSocket connected')
      setStatus('connected')

      if (socketRef.current) {
        pingTimer.current = setInterval(() => {
          if (socketRef.current?.connected) {
            lastPingTime.current = performance.now()
            socketRef.current.emit('ping')
          }
        }, 500)
      }
    })

    // === DISCONNECTION EVENT ===
    socketRef.current.on('disconnect', () => {
      console.log('❌ WebSocket disconnected')
      setStatus('disconnected')
      setLatency(0)

      if (pingTimer.current) {
        clearInterval(pingTimer.current)
        pingTimer.current = null
      }
    })

    // === ERROR EVENT ===
    socketRef.current.on('error', (error) => {
      console.error('❌ WebSocket error:', error)
      setStatus('disconnected')
    })

    // === CONNECTION ERROR (Failed to connect) ===
    socketRef.current.on('connect_error', (err) => {
      console.warn('⚠️ Connection failed:', err.message)
      setStatus('disconnected')
    })

    // === PONG EVENT (latency measurement) ===
    socketRef.current.on('pong', () => {
      if (socketRef.current?.connected) {
        const now = performance.now()
        const latencyMs = Math.round(now - lastPingTime.current)
        setLatency(latencyMs)
      }
    })

    // === DATA EVENTS ===

    // Batch Listener
    // No throttling for batch data to prevent data loss. The backend controls the rate (approx 30Hz).
    socketRef.current.on('bio_data_batch', (batchData) => {
      if (!batchData || !batchData.samples || batchData.samples.length === 0) return

      // Optimized parsing: Avoid try-catch block for clean data to reduce V8 deopt
      // Only wrap critical parts or assume backend data shape is mostly correct.

      const lastSample = batchData.samples[batchData.samples.length - 1]

      // Fast path reconstruction
      const rawPayload = {
        stream_name: batchData.stream_name,
        // We only strictly need channels/timestamp for 'lastMessage' consumers (non-LiveView)
        // LiveView uses _batch directly.
        channels: lastSample.channels,
        sample_rate: batchData.sample_rate,
        sample_count: lastSample.sample_count,
        timestamp: lastSample.timestamp,
        _batch: batchData.samples
      }

      setLastMessage({
        // Avoid JSON.stringify if not strictly needed by consumers, but useWebSocket contract implies string 'data'
        data: JSON.stringify(rawPayload),
        timestamp: Date.now(),
        raw: rawPayload
      })
    })

    let lastUpdate = 0
    socketRef.current.on('bio_data_update', (data) => {
      try {
        // Throttle updates to ~30Hz (33ms)
        const now = Date.now()
        if (now - lastUpdate < 33) return
        lastUpdate = now

        // Handle NEW LSL format
        if (data.stream_name && data.channels && typeof data.channels === 'object') {
          const channels = data.channels
          const normalized = {}

          Object.entries(channels).forEach(([idx, ch]) => {
            if (typeof ch === 'object') {
              normalized[idx] = {
                value: ch.value ?? 0,
                sensor: ch.type || ch.label || 'UNKNOWN',
                label: ch.label,
                timestamp: ch.timestamp
              }
            } else {
              normalized[idx] = {
                value: ch,
                sensor: 'UNKNOWN'
              }
            }
          })

          let timestamp = data.timestamp || Date.now()
          if (timestamp < 10000000000) {
            timestamp = timestamp * 1000 // Convert to milliseconds
          }

          setLastMessage({
            data: JSON.stringify(data),
            timestamp: Date.now(),
            raw: {
              timestamp,
              channels: normalized,
              sample_rate: data.sample_rate,
              num_channels: data.channel_count,
              stream_name: data.stream_name,
              sample_count: data.sample_count
            }
          })
        }
        else if (data.channels) {
          setLastMessage({
            data: JSON.stringify(data),
            timestamp: Date.now(),
            raw: data
          })
        }
      } catch (e) {
        console.warn('⚠️ Failed to parse bio_data_update:', e)
      }
    })

    // === ALTERNATIVE DATA EVENT ===
    socketRef.current.on('signal_update', (data) => {
      try {
        if (data.channels) {
          setLastMessage({
            data: JSON.stringify(data),
            timestamp: Date.now(),
            raw: data
          })
        }
      } catch (e) {
        console.warn('⚠️ Failed to parse signal_update:', e)
      }
    })

    // === CONFIG UPDATE EVENT ===
    socketRef.current.on('config_updated', (data) => {
      console.log('🔄 Config updated from server:', data)
      if (data && data.config) {
        setLastConfig(data.config)
      }
    })

    // === EVENT STREAM ===
    socketRef.current.on('bio_event', (eventData) => {
      console.log('⚡ Bio Event:', eventData)
      setLastEvent(eventData)
    })

    socketRef.current.on('emg_prediction', (data) => {
      // console.log('🧠 Prediction:', data) // Optional logging
      setLastEvent({ type: 'emg_prediction', ...data })
    })

    // === STATUS EVENTS ===
    socketRef.current.on('status', (data) => {
      console.log('📊 Server status:', data)
    })

    socketRef.current.on('response', (data) => {
      console.log('📨 Server response:', data)
    })
  }

  const disconnect = () => {
    console.log('🔌 Disconnecting...')

    if (pingTimer.current) {
      clearInterval(pingTimer.current)
      pingTimer.current = null
    }

    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
    }

    setStatus('disconnected')
    setLatency(0)
    setCurrentUrl(null)
    console.log('✅ Disconnected')
  }

  const sendMessage = (data) => {
    if (!socketRef.current || !socketRef.current.connected) {
      console.warn('⚠️ WebSocket not connected, cannot send message:', data)
      return false
    }

    try {
      socketRef.current.emit('message', data)
      console.log('📤 Sent message:', data)
      return true
    } catch (e) {
      console.error('❌ Error sending message:', e)
      return false
    }
  }

  const requestStatus = () => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('request_status')
      console.log('📡 Status request sent')
    }
  }

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [])

  return {
    status,
    lastMessage,
    lastConfig,
    lastEvent,
    latency,
    connect,
    disconnect,
    currentUrl,
    sendMessage,
    requestStatus
  }
}

export default useWebSocket
