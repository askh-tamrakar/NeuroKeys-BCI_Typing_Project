import React, { useState, useEffect, useCallback, useRef } from 'react';
import TimeSeriesZoomChart from '../charts/TimeSeriesZoomChart';
import WindowListPanel from '../calibration/WindowListPanel';
import ConfigPanel from '../calibration/ConfigPanel';
import { CalibrationApi } from '../../services/calibrationApi';

/**
 * CalibrationView
 * The main container for the BCI calibration experience.
 */
export default function CalibrationView({ wsData, wsEvent, config: initialConfig }) {
    // Top-level states
    const [activeSensor, setActiveSensor] = useState('EMG'); // 'EMG' | 'EOG' | 'EEG'
    const [mode, setMode] = useState('realtime'); // 'realtime' | 'recording'
    const [config, setConfig] = useState(initialConfig || {});
    const [isCalibrating, setIsCalibrating] = useState(false);
    const [runInProgress, setRunInProgress] = useState(false);
    const [windowProgress, setWindowProgress] = useState({});

    // Data states
    const [chartData, setChartData] = useState([]);
    const [markedWindows, setMarkedWindows] = useState([]);
    const [activeWindow, setActiveWindow] = useState(null);
    const [highlightedWindow, setHighlightedWindow] = useState(null); // New: for inspection
    const [targetLabel, setTargetLabel] = useState('Rock'); // e.g., 'Rock', 'Paper', etc.

    // Refs for accessing latest state inside interval/timeouts
    const chartDataRef = useRef(chartData);
    const activeSensorRef = useRef(activeSensor);
    const targetLabelRef = useRef(targetLabel);

    // Keep refs in sync
    useEffect(() => { chartDataRef.current = chartData; }, [chartData]);
    useEffect(() => { activeSensorRef.current = activeSensor; }, [activeSensor]);
    useEffect(() => { targetLabelRef.current = targetLabel; }, [targetLabel]);


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
                    // We need to pick the correct channel for activeSensor
                    const mapping = config.channel_mapping || {};
                    const targetChIdx = Object.keys(recording.data[0]?.channels || {}).find(idx => {
                        const chKey = `ch${idx}`;
                        return mapping[chKey]?.sensor === activeSensor || mapping[chKey]?.type === activeSensor;
                    }) || "0";

                    const formattedData = recording.data.map(point => ({
                        time: point.timestamp,
                        value: point.channels[`ch${targetChIdx}`] || point.channels[targetChIdx] || 0
                    }));

                    setChartData(formattedData);
                    console.log(`[CalibrationView] Loaded ${formattedData.length} samples for ${activeSensor}`);
                }
            } catch (error) {
                console.error('[CalibrationView] Failed to load recording:', error);
                alert('Failed to load recording data.');
            } finally {
                setIsLoadingRecording(false);
            }
        };

        loadSelectedRecording();
    }, [selectedRecording, mode, activeSensor, config.channel_mapping]);


    // Zoom state (Y-axis) similar to LiveView
    const [zoom, setZoom] = useState(1);
    const [manualYRange, setManualYRange] = useState("");
    const BASE_AMPLITUDE = 500;

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
        // Set default label based on sensor
        if (sensor === 'EMG') setTargetLabel('Rock');
        else if (sensor === 'EOG') setTargetLabel('blink');
        else if (sensor === 'EEG') setTargetLabel('target_10Hz');
    };

    const handleStartCalibration = async () => {
        setIsCalibrating(true);
        await CalibrationApi.startCalibration(activeSensor, mode, targetLabel, windowDuration);

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

            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: sensorForWindow,
                mode: 'realtime',
                startTime: start,
                endTime: end,
                label: labelForWindow,
                status: 'pending' // Added immediately to list
            };

            // Add to list IMMEDIATELY so it appears and travels with the chart
            setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));
            setActiveWindow(newWindow); // Keep track for logic, but maybe not render separately?

            // Wait for window to finish
            setTimeout(async () => {
                // Mark as saving
                setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saving' } }));
                setRunInProgress(true);

                try {
                    // Extract samples from chartDataRef (latest data)
                    const currentData = chartDataRef.current;

                    const samplesPoints = currentData.filter(p => p.time >= start && p.time <= end);
                    const samples = samplesPoints.map(p => p.value);
                    const timestamps = samplesPoints.map(p => p.time);

                    if (samples.length === 0) {
                        console.warn(`[CalibrationView] No samples or empty range. Win: ${start}-${end}.`);
                        throw new Error("No data collected in window range");
                    }

                    // Send to backend
                    const resp = await CalibrationApi.sendWindow(sensorForWindow, {
                        action: labelForWindow,
                        channel: 0,
                        samples,
                        timestamps
                    });

                    // Update progress
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saved' } }));

                    // Determine prediction result
                    const detected = resp.detected === true;
                    const predicted = detected ? labelForWindow : 'Rest';
                    const isCorrect = predicted === labelForWindow;

                    // Update the window in the list (don't add new one)
                    setMarkedWindows(prev => prev.map(w => {
                        if (w.id === newWindow.id) {
                            return {
                                ...w,
                                predictedLabel: predicted,
                                status: isCorrect ? 'correct' : 'incorrect',
                                features: resp.features
                            };
                        }
                        return w;
                    }));

                } catch (err) {
                    console.error('Auto-save window error:', err);
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error', message: err?.message || String(err) } }));

                    setMarkedWindows(prev => prev.map(w => {
                        if (w.id === newWindow.id) {
                            return { ...w, predictedLabel: 'Error', status: 'incorrect' };
                        }
                        return w;
                    }));
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
            status: 'pending'
        };

        // Add immediately
        setMarkedWindows(prev => [...prev, newWindow].slice(-MAX_WINDOWS));

        // Mark as saving
        setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saving' } }));
        setRunInProgress(true);

        try {
            // Extract samples from chartData
            const samplesPoints = chartData.filter(p => p.time >= start && p.time <= end);
            const samples = samplesPoints.map(p => p.value);
            const timestamps = samplesPoints.map(p => p.time);

            // Send to backend
            const resp = await CalibrationApi.sendWindow(activeSensor, {
                action: targetLabel,
                channel: 0,
                samples,
                timestamps
            });

            setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'saved' } }));

            // Determine prediction result
            const detected = resp.detected === true;
            const predicted = detected ? targetLabel : 'Rest';
            const isCorrect = predicted === targetLabel;

            // Update in place
            setMarkedWindows(prev => prev.map(w => {
                if (w.id === newWindow.id) {
                    return {
                        ...w,
                        predictedLabel: predicted,
                        status: isCorrect ? 'correct' : 'incorrect',
                        features: resp.features
                    };
                }
                return w;
            }));

        } catch (err) {
            console.error('Manual window save error:', err);
            setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error', message: err?.message || String(err) } }));

            setMarkedWindows(prev => prev.map(w => {
                if (w.id === newWindow.id) {
                    return { ...w, predictedLabel: 'Error', status: 'incorrect' };
                }
                return w;
            }));
        } finally {
            setRunInProgress(false);
        }
    };

    const deleteWindow = (id) => {
        setMarkedWindows(prev => prev.filter(w => w.id !== id));
    };

    const markMissed = (id) => {
        setMarkedWindows(prev => prev.map(w => w.id === id ? { ...w, isMissedActual: !w.isMissedActual } : w));
    };

    // Run calibration logic
    const runCalibration = async () => {
        if (!markedWindows || markedWindows.length === 0) return;

        setRunInProgress(true);
        try {
            // 1. Call robust calibration endpoint
            const result = await CalibrationApi.calibrateThresholds(activeSensor, markedWindows);
            console.log('[CalibrationView] Calibration result:', result);

            // 2. Update config locally
            // Ideally we also trigger the ConfigPanel to reload, but since config is lifted state in parent (usually), 
            // or here passing down... currently `config` is local state.
            // We should refetch configuration.
            const refreshedConfig = await CalibrationApi.fetchSensorConfig();
            setConfig(refreshedConfig);

            // 3. Update window statuses (if showing legacy list)
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
            alert(`Calibration Complete! Accuracy: ${(result.accuracy * 100).toFixed(1)}%`);

        } catch (err) {
            console.error('Calibration error:', err);
            alert(`Calibration failed: ${err.message}`);
        } finally {
            setRunInProgress(false);
        }
    };

    // Auto-Calibration Trigger
    // Removed batchSize state, useEffect, and Input UI

    // Update chart data from WS or Mock
    useEffect(() => {
        if (mode === 'realtime' && wsData) {
            // Process incoming LSL/WS data for the active sensor
            const payload = wsData.raw || wsData;
            if (payload?.channels) {
                const val = payload.channels[0] || 0;
                const point = { time: Date.now(), value: typeof val === 'number' ? val : (val.value || 0) };

                // Throttle upgrades if necessary, but 60Hz React renders are usually OK with simple array appends
                // Increased buffer size to ensure we have data when window completes (future-spawned windows)
                // 10000 samples at 512Hz is ~20s, plenty for 5s window
                setChartData(prev => {
                    const next = [...prev, point];
                    if (next.length > 10000) return next.slice(-10000);
                    return next;
                });
            }
        }
    }, [wsData, mode, activeSensor]);

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
        // Use SAME synchronized frameTime
        const now = frameTime;
        const w = timeWindow;
        const center = Math.round(w / 2);

        return markedWindows.map(win => {
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
        <div className="flex flex-col gap-4 h-[calc(100vh-3rem)] p-6 bg-bg text-text animate-in fade-in duration-500 overflow-hidden">
            {/* Header / Tabs */}
            <div className="flex-none flex flex-col lg:flex-row lg:items-center justify-between gap-6 card bg-surface border border-border p-6 rounded-2xl shadow-card">
                <div className="flex items-center gap-4">
                    <div className="p-3 bg-primary/10 rounded-xl border border-primary/20">
                        <span className="text-2xl">🎯</span>
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">Calibration Studio</h2>
                        <p className="text-xs text-muted font-mono uppercase tracking-widest">
                            Fine-tune sensor detection thresholds
                        </p>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                    <div className="flex bg-bg/50 p-1 rounded-xl border border-border">
                        {['EMG', 'EOG', 'EEG'].map(s => (
                            <button
                                key={s}
                                onClick={() => handleSensorChange(s)}
                                className={`px-6 py-2 rounded-lg font-bold text-sm transition-all ${activeSensor === s ? 'bg-primary text-primary-contrast shadow-lg' : 'text-muted hover:text-text'
                                    }`}
                            >
                                {s}
                            </button>
                        ))}
                    </div>

                    <div className="w-[1px] h-8 bg-border mx-2"></div>

                    <div className="flex bg-bg/50 p-1 rounded-xl border border-border">
                        {['realtime', 'recording'].map(m => (
                            <button
                                key={m}
                                onClick={() => setMode(m)}
                                className={`px-4 py-2 rounded-lg font-bold text-xs transition-all uppercase tracking-wider ${mode === m ? 'bg-accent text-primary-contrast shadow-lg' : 'text-muted hover:text-text'
                                    }`}
                            >
                                {m}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Main Workspace: Flex Column */}
            <div className="flex flex-col gap-4 flex-grow min-h-0">

                {/* Graph Area: Fixed or Flexible height? Fixed for stability. */}
                <div className="flex-none flex flex-col">
                    <div className="card bg-surface border border-border p-6 rounded-2xl shadow-card flex flex-col gap-4">
                        <div className="flex-none flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
                            <div className="flex items-center gap-3">
                                <div className="text-xs font-bold text-muted uppercase">Zoom:</div>
                                <div className="flex gap-1">
                                    {[1, 2, 5, 10, 25].map(z => (
                                        <button
                                            key={z}
                                            onClick={() => { setZoom(z); setManualYRange(""); }}
                                            className={`px-2 py-1 text-[10px] rounded font-bold transition-all ${zoom === z && !manualYRange
                                                ? 'bg-primary text-white shadow-lg'
                                                : 'bg-surface/50 hover:bg-white/10 text-muted hover:text-text border border-border'
                                                }`}
                                        >
                                            {z}x
                                        </button>
                                    ))}
                                </div>

                                <div className="h-4 w-[1px] bg-border mx-2"></div>

                                <div className="flex items-center gap-2">
                                    <div className="text-xs font-bold text-muted uppercase">Y-Range (uV):</div>
                                    <input
                                        type="number"
                                        placeholder="+/- uV"
                                        value={manualYRange}
                                        onChange={(e) => setManualYRange(e.target.value)}
                                        className="w-20 bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:outline-none focus:border-primary"
                                    />
                                </div>
                            </div>

                            <div className="flex items-center gap-3">
                                {mode === 'recording' && (
                                    <div className="flex items-center gap-3 p-3 bg-bg/50 border border-border rounded-xl">
                                        <label className="text-xs font-bold text-muted uppercase">Load File:</label>
                                        <select
                                            onChange={(e) => setSelectedRecording(e.target.value)}
                                            className="flex-grow bg-transparent border-none text-sm font-mono text-primary outline-none"
                                        >
                                            <option value="">Choose a recording...</option>
                                            {availableRecordings.filter(r => r.type === activeSensor).map(r => (
                                                <option value={r.name}>{r.name}</option>
                                            ))}
                                        </select>
                                    </div>
                                )}
                            </div>

                            <div className="flex items-center gap-3">
                                {/* Controls aligned to the right of the Start button: Time window, Window duration, Target */}
                                <div className="flex items-center gap-2 ml-2">
                                    <label className="text-xs font-bold text-muted uppercase">Time Win:</label>
                                    <select
                                        value={timeWindow}
                                        onChange={(e) => setTimeWindow(Number(e.target.value))}
                                        className="bg-bg border border-border rounded px-2 py-1 text-sm font-bold outline-none"
                                    >
                                        {[3000, 5000, 8000, 10000, 15000, 20000].map(v => (
                                            <option key={v} value={v}>{v / 1000}s</option>
                                        ))}
                                    </select>

                                    <label className="text-xs font-bold text-muted uppercase">Window:</label>
                                    <select
                                        value={windowDuration}
                                        onChange={(e) => setWindowDuration(Number(e.target.value))}
                                        className="bg-bg border border-border rounded px-2 py-1 text-sm font-bold outline-none"
                                    >
                                        {[500, 1000, 1500, 2000].map(v => (
                                            <option key={v} value={v}>{v}ms</option>
                                        ))}
                                    </select>

                                    <label className="text-xs font-bold text-muted uppercase">Target:</label>
                                    <select
                                        value={targetLabel}
                                        onChange={(e) => setTargetLabel(e.target.value)}
                                        className="bg-bg border border-border rounded px-2 py-1 text-sm font-bold outline-none"
                                    >
                                        {activeSensor === 'EMG' && ['Rock', 'Paper', 'Scissors', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                        {activeSensor === 'EOG' && ['blink', 'doubleBlink', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                        {activeSensor === 'EEG' && ['target_10Hz', 'target_12Hz', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                    </select>

                                    <button
                                        onClick={isCalibrating ? handleStopCalibration : handleStartCalibration}
                                        className={`px-6 py-2 rounded-xl font-bold transition-all shadow-glow ${isCalibrating
                                            ? 'bg-red-500 text-white hover:opacity-90'
                                            : 'bg-primary text-primary-contrast hover:opacity-90 hover:translate-y-[-2px]'
                                            }`}
                                    >
                                        {isCalibrating ? 'Stop Calibration' : 'Start Calibration'}
                                    </button>
                                </div>

                            </div>
                        </div>

                        <div className="w-full h-[320px]">
                            {/* Chart Container fixed height for stability */}
                            <TimeSeriesZoomChart
                                data={sweepChartData}
                                title={`${activeSensor} Signal Stream`}
                                mode={mode}
                                height={320}
                                markedWindows={mappedWindows}
                                activeWindow={null} // activeWindow is now part of markedWindows with 'pending' status
                                onWindowSelect={handleManualWindowSelect}
                                yDomain={currentYDomain}
                                scannerX={Math.round(timeWindow / 2)}
                                scannerValue={scannerValue}
                                timeWindowMs={timeWindow}
                                color={activeSensor === 'EMG' ? '#3b82f6' : (activeSensor === 'EOG' ? '#10b981' : '#f59e0b')}
                            />
                        </div>

                        <div className="flex-none flex justify-between items-center text-[10px] text-muted font-mono uppercase tracking-widest pt-2">
                            <span>Status: {isCalibrating ? 'Active Collection' : 'Idle'}</span>
                            <span>Windows: {markedWindows.length}</span>
                        </div>
                    </div>
                </div>

                {/* Bottom Row Area: Fills remaining space */}
                <div className="flex-grow min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* Config (left) */}
                    <div className="lg:col-span-4 h-full">
                        <ConfigPanel config={config} sensor={activeSensor} onSave={setConfig} />
                    </div>

                    {/* Stats (center) */}
                    <div className="lg:col-span-4 h-full flex flex-col gap-6">
                        <div className="card bg-surface/50 border border-border p-4 rounded-xl flex items-center justify-between flex-grow">
                            <div>
                                <div className="text-[10px] text-muted uppercase font-bold">Accuracy</div>
                                <div className="text-lg font-bold text-emerald-400">
                                    {markedWindows.length > 0 ? ((markedWindows.filter(w => w.status === 'correct').length / markedWindows.length) * 100).toFixed(0) : 0}%
                                </div>
                            </div>
                            <div className="w-10 h-10 rounded-full border-2 border-emerald-500/20 flex items-center justify-center text-emerald-400 text-xs font-bold">
                                GC
                            </div>
                        </div>

                        <div className="card bg-surface/50 border border-border p-4 rounded-xl flex items-center justify-between flex-grow">
                            <div>
                                <div className="text-[10px] text-muted uppercase font-bold">Missed Signals</div>
                                <div className="text-lg font-bold text-red-400">
                                    {markedWindows.filter(w => w.isMissedActual).length}
                                </div>
                            </div>
                            <div className="w-10 h-10 rounded-full border-2 border-red-500/20 flex items-center justify-center text-red-400 text-xs font-bold">
                                ER
                            </div>
                        </div>
                    </div>

                    {/* Windows List (right) */}
                    <div className="lg:col-span-4 h-full">
                        <WindowListPanel
                            windows={markedWindows}
                            onDelete={deleteWindow}
                            onMarkMissed={markMissed}
                            onHighlight={setHighlightedWindow}
                            activeSensor={activeSensor}
                            onRun={runCalibration}
                            running={runInProgress}
                            windowProgress={windowProgress}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
