/**
 * ConfigService
 * Handles loading and saving of sensor configuration.
 * Currently uses localStorage to simulate persistence.
 * Future: Connect to backend API.
 */

const STORAGE_KEY = 'sensor_config'

// Default config matching the provided JSON structure
export const DEFAULT_CONFIG = {
    sampling_rate: 512,
    channel_mapping: {
        ch0: { sensor: 'EEG', enabled: true },
        ch1: { sensor: 'EEG', enabled: true },
        ch2: { sensor: 'EEG', enabled: true },
        ch3: { sensor: 'EEG', enabled: true },
        ch4: { sensor: 'EEG', enabled: true },
        ch5: { sensor: 'EEG', enabled: true },
        ch6: { sensor: 'EEG', enabled: true },
        ch7: { sensor: 'EEG', enabled: true }
    },
    filters: {
        notch: { freq: 50.0, enabled: true },
        bandpass: { low: 0.5, high: 45.0, enabled: true },
        high_pass: { cutoff: 10.0, enabled: false } // placeholder
    },
    display: {
        timeWindowMs: 10000,
        showGrid: true
    }
}

export const ConfigService = {
    /**
     * Load configuration from storage or return defaults.
     * @returns {Promise<Object>} config object
     */
    async loadConfig() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY)
            if (stored) {
                return { ...DEFAULT_CONFIG, ...JSON.parse(stored) }
            }
        } catch (e) {
            console.warn('Failed to load config from localStorage', e)
        }
        return JSON.parse(JSON.stringify(DEFAULT_CONFIG))
    },

    /**
     * Save configuration to storage.
     * @param {Object} config 
     */
    async saveConfig(config) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
            console.log('Config saved to localStorage')
        } catch (e) {
            console.error('Failed to save config', e)
        }
    },

    /**
     * Export config as JSON file (user download).
     */
    exportToFile(config) {
        const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'sensor_config.json'
        a.click()
        URL.revokeObjectURL(url)
    }
}
