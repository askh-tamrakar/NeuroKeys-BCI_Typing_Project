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

    const currentYDomain = (() => {
        if (manualYRange && !isNaN(parseFloat(manualYRange))) {
            const r = parseFloat(manualYRange);
            return [-r, r];
        }
        return [-BASE_AMPLITUDE / zoom, BASE_AMPLITUDE / zoom];
    })();

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
                status: 'pending'
            };

            setActiveWindow(newWindow);

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
                        // Don't throw logic error, just fail this window gracefully
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

                    // Add to windows list - State Update Batch 1
                    setMarkedWindows(prev => {
                        const completedWindow = {
                            ...newWindow,
                            predictedLabel: predicted,
                            status: isCorrect ? 'correct' : 'incorrect',
                            features: resp.features
                        };
                        const next = [...prev, completedWindow];
                        return next.slice(-MAX_WINDOWS);
                    });
                } catch (err) {
                    console.error('Auto-save window error:', err);
                    setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error', message: err?.message || String(err) } }));

                    setMarkedWindows(prev => {
                        const errorWindow = {
                            ...newWindow,
                            predictedLabel: 'Error',
                            status: 'incorrect'
                        };
                        const next = [...prev, errorWindow];
                        return next.slice(-MAX_WINDOWS);
                    });
                } finally {
                    setRunInProgress(false);
                    setActiveWindow(null); // Clear active only after added to list
                }
            }, delayToCenter + currentDur);
        };

        createNextWindow();

        // Use a dynamic timeouts or interval? 
        // Interval is simpler, but if duration changes, interval needs valid ref reading?
        // setInterval captures the delay argument.
        // If we want robust timing calculated from Ref each time, recursive setTimeout is better.
        // But for now, let's just use the ref values inside the callback.
        // The interval *period* typically doesn't need to change dynamically unless user changes Window Duration.
        // If they do, they usually stop/start calibration. 
        // So standard interval using the INITIAL execution time's duration is okay-ish, or better:
        // Let's rely on the outer scoped `windowDuration` since we call startAutoWindowing() usually after setting configs.
        // But to be safe, we'll use the value at start time.

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

            // Compare prediction with labeled action for correct/missed status
            const isCorrect = predicted === targetLabel;

            setMarkedWindows(prev => {
                const completedWindow = {
                    ...newWindow,
                    predictedLabel: predicted,
                    status: isCorrect ? 'correct' : 'incorrect',
                    features: resp.features
                };
                const next = [...prev, completedWindow];
                return next.slice(-MAX_WINDOWS);
            });
        } catch (err) {
            console.error('Manual window save error:', err);
            setWindowProgress(prev => ({ ...prev, [newWindow.id]: { status: 'error', message: err?.message || String(err) } }));

            setMarkedWindows(prev => {
                const errorWindow = { ...newWindow, predictedLabel: 'Error', status: 'incorrect' };
                const next = [...prev, errorWindow];
                return next.slice(-MAX_WINDOWS);
            });
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
            const refreshedConfig = await CalibrationApi.fetchSensorConfig();
            setConfig(refreshedConfig);

            // 3. Update window statuses (if showing legacy list)
            if (result.window_results) {
                setMarkedWindows(prev => {
                    return prev.map((w, i) => {
                        const res = result.window_results[i];
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
                // Increased buffer size to ensure we have data when window completes (future-spawned windows)
                // 10000 samples at 512Hz is ~20s, plenty for 5s window + delays
                setChartData(prev => [...prev.slice(-10000), point]);
            }
        }
    }, [wsData, mode, activeSensor]);

    // Compute sweep-style data for calibration: plotted portion left of center, unplotted baseline to right
    const sweepChartData = (() => {
        const w = timeWindow;
        const center = Math.round(w / 2);
        const now = Date.now();

        // plotted points: newest at center, older to the left
        const plotted = chartData.map(d => {
            const age = now - d.time;
            const x = Math.round(center - age);
            return { time: x, value: d.value };
        }).filter(p => Number.isFinite(p.time) && p.time >= 0 && p.time <= center);

        // baseline (unplotted) to right of center — keep static at 0 to avoid vertical movement
        const step = 100; // ms resolution
        const baseline = [];
        for (let t = center; t <= w; t += step) {
            baseline.push({ time: Math.round(t), future: 0 });
        }

        const merged = [...plotted, ...baseline];
        merged.sort((a, b) => a.time - b.time);
        return merged;
    })();

    // Map action windows to sweep coordinates so they match the chart data (center-relative)
    // chartData logic: x = center - (now - time)
    const mappedWindows = (() => {
        const now = Date.now();
        const w = timeWindow;
        const center = Math.round(w / 2);
        // We want to show windows that are in the view [0, w] or slightly approaching
        // entrancePad allows seeing them just before they enter right edge?
        // Actually, if we spawn at T+center, they are at x=w.

        return markedWindows.map(win => {
            // win.startTime is logic time. 
            // x = center - (now - win.startTime)
            // If win.startTime > now (future), x > center.
            // If win.startTime = now + center, x = center - (-center) = 2*center = w.

            const x1 = Math.round(center - (now - win.endTime));
            const x2 = Math.round(center - (now - win.startTime));

            // Note: x1 (end) will be less than x2 (start) because older times have smaller x?
            // Wait. Chart logic:
            // Newer points (larger time) have smaller age, so x is larger (closer to center/right?).
            // time = 1000. now = 2000. age = 1000. x = center - 1000.
            // time = 1500. now = 2000. age = 500. x = center - 500. (Right of previous).
            // So Start Time (smaller t) should be Left of End Time (larger t).
            // But we said "Future" spawns at Right.
            // Future t > now. age < 0. x > center.
            // So future is to the Right.
            // Start < End. So Start is Left of End? 
            // Wait. A window is [Start, End]. Start occurs before End.
            // So Start is "older" than End.
            // So Start should be to the Left of End.
            // x2 (Start) should be smaller than x1 (End).

            return { ...win, startTime: x2, endTime: x1 };
        }).filter(win => win.endTime >= -200 && win.startTime <= (w + 200));
    })();

    const activeWindowMapped = (() => {
        if (!activeWindow) return null;
        const now = Date.now();
        const w = timeWindow;
        const center = Math.round(w / 2);

        const x1 = Math.round(center - (now - activeWindow.endTime));
        const x2 = Math.round(center - (now - activeWindow.startTime));

        return { ...activeWindow, startTime: x2, endTime: x1 };
    })();

    // scanner value is the latest sample value (will be plotted at center)
    const scannerValue = chartData.length ? chartData[chartData.length - 1].value : 0;

    // Cleanup
    useEffect(() => {
        return () => {
            if (windowIntervalRef.current) clearInterval(windowIntervalRef.current);
        };
    }, []);

    return (
        <div className="flex flex-col gap-6 h-full min-h-[800px] p-6 bg-bg text-text animate-in fade-in duration-500">
            {/* Header / Tabs */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 card bg-surface border border-border p-6 rounded-2xl shadow-card">
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

            {/* Main Workspace: Graph full-width on top, panels below */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 flex-grow">
                {/* Graph: full width on large screens */}
                <div className="lg:col-span-12">
                    <div className="card bg-surface border border-border p-6 rounded-2xl shadow-card flex flex-col gap-4">
                        <div className="flex flex-col lg:flex-row lg:justify-between lg:items-center gap-4">
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

                        <div className="w-full h-[420px]">
                            <TimeSeriesZoomChart
                                data={sweepChartData}
                                title={`${activeSensor} Signal Stream`}
                                mode={mode}
                                markedWindows={mappedWindows}
                                activeWindow={activeWindowMapped}
                                onWindowSelect={handleManualWindowSelect}
                                yDomain={currentYDomain}
                                scannerX={Math.round(timeWindow / 2)}
                                scannerValue={scannerValue}
                                timeWindowMs={timeWindow}
                                color={activeSensor === 'EMG' ? '#3b82f6' : (activeSensor === 'EOG' ? '#10b981' : '#f59e0b')}
                            />
                        </div>

                        <div className="flex justify-between items-center text-[10px] text-muted font-mono uppercase tracking-widest pt-2">
                            <span>Status: {isCalibrating ? 'Active Collection' : 'Idle'}</span>
                            <span>Windows: {markedWindows.length}</span>
                        </div>
                    </div>
                </div>

                {/* Bottom row: Config (left), Stats (center), Windows (right) */}
                <div className="lg:col-span-4 h-full">
                    <ConfigPanel config={config} sensor={activeSensor} onSave={setConfig} />
                </div>

                <div className="lg:col-span-4 h-full flex flex-col gap-6">
                    <div className="card bg-surface/50 border border-border p-4 rounded-xl flex items-center justify-between">
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

                    <div className="card bg-surface/50 border border-border p-4 rounded-xl flex items-center justify-between">
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

                <div className="lg:col-span-4 h-full">
                    <WindowListPanel
                        windows={markedWindows}
                        onDelete={deleteWindow}
                        onMarkMissed={markMissed}
                        activeSensor={activeSensor}
                        onRun={runCalibration}
                        running={runInProgress}
                        windowProgress={windowProgress}
                    />
                </div>
            </div>
        </div>
    );
}
