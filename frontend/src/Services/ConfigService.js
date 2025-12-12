const CONFIG_KEY = 'biosignals-config'
const CONFIG_DEFAULTS = {
    sampling_rate: 512,
    channel_mapping: {
        ch0: {
            sensor: 'EMG',
            enabled: true
        },
        ch1: {
            sensor: 'EEG',
            enabled: true
        }
    },
    filters: {
        EMG: {
            type: 'high_pass',
            cutoff: 70.0,
            order: 4
        },
        EOG: {
            type: 'low_pass',
            cutoff: 10.0,
            order: 4
        },
        EEG: {
            filters: [
                {
                    type: 'notch',
                    freq: 50.0,
                    Q: 30
                },
                {
                    type: 'bandpass',
                    low: 0.5,
                    high: 45.0,
                    order: 4
                }
            ]
        }
    },
    display: {
        timeWindowMs: 10000,
        showGrid: true,
        scannerX: 0
    },
    num_channels: 2
}

export const ConfigService = {
    /**
     * Load config from localStorage first, then sync with backend
     * Returns immediately with cached config
     * Syncs backend version in background (if endpoint exists)
     */
    async loadConfig() {
        try {
            // Try localStorage first (instant)
            const cached = localStorage.getItem(CONFIG_KEY)
            if (cached) {
                console.log('✅ Config loaded from localStorage')
                const config = JSON.parse(cached)

                // Background sync with backend (non-blocking)
                this.syncFromBackend().catch(e => {
                    console.warn('⚠️ Failed to sync config from backend:', e)
                })

                return config
            }
        } catch (e) {
            console.warn('⚠️ Failed to load from localStorage:', e)
        }

        // If no cache, try to load from backend (if endpoint exists)
        try {
            console.log('📡 Fetching config from backend...')
            const response = await fetch('/api/config')

            if (response.status === 404) {
                console.log('ℹ️ Backend /api/config endpoint not available (older web_server.py)')
                console.log('ℹ️ Using localStorage mode - config will persist locally')
                localStorage.setItem(CONFIG_KEY, JSON.stringify(CONFIG_DEFAULTS))
                return CONFIG_DEFAULTS
            }

            if (response.ok) {
                const config = await response.json()
                console.log('✅ Config loaded from backend')
                localStorage.setItem(CONFIG_KEY, JSON.stringify(config))
                return config
            }
        } catch (e) {
            console.warn('⚠️ Failed to load from backend:', e)
        }

        // Fallback to defaults
        console.log('📋 Using default config')
        localStorage.setItem(CONFIG_KEY, JSON.stringify(CONFIG_DEFAULTS))
        return CONFIG_DEFAULTS
    },

    /**
     * Save config to both localStorage and backend
     * Works with both old and new web_server.py versions
     */
    async saveConfig(config) {
        if (!config) {
            console.error('❌ Cannot save null config')
            return false
        }

        try {
            // Save to localStorage immediately (always works)
            localStorage.setItem(CONFIG_KEY, JSON.stringify(config))
            console.log('💾 Config saved to localStorage')

            // Try to persist to backend (if endpoint exists)
            await this.saveToBackend(config).catch(err => {
                console.warn('⚠️ Backend save failed, but localStorage is fine:', err)
            })

            return true
        } catch (e) {
            console.error('❌ Failed to save config:', e)
            return false
        }
    },

    /**
     * Sync config from backend to localStorage
     * Gracefully handles missing endpoint
     */
    async syncFromBackend() {
        try {
            const response = await fetch('/api/config')

            if (response.status === 404) {
                console.log('ℹ️ Backend endpoint not available')
                return false
            }

            if (!response.ok) {
                console.warn(`⚠️ Backend returned ${response.status}`)
                return false
            }

            const config = await response.json()
            localStorage.setItem(CONFIG_KEY, JSON.stringify(config))
            console.log('🔄 Config synced from backend')
            return true
        } catch (e) {
            console.warn('⚠️ Failed to sync from backend:', e)
            return false
        }
    },

    /**
     * Save config to backend
     * FIXED: Gracefully handles missing endpoint
     */
    async saveToBackend(config) {
        try {
            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            })

            // 404 means endpoint doesn't exist (older web_server.py)
            if (response.status === 404) {
                console.log('ℹ️ Backend /api/config POST endpoint not found')
                console.log('ℹ️ Config will be saved to localStorage only')
                console.log('ℹ️ To enable backend persistence, update to web_server_FIXED.py')
                return true // Still success since localStorage is saved
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`)
            }

            console.log('📤 Config saved to backend')
            return true
        } catch (e) {
            console.warn('⚠️ Backend save failed, config saved to localStorage:', e)
            return true // Still success - localStorage is working
        }
    },

    /**
     * Clear all config (localStorage + backend if available)
     */
    async clearConfig() {
        try {
            localStorage.removeItem(CONFIG_KEY)
            console.log('🗑️ Config cleared from localStorage')

            // Also notify backend if endpoint exists
            try {
                await fetch('/api/config', { method: 'DELETE' }).catch(() => { })
            } catch (e) {
                console.warn('⚠️ Could not notify backend of config clear')
            }

            return true
        } catch (e) {
            console.error('❌ Failed to clear config:', e)
            return false
        }
    },

    /**
     * Merge partial config with existing
     */
    mergeConfig(partial) {
        const cached = localStorage.getItem(CONFIG_KEY)
        const existing = cached ? JSON.parse(cached) : CONFIG_DEFAULTS

        const merged = {
            ...existing,
            ...partial,
            channel_mapping: {
                ...existing.channel_mapping,
                ...partial.channel_mapping
            },
            filters: {
                ...existing.filters,
                ...partial.filters
            },
            display: {
                ...existing.display,
                ...partial.display
            }
        }

        return merged
    }
}

export default ConfigService
