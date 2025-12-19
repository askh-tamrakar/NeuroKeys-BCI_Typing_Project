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

    // Data states
    const [chartData, setChartData] = useState([]);
    const [markedWindows, setMarkedWindows] = useState([]);
    const [activeWindow, setActiveWindow] = useState(null);
    const [targetLabel, setTargetLabel] = useState('Rock'); // e.g., 'Rock', 'Paper', etc.

    // Recording mode states
    const [availableRecordings, setAvailableRecordings] = useState([
        { id: '1', name: 'EMG-19-12-2025__12-00-00.json', type: 'EMG' },
        { id: '2', name: 'EOG-18-12-2025__10-30-00.json', type: 'EOG' },
    ]);
    const [selectedRecording, setSelectedRecording] = useState(null);

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
    const SWEEP_WINDOW_MS = 5000; // visible sweep window length for calibration plot

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
            const start = Date.now();
            const end = start + windowDuration;
            const newWindow = {
                id: Math.random().toString(36).substr(2, 9),
                sensor: activeSensor,
                mode: 'realtime',
                startTime: start,
                endTime: end,
                label: targetLabel,
                status: 'pending'
            };

            setActiveWindow(newWindow);

            // Mock prediction after window ends
            setTimeout(() => {
                setMarkedWindows(prev => [
                    ...prev,
                    { ...newWindow, predictedLabel: Math.random() > 0.3 ? targetLabel : 'Rest', status: 'correct' }
                ]);
                setActiveWindow(null);
            }, WINDOW_DURATION);
        };

        createNextWindow();
        windowIntervalRef.current = setInterval(createNextWindow, windowDuration + GAP_DURATION);
    };

    const handleManualWindowSelect = (start, end) => {
        const newWindow = {
            id: Math.random().toString(36).substr(2, 9),
            sensor: activeSensor,
            mode: 'recording',
            startTime: start,
            endTime: end,
            label: targetLabel,
            status: 'correct' // Assume user marking is ground truth
        };
        setMarkedWindows(prev => [...prev, newWindow]);
    };

    const deleteWindow = (id) => {
        setMarkedWindows(prev => prev.filter(w => w.id !== id));
    };

    const markMissed = (id) => {
        setMarkedWindows(prev => prev.map(w => w.id === id ? { ...w, isMissedActual: !w.isMissedActual } : w));
    };

    // Update chart data from WS or Mock
    useEffect(() => {
        if (mode === 'realtime' && wsData) {
            // Process incoming LSL/WS data for the active sensor
            // This is a simplified version of LiveView logic
            const payload = wsData.raw || wsData;
            if (payload?.channels) {
                const val = payload.channels[0] || 0; // Mock: take first channel
                const point = { time: Date.now(), value: typeof val === 'number' ? val : (val.value || 0) };
                setChartData(prev => [...prev.slice(-200), point]);
            }
        }
    }, [wsData, mode, activeSensor]);

    // Compute sweep-style data for calibration: plotted portion left of center, unplotted baseline to right
    const sweepChartData = (() => {
        const w = SWEEP_WINDOW_MS;
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

    // Map action windows to sweep coordinates so they travel right->left and disappear at left edge
    const mappedWindows = (() => {
        const now = Date.now();
        const w = SWEEP_WINDOW_MS;
        return markedWindows.map(win => {
            const x1 = Math.round(w - (now - win.endTime));
            const x2 = Math.round(w - (now - win.startTime));
            return { ...win, startTime: x2, endTime: x1 };
        }).filter(win => win.endTime >= 0 && win.startTime <= w);
    })();

    const activeWindowMapped = (() => {
        if (!activeWindow) return null;
        const now = Date.now();
        const w = SWEEP_WINDOW_MS;
        const x1 = Math.round(w - (now - activeWindow.endTime));
        const x2 = Math.round(w - (now - activeWindow.startTime));
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
                                    {[1, 2, 5, 10, 20].map(z => (
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
                                                <option key={r.id} value={r.name}>{r.name}</option>
                                            ))}
                                        </select>
                                    </div>
                                )}
                            </div>

                            <div className="flex items-center gap-3">
                                <label className="text-xs font-bold text-muted uppercase">Window (ms):</label>
                                <select
                                    value={windowDuration}
                                    onChange={(e) => setWindowDuration(Number(e.target.value))}
                                    className="bg-bg border border-border rounded-lg px-2 py-1 text-sm font-bold focus:border-primary outline-none"
                                >
                                    {[500, 1000, 1500, 2000, 3000].map(v => (
                                        <option key={v} value={v}>{v} ms</option>
                                    ))}
                                </select>

                                <label className="text-xs font-bold text-muted uppercase">Target Class:</label>
                                <select
                                    value={targetLabel}
                                    onChange={(e) => setTargetLabel(e.target.value)}
                                    className="bg-bg border border-border rounded-lg px-3 py-1.5 text-sm font-bold focus:border-primary outline-none"
                                >
                                    {activeSensor === 'EMG' && ['Rock', 'Paper', 'Scissors', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                    {activeSensor === 'EOG' && ['blink', 'doubleBlink', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                    {activeSensor === 'EEG' && ['target_10Hz', 'target_12Hz', 'Rest'].map(l => <option key={l} value={l}>{l}</option>)}
                                </select>
                            </div>

                            <div className="flex items-center gap-3">
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

                        <div className="w-full h-[420px]">
                            <TimeSeriesZoomChart
                                data={sweepChartData}
                                title={`${activeSensor} Signal Stream`}
                                mode={mode}
                                markedWindows={mappedWindows}
                                activeWindow={activeWindowMapped}
                                onWindowSelect={handleManualWindowSelect}
                                yDomain={currentYDomain}
                                scannerX={Math.round(SWEEP_WINDOW_MS / 2)}
                                scannerValue={scannerValue}
                                timeWindowMs={SWEEP_WINDOW_MS}
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
                    />
                </div>
            </div>
        </div>
    );
}
