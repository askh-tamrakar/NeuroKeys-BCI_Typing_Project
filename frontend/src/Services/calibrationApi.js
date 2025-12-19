/**
 * @typedef {'EMG' | 'EOG' | 'EEG'} SensorType
 */

/**
 * @typedef {'realtime' | 'recording'} CalibrationMode
 */

/**
 * @typedef {Object} CalibrationWindow
 * @property {string} id
 * @property {SensorType} sensor
 * @property {CalibrationMode} mode
 * @property {number} startTime
 * @property {number} endTime
 * @property {string} label
 * @property {string} [predictedLabel]
 * @property {'correct' | 'incorrect' | 'pending'} status
 * @property {boolean} [isMissedActual]
 */

/**
 * @typedef {Object} SensorConfig
 * @property {Object} channel_mapping
 * @property {Object} features
 * @property {Object} filters
 * @property {number} sampling_rate
 */

/**
 * Mock API service for calibration orchestration.
 */
export const CalibrationApi = {
    /**
     * Fetches the current sensor configuration.
     * @returns {Promise<SensorConfig>}
     */
    async fetchSensorConfig() {
        console.log('[CalibrationApi] Fetching sensor config...');
        // In a real app, this would be a fetch call to /api/config
        const response = await fetch('/api/config'); // Assuming a proxy setup
        if (!response.ok) {
            // Fallback or mock if backend is not ready
            return {
                channel_mapping: {},
                features: {
                    EMG: { Rock: { rms: [400, 800] }, Rest: { rms: [0, 200] } },
                    EOG: { blink: { threshold: 0.5 } },
                    EEG: { target_10Hz: { power: 10 } }
                },
                filters: {},
                sampling_rate: 250
            };
        }
        return response.json();
    },

    /**
     * Saves the updated sensor configuration.
     * @param {SensorConfig} updatedConfig 
     */
    async saveSensorConfig(updatedConfig) {
        console.log('[CalibrationApi] Saving sensor config:', updatedConfig);
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedConfig)
        });
        return response.ok;
    },

    /**
     * Signals the backend to start a calibration session.
     * @param {SensorType} sensorType 
     * @param {CalibrationMode} mode 
     * @param {string} classLabel 
     * @param {number} windowDurationMs 
     */
    async startCalibration(sensorType, mode, classLabel, windowDurationMs) {
        console.log(`[CalibrationApi] Starting ${mode} calibration for ${sensorType} (${classLabel})`);
        // Mock command back to backend
        return { success: true, sessionId: Date.now().toString() };
    },

    /**
     * Signals the backend to stop the current calibration session.
     * @param {SensorType} sensorType 
     */
    async stopCalibration(sensorType) {
        console.log(`[CalibrationApi] Stopping calibration for ${sensorType}`);
        return { success: true };
    },

    /**
     * Triggers the calibration logic on a set of labeled windows.
     * @param {SensorType} sensorType 
     * @param {CalibrationWindow[]} labeledWindows 
     * @returns {Promise<Object>} Proposed parameter updates
     */
    async runCalibration(sensorType, labeledWindows) {
        console.log(`[CalibrationApi] Running calibration for ${sensorType} with ${labeledWindows.length} windows`);

        // Mock processing delay
        await new Promise(r => setTimeout(r, 1000));

        // Return dummy recommended updates based on sensor type
        if (sensorType === 'EMG') {
            return {
                recommendations: {
                    Rock: { rms: [450, 850] }, // shifted slightly
                    Rest: { rms: [0, 180] }
                },
                summary: {
                    total: labeledWindows.length,
                    correct: labeledWindows.filter(w => w.status === 'correct').length,
                    missed: labeledWindows.filter(w => w.isMissedActual).length
                }
            };
        }

        return { recommendations: {}, summary: { total: 0, correct: 0, missed: 0 } };
    }
};
