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
                    EOG: { SingleBlink: { threshold: 0.5 }, DoubleBlink: { threshold: 1.0 } },
                    EEG: { profiles: { Concentration: { power: 10 }, Relaxation: { power: 5 } } }
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
        // Legacy mock - use calibrateThresholds instead
        return { recommendations: {}, summary: { total: 0, correct: 0, missed: 0 } };
    },

    /**
     * Calibrate detection thresholds using all collected windows.
     * @param {SensorType} sensorType
     * @param {CalibrationWindow[]} windows - All collected windows with features
     * @returns {Promise<Object>} Calibration results with updated thresholds and accuracy
     */
    async calibrateThresholds(sensorType, windows) {
        console.log(`[CalibrationApi] Calibrating thresholds for ${sensorType} with ${windows.length} windows`);

        try {
            // Prepare windows payload with action, features, status
            const windowsPayload = windows.map(w => ({
                action: w.label,
                features: w.features || {},
                status: w.status
            }));

            const response = await fetch('/api/calibrate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    sensor: sensorType,
                    windows: windowsPayload
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Calibration failed');
            }

            const result = await response.json();
            console.log('[CalibrationApi] Calibration result:', result);
            return result;
        } catch (err) {
            console.error('[CalibrationApi] Calibration error:', err);
            throw err;
        }
    },

    /**
     * Send a single window (samples) to the backend for saving and feature extraction.
     * @param {string} sensorType
     * @param {{action: string, channel?: number, samples: number[], timestamps?: number[]}} windowPayload
     */
    async sendWindow(sensorType, windowPayload, sessionName = null) {
        try {
            const body = {
                sensor: sensorType,
                action: windowPayload.action,
                channel: windowPayload.channel,
                samples: windowPayload.samples,
                timestamps: windowPayload.timestamps,
                session_name: sessionName // Pass session name
            };

            const resp = await fetch('/api/window', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!resp.ok) {
                const txt = await resp.text();
                throw new Error(`Server error: ${resp.status} ${txt}`);
            }

            return resp.json();
        } catch (err) {
            console.error('[CalibrationApi] sendWindow error', err);
            throw err;
        }
    },

    /**
     * Lists all available recordings from the server.
     * @returns {Promise<Array<{name: string, size: number, created: number}>>}
     */
    async listRecordings() {
        try {
            const response = await fetch('/api/recordings');
            if (!response.ok) throw new Error('Failed to list recordings');
            return response.json();
        } catch (error) {
            console.error('[CalibrationApi] Error listing recordings:', error);
            return [];
        }
    },

    /**
     * Fetches the content of a specific recording.
     * @param {string} filename 
     * @returns {Promise<Object>}
     */
    async getRecording(filename) {
        try {
            const response = await fetch(`/api/recordings/${encodeURIComponent(filename)}`);
            console.log(response);
            if (!response.ok) throw new Error('Failed to fetch recording');
            return response.json();
        } catch (error) {
            console.error('[CalibrationApi] Error getting recording:', error);
            throw error;
        }
    },

    /**
     * Start EMG recording for a specific label.
     * @param {number} label - 0=Rest, 1=Rock, 2=Paper, 3=Scissors
     */
    async startEmgRecording(label) {
        try {
            const response = await fetch('/api/emg/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ label })
            });
            return response.json();
        } catch (error) {
            console.error('[CalibrationApi] Error starting EMG recording:', error);
            throw error;
        }
    },

    /**
     * Stop EMG recording.
     */
    async stopEmgRecording() {
        try {
            const response = await fetch('/api/emg/stop', { method: 'POST' });
            return response.json();
        } catch (error) {
            console.error('[CalibrationApi] Error stopping EMG recording:', error);
            throw error;
        }
    },

    /**
     * Get EMG recording status and counts.
     */
    async getEmgStatus() {
        try {
            const response = await fetch('/api/emg/status');
            if (!response.ok) return null;
            return response.json();
        } catch (error) {
            console.error('[CalibrationApi] Error getting EMG status:', error);
            return null;
        }
    },

    /**
     * Toggle real-time prediction for a sensor.
     * @param {string} sensorType 
     * @param {boolean} isActive 
     */
    async togglePrediction(sensorType, isActive) {
        if (sensorType !== 'EMG' && sensorType !== 'EOG') return;
        const action = isActive ? 'start' : 'stop';
        try {
            const response = await fetch(`/api/${sensorType.toLowerCase()}/predict/${action}`, { method: 'POST' });
            return response.json();
        } catch (error) {
            console.error(`[CalibrationApi] Error toggling ${sensorType} prediction:`, error);
        }
    }
};

