/**
 * ConfigService - Updated for Flask-SocketIO Backend
 * 
 * Features:
 * ✅ Load config from localStorage
 * ✅ Save config to localStorage
 * ✅ Sync config to Flask backend via WebSocket
 * ✅ Export config as JSON file
 * 
 * Minimal changes - just added WebSocket sync capability
 */

const STORAGE_KEY = 'biosignal_config'

// Placeholder for WebSocket message sender (will be injected)
let webSocketSender = null

export const ConfigService = {
    /**
     * Set the WebSocket message sender function
     * Call this from your component that has sendMessage
     */
    setWebSocketSender(sender) {
        webSocketSender = sender
        console.log('✅ WebSocket sender registered')
    },

    /**
     * Load configuration from localStorage or return defaults.
     * @returns {Promise<Object>} config object
     */
    async loadConfig() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY)
            if (stored) {
                const parsed = JSON.parse(stored)
                console.log('✅ Config loaded from localStorage')
                return parsed
            }
        } catch (e) {
            console.warn('Failed to load config from localStorage', e)
        }

        // Return defaults if nothing stored
        const defaults = {
            sampling_rate: 512,
            display: {
                timeWindowMs: 10000,
                showGrid: true
            },
            channel_mapping: {
                ch0: { label: 'EEG_0', type: 'EEG', enabled: true },
                ch1: { label: 'EMG_1', type: 'EMG', enabled: true }
            }
        }

        return JSON.parse(JSON.stringify(defaults))
    },

    /**
     * Save configuration to localStorage AND sync to Flask backend
     * @param {Object} config 
     */
    async saveConfig(config) {
        try {
            // Save to localStorage
            localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
            console.log('📝 Config saved to localStorage')

            // Sync to Flask backend via WebSocket
            if (webSocketSender) {
                webSocketSender({
                    type: 'CONFIG_UPDATE',
                    config: config,
                    timestamp: Date.now()
                })
                console.log('🔄 Config synced to Flask backend')
            }

            return true
        } catch (e) {
            console.error('❌ Failed to save config', e)
            return false
        }
    },

    /**
     * Export config as JSON file (user download)
     * @param {Object} config 
     */
    exportToFile(config) {
        try {
            const blob = new Blob([JSON.stringify(config, null, 2)], {
                type: 'application/json'
            })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = 'biosignal_config.json'
            a.click()
            URL.revokeObjectURL(url)
            console.log('✅ Config exported to file')
        } catch (e) {
            console.error('❌ Failed to export config', e)
        }
    },

    /**
     * Get config from Flask backend
     * (Optional: if you want to sync from server)
     */
    async fetchConfigFromServer() {
        try {
            // This would call your Flask API endpoint
            // For now, just logs the intent
            console.log('📡 Fetching config from server...')
            // fetch('/api/config').then(r => r.json())
        } catch (e) {
            console.error('❌ Failed to fetch config from server', e)
        }
    }
}

export const DEFAULT_CONFIG = {
    sampling_rate: 512,
    display: {
        timeWindowMs: 10000,
        showGrid: true
    },
    channel_mapping: {
        ch0: { label: 'EEG_0', type: 'EEG', enabled: true },
        ch1: { label: 'EMG_1', type: 'EMG', enabled: true }
    }
}
