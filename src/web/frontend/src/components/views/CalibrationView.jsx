import React, { useState, useEffect, useCallback, useRef } from 'react';
import TimeSeriesZoomChart from '../charts/TimeSeriesZoomChart';
import { CalibrationApi } from '../../services/calibrationApi';

/**
 * CalibrationView
 * The main container for the BCI calibration experience.
 */
export default function CalibrationView({ wsData, wsEvent, config: initialConfig }) {
    // Top-level states
    const [activeSensor, setActiveSensor] = useState('EMG'); // 'EMG' | 'EOG' | 'EEG'
    const [activeChannelIndex, setActiveChannelIndex] = useState(0); // Explicitly selected channel index
    const [mode, setMode] = useState('realtime');

    // Data states
    const [chartData, setChartData] = useState([]);
    const [markedWindows, setMarkedWindows] = useState([]); // Simplified: we might drop this or keep empty for chart prop compatibility
    const [manualYRange, setManualYRange] = useState("");
    const [zoom, setZoom] = useState(1);
    const [timeWindow, setTimeWindow] = useState(5000);

    const BASE_AMPLITUDE = 1500;

    const currentYDomain = React.useMemo(() => {
        if (manualYRange && !isNaN(parseFloat(manualYRange))) {
            const r = parseFloat(manualYRange);
            return [-r, r];
        }
        return [-BASE_AMPLITUDE / zoom, BASE_AMPLITUDE / zoom];
    }, [manualYRange, zoom]);

    // Compute matching channels for the active sensor
    const matchingChannels = React.useMemo(() => {
        if (!initialConfig?.channel_mapping) return [];
        return Object.entries(initialConfig.channel_mapping)
            .filter(([key, val]) => val.sensor === activeSensor || val.type === activeSensor)
            .map(([key, val]) => ({
                id: key,
                index: parseInt(key.replace('ch', ''), 10),
                label: val.label || val.name || key
            }))
            .sort((a, b) => a.index - b.index);
    }, [activeSensor, initialConfig]);

    // Auto-select first matching channel when sensor changes
    useEffect(() => {
        if (matchingChannels.length > 0) {
            const exists = matchingChannels.find(c => c.index === activeChannelIndex);
            if (!exists) {
                setActiveChannelIndex(matchingChannels[0].index);
            }
        } else {
            if (activeChannelIndex !== 0) setActiveChannelIndex(0);
        }
    }, [activeSensor, matchingChannels, activeChannelIndex]);

    const handleSensorChange = (sensor) => {
        setActiveSensor(sensor);
        setChartData([]); // Clear chart
    };

    // Update chart data from WS
    // Note: Reusing existing logic but simplified
    useEffect(() => {
        if (wsData) {
            const payload = wsData.raw || wsData;
            if (payload?.channels) {
                const channelIndex = activeChannelIndex;
                const val = payload.channels[channelIndex] !== undefined ? payload.channels[channelIndex] : 0;
                const point = { time: Date.now(), value: typeof val === 'number' ? val : (val.value || 0) };

                setChartData(prev => {
                    const next = [...prev, point];
                    if (next.length > 5000) return next.slice(-5000);
                    return next;
                });
            }
        }
    }, [wsData, activeSensor, activeChannelIndex]);

    // Unified Time Reference for this Render Frame
    const [frameTime, setFrameTime] = useState(Date.now());
    useEffect(() => {
        setFrameTime(Date.now());
        const loop = setInterval(() => setFrameTime(Date.now()), 30);
        return () => clearInterval(loop);
    }, [chartData]);

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

    const scannerValue = chartData.length ? chartData[chartData.length - 1].value : 0;



    return (
        <div className="flex flex-col gap-2 h-[100dvh] p-2 bg-bg text-text animate-in fade-in duration-500 overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
            {/* Header / Tabs */}
            <div className="flex-none flex flex-col lg:flex-row lg:items-center justify-between gap-4 card bg-surface border border-border p-4 rounded-2xl shadow-card">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary/10 rounded-xl border border-primary/20">
                        <span className="text-xl">🎯</span>
                    </div>
                    <div>
                        <h2 className="text-xl font-bold tracking-tight">Calibration Studio</h2>
                        <p className="text-[10px] text-muted font-mono uppercase tracking-widest">
                            Fine-tune sensor detection thresholds
                        </p>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <div className="flex bg-bg/50 p-1 rounded-xl border border-border">
                        {['EMG', 'EOG', 'EEG'].map(s => (
                            <button
                                key={s}
                                onClick={() => handleSensorChange(s)}
                                className={`px-4 py-1.5 rounded-lg font-bold text-xs transition-all ${activeSensor === s ? 'bg-primary text-primary-contrast shadow-lg' : 'text-muted hover:text-text'
                                    }`}
                            >
                                {s}
                            </button>
                        ))}
                    </div>

                    {matchingChannels.length > 1 && (
                        <div className="flex bg-bg/50 p-1 rounded-xl border border-border animate-in slide-in-from-left-2 duration-300">
                            {matchingChannels.map(ch => (
                                <button
                                    key={ch.id}
                                    onClick={() => setActiveChannelIndex(ch.index)}
                                    className={`px-3 py-1.5 rounded-lg font-bold text-[10px] transition-all uppercase tracking-wider ${activeChannelIndex === ch.index
                                        ? 'bg-primary text-primary-contrast shadow-lg'
                                        : 'text-muted hover:text-text'
                                        }`}
                                >
                                    {ch.label}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

            </div>

            {/* Main Workspace: Flex Column */}
            <div className="flex-none flex flex-col gap-2">



                {/* Graph Area */}
                <div className="flex-none flex flex-col">
                    <div className="card bg-surface border border-border p-4 rounded-2xl shadow-card flex flex-col gap-2">

                        <div className="flex-none flex flex-col lg:flex-row lg:justify-between lg:items-center gap-2">
                            <div className="flex items-center gap-2">
                                <div className="text-[10px] font-bold text-muted uppercase">Zoom:</div>
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

                                <div className="h-3 w-[1px] bg-border mx-1"></div>

                                <div className="flex items-center gap-2">
                                    <div className="text-[10px] font-bold text-muted uppercase">Y (uV):</div>
                                    <input
                                        type="number"
                                        placeholder="+/-"
                                        value={manualYRange}
                                        onChange={(e) => setManualYRange(e.target.value)}
                                        className="w-16 bg-bg border border-border rounded px-2 py-1 text-[10px] text-text focus:outline-none focus:border-primary"
                                    />
                                </div>
                            </div>




                        </div>

                        <div className="w-full h-[300px]">
                            {/* Chart Container fixed height for stability */}
                            <TimeSeriesZoomChart
                                data={sweepChartData}
                                title={`${activeSensor} Signal Stream`}
                                mode={mode}
                                height={300}
                                markedWindows={[]}
                                activeWindow={null}
                                onWindowSelect={() => { }}
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

            {/* Data Collection Controls */}
            <div className="flex-grow min-h-0 flex flex-col gap-4 p-4">
                {activeSensor === 'EMG' ? (
                    <DataCollectionPanel
                        api={CalibrationApi}
                        activeSensor={activeSensor}
                        wsEvent={wsEvent}
                    />
                ) : (
                    <div className="flex items-center justify-center h-full text-muted">
                        Select EMG to use Data Collection Mode
                    </div>
                )}
            </div>
        </div>
    );
}

// Sub-component for Data Collection
function DataCollectionPanel({ api, activeSensor, wsEvent }) {
    const [status, setStatus] = useState({ recording: false, current_label: '', counts: {} });
    const [autoMode, setAutoMode] = useState(false);
    const [autoCount, setAutoCount] = useState(0);
    const [isPredicting, setIsPredicting] = useState(false);
    const [prediction, setPrediction] = useState(null);
    const intervalRef = useRef(null);

    const refreshStatus = useCallback(async () => {
        const s = await api.getEmgStatus();
        if (s) setStatus(s);
    }, [api]);

    // Poll status
    useEffect(() => {
        refreshStatus();
        const poll = setInterval(refreshStatus, 1000);
        return () => clearInterval(poll);
    }, [refreshStatus]);

    const handleStart = async (label) => {
        await api.startEmgRecording(label);
        refreshStatus();
    };

    const handleStop = async () => {
        await api.stopEmgRecording();
        refreshStatus();
    };

    const handleAutoRecord = async (label) => {
        if (autoMode || status.recording) return;
        setAutoMode(true);
        setAutoCount(20);

        // Start Recording
        await api.startEmgRecording(label);
        refreshStatus();

        // Timer to stop after approx 5 seconds (20 samples * 0.25s stride = 5s)
        // Adjust based on backend windowing (0.5s window, 0.25s step)
        // 20 windows = (19 * 0.25) + 0.5 = 5.25 seconds
        setTimeout(async () => {
            await api.stopEmgRecording();
            setAutoMode(false);
            refreshStatus();
        }, 5500);
    };

    // Live Prediction Listener
    useEffect(() => {
        if (isPredicting && wsEvent && wsEvent.type === 'emg_prediction') {
            setPrediction(wsEvent);
        }
    }, [wsEvent, isPredicting]);

    const togglePrediction = async () => {
        const newState = !isPredicting;
        setIsPredicting(newState);
        await api.togglePrediction(activeSensor, newState);
        if (!newState) setPrediction(null);
    };

    const handleDelete = async () => {
        if (!confirm('Are you sure you want to delete ALL EMG data?')) return;
        try {
            await fetch('/api/emg/data', { method: 'DELETE' });
            refreshStatus();
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div className="flex flex-col gap-6">
            {/* Status Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {['Rest', 'Rock', 'Paper', 'Scissors'].map((label, idx) => (
                    <div key={label} className="card bg-surface border border-border p-4 rounded-xl flex flex-col items-center justify-center">
                        <div className="text-xs text-muted uppercase font-bold text-center mb-1">{label}</div>
                        <div className="text-3xl font-mono font-bold text-primary">
                            {status.counts[String(idx)] || 0}
                        </div>
                        <div className="text-[10px] text-muted">samples</div>
                    </div>
                ))}

                <div className={`card border border-border p-4 rounded-xl flex flex-col items-center justify-center ${status.recording ? 'bg-red-500/10 border-red-500 animate-pulse' : 'bg-surface'}`}>
                    <div className="text-xs text-muted uppercase font-bold text-center mb-1">Status</div>
                    <div className={`text-lg font-bold ${status.recording ? 'text-red-500' : 'text-muted'}`}>
                        {status.recording ? 'RECORDING' : 'IDLE'}
                    </div>
                    {status.recording && <div className="text-[10px] text-red-500">{status.current_label}</div>}
                </div>
            </div>

            {/* Actions */}
            <div className="card bg-surface border border-border p-6 rounded-xl">
                <div className="flex justify-between items-center mb-6">
                    <div>
                        <h3 className="text-lg font-bold">Data Collection Controls</h3>
                        <p className="text-xs text-muted">Record raw EMG windows for ML training.</p>
                    </div>
                    <button
                        onClick={handleDelete}
                        className="px-4 py-2 text-xs font-bold text-red-500 border border-red-500/50 rounded-lg hover:bg-red-500/10 transition-colors uppercase tracking-wider"
                    >
                        Clear All Data
                    </button>
                </div>

                {status.recording ? (
                    <div className="flex flex-col items-center justify-center py-8 gap-4 bg-bg/50 rounded-xl border border-border border-dashed">
                        {autoMode ? (
                            <div className="text-xl font-bold text-primary animate-pulse">Auto-Recording ~20 Samples...</div>
                        ) : (
                            <div className="text-xl font-bold text-red-500 animate-pulse">Recording ({status.current_label})...</div>
                        )}
                        <button
                            onClick={handleStop}
                            className="px-12 py-4 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl shadow-lg hover:scale-105 transition-all uppercase tracking-widest text-lg"
                        >
                            STOP & SAVE
                        </button>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        {/* Manual Controls */}
                        <div className="flex flex-col gap-4">
                            <h4 className="text-xs font-bold text-muted uppercase tracking-wider">Manual Recording</h4>
                            <div className="grid grid-cols-2 gap-3">
                                {['Rest', 'Rock', 'Paper', 'Scissors'].map((l, i) => (
                                    <button
                                        key={l}
                                        onClick={() => handleStart(l)} // Backend expects string label now? API wrapper handles it? API wrapper takes int?
                                        // Wait, API wrapper startEmgRecording takes 'label' (int 0-3).
                                        // Let's pass the integer index.
                                        // My startEmgRecording in CalibrationApi.js: "async startEmgRecording(label) { ... body: JSON.stringify({ label }) ... }"
                                        // "label" can be 0,1,2,3.
                                        className="h-12 bg-surface hover:bg-primary/20 border border-border hover:border-primary/50 rounded-lg font-bold text-sm text-text transition-all flex items-center justify-center"
                                        onClickCapture={(e) => { e.stopPropagation(); handleStart(i); }}
                                    >
                                        {l}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Auto Controls */}
                        <div className="flex flex-col gap-4">
                            <h4 className="text-xs font-bold text-muted uppercase tracking-wider">Auto-Batch (20 Samples)</h4>
                            <div className="grid grid-cols-2 gap-3">
                                {['Rest', 'Rock', 'Paper', 'Scissors'].map((l, i) => (
                                    <button
                                        key={`auto-${l}`}
                                        onClick={() => handleAutoRecord(i)}
                                        className="h-12 bg-surface hover:bg-emerald-500/20 border border-border hover:border-emerald-500/50 rounded-lg font-bold text-sm text-text transition-all flex items-center justify-center gap-2 group"
                                    >
                                        <div className="w-2 h-2 rounded-full bg-emerald-500 group-hover:animate-ping" />
                                        Auto {l}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {/* Live Prediction / Verification Section */}
                <div className="card bg-surface border border-border p-6 rounded-xl mt-6">
                    <div className="flex justify-between items-center mb-6">
                        <div>
                            <h3 className="text-lg font-bold">Model Verification</h3>
                            <p className="text-xs text-muted">Test trained model with live data.</p>
                        </div>
                        <button
                            onClick={togglePrediction}
                            className={`px-6 py-2 rounded-lg font-bold text-xs uppercase tracking-wider transition-all shadow-glow ${isPredicting
                                    ? 'bg-amber-500 text-white hover:bg-amber-600'
                                    : 'bg-surface border border-border hover:border-primary/50 text-text'
                                }`}
                        >
                            {isPredicting ? 'Stop Prediction' : 'Start Live Detection'}
                        </button>
                    </div>

                    {isPredicting && (
                        <div className="flex flex-col items-center justify-center p-8 bg-bg/30 rounded-xl border border-border transition-all animate-in fade-in zoom-in-95">
                            <div className="text-xs text-muted font-bold uppercase tracking-widest mb-3">Predicted Gesture</div>
                            <div className={`text-6xl font-black mb-4 tracking-tighter transition-all ${prediction ? 'text-primary scale-110' : 'text-muted/20'
                                }`}>
                                {prediction ? prediction.label : 'Waiting...'}
                            </div>

                            {prediction && (
                                <div className="w-full max-w-xs flex flex-col gap-1">
                                    <div className="flex justify-between text-[10px] font-mono text-muted uppercase">
                                        <span>Confidence</span>
                                        <span>{Math.round(prediction.confidence * 100)}%</span>
                                    </div>
                                    <div className="w-full h-2 bg-surface rounded-full overflow-hidden border border-white/5">
                                        <div
                                            className="h-full bg-gradient-to-r from-primary/50 to-primary transition-all duration-300 ease-out"
                                            style={{ width: `${Math.max(5, prediction.confidence * 100)}%` }}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
