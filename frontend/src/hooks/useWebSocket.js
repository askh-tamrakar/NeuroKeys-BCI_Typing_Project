/**
 * useWebSocket.js - FIXED VERSION
 * 
 * Critical fixes:
 * 1. Guard all socketRef.current operations with null checks
 * 2. Clear ping timer BEFORE nullifying socketRef
 * 3. Guard sendMessage with socket.connected check
 * 4. Prevent timer firing after disconnect
 */

import { useState, useEffect, useRef } from 'react'

export function useWebSocket(url = 'http://localhost:5000') {
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

    console.log(`🔌 Connecting to WebSocket: ${endpoint}`)
    setStatus('connecting')
    setCurrentUrl(endpoint)

    const script = document.createElement('script')
    script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js'

    script.onload = () => {
      const io = window.io
      if (!io) {
        console.error('❌ Socket.IO library failed to load')
        setStatus('error')
        return
      }

      socketRef.current = io(endpoint, {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 5,
        transports: ['websocket', 'polling']
      })

      // === CONNECTION EVENT ===
      socketRef.current.on('connect', () => {
        console.log('✅ WebSocket connected')
        setStatus('connected')

        // CRITICAL FIX: Only start ping if socket still exists
        if (socketRef.current) {
          pingTimer.current = setInterval(() => {
            // CRITICAL FIX: Guard emit operation
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

        // CRITICAL FIX: Clear timer BEFORE nullifying socket
        if (pingTimer.current) {
          clearInterval(pingTimer.current)
          pingTimer.current = null
        }
      })

      // === ERROR EVENT ===
      socketRef.current.on('error', (error) => {
        console.error('❌ WebSocket error:', error)
        setStatus('error')
      })

      // === PONG EVENT (latency measurement) ===
      socketRef.current.on('pong', () => {
        // CRITICAL FIX: Guard before using
        if (socketRef.current?.connected) {
          const now = performance.now()
          const latencyMs = Math.round(now - lastPingTime.current)
          setLatency(latencyMs)
          console.log(`📊 Latency: ${latencyMs}ms`)
        }
      })

      // === DATA EVENTS ===
      // === DATA EVENTS ===

      // Batch Listener (Restored)
      socketRef.current.on('bio_data_batch', (batchData) => {
        try {
          if (!batchData || !batchData.samples || batchData.samples.length === 0) return

          // compatibility: use last sample for simple views
          const lastSample = batchData.samples[batchData.samples.length - 1]

          const rawPayload = {
            stream_name: batchData.stream_name,
            channels: lastSample.channels,
            sample_rate: batchData.sample_rate,
            sample_count: lastSample.sample_count,
            timestamp: lastSample.timestamp,
            // Attach FULL BATCH for LiveView
            _batch: batchData.samples
          }

          setLastMessage({
            data: JSON.stringify(rawPayload),
            timestamp: Date.now(),
            raw: rawPayload
          })
        } catch (e) {
          console.warn('⚠️ Failed to parse bio_data_batch:', e)
        }
      })

      let lastUpdate = 0
      socketRef.current.on('bio_data_update', (data) => {
        try {
          // Throttle updates to ~30Hz (33ms) to prevent main thread saturation
          const now = Date.now()
          if (now - lastUpdate < 33) return
          lastUpdate = now

          // Handle NEW LSL format (from fixed web_server.py)
          if (data.stream_name && data.channels && typeof data.channels === 'object') {
            const channels = data.channels
            const normalized = {}

            // Convert channels object: {0: {...}, 1: {...}}
            Object.entries(channels).forEach(([idx, ch]) => {
              if (typeof ch === 'object') {
                normalized[idx] = {
                  value: ch.value ?? 0,
                  sensor: ch.type || ch.label || 'UNKNOWN',
                  label: ch.label,
                  timestamp: ch.timestamp // CRITICAL: Preserve per-channel timestamp
                }
              } else {
                normalized[idx] = {
                  value: ch,
                  sensor: 'UNKNOWN'
                }
              }
            })

            // Handle timestamp conversion (LSL uses seconds)
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
          // Handle OLD format (backward compatibility)
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

      // === STATUS EVENTS ===
      socketRef.current.on('status', (data) => {
        console.log('📊 Server status:', data)
      })

      socketRef.current.on('response', (data) => {
        console.log('📨 Server response:', data)
      })
    }

    script.onerror = () => {
      console.error('❌ Failed to load Socket.IO library')
      setStatus('error')
    }

    document.head.appendChild(script)
  }

  /**
   * CRITICAL FIX: Proper disconnect with cleanup
   */
  const disconnect = () => {
    console.log('🔌 Disconnecting...')

    // CRITICAL: Clear timer BEFORE disconnecting
    if (pingTimer.current) {
      clearInterval(pingTimer.current)
      pingTimer.current = null
    }

    // Then disconnect socket
    if (socketRef.current) {
      socketRef.current.disconnect()
      socketRef.current = null
    }

    setStatus('disconnected')
    setLatency(0)
    setCurrentUrl(null)
    console.log('✅ Disconnected')
  }

  /**
   * CRITICAL FIX: Guard sendMessage with connection check
   */
  const sendMessage = (data) => {
    // CRITICAL: Check both socket existence AND connected status
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

  /**
   * Request server status
   */
  const requestStatus = () => {
    if (socketRef.current?.connected) {
      socketRef.current.emit('request_status')
      console.log('📡 Status request sent')
    }
  }

  /**
   * CRITICAL: Cleanup on unmount
   */
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
