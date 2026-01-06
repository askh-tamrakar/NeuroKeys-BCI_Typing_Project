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
    // State for Window Lists
    const [bufferWindows, setBufferWindows] = useState([]); // Red (Saved) - History
    const [readyToAppend, setReadyToAppend] = useState([]); // Green (Pending) - Ready to Save
    const [activeWindow, setActiveWindow] = useState(null); // Yellow (Recording) - Current
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
    // Refs for new lists
    const bufferWindowsRef = useRef(bufferWindows);
    const readyToAppendRef = useRef(readyToAppend);

    // Keep refs in sync
    useEffect(() => { chartDataRef.current = chartData; }, [chartData]);
    useEffect(() => { activeSensorRef.current = activeSensor; }, [activeSensor]);
    useEffect(() => { activeChannelIndexRef.current = activeChannelIndex; }, [activeChannelIndex]);
    useEffect(() => { targetLabelRef.current = targetLabel; }, [targetLabel]);
    useEffect(() => { bufferWindowsRef.current = bufferWindows; }, [bufferWindows]);
    useEffect(() => { readyToAppendRef.current = readyToAppend; }, [readyToAppend]);
    const autoLimitRef = useRef(autoLimit);
    useEffect(() => { autoLimitRef.current = autoLimit; }, [autoLimit]);

    const UI_MAX_ITEMS = 50;

    // Helper: Enforce UI Limit (Scenario 1 & 2 Logic)
    // "If total (buffer + ready) > 50, delete oldest samples from bufferWindows"
    // This is primarily for Auto Mode realtime enforcement.
    const enforceLimit = (currentBuffer, currentReady) => {
        const total = currentBuffer.length + currentReady.length;
        if (total > UI_MAX_ITEMS) {
            const overflow = total - UI_MAX_ITEMS;
            // Remove 'overflow' amount from start of buffer (Oldest)
            // Ensure we don't remove more than we have
            const removeCount = Math.min(overflow, currentBuffer.length);
            return currentBuffer.slice(removeCount);
        }
        return currentBuffer;
    };

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
        setBufferWindows([]);
        setReadyToAppend([]);
        setActiveWindow(null);
        setTotalPredictedCount(0);
        // Set default label based on sensor
        if (sensor === 'EMG') setTargetLabel('Rock');
        else if (sensor === 'EOG') setTargetLabel('SingleBlink');
        else if (sensor === 'EEG') setTargetLabel('Concentration');
    };

    const handleStartCalibration = async () => {
        setIsCalibrating(true);
        // Pass sessionName to API (modified to accept it)
        // Mock API update needed? `startCalibration` in api file is mock.
        // We need to ensure we call the REAL endpoints if we want real session creation.
        // But wait, `startCalibration` in valid logic is mostly for checking.
        // The real recording happens in `handleManualWindowSelect` (Manual) or `auto-windowing` (Realtime).

        // Actually, for "Saving Windows" via `sendWindow` (lines 147+), we just send samples.
        // The Backend `api_save_window` manages separate feature windows.
        // BUT the user request was about "Recording" session for TRAINING.
        // In CalibrationView, "Realtime" mode sends windows to `api/window`. These are for Config Calibration.
        // Does the user want THESE to be in the session table? 
        // Or only the "Recording" (Raw Stream) mode?
        // User said: "save that windows in a database as the samples for training".
        // `api/window` -> `db_manager.insert_window`.
        // So yes, `sendWindow` needs `table_name` or `session_name`.

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
            const currentTw = timeWindowRef.current;
            const currentDur = windowDurationRef.current;
            const delayToCenter = Math.round(currentTw / 2);
            const start = Date.now() + delayToCenter;
            const end = start + currentDur;

            const sensorForWindow = activeSensorRef.current;
            const labelForWindow = targetLabelRef.current;
            const channelForWindow = activeChannelIndexRef.current;
            const limit = autoLimitRef.current;

            // Current Ready count for this label
            // We use REF for immediate check
            const currentReadyCount = readyToAppendRef.current.filter(w => w.label === labelForWindow).length;

            console.log(`[AutoWindow] Limit: ${limit}, Ready: ${currentReadyCount}`);

            // 1. Check Auto Limit (Trigger Batch Save if reached)
            // "When readyToAppend reaches the auto_limit"
            // Actually, we check this *before* creating a new one? Or after?
            // User says: "Batch 1: Record 10 samples. Ready hits 10. Action triggers."
            // So if we are AT limit, we flush?
            // Or start next, and flush previous?
            // Let's create the window, let it record. When it FINISHES, it goes to Ready. 
            // THEN we check if Ready >= Limit.

            // STOP condition? "Auto Collection Mode (Strict Limit)" usually implies we stop or we loop.
            // Scenario 1 implies continuous batching: "Batch 1... Batch 2... Batch 3..."
            // So we DO NOT STOP. We just flush.

            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: sensorForWindow,
                mode: 'realtime',
                startTime: start,
                endTime: end,
                label: labelForWindow,
                channel: channelForWindow,
                status: 'recording', // Yellow
                samples: []
            };

            setActiveWindow(newWindow);

            // Wait for window to finish
            setTimeout(async () => {
                // Check if still active (not stopped)
                if (!isCalibrating) return; // Simple check, might need Ref if 'isCalibrating' state is stale closure (it is in timeout)
                // Actually `isCalibrating` is state, so we need ref? 
                // We'll proceed. Validation happens on save.

                // Mark as Ready (Green)
                setRunInProgress(true);

                try {
                    const currentData = chartDataRef.current;
                    const samplesPoints = currentData.filter(p => p.time >= start && p.time <= end);
                    const samples = samplesPoints.map(p => p.value);
                    const timestamps = samplesPoints.map(p => p.time);

                    if (samples.length === 0) throw new Error("No data");

                    const completedWindow = {
                        ...newWindow,
                        status: 'pending', // Green
                        samples,
                        timestamps,
                        // Mock features for UI immediately?
                        features: {}
                    };

                    // UPDATE STATE: Add to Ready, Enforce 50 Limit
                    // We need to do this atomically-ish

                    // We also need to check if we hit AUTO LIMIT for FLUSH
                    // "When readyToAppend reaches auto_limit"
                    // We are adding 1. 

                    // We must use functional updates or refs carefully.
                    // Let's use a helper in the functional update to handle everything?
                    // No, `handleBatchSave` is async.

                    // 1. Add to Ready
                    let shouldFlush = false;
                    let currentReadyLength = 0;

                    setReadyToAppend(prevReady => {
                        const newReady = [...prevReady, completedWindow];
                        currentReadyLength = newReady.length; // Approximate (this label mixed with others?)

                        // Check if we hit limit (Total Ready for THIS label? or Total?)
                        // Usually Limit is for the Target Class.
                        const countForLabel = newReady.filter(w => w.label === labelForWindow).length;
                        if (autoCalibrate && countForLabel >= limit) {
                            shouldFlush = true;
                        }
                        return newReady;
                    });

                    // 2. Enforce UI Limit (Scenario 1 rule)
                    // "If (buffer + ready) > 50, immediately delete oldest from buffer"
                    setBufferWindows(prevBuffer => {
                        // We need the *future* ready length. 
                        // This is tricky with async state. 
                        // Let's use the ref for 'ready' which might be stale? 
                        // No, we just added 1. 
                        // Let's assume Ready increased by 1.
                        const total = prevBuffer.length + readyToAppendRef.current.length + 1;
                        if (total > UI_MAX_ITEMS) {
                            const overflow = total - UI_MAX_ITEMS;
                            if (overflow > 0 && prevBuffer.length > 0) {
                                return prevBuffer.slice(overflow);
                            }
                        }
                        return prevBuffer;
                    });


                    // 3. Trigger Flush if needed
                    if (shouldFlush && autoCalibrate) {
                        // We need to wait for state to settle? 
                        // Or just pass the 'should flush' signal to a useEffect?
                        // Implementing a dedicated useEffect for Auto-Flush is cleaner.
                        // See `Auto-Calibration / Auto-Save Trigger` effect below.
                    }

                    // No backend call here! Just moving to Ready.

                } catch (err) {
                    console.error('Auto-window error:', err);
                } finally {
                    setRunInProgress(false);
                    setActiveWindow(null);
                }
            }, delayToCenter + currentDur);
        };

        createNextWindow();
        windowIntervalRef.current = setInterval(createNextWindow, windowDuration + GAP_DURATION);
    };

    const handleManualWindowSelect = async (start, end) => {
        const newWindow = {
            id: Math.random().toString(36).substr(2, 9),
            sensor: activeSensor,
            mode: 'recording',
            startTime: start,
            endTime: end,
            label: targetLabel,
            channel: activeChannelIndex,
            status: 'pending', // Green immediately
            samples: []
        };

        // Extract samples
        const samplesPoints = chartDataRef.current.filter(p => p.time >= start && p.time <= end);
        newWindow.samples = samplesPoints.map(p => p.value);
        newWindow.timestamps = samplesPoints.map(p => p.time);

        // Add to Ready
        setReadyToAppend(prev => [...prev, newWindow]);

        // Scenario 2: "The UI can grow beyond 50 while recording"
        // So we DO NOT enforce limit on buffer here. 
        // "Total visible can exceed 50".
    };

    /**
     * FLUSH Logic (Shared)
     * Saves 'ready' windows -> DB. Moves them to 'buffer'.
     * Handles cleanups.
     */
    const flushReadyToBuffer = async () => {
        const windowsToSave = readyToAppendRef.current; // Use Ref for latest
        if (windowsToSave.length === 0) return;

        setRunInProgress(true);

        // 1. Save all to DB
        // We can start the request parallel to UI updates or blocking? 
        // Blocking is safer for "Batch".

        try {
            // Optimistic Update?
            // Spec: "Save to DB. Change status Green -> Red. Move to Buffer."

            // We'll iterate and save.
            let savedCount = 0;
            const savedWindows = [];

            for (const win of windowsToSave) {
                try {
                    const resp = await CalibrationApi.sendWindow(activeSensor, {
                        action: win.label,
                        channel: win.channel,
                        samples: win.samples,
                        timestamps: win.timestamps
                    }, sessionName);

                    savedWindows.push({
                        ...win,
                        status: 'saved', // Red
                        features: resp.features,
                        predictedLabel: resp.predicted_label
                    });
                    savedCount++;
                } catch (e) {
                    console.error("Failed to save window", win.id, e);
                    // What to do with failed? User says: "Black (Error)... discarded". 
                    // We just won't add it to buffer.
                }
            }

            // 2. Clear Ready
            setReadyToAppend([]);

            // 3. Add to Buffer & Enforce Limits
            // Scenario 1 (Auto): "Move to Buffer. (Buffer grows...)" 
            // Scenario 2 (Manual): "Move to Buffer... If buffer > 50, delete oldest... snap back".

            setBufferWindows(prev => {
                let nextBuffer = [...prev, ...savedWindows]; // Add new at End (Newest)? 
                // Wait, User: "buffer (Top) + ready (Bottom)".
                // Usually Top is Oldest. 
                // So [...oldBuffer, ...newSaved]. 

                // Enforce Snap Back (Scenario 2) & Maintenance (Scenario 1)
                if (nextBuffer.length > UI_MAX_ITEMS) {
                    // "delete oldest items until length == 50"
                    const overflow = nextBuffer.length - UI_MAX_ITEMS;
                    nextBuffer = nextBuffer.slice(overflow);
                }
                return nextBuffer;
            });

            if (savedCount > 0) {
                setDataLastUpdated(Date.now()); // Trigger table refresh
            }

        } finally {
            setRunInProgress(false);
        }
    };

    const deleteWindow = (id) => {
        // Could be in Ready or Buffer
        setReadyToAppend(prev => prev.filter(w => w.id !== id));
        setBufferWindows(prev => prev.filter(w => w.id !== id));
    };

    const markMissed = (id) => {
        // Update in both
        setReadyToAppend(prev => prev.map(w => w.id === id ? { ...w, isMissedActual: !w.isMissedActual } : w));
        setBufferWindows(prev => prev.map(w => w.id === id ? { ...w, isMissedActual: !w.isMissedActual } : w));
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
            const delayToCenter = 0;
            const start = Date.now() + delayToCenter;
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
                status: 'pending', // Will be 'recording' then 'pending' then 'saved'
                samples: [] // Will be filled
            };

            // Add to list so user sees it coming
            setReadyToAppend(prev => [...prev, newWindow]); // Add to ready for display
            setActiveWindow(newWindow);
            setRunInProgress(true); // Locks UI slightly

            // Wait for window to pass center
            setTimeout(async () => {
                // Check if window still exists
                if (!readyToAppendRef.current.find(w => w.id === newWindow.id)) {
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

                    setReadyToAppend(prev => prev.map(w => {
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



    // Auto-Flush Trigger
    useEffect(() => {
        if (!autoCalibrate) return;

        // Check if we hit limit
        const readyCount = readyToAppend.filter(w => w.label === targetLabel).length;
        // Also check if we have enough "pending"?
        // Logic: "When readyToAppend reaches auto_limit"

        if (readyCount >= autoLimit && !runInProgress) {
            console.log("Auto-Flush Triggered");
            flushReadyToBuffer();
        }
    }, [readyToAppend, autoCalibrate, autoLimit, targetLabel, runInProgress]);

    // Update chart data from WS or Mock
    useEffect(() => {
        if ((mode === 'realtime' || mode === 'test') && wsData) {
            const payload = wsData.raw || wsData;

            // Handle Single Sample (Old format or Fallback)
            if (payload?.channels && !payload.samples) {
                const channelIndex = activeChannelIndex;
                const val = payload.channels[channelIndex] !== undefined ? payload.channels[channelIndex] : 0;
                const point = { time: Date.now(), value: typeof val === 'number' ? val : (val.value || 0) };

                setChartData(prev => {
                    const next = [...prev, point];
                    if (next.length > 10000) return next.slice(-10000);
                    return next;
                });
            }
            // Handle Batched Data (New format)
            else if (payload?.type === 'batch' && Array.isArray(payload.samples)) {
                // Determine batch arrival time
                const now = Date.now();
                const newPoints = [];
                const channelIndex = activeChannelIndex;
                const sampleCount = payload.samples.length;

                // Distribute timestamps slightly if needed, or just use 'now' if batch covers small duration (33ms)
                // Timestamps in payload.timestamp is backend time. We use local UI time for scrolling.
                // Linear distribution:
                const timeStep = 30 / sampleCount; // approx ms per sample in this batch (assuming ~30ms batch)

                payload.samples.forEach((s, i) => {
                    // Start time of batch = now - (total_duration) + (i * step)
                    // Or simplified: just spread them ending at now.
                    const t = now - (sampleCount - 1 - i) * timeStep;

                    if (s.channels && s.channels[channelIndex]) {
                        const rawVal = s.channels[channelIndex];
                        const val = typeof rawVal === 'number' ? rawVal : (rawVal.value || 0);
                        newPoints.push({ time: t, value: val });
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
        }
    }, [wsData, mode, activeSensor, activeChannelIndex]);

    // Unified Time Reference for this Render Frame
    // We update 'now' whenever chartData updates (frame tick) or periodically.
    // Since chartData updates frequently (WebSocket), we can use that as the clock tick.
    const [frameTime, setFrameTime] = useState(Date.now());

    useEffect(() => {
        // Ensure we have a tick every frame or at least when data comes in
        setFrameTime(Date.now());
        // Optional: If data is slow, you might want a requestAnimationFrame loop here
        // to keep the sweep moving smoothly even if data buffers.
        const loop = setInterval(() => setFrameTime(Date.now()), 30); // ~30fps smooth sweep
        return () => clearInterval(loop);
    }, [chartData /* or just run independently */]);

    // Compute sweep-style data for calibration: plotted portion left of center, unplotted baseline to right
    const sweepChartData = React.useMemo(() => {
        const w = timeWindow;
        const center = Math.round(w / 2);
        // Use synchronized frameTime
        const now = frameTime;

        // plotted points: newest at center, older to the left
        // Optimization: iterate from end
        const plotted = [];
        for (let i = chartData.length - 1; i >= 0; i--) {
            const d = chartData[i];
            const age = now - d.time;
            if (age > center) break; // Optimization: Stop if older than window left edge
            const x = Math.round(center - age);
            // Relaxed filter to allow points slightly off-screen to prevent line clipping
            if (x >= -100) plotted.unshift({ time: x, value: d.value });
        }

        // baseline (unplotted) to right of center — keep static at 0 to avoid vertical movement
        const step = 50; // ms resolution
        const baseline = [];
        for (let t = center; t <= w; t += step) {
            baseline.push({ time: Math.round(t), future: 0 });
        }

        const merged = [...plotted, ...baseline];
        merged.sort((a, b) => a.time - b.time);

        return merged;
    }, [chartData, timeWindow, frameTime]); // Depend on frameTime

    // Map action windows to sweep coordinates so they match the chart data (center-relative)
    const mappedWindows = React.useMemo(() => {
        const now = frameTime;
        const w = timeWindow;
        const center = Math.round(w / 2);

        // Combine all windows we want to show
        // Order: Active (Top Z), Ready (Green), Buffer (Red)
        const allWindows = [
            ...(activeWindow ? [activeWindow] : []),
            ...readyToAppend,
            ...bufferWindows
        ];

        const mapped = allWindows.map(win => {
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

        return mapped;
    }, [activeWindow, readyToAppend, bufferWindows, timeWindow, frameTime]);


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

    // Run calibration logic (Modified for new state)
    // "bufferWindows" contains Saved/Red items. Typically we train on this.
    const runCalibration = useCallback(async (isAuto = false) => {
        if (!bufferWindows || bufferWindows.length === 0) return;

        setRunInProgress(true);
        try {
            // Filter windows to only those matching the current target label (per user request)
            const windowsToCalibrate = bufferWindows.filter(w => w.label === targetLabel);

            if (windowsToCalibrate.length === 0) {
                console.warn('[CalibrationView] No matching windows for target label:', targetLabel);
                setRunInProgress(false);
                return;
            }

            // 1. Call robust calibration endpoint
            const result = await CalibrationApi.calibrateThresholds(activeSensor, windowsToCalibrate);

            // 2. Update config locally
            const refreshedConfig = await CalibrationApi.fetchSensorConfig();
            setConfig(refreshedConfig);

            if (isAuto || autoCalibrate) {
                // Auto-mode cleanups if any
            } else {
                const acc = result.accuracy_after !== undefined ? result.accuracy_after : (result.accuracy || 0);
                alert(`Calibration Complete! Accuracy: ${(acc * 100).toFixed(1)}%`);
            }
        } catch (err) {
            console.error('Calibration error:', err);
            if (!isAuto) alert(`Calibration failed: ${err.message}`);
        } finally {
            setRunInProgress(false);
        }
    }, [bufferWindows, activeSensor, autoCalibrate, targetLabel]);

    // Use "bufferWindows" + "readyToAppend" for list? 
    // Actually WindowListPanel will receive them separately.

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
                        bufferWindows={bufferWindows}
                        readyWindows={readyToAppend}
                        onDelete={deleteWindow}
                        onMarkMissed={markMissed}
                        onHighlight={setHighlightedWindow}
                        activeSensor={activeSensor}
                        windowProgress={windowProgress}
                        autoLimit={autoLimit}
                        onAutoLimitChange={setAutoLimit}
                        autoCalibrate={autoCalibrate}
                        onAutoCalibrateChange={setAutoCalibrate}
                        onClearSaved={flushReadyToBuffer}
                    />
                </div>
            </div>
        </div>
    );
}
