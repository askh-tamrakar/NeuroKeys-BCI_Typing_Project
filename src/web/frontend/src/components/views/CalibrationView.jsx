import React, { useState, useEffect, useCallback, useRef } from 'react';
import WorkerTimeSeriesChart from '../charts/WorkerTimeSeriesChart';
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
    // Data states (chartData removed for Worker optimization)
    // const [chartData, setChartData] = useState([]); // REMOVED

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
    // const chartDataRef = useRef(chartData); // REMOVED
    const chartRef = useRef(null); // Access to Worker Chart
    const latestSignalTimeRef = useRef(Date.now()); // Track latest TS for logic

    const activeSensorRef = useRef(activeSensor);
    const activeChannelIndexRef = useRef(activeChannelIndex); // Ref for channel
    const targetLabelRef = useRef(targetLabel);
    const markedWindowsRef = useRef(markedWindows);
    const readyWindowsRef = useRef(readyWindows);

    // Keep refs in sync
    // useEffect(() => { chartDataRef.current = chartData; }, [chartData]);

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

                    // Wait for chartRef to be ready?
                    if (chartRef.current) {
                        chartRef.current.clearData();
                        chartRef.current.addData(formattedData);
                    }
                    latestSignalTimeRef.current = formattedData.length > 0 ? formattedData[formattedData.length - 1].time : Date.now();

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
    const MAX_WINDOWS = autoCalibrate ? 50 : 2000;

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

    const startAutoWindowing = useCallback(() => {
        const createNextWindow = () => {
            const currentTw = timeWindowRef.current;
            const currentDur = windowDurationRef.current;

            // Use latest signal timestamp tracked via WS
            const latestTs = latestSignalTimeRef.current;

            // Visual sync spawn
            const delayToCenter = Math.round(currentTw / 2);
            const start = latestTs + delayToCenter;
            const end = start + currentDur;

            const sensorForWindow = activeSensorRef.current;
            const labelForWindow = targetLabelRef.current;
            const channelForWindow = activeChannelIndexRef.current;
            const limit = autoLimitRef.current;

            // Count pending/collected matching label
            const currentBatchCount = markedWindowsRef.current.filter(w =>
                w.label === labelForWindow &&
                (w.status === 'pending' || w.status === 'collected')
            ).length;

            if (autoCalibrate && currentBatchCount >= limit) {
                return;
            }

            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: sensorForWindow,
                mode: 'realtime',
                startTime: start,
                endTime: end,
                label: labelForWindow,
                channel: channelForWindow,
                status: 'pending',
                samples: []
            };

            setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));
            setActiveWindow(newWindow);

            const checkAndCollect = async () => {
                // Check if still valid
                if (!markedWindowsRef.current.find(w => w.id === newWindow.id)) return;

                // Sync check
                const latestDataTs = latestSignalTimeRef.current;
                const systemLag = Math.max(0, Date.now() - latestDataTs);

                const shiftedStart = start + systemLag;
                const shiftedEnd = end + systemLag;

                if (latestDataTs < shiftedEnd - 50) {
                    // Wait slightly longer
                    const now = Date.now();
                    if (now > shiftedEnd + 5000) {
                        console.warn("[AutoWindow] Timeout waiting for data");
                        return; // Abort
                    }
                    setTimeout(checkAndCollect, 100);
                    return;
                }

                try {
                    // ASYNC FETCH FROM WORKER
                    if (!chartRef.current) throw new Error("Chart not ready");

                    const samplesPoints = await chartRef.current.getSamples(shiftedStart, shiftedEnd);

                    if (!samplesPoints || samplesPoints.length === 0) {
                        throw new Error("No data collected");
                    }

                    const samples = samplesPoints.map(p => p.value);
                    const timestamps = samplesPoints.map(p => p.time);

                    const collectedWindow = {
                        ...newWindow,
                        startTime: shiftedStart,
                        endTime: shiftedEnd,
                        samples,
                        timestamps,
                        status: 'collected',
                        lagCorrection: systemLag
                    };

                    setReadyWindows(prev => {
                        const next = [...prev, collectedWindow];
                        setWindowProgress(prevProg => ({ ...prevProg, [newWindow.id]: { status: 'collected' } }));
                        return next;
                    });

                    setMarkedWindows(prev => prev.map(w => w.id === newWindow.id ? collectedWindow : w));

                } catch (err) {
                    console.error('Auto-collection error:', err);
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error', message: String(err) } }));

                    const errorWindow = { ...newWindow, status: 'error', error: String(err) };
                    setBufferWindows(prev => [...prev, errorWindow]);
                    setMarkedWindows(prev => prev.map(w => w.id === newWindow.id ? { ...w, status: 'error' } : w));

                } finally {
                    setActiveWindow(null);
                }
            };

            // Initial wait
            setTimeout(checkAndCollect, delayToCenter + currentDur + 100);
        };

        createNextWindow();
        windowIntervalRef.current = setInterval(createNextWindow, windowDuration + GAP_DURATION);
    }, [windowDuration, GAP_DURATION, activeSensor, targetLabel, activeChannelIndex, autoLimit, autoCalibrate]);

    const handleStartCalibration = useCallback(async () => {
        setIsCalibrating(true);

        await CalibrationApi.startCalibration(activeSensor, mode, targetLabel, windowDuration, sessionName);

        if (mode === 'realtime') {
            // Start auto-windowing logic
            startAutoWindowing();
        }
    }, [activeSensor, mode, targetLabel, windowDuration, sessionName, startAutoWindowing]);

    const handleStopCalibration = useCallback(async () => {
        setIsCalibrating(false);
        if (windowIntervalRef.current) clearInterval(windowIntervalRef.current);
        await CalibrationApi.stopCalibration(activeSensor);
        setActiveWindow(null);
    }, [activeSensor]);




    const handleManualWindowSelect = useCallback(async (start, end) => {
        const newWindow = {
            id: Math.random().toString(36).substr(2, 9),
            sensor: activeSensor,
            mode: 'recording',
            startTime: start,
            endTime: end,
            label: targetLabel,
            channel: activeChannelIndex,
            status: 'recording',
            samples: []
        };

        setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));
        setActiveWindow(newWindow);

        // Fetch Data immediately
        try {
            if (!chartRef.current) throw new Error("Chart not ready");

            const samplesPoints = await chartRef.current.getSamples(start, end);

            if (!samplesPoints || samplesPoints.length === 0) {
                // Warn but maybe keep window?
                console.warn("Manual selection has no data");
            }

            const samples = samplesPoints ? samplesPoints.map(p => p.value) : [];
            const timestamps = samplesPoints ? samplesPoints.map(p => p.time) : [];

            const collectedWindow = {
                ...newWindow,
                samples,
                timestamps,
                status: 'collected'
            };

            setReadyWindows(prev => [...prev, collectedWindow]);

            setMarkedWindows(prev => {
                const existing = prev.find(w => w.id === newWindow.id);
                if (existing) {
                    return prev.map(w => w.id === newWindow.id ? collectedWindow : w);
                }
                return [...prev, collectedWindow].slice(-MAX_WINDOWS);
            });

        } catch (err) {
            console.error("Manual selection error:", err);
            setMarkedWindows(prev => prev.filter(w => w.id !== newWindow.id));
        }
    }, [activeSensor, activeChannelIndex, targetLabel, MAX_WINDOWS]);




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
        setReadyWindows(prev => prev.filter(w => w.id !== id));
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

    // Test Mode Handler
    const handleTestRecord = async (targetGestureLabel) => {
        return new Promise((resolve, reject) => {
            const currentTw = timeWindowRef.current;
            const currentDur = windowDurationRef.current;
            const latestTs = latestSignalTimeRef.current; // Ref

            const delayToCenter = currentTw / 2;
            const start = latestTs + delayToCenter;
            const end = start + currentDur;

            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: activeSensor,
                mode: 'test',
                startTime: start,
                endTime: end,
                label: targetGestureLabel,
                channel: activeChannelIndex,
                status: 'pending',
                samples: []
            };

            setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));
            setActiveWindow(newWindow);
            setRunInProgress(true); // Locks UI slightly

            setTimeout(async () => {
                if (!markedWindowsRef.current.find(w => w.id === newWindow.id)) {
                    reject(new Error("Window deleted"));
                    return;
                }

                try {
                    const latestDataTs = latestSignalTimeRef.current;
                    const systemLag = Math.max(0, Date.now() - latestDataTs);
                    const shiftedStart = start + systemLag;
                    const shiftedEnd = end + systemLag;

                    // ASYNC FETCH
                    if (!chartRef.current) throw new Error("Chart not ready");
                    const samplesPoints = await chartRef.current.getSamples(shiftedStart, shiftedEnd);

                    if (!samplesPoints || samplesPoints.length === 0) throw new Error("No data collected");

                    const samples = samplesPoints.map(p => p.value);
                    const timestamps = samplesPoints.map(p => p.time);

                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saving' } }));

                    const resp = await CalibrationApi.sendWindow(activeSensor, {
                        action: targetGestureLabel,
                        channel: activeChannelIndex,
                        samples,
                        timestamps
                    }, sessionName);

                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saved' } }));

                    setMarkedWindows(prev => prev.map(w => {
                        if (w.id === newWindow.id) {
                            return {
                                ...w,
                                predictedLabel: resp.predicted_label,
                                status: 'saved',
                                features: resp.features,
                                startTime: shiftedStart,
                                endTime: shiftedEnd,
                                samples: samples
                            };
                        }
                        return w;
                    }));

                    resolve({ detected: resp.detected, predicted_label: resp.predicted_label });

                } catch (e) {
                    console.error("Test record failed:", e);
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error' } }));
                    reject(e);
                } finally {
                    setRunInProgress(false);
                    setActiveWindow(null);
                }
            }, delayToCenter + currentDur + 200);
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

    // Optimization: Flusing directly to Worker
    const incomingBufferRef = useRef([]);

    // Update chart data from WS or Mock (Buffered and sent to Worker)
    useEffect(() => {
        if ((mode === 'realtime' || mode === 'test') && wsData) {
            const payload = wsData.raw || wsData;

            let samples = [];
            if (payload._batch) {
                samples = payload._batch;
            } else if (payload.type === 'batch' && Array.isArray(payload.samples)) {
                samples = payload.samples;
            } else if (payload.channels) {
                samples = [payload];
            }

            if (samples.length === 0) return;

            const samplingRate = config?.sampling_rate || 250;
            const sampleIntervalMs = Math.round(1000 / samplingRate);
            const channelIndex = activeChannelIndex;

            samples.forEach((s) => {
                let incomingTs = Number(s.timestamp);
                if (!incomingTs || incomingTs < 1e9) incomingTs = Date.now();

                // Monotonic timestamp logic
                if (!window.__calibLastTs) window.__calibLastTs = incomingTs;
                if (incomingTs <= window.__calibLastTs) {
                    incomingTs = window.__calibLastTs + sampleIntervalMs;
                }
                window.__calibLastTs = incomingTs;

                // Robust channel extraction
                if (s.channels) {
                    let rawVal = undefined;
                    if (s.channels[channelIndex] !== undefined) rawVal = s.channels[channelIndex];
                    else if (s.channels[`ch${channelIndex}`] !== undefined) rawVal = s.channels[`ch${channelIndex}`];

                    if (rawVal !== undefined) {
                        const val = typeof rawVal === 'number' ? rawVal : (rawVal.value || 0);
                        // PUSH TO LOCAL BUFFER
                        incomingBufferRef.current.push({ time: incomingTs, value: val });
                    }
                }
            });

            // Update latest time reference immediately if we have data
            if (incomingBufferRef.current.length > 0) {
                latestSignalTimeRef.current = incomingBufferRef.current[incomingBufferRef.current.length - 1].time;
            }
        }
    }, [wsData, mode, activeSensor, activeChannelIndex, config]);

    // Flush to Worker loop (30fps)
    useEffect(() => {
        const intervalId = setInterval(() => {
            if (incomingBufferRef.current.length === 0) return;

            const newPoints = incomingBufferRef.current;
            incomingBufferRef.current = []; // Clear ref immediately

            // Send to Worker
            if (chartRef.current) {
                chartRef.current.addData(newPoints);
            }
        }, 16); // 60fps flush for smoother scrolling
        return () => clearInterval(intervalId);
    }, []);

    // Sync Windows to Worker
    useEffect(() => {
        if (chartRef.current) {
            chartRef.current.updateWindows(markedWindows);
        }
    }, [markedWindows]);

    // Derived state instead of useEffect -> setState (Double render fix)
    const frameTime = React.useMemo(() => {
        // The WorkerTimeSeriesChart will manage its own internal time,
        // but we still need a 'now' for mapping windows.
        // We can use the latestSignalTimeRef for this.
        return latestSignalTimeRef.current;
    }, [latestSignalTimeRef.current]); // Updates when latestSignalTimeRef changes

    const scannerValue = 0; // Worker chart handles scanner internally

    // Cleanup
    useEffect(() => {
        return () => {
            if (windowIntervalRef.current) clearInterval(windowIntervalRef.current);
        };
    }, []);

    // Keyboard Controls
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Ignore if typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key.toLowerCase()) {
                case 's':
                    if (isCalibrating) handleStopCalibration();
                    else handleStartCalibration();
                    break;
                case 'a':
                    setAutoCalibrate(prev => !prev);
                    break;
                case 'arrowup':
                    e.preventDefault();
                    setAutoLimit(prev => Math.min(prev + 5, 2000)); // Cap at 2000
                    break;
                case 'arrowdown':
                    e.preventDefault();
                    setAutoLimit(prev => Math.max(prev - 5, 5)); // Floor at 5
                    break;
                default:
                    break;
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isCalibrating, handleStartCalibration, handleStopCalibration]);

    // Memoize chart config to prevent spurious worker updates
    const chartConfig = React.useMemo(() => ({
        yMin: currentYDomain[0],
        yMax: currentYDomain[1],
        lineColor: activeSensor === 'EMG' ? '#3b82f6' : (activeSensor === 'EOG' ? '#10b981' : '#f59e0b'),
        bgColor: 'transparent',
        gridColor: '#444'
    }), [currentYDomain, activeSensor]);

    return (
        <div className="flex flex-col h-[calc(100dvh-120px)] bg-bg text-text animate-in fade-in duration-500 overflow-hidden">

            {/* TOP ROW: SIDEBAR + CHART (50%) */}
            <div className="h-[50%] flex-none flex min-h-0 px-2 pb-2 pt-2 gap-2">
                {/* SIDEBAR CARD */}
                <div className="w-[260px] flex-none flex flex-col bg-surface border-border border-2 rounded-xl shadow-sm overflow-hidden">
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
                <div className="flex-grow min-w-0 bg-surface border-2 border-border rounded-xl shadow-sm overflow-hidden flex flex-col relative group">
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
                            <WorkerTimeSeriesChart
                                ref={chartRef}
                                timeWindow={timeWindow}
                                activeSensor={activeSensor}
                                activeChannelIndex={activeChannelIndex}
                                config={chartConfig}
                                onWindowSelect={handleManualWindowSelect}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* BOTTOM ROW: SESSION + WINDOW LIST (50%) */}
            <div className="h-[50%] flex-none min-h-0 px-2 pb-2 pt-0 grid grid-cols-1 lg:grid-cols-12 gap-2">
                {/* Session Panel */}
                <div className="lg:col-span-9 h-full min-h-0 overflow-hidden shadow-sm">
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
                <div className="lg:col-span-3 h-full min-h-0 overflow-hidden shadow-sm">
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
