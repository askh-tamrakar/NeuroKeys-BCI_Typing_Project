import React, { useState, useEffect, useCallback, useRef } from 'react';
import TimeSeriesZoomChart from '../charts/TimeSeriesZoomChart';
import WindowListPanel from '../calibration/WindowListPanel';
import ConfigPanel from '../calibration/ConfigPanel';
import SessionManagerPanel from '../calibration/SessionManagerPanel';
import TestPanel from '../calibration/TestPanel';
import { CalibrationApi } from '../../services/calibrationApi';

/**
 * CalibrationView
 * The main container for the BCI calibration experience.
 */
export default function CalibrationView({ wsData, wsEvent, config: initialConfig }) {
    // Top-level states
    const [activeSensor, setActiveSensor] = useState('EMG'); // 'EMG' | 'EOG' | 'EEG'
    const [activeChannelIndex, setActiveChannelIndex] = useState(0); // Explicitly selected channel index
    const [mode, setMode] = useState('realtime'); // 'realtime' | 'recording' | 'collection'
    const [config, setConfig] = useState(initialConfig || {});
    const [isCalibrating, setIsCalibrating] = useState(false);
    const [runInProgress, setRunInProgress] = useState(false);
    const [windowProgress, setWindowProgress] = useState({});
    const [autoCalibrate, setAutoCalibrate] = useState(false); // Auto-calibration toggle

    // Data states
    const [chartData, setChartData] = useState([]);
    const [markedWindows, setMarkedWindows] = useState([]);
    const [readyWindows, setReadyWindows] = useState([]); // Windows waiting to be appended
    const [bufferWindows, setBufferWindows] = useState([]); // History of processed windows
    const [activeWindow, setActiveWindow] = useState(null);
    const [highlightedWindow, setHighlightedWindow] = useState(null); // New: for inspection
    const [targetLabel, setTargetLabel] = useState('Rock'); // e.g., 'Rock', 'Paper', etc.

    const [totalPredictedCount, setTotalPredictedCount] = useState(0);

    // Session Management
    const [sessionName, setSessionName] = useState(() => {
        const now = new Date();
        return `Session_${now.getDate()}_${now.getHours()}${now.getMinutes()}`;
    });
    const [appendMode, setAppendMode] = useState(false);
    const [autoLimit, setAutoLimit] = useState(30);

    const [dataLastUpdated, setDataLastUpdated] = useState(0);

    // Refs for accessing latest state inside interval/timeouts
    const chartDataRef = useRef(chartData);
    const activeSensorRef = useRef(activeSensor);
    const activeChannelIndexRef = useRef(activeChannelIndex); // Ref for channel
    const targetLabelRef = useRef(targetLabel);
    const markedWindowsRef = useRef(markedWindows);
    const readyWindowsRef = useRef(readyWindows);

    // Keep refs in sync
    useEffect(() => { chartDataRef.current = chartData; }, [chartData]);
    useEffect(() => { activeSensorRef.current = activeSensor; }, [activeSensor]);
    useEffect(() => { activeChannelIndexRef.current = activeChannelIndex; }, [activeChannelIndex]);
    useEffect(() => { targetLabelRef.current = targetLabel; }, [targetLabel]);
    useEffect(() => { markedWindowsRef.current = markedWindows; }, [markedWindows]);
    useEffect(() => { readyWindowsRef.current = readyWindows; }, [readyWindows]);
    const autoLimitRef = useRef(autoLimit);
    useEffect(() => { autoLimitRef.current = autoLimit; }, [autoLimit]);

    // Compute matching channels for the active sensor
    const matchingChannels = React.useMemo(() => {
        if (!config?.channel_mapping) return [];
        return Object.entries(config.channel_mapping)
            .filter(([key, val]) => val.sensor === activeSensor || val.type === activeSensor)
            .map(([key, val]) => ({
                id: key,
                index: parseInt(key.replace('ch', ''), 10),
                label: val.label || val.name || key
            }))
            .sort((a, b) => a.index - b.index);
    }, [activeSensor, config]);

    // Auto-select first matching channel when sensor changes
    useEffect(() => {
        console.log('[CalibrationView] matchingChannels:', matchingChannels);
        if (matchingChannels.length > 0) {
            // If current selection is not in the new list, reset to first match
            const exists = matchingChannels.find(c => c.index === activeChannelIndex);
            if (!exists) {
                console.log(`[CalibrationView] Auto-switching channel from ${activeChannelIndex} to ${matchingChannels[0].index} for sensor ${activeSensor}`);
                setActiveChannelIndex(matchingChannels[0].index);
            }
        } else {
            // Fallback if no mapping found (shouldn't happen with valid config)
            if (activeChannelIndex !== 0) setActiveChannelIndex(0);
        }
    }, [activeSensor, matchingChannels, activeChannelIndex]);

    // Ensure config is loaded on mount
    useEffect(() => {
        const loadConfig = async () => {
            try {
                const cfg = await CalibrationApi.fetchSensorConfig();
                console.log('[CalibrationView] Fetched config:', cfg);
                setConfig(cfg);
            } catch (err) {
                console.error('[CalibrationView] Failed to load config:', err);
            }
        };
        if (!initialConfig || Object.keys(initialConfig).length === 0) {
            loadConfig();
        }
    }, [initialConfig]);


    // Recording mode states
    const [availableRecordings, setAvailableRecordings] = useState([]);
    const [selectedRecording, setSelectedRecording] = useState(null);
    const [isRecording, setIsRecording] = useState(false);
    const [isLoadingRecording, setIsLoadingRecording] = useState(false);

    // Fetch recordings list
    const refreshRecordings = useCallback(async () => {
        const list = await CalibrationApi.listRecordings();
        setAvailableRecordings(list);
    }, []);

    useEffect(() => {
        refreshRecordings();
    }, [refreshRecordings]);

    // Handle recording selection and data loading
    useEffect(() => {
        const loadSelectedRecording = async () => {
            if (!selectedRecording || mode !== 'recording') return;

            setIsLoadingRecording(true);
            try {
                const recording = await CalibrationApi.getRecording(selectedRecording);

                // recording.data is Array of { timestamp, channels: { ch0, ch1... } }
                if (recording && recording.data) {
                    // Map to chartData format { time, value }
                    // Use activeChannelIndex
                    const targetChIdx = activeChannelIndex;

                    const formattedData = recording.data.map(point => ({
                        time: point.timestamp,
                        value: point.channels[`ch${targetChIdx}`] || point.channels[targetChIdx] || 0
                    }));

                    setChartData(formattedData);
                    console.log(`[CalibrationView] Loaded ${formattedData.length} samples for ${activeSensor} Ch${targetChIdx}`);
                }
            } catch (error) {
                console.error('[CalibrationView] Failed to load recording:', error);
                alert('Failed to load recording data.');
            } finally {
                setIsLoadingRecording(false);
            }
        };

        loadSelectedRecording();
    }, [selectedRecording, mode, activeSensor, activeChannelIndex]); // Depend on activeChannelIndex


    // Zoom state (Y-axis) similar to LiveView
    const [zoom, setZoom] = useState(1);
    const [manualYRange, setManualYRange] = useState("");
    const BASE_AMPLITUDE = 1500;

    const currentYDomain = React.useMemo(() => {
        if (manualYRange && !isNaN(parseFloat(manualYRange))) {
            const r = parseFloat(manualYRange);
            return [-r, r];
        }
        return [-BASE_AMPLITUDE / zoom, BASE_AMPLITUDE / zoom];
    }, [manualYRange, zoom]);

    // Refs for real-time windowing
    const windowIntervalRef = useRef(null);
    const [windowDuration, setWindowDuration] = useState(1500); // ms
    const GAP_DURATION = 500; // ms
    const [timeWindow, setTimeWindow] = useState(5000); // visible sweep window length for calibration plot
    const MAX_WINDOWS = 50;

    // Additional Refs for windowing logic (Defined here to avoid TDZ)
    const timeWindowRef = useRef(timeWindow);
    const windowDurationRef = useRef(windowDuration);

    useEffect(() => { timeWindowRef.current = timeWindow; }, [timeWindow]);
    useEffect(() => { windowDurationRef.current = windowDuration; }, [windowDuration]);

    // Handlers
    const handleSensorChange = (sensor) => {
        setActiveSensor(sensor);
        setMarkedWindows([]);
        setTotalPredictedCount(0);
        // Set default label based on sensor
        if (sensor === 'EMG') setTargetLabel('Rock');
        else if (sensor === 'EOG') setTargetLabel('SingleBlink');
        else if (sensor === 'EEG') setTargetLabel('Concentration');
    };

    const handleStartCalibration = async () => {
        setIsCalibrating(true);

        await CalibrationApi.startCalibration(activeSensor, mode, targetLabel, windowDuration, sessionName);

        if (mode === 'realtime') {
            // Start auto-windowing logic
            startAutoWindowing();
        }
    };

    const handleStopCalibration = async () => {
        setIsCalibrating(false);
        if (windowIntervalRef.current) clearInterval(windowIntervalRef.current);
        await CalibrationApi.stopCalibration(activeSensor);
        setActiveWindow(null);
    };

    const startAutoWindowing = () => {
        const createNextWindow = () => {
            // Access latest config from refs
            const currentTw = timeWindowRef.current;
            const currentDur = windowDurationRef.current;

            // Visual sync: Window spawns at visual edge (future) and travels to center (now)
            const delayToCenter = Math.round(currentTw / 2);

            const start = Date.now() + delayToCenter;
            const end = start + currentDur;

            // Capture current settings from refs
            const sensorForWindow = activeSensorRef.current;
            const labelForWindow = targetLabelRef.current;
            const channelForWindow = activeChannelIndexRef.current; // Use Ref

            const limit = autoLimitRef.current;
            const currentBatchCount = markedWindowsRef.current.filter(w =>
                w.label === labelForWindow &&
                (w.status === 'pending' || w.status === 'collected')
            ).length;

            console.log(`[AutoWindow] Limit: ${limit}, Current Batch: ${currentBatchCount}`);

            if (autoCalibrate && currentBatchCount >= limit) {
                // Do not spawn new window if batch target reached (wait for save)
                return;
            }

            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: sensorForWindow,
                mode: 'realtime',
                startTime: start,
                endTime: end,
                label: labelForWindow,
                channel: channelForWindow, // Store channel in window metadata
                status: 'pending', // Added immediately to list
                samples: []
            };

            // Add to list IMMEDIATELY so it appears and travels with the chart
            setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));
            setActiveWindow(newWindow); // Keep track for logic, but maybe not render separately?

            // Function to wait for data to arrive
            const checkAndCollect = async () => {
                // Check if window still exists (was not deleted)
                if (!markedWindowsRef.current.find(w => w.id === newWindow.id)) {
                    return;
                }

                const currentData = chartDataRef.current;

                // DATA SYNC CHECK:
                // Ensure the LATEST data point in buffer is at least as new as 'end'
                // If not, wait a bit longer (up to a timeout).
                const latestDataTs = currentData.length > 0 ? currentData[currentData.length - 1].time : 0;

                if (latestDataTs < end - 50) { // Tolerance of 50ms
                    // Data hasn't arrived yet!
                    const now = Date.now();
                    // Sanity check: If we are WAY past 'end' (e.g. 5 seconds) and still no data, abort.
                    if (now > end + 5000) {
                        console.warn("[AutoWindow] Timed out waiting for data.");
                    } else {
                        // Check again in 100ms
                        setTimeout(checkAndCollect, 100);
                        return;
                    }
                }

                try {
                    // Extract samples from chartDataRef (latest data)
                    const samplesPoints = currentData.filter(p => p.time >= start && p.time <= end);

                    // If zero samples found, but we waited... try one last re-filter with slightly wider tolerance?
                    // Or just fail.

                    if (samplesPoints.length === 0) {
                        // Debug info
                        const dataStart = currentData.length > 0 ? currentData[0].time : 'N/A';
                        const dataEnd = currentData.length > 0 ? currentData[currentData.length - 1].time : 'N/A';
                        console.warn(`[AutoWindow] Empty Win: ${start}-${end}. Data Range: ${dataStart}-${dataEnd}. WaitTs: ${latestDataTs}`);
                        throw new Error("No data collected");
                    }

                    const samples = samplesPoints.map(p => p.value);
                    const timestamps = samplesPoints.map(p => p.time);

                    const collectedWindow = {
                        ...newWindow,
                        samples,
                        timestamps,
                        status: 'collected' // GREEN
                    };

                    setReadyWindows(prev => {
                        const next = [...prev, collectedWindow];
                        setWindowProgress(prevProg => ({ ...prevProg, [newWindow.id]: { status: 'collected' } }));
                        return next;
                    });

                    // Update UI List to show GREEN
                    setMarkedWindows(prev => prev.map(w => w.id === newWindow.id ? { ...w, status: 'collected', samples } : w));

                } catch (err) {
                    console.error('Auto-collection error:', err);
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error', message: String(err) } }));

                    // Error -> BLACK -> Buffer (History)
                    const errorWindow = { ...newWindow, status: 'error', error: String(err) };
                    setBufferWindows(prev => [...prev, errorWindow]);
                    setMarkedWindows(prev => prev.map(w => w.id === newWindow.id ? { ...w, status: 'error' } : w));

                } finally {
                    setActiveWindow(null);
                }
            };

            // Initial wait: wait until visual end, plus a small buffer
            setTimeout(checkAndCollect, delayToCenter + currentDur + 100);
        };

        createNextWindow();
        windowIntervalRef.current = setInterval(createNextWindow, windowDuration + GAP_DURATION);
    };

    const handleManualWindowSelect = async (start, end) => {
        // Create window object
        const newWindow = {
            id: Math.random().toString(36).substr(2, 9),
            sensor: activeSensor,
            mode: 'recording',
            startTime: start,
            endTime: end,
            label: targetLabel,
            channel: activeChannelIndex,
            status: 'recording', // Initially Yellow
            samples: []
        };

        try {
            // Extract samples from chartDataRef
            const currentData = chartDataRef.current;
            const samplesPoints = currentData.filter(p => p.time >= start && p.time <= end);

            if (!samplesPoints || samplesPoints.length === 0) {
                // Throw to enter catch block -> Buffer as Error
                throw new Error("No data in selected range");
            }

            const samples = samplesPoints.map(p => p.value);
            const timestamps = samplesPoints.map(p => p.time);

            newWindow.samples = samples;
            newWindow.timestamps = timestamps;
            newWindow.status = 'collected'; // GREEN

            // Add to READY list
            setReadyWindows(prev => [...prev, newWindow]);

            // Add to UI List (if not already there) and set as collected
            setMarkedWindows(prev => {
                const existing = prev.find(w => w.id === newWindow.id);
                if (existing) {
                    return prev.map(w => w.id === newWindow.id ? { ...w, status: 'collected', samples } : w);
                }
                // If manual was not in list, add it
                return [...prev, newWindow].slice(-50);
            });

        } catch (err) {
            console.warn("Manual selection error:", err);
            newWindow.status = 'error'; // BLACK

            // Add to BUFFER as Error history
            setBufferWindows(prev => [...prev, newWindow]);
        }
    };

    /**
     * Saves all 'collected' (Green) windows from readyWindows to the database.
     */
    const handleAppendSamples = async () => {
        // Use Ref to get current snapshot of ready windows
        const toAppend = readyWindowsRef.current;

        if (!toAppend || toAppend.length === 0) return;

        setRunInProgress(true);

        // Mark strictly the ready windows as saving? 
        // Or just iterate them.

        try {
            let savedCount = 0;

            for (const win of toAppend) {
                try {
                    const resp = await CalibrationApi.sendWindow(activeSensor, {
                        action: win.label,
                        channel: win.channel,
                        samples: win.samples,
                        timestamps: win.timestamps
                    }, sessionName);

                    // Success -> Create Saved version for Buffer
                    const savedWindow = {
                        ...win,
                        status: 'saved', // RED
                        features: resp.features,
                        predictedLabel: resp.predicted_label
                    };

                    // Move to Buffer
                    setBufferWindows(prev => [...prev, savedWindow]);
                    savedCount++;

                    // Update UI List to show SAVED (e.g. Red/Blue)
                    setMarkedWindows(prev => prev.map(w => w.id === win.id ? {
                        ...w,
                        status: 'saved',
                        features: resp.features,
                        predictedLabel: resp.predicted_label
                    } : w));

                } catch (err) {
                    console.error("Error saving window:", win.id, err);
                    // Error -> BLACK -> Buffer
                    const errorWindow = { ...win, status: 'error', error: String(err) };
                    setBufferWindows(prev => [...prev, errorWindow]);
                }
            }

            // Clear Ready List (all were processed into buffer, either as saved or error)
            setReadyWindows([]);

            if (savedCount > 0) {
                setDataLastUpdated(Date.now()); // Trigger table refresh
            }

        } finally {
            setRunInProgress(false);
        }
    };

    const deleteWindow = (id) => {
        setMarkedWindows(prev => prev.filter(w => w.id !== id));
    };

    const handleClearAllWindows = () => {
        setMarkedWindows([]);
        setReadyWindows([]);
        setBufferWindows([]);
        setTotalPredictedCount(0);
    };

    const markMissed = (id) => {
        setMarkedWindows(prev => prev.map(w => w.id === id ? { ...w, isMissedActual: !w.isMissedActual } : w));
    };

    // Test Mode Handler: Spawns a window, waits, extracts, sends, returns prediction.
    const handleTestRecord = async (targetGestureLabel) => {
        console.log("[Test] Spawning window for:", targetGestureLabel);
        return new Promise((resolve, reject) => {
            const currentTw = timeWindowRef.current;
            const currentDur = windowDurationRef.current;

            // Spawn window IMMEDIATELY at center (time=now) to ensure visibility
            // Window is [Now, Now+Dur]. Center is reference.
            // visual X = center - (now - t).
            // t=now => X=center. t=now+dur => X=center+dur.
            // If scanner is at center, this means it starts at scanner and grows right?
            // Actually, we want it to start at scanner and travel left? 
            // "Realtime" chart moves data Left to Right? 
            // No, standard is Newest at Right?
            // "Sweeep" chart: Newest at Center. Old is Left. Future is Right.
            // So Future window should be at Right of Center.
            // If data moves Left, Window should move Left with it.
            // So we spawn it at Center?
            // Start (spawn) the window such that it reaches the center exactly when we want to record?
            // "Scrolling" visualization: Future is Right, Past is Left. Center is Now.
            // If we want the user to see it APPROACH, we must spawn it in the Future (Right).
            // Then it travels left.
            // When it hits Center (Now), we record.
            const delayToCenter = currentTw / 2;
            const start = Date.now() + delayToCenter; // Future timestamp
            const end = start + currentDur;

            console.log(`[Test] Window Spawn: Start=${start} End=${end} (Now=${Date.now()})`);

            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: activeSensor,
                mode: 'test',
                startTime: start,
                endTime: end,
                label: targetGestureLabel, // "Rock" etc.
                channel: activeChannelIndex,
                status: 'pending',
                samples: [] // Will be filled
            };

            // Add to list so user sees it coming
            setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));
            setActiveWindow(newWindow);
            setRunInProgress(true); // Locks UI slightly

            // Wait for window to pass center
            setTimeout(async () => {
                // Check if window still exists
                if (!markedWindowsRef.current.find(w => w.id === newWindow.id)) {
                    reject(new Error("Window deleted"));
                    return;
                }

                try {
                    const currentData = chartDataRef.current;
                    const samplesPoints = currentData.filter(p => p.time >= start && p.time <= end);
                    const samples = samplesPoints.map(p => p.value);
                    const timestamps = samplesPoints.map(p => p.time);

                    if (samples.length === 0) throw new Error("No data collected");

                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saving' } }));

                    // Send to backend with action="Test" or similar to imply we want a blind prediction if possible
                    // Actually we can pass the real label so backend can ALSO check 'detected'
                    // But we want the blind label too.
                    const resp = await CalibrationApi.sendWindow(activeSensor, {
                        action: targetGestureLabel,
                        channel: activeChannelIndex,
                        samples,
                        timestamps
                    }, sessionName);

                    // Update UI status
                    // Removed: Prediction check (user request)
                    // Always mark as 'saved' (green)
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saved' } }));

                    setMarkedWindows(prev => prev.map(w => {
                        if (w.id === newWindow.id) {
                            return {
                                ...w,
                                predictedLabel: resp.predicted_label, // Keep for debug, but don't rely on it
                                status: 'saved', // New status for Green
                                features: resp.features,
                                samples: samples // Store raw samples for graph
                            };
                        }
                        return w;
                    }));

                    // Resolve promise for TestPanel
                    resolve({ detected: resp.detected, predicted_label: resp.predicted_label });

                } catch (e) {
                    console.error("Test record failed:", e);
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error' } }));
                    reject(e);
                } finally {
                    setRunInProgress(false);
                    setActiveWindow(null);
                }
            }, delayToCenter + currentDur + 200); // +200ms buffer
        });
    };

    // Run calibration logic
    const runCalibration = useCallback(async (isAuto = false) => {
        if (!markedWindows || markedWindows.length === 0) return;

        setRunInProgress(true);
        try {
            // Filter windows to only those matching the current target label (per user request)
            const windowsToCalibrate = markedWindows.filter(w => w.label === targetLabel);

            if (windowsToCalibrate.length === 0) {
                console.warn('[CalibrationView] No matching windows for target label:', targetLabel);
                setRunInProgress(false);
                return;
            }

            // 1. Call robust calibration endpoint
            const result = await CalibrationApi.calibrateThresholds(activeSensor, windowsToCalibrate);
            console.log('[CalibrationView] Calibration result:', result);

            // 2. Update config locally
            // Ideally we also trigger the ConfigPanel to reload, but since config is lifted state in parent (usually), 
            // or here passing down... currently `config` is local state.
            // We should refetch configuration.
            const refreshedConfig = await CalibrationApi.fetchSensorConfig();
            setConfig(refreshedConfig);

            if (isAuto || autoCalibrate) {
                // Auto-mode: Reset progress and samples
                setMarkedWindows([]);
                console.log('[CalibrationView] Auto-calibration complete. Resetting samples.');
            } else {
                // Manual mode: Update window statuses to show results
                if (result.window_results) {
                    setMarkedWindows(prev => {
                        return prev.map((w, i) => {
                            const res = result.window_results[i];
                            // Heuristic match by index as IDs might not persist in backend pure logic
                            // If actions match
                            if (res && res.action === w.label) {
                                return {
                                    ...w,
                                    status: res.status_after,
                                    predictedLabel: res.status_after === 'correct' ? w.label : 'Rest'
                                };
                            }
                            return w;
                        });
                    });
                }
                const acc = result.accuracy_after !== undefined ? result.accuracy_after : (result.accuracy || 0);
                alert(`Calibration Complete! Accuracy: ${(acc * 100).toFixed(1)}%`);
                // Reset just like auto mode
                setMarkedWindows([]);
                setTotalPredictedCount(0);
            }

        } catch (err) {
            console.error('Calibration error:', err);
            // Only alert in manual mode or log in auto
            if (!isAuto) {
                alert(`Calibration failed: ${err.message}`);
            } else {
                console.warn('Auto-calibration failed. Disabling auto-mode.');
                setAutoCalibrate(false);
            }
        } finally {
            setRunInProgress(false);
        }
    }, [markedWindows, activeSensor, autoCalibrate]);

    // Auto-Calibration / Auto-Save Trigger
    useEffect(() => {
        if (!autoCalibrate || runInProgress) return;

        // Count valid active samples (ready to save)
        const readyBatchCount = markedWindows.filter(w => w.status === 'collected' && w.label === targetLabel).length;
        console.log(`[AutoEffect] Ready Batch: ${readyBatchCount}, Limit: ${autoLimit}`);

        // Check Limit (Batch Size)
        if (readyBatchCount >= autoLimit) {
            // Check if we have unsaved collected windows
            const hasUnsaved = markedWindows.some(w => w.status === 'collected');

            if (hasUnsaved) {
                console.log(`[CalibrationView] Limit ${autoLimit} reached. Auto-appending...`);
                handleAppendSamples();
            }
            return;
        }

    }, [markedWindows, autoCalibrate, isCalibrating, runInProgress, activeSensor, autoLimit]);

    // Update chart data from WS or Mock
    useEffect(() => {
        if ((mode === 'realtime' || mode === 'test') && wsData) {
            const payload = wsData.raw || wsData;

            // Unify batch vs single handling (match LiveView logic)
            // Some backends send { _batch: [...] }, others { type: 'batch', samples: [...] }
            // or just a single { channels: ... } object.

            let samples = [];
            if (payload._batch) {
                samples = payload._batch;
            } else if (payload.type === 'batch' && Array.isArray(payload.samples)) {
                samples = payload.samples;
            } else if (payload.channels) {
                samples = [payload];
            }

            if (samples.length === 0) return;

            // Use sampling rate from config, default to 250Hz
            const samplingRate = config?.sampling_rate || 250;
            const sampleIntervalMs = Math.round(1000 / samplingRate);

            const newPoints = [];
            const channelIndex = activeChannelIndex;

            samples.forEach((s) => {
                let incomingTs = Number(s.timestamp);
                if (!incomingTs || incomingTs < 1e9) incomingTs = Date.now();

                // Monotonic timestamp logic
                if (!window.__calibLastTs) window.__calibLastTs = incomingTs;

                // Enforce monotonicity if it's a batch sequence or just subsequent packets
                if (incomingTs <= window.__calibLastTs) {
                    incomingTs = window.__calibLastTs + sampleIntervalMs;
                }
                window.__calibLastTs = incomingTs;

                // Robust channel extraction (Array or Object)
                if (s.channels) {
                    let rawVal = undefined;
                    // Try direct index
                    if (s.channels[channelIndex] !== undefined) rawVal = s.channels[channelIndex];
                    // Try string key "ch0" if needed
                    else if (s.channels[`ch${channelIndex}`] !== undefined) rawVal = s.channels[`ch${channelIndex}`];

                    if (rawVal !== undefined) {
                        const val = typeof rawVal === 'number' ? rawVal : (rawVal.value || 0);
                        newPoints.push({ time: incomingTs, value: val });
                    }
                }
            });

            if (newPoints.length > 0) {
                setChartData(prev => {
                    const next = [...prev, ...newPoints];
                    // Limit buffer size
                    if (next.length > 10000) return next.slice(-10000);
                    return next;
                });
            }
        }
    }, [wsData, mode, activeSensor, activeChannelIndex]);

    const [frameTime, setFrameTime] = useState(Date.now());

    useEffect(() => {
        if (chartData.length > 0) {
            const latestTs = chartData[chartData.length - 1].time;
            setFrameTime(latestTs);
        } else {
            // Fallback to wall clock if no data
            setFrameTime(Date.now());
        }
    }, [chartData]);
    // Compute sweep-style data for calibration: plotted portion left of center, unplotted baseline to right
    const sweepChartData = React.useMemo(() => {
        const w = timeWindow;
        const center = Math.round(w / 2);
        // Use synchronized frameTime
        const now = frameTime;

        // plotted points: newest at center, older to the left
        // Optimization: iterate from end
        // plotted points: newest at center, older to the left
        // Optimization: iterate from end
        const plotted = [];
        for (let i = chartData.length - 1; i >= 0; i--) {
            const d = chartData[i];

            // STRICT CLIP: Do not plot points from the future (right of center)
            if (d.time > now) continue;

            const age = now - d.time;
            if (age > center) break; // Optimization: Stop if older than window left edge
            const x = Math.round(center - age);
            // Relaxed filter to allow points slightly off-screen to prevent line clipping
            if (x >= -100) plotted.unshift({ time: x, value: d.value });
        }

        const merged = [...plotted];

        // BRIDGE THE GAP:
        // Add a point exactly at 'center' with the newest value to connect the line visually
        // to the baseline (if we want baseline) or just to terminate cleanly at the cursor.
        // If we want the line to look like it continues flat, we add (center, lastVal).
        // Also start the 'future' line here so they connect? 
        // We set future: 0 at center to start the flat line.
        if (plotted.length > 0) {
            const lastVal = plotted[plotted.length - 1].value;
            // Push a point right at the cursor line. 
            // We give it 'value' (for history line to reach center) AND 'future' (for future line to start at 0? No, usually separate)
            // If we want the future line to start at y=0, we should put a point at (center, future=0).
            // But if we want it to look connected, maybe not.
            // User requested "horizontal line on the point y = 0".
            // So independent of where signal ends, it should be at 0.
            merged.push({ time: Math.round(center), value: lastVal });
        }

        // Future baseline (flat line at 0)
        const step = 50; // ms resolution
        // Start exactly at center to ensure it touches the cursor line
        for (let t = center; t <= w; t += step) {
            merged.push({ time: Math.round(t), future: 0 });
        }

        merged.sort((a, b) => a.time - b.time);

        return merged;
    }, [chartData, timeWindow, frameTime]); // Depend on frameTime

    // Map action windows to sweep coordinates so they match the chart data (center-relative)
    const mappedWindows = React.useMemo(() => {
        // Use SAME synchronized frameTime
        const now = frameTime;
        const w = timeWindow;
        const center = Math.round(w / 2);

        const mapped = markedWindows.map(win => {
            const ageStart = now - win.startTime;
            const ageEnd = now - win.endTime;

            const x1 = Math.round(center - ageEnd);     // Right edge
            const x2 = Math.round(center - ageStart);   // Left edge

            return {
                ...win,
                startTime: x2,
                endTime: x1
            };
        });

        if (markedWindows.length > 0 && Math.random() < 0.05) {
            console.log("[CalibrationView] Mapped:", mapped.length, "First:", mapped[0]);
        }

        return mapped;
    }, [markedWindows, timeWindow, frameTime]); // Depend on frameTime

    // Active/Pending Window
    const activeWindowMapped = React.useMemo(() => {
        if (!activeWindow) return null;
        // Use SAME synchronized frameTime
        const now = frameTime;
        const w = timeWindow;
        const center = Math.round(w / 2);

        const x1 = Math.round(center - (now - activeWindow.endTime));
        const x2 = Math.round(center - (now - activeWindow.startTime));

        return { ...activeWindow, startTime: x2, endTime: x1 };
    }, [activeWindow, timeWindow, frameTime]);

    // Highlighted Window (for inspection)
    const highlightedWindowMapped = React.useMemo(() => {
        if (!highlightedWindow) return null;
        const now = frameTime;
        const w = timeWindow;
        const center = Math.round(w / 2);

        const x1 = Math.round(center - (now - highlightedWindow.endTime));
        const x2 = Math.round(center - (now - highlightedWindow.startTime));

        return { ...highlightedWindow, startTime: x2, endTime: x1, color: '#ff00ff' }; // magenta highlight
    }, [highlightedWindow, timeWindow, frameTime]);


    const scannerValue = chartData.length ? chartData[chartData.length - 1].value : 0;

    // Cleanup
    useEffect(() => {
        return () => {
            if (windowIntervalRef.current) clearInterval(windowIntervalRef.current);
        };
    }, []);

    return (
        <div className="flex flex-col h-[calc(100dvh-120px)] bg-bg text-text animate-in fade-in duration-500 overflow-hidden">

            {/* TOP ROW: SIDEBAR + CHART (50%) */}
            <div className="h-[50%] flex-none flex min-h-0 p-2 gap-2">
                {/* SIDEBAR CARD */}
                <div className="w-[260px] flex-none flex flex-col bg-surface border border-border rounded-xl shadow-sm overflow-hidden">
                    {/* Sidebar Header */}
                    <div className="p-3 border-b border-border flex items-center gap-2 bg-surface/50">
                        <div className="p-1.5 bg-primary/10 rounded-lg border border-primary/20 shrink-0">
                            <span className="text-lg">🎯</span>
                        </div>
                        <div>
                            <h2 className="text-sm font-bold tracking-tight leading-tight">Calibration</h2>
                            <p className="text-xs text-muted font-mono uppercase tracking-widest">Controls</p>
                        </div>
                    </div>

                    {/* Sidebar Scrollable Content */}
                    <div className="flex-grow overflow-y-auto p-3 space-y-4 custom-scrollbar">

                        {/* 1. SENSOR & MODE */}
                        <div className="space-y-2">
                            <label className="text-xs font-bold text-muted uppercase tracking-wider block">Sensor & Mode</label>
                            <div className="flex bg-bg p-1 rounded-lg border border-border">
                                {['EMG', 'EOG', 'EEG'].map(s => (
                                    <button
                                        key={s}
                                        onClick={() => handleSensorChange(s)}
                                        className={`flex-1 py-1 rounded font-bold text-xs transition-all ${activeSensor === s ? 'bg-primary text-primary-contrast shadow-sm' : 'text-muted hover:text-text'
                                            }`}
                                    >
                                        {s}
                                    </button>
                                ))}
                            </div>
                            <div className="grid grid-cols-3 gap-1">
                                {['realtime', 'recording', 'test'].map(m => (
                                    <button
                                        key={m}
                                        onClick={() => setMode(m)}
                                        className={`px-1 py-1 rounded font-bold text-xs transition-all uppercase tracking-wider border border-transparent ${mode === m
                                            ? 'bg-accent text-primary-contrast shadow-sm border-accent/20'
                                            : 'bg-bg text-muted hover:text-text hover:border-border'
                                            }`}
                                    >
                                        {m}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 2. CHANNELS (If Multi) */}
                        {matchingChannels.length > 1 && (
                            <div className="space-y-2 animate-in slide-in-from-left-2 duration-300">
                                <label className="text-xs font-bold text-muted uppercase tracking-wider block">Active Channel</label>
                                <div className="flex flex-wrap gap-2">
                                    {matchingChannels.map(ch => (
                                        <button
                                            key={ch.id}
                                            onClick={() => setActiveChannelIndex(ch.index)}
                                            className={`px-2 py-1 rounded font-bold text-xs transition-all uppercase tracking-wider border ${activeChannelIndex === ch.index
                                                ? 'bg-primary text-primary-contrast border-primary shadow-sm'
                                                : 'bg-bg text-muted border-border hover:text-text'
                                                }`}
                                        >
                                            {ch.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        <div className="h-[1px] w-full bg-border/50"></div>

                        {/* 3. COLLECTION CONTROLS */}
                        <div className="space-y-3">
                            <label className="text-xs font-bold text-muted uppercase tracking-wider block">Data Collection</label>

                            {/* Target Label */}
                            <div className="space-y-1">
                                <span className="text-xs text-muted uppercase">Target Label</span>
                                <div className="relative">
                                    <select
                                        value={targetLabel}
                                        onChange={(e) => setTargetLabel(e.target.value)}
                                        className="w-full appearance-none bg-bg border border-border rounded px-2 py-1.5 text-xs font-bold font-mono outline-none focus:border-primary transition-colors pr-6"
                                    >
                                        {activeSensor === 'EMG' && ['Rock', 'Paper', 'Scissors', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                        {activeSensor === 'EOG' && ['SingleBlink', 'DoubleBlink', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                        {activeSensor === 'EEG' && ['Concentration', 'Relaxation', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                    </select>
                                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-muted pointer-events-none text-[10px]">▼</span>
                                </div>
                            </div>

                            {/* Action Button */}
                            <button
                                onClick={isCalibrating ? handleStopCalibration : handleStartCalibration}
                                className={`w-full py-3 rounded-lg font-black text-sm uppercase tracking-widest transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 ${isCalibrating
                                    ? 'bg-red-500 text-white hover:bg-red-600 shadow-red-500/20'
                                    : 'bg-primary text-primary-contrast hover:opacity-90 shadow-primary/25'
                                    }`}
                            >
                                {isCalibrating ? 'STOP' : 'START CAPTURE'}
                            </button>
                        </div>
                    </div>
                </div>

                {/* CHART CARD */}
                <div className="flex-grow min-w-0 bg-surface border border-border rounded-xl shadow-sm overflow-hidden flex flex-col relative group">
                    {/* Status Badge Overlay */}
                    <div className="absolute top-1.5 right-3 z-10">
                        <div className={`px-2 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider border backdrop-blur-sm shadow-sm ${isCalibrating
                            ? 'bg-red-500/10 text-red-500 border-red-500/20 animate-pulse'
                            : 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'}`}>
                            {isCalibrating ? '● REC' : '● IDLE'}
                        </div>
                    </div>

                    {/* Chart Header Controls */}
                    <div className="px-3 py-1.5 border-b border-border bg-surface/50 flex items-center justify-between gap-4 max-h-[40px] flex-none">
                        <div className="flex items-center gap-3 overflow-x-auto no-scrollbar">
                            {/* Zoom */}
                            <div className="flex items-center gap-2 shrink-0">
                                <span className="text-xs font-bold text-muted uppercase">Zoom</span>
                                <div className="flex gap-0.5">
                                    {[1, 2, 5, 10, 25].map(z => (
                                        <button
                                            key={z}
                                            onClick={() => { setZoom(z); setManualYRange(""); }}
                                            className={`px-1.5 py-0.5 text-xs rounded font-bold transition-all ${zoom === z && !manualYRange
                                                ? 'bg-primary text-white shadow-sm'
                                                : 'bg-surface hover:bg-white/10 text-muted hover:text-text border border-border'
                                                }`}
                                        >
                                            {z}x
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <div className="w-[1px] h-3 bg-border shrink-0"></div>

                            {/* Window / Duration */}
                            <div className="flex items-center gap-2 shrink-0">
                                <label className="text-xs font-bold text-muted uppercase">Win</label>
                                <select
                                    value={timeWindow}
                                    onChange={(e) => setTimeWindow(Number(e.target.value))}
                                    className="bg-bg border border-border rounded px-1 py-0.5 text-xs font-mono outline-none"
                                >
                                    {[3000, 5000, 8000, 10000, 15000, 20000].map(v => (
                                        <option key={v} value={v}>{v / 1000}s</option>
                                    ))}
                                </select>

                                <label className="text-xs font-bold text-muted uppercase ml-1">Dur</label>
                                <select
                                    value={windowDuration}
                                    onChange={(e) => setWindowDuration(Number(e.target.value))}
                                    className="bg-bg border border-border rounded px-1 py-0.5 text-xs font-mono outline-none"
                                >
                                    {[500, 1000, 1500, 2000].map(v => (
                                        <option key={v} value={v}>{v}ms</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                    </div>

                    <div className="flex-grow relative">
                        <div className="absolute inset-0 p-2">
                            <TimeSeriesZoomChart
                                data={sweepChartData}
                                title=""
                                mode={mode}
                                height="100%"
                                markedWindows={mappedWindows}
                                activeWindow={null}
                                onWindowSelect={handleManualWindowSelect}
                                yDomain={currentYDomain}
                                scannerX={Math.round(timeWindow / 2)}
                                scannerValue={scannerValue}
                                timeWindowMs={timeWindow}
                                color={activeSensor === 'EMG' ? '#3b82f6' : (activeSensor === 'EOG' ? '#10b981' : '#f59e0b')}
                                curveType="natural"
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* BOTTOM ROW: SESSION + WINDOW LIST (50%) */}
            <div className="h-[50%] flex-none min-h-0 p-2 pt-0 grid grid-cols-1 lg:grid-cols-12 gap-2">
                {/* Session Panel */}
                <div className="lg:col-span-9 h-full min-h-0 overflow-hidden rounded-xl border border-border shadow-sm">
                    {mode === 'realtime' ? (
                        <SessionManagerPanel
                            activeSensor={activeSensor}
                            currentSessionName={sessionName}
                            onSessionChange={setSessionName}
                            refreshTrigger={dataLastUpdated}
                        />
                    ) : (
                        <ConfigPanel config={config} sensor={activeSensor} onSave={setConfig} />
                    )}
                </div>

                {/* Window List */}
                <div className="lg:col-span-3 h-full min-h-0 overflow-hidden rounded-xl border border-border shadow-sm">
                    <WindowListPanel
                        windows={markedWindows}
                        onDelete={deleteWindow}
                        onMarkMissed={markMissed}
                        onHighlight={setHighlightedWindow}
                        activeSensor={activeSensor}
                        windowProgress={windowProgress}
                        autoLimit={autoLimit}
                        onAutoLimitChange={setAutoLimit}
                        autoCalibrate={autoCalibrate}
                        onAutoCalibrateChange={setAutoCalibrate}
                        onClearSaved={handleAppendSamples}
                        onDeleteAll={handleClearAllWindows}
                    />
                </div>
            </div>
        </div>
    );
}
