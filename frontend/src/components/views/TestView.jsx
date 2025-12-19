import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import SignalChart from '../charts/SignalChart';
import WindowListPanel from '../calibration/WindowListPanel';
import ConfigPanel from '../calibration/ConfigPanel';
import { CalibrationApi } from '../../services/calibrationApi';

/**
 * CalibrationView
 * The main container for the BCI calibration experience.
 */
export default function TestView({ wsData, wsEvent, config: initialConfig }) {
    // Top-level states
    const [activeSensor, setActiveSensor] = useState('EMG'); // 'EMG' | 'EOG' | 'EEG'
    const [mode, setMode] = useState('realtime'); // 'realtime' | 'recording'
    const [config, setConfig] = useState(initialConfig || {});
    const [isCalibrating, setIsCalibrating] = useState(false);

    const timeWindowMs = 10000;

    // Load config if prop is empty
    useEffect(() => {
        if (!initialConfig || Object.keys(initialConfig).length === 0) {
            import('../../services/ConfigService').then(({ ConfigService }) => {
                ConfigService.loadConfig().then(cfg => {
                    setConfig(cfg);
                });
            });
        }
    }, [initialConfig]);

    // Data states
    const [chartData, setChartData] = useState([]);
    const [markedWindows, setMarkedWindows] = useState([]);
    const [activeWindow, setActiveWindow] = useState(null);
    const [targetLabel, setTargetLabel] = useState('Rock'); // e.g., 'Rock', 'Paper', etc.

    // Recording mode states
    const [availableRecordings, setAvailableRecordings] = useState([]);
    const [selectedRecording, setSelectedRecording] = useState(null);
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

    // Refs for real-time windowing
    const windowIntervalRef = useRef(null);
    const WINDOW_DURATION = 1500; // ms
    const GAP_DURATION = 500; // ms

    // Handlers
    const handleSensorChange = (sensor) => {
        setActiveSensor(sensor);
        setMarkedWindows([]);
        // Set default label based on sensor
        if (sensor === 'EMG') setTargetLabel('Rock');
        else if (sensor === 'EOG') setTargetLabel('blink');
        else if (sensor === 'EEG') setTargetLabel('target_10Hz');

        // Clear selection when sensor changes
        setSelectedRecording(null);
        if (mode === 'recording') setChartData([]);
    };

    const handleStartCalibration = async () => {
        setIsCalibrating(true);
        await CalibrationApi.startCalibration(activeSensor, mode, targetLabel, WINDOW_DURATION);

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
            const end = start + WINDOW_DURATION;
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
        windowIntervalRef.current = setInterval(createNextWindow, WINDOW_DURATION + GAP_DURATION);
    };

    const handleManualWindowSelect = (start, end) => {
        const newWindow = {
            id: Math.random().toString(36).substr(2, 9),
            sensor: activeSensor,
            mode: 'recording',
            startTime: start,
            endTime: end,
            label: targetLabel,
            status: 'correct'
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
            const payload = wsData.raw || wsData;
            if (payload?.channels) {
                // Find correct channel for active sensor type
                const mapping = config.channel_mapping || {};

                // Try to find the first enabled channel matching the active sensor
                const targetChIdx = Object.keys(payload.channels).find(idx => {
                    const chKey = `ch${idx}`;
                    return mapping[chKey]?.sensor === activeSensor || mapping[chKey]?.type === activeSensor;
                });

                const channelData = payload.channels[targetChIdx] || payload.channels[0] || payload.channels["0"];

                if (channelData !== undefined) {
                    const val = typeof channelData === 'number' ? channelData : (channelData.value ?? 0);

                    // Normalize timestamp (ms) - Match LiveView.jsx logic
                    let ts = Number(payload.timestamp);
                    if (!ts || ts < 1e9) {
                        ts = Date.now();
                    }

                    const numericVal = Number(val);
                    if (isNaN(numericVal)) return;

                    const point = { time: ts, value: numericVal };
                    setChartData(prev => {
                        const newArr = [...prev, point];
                        const cutoff = ts - timeWindowMs; // Match sweep window
                        return newArr.filter(p => p.time > cutoff);
                    });
                }
            }
        }
    }, [wsData, mode, activeSensor, config.channel_mapping]);

    // Cleanup
    useEffect(() => {
        return () => {
            if (windowIntervalRef.current) clearInterval(windowIntervalRef.current);
        };
    }, []);

    // --- SWEEP TRANSFORM LOGIC (from LiveView.jsx) ---
    const sweepData = useMemo(() => {
        if (chartData.length === 0) return { active: [], history: [], scanner: null };
        const latestTs = chartData[chartData.length - 1].time;
        const scannerPos = latestTs % timeWindowMs;
        const cycleStartTs = latestTs - scannerPos;

        const active = [];
        const history = [];

        chartData.forEach(d => {
            const mappedTime = d.time % timeWindowMs;
            if (d.time > (latestTs - timeWindowMs)) {
                if (d.time >= cycleStartTs) {
                    active.push({ ...d, time: mappedTime });
                } else {
                    history.push({ ...d, time: mappedTime });
                }
            }
        });

        active.sort((a, b) => a.time - b.time);
        history.sort((a, b) => a.time - b.time);

        return { active, history, scanner: scannerPos };
    }, [chartData, timeWindowMs]);

    return (
        <div className="flex flex-col gap-6 h-full p-6 bg-bg text-text animate-in fade-in duration-500 overflow-y-auto">
            {/* Header */}
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

            {/* Top Row: Full-width Graph */}
            <div className="card bg-surface border border-border p-6 rounded-2xl shadow-card flex flex-col gap-4">
                <div className="flex justify-between items-center">
                    <div className="flex items-center gap-6">
                        <div className="flex items-center gap-2">
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

                        {mode === 'recording' && (
                            <div className="flex items-center gap-3 p-2 bg-bg/50 border border-border rounded-xl">
                                <label className="text-[10px] font-bold text-muted uppercase">Recording:</label>
                                <select
                                    onChange={(e) => setSelectedRecording(e.target.value)}
                                    className="bg-transparent border-none text-xs font-mono text-primary outline-none min-w-[200px]"
                                >
                                    <option value="">Choose a recording...</option>
                                    {availableRecordings.filter(r => r.type === activeSensor).map(r => (
                                        <option value={r.name}>{r.name}</option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    <button
                        onClick={isCalibrating ? handleStopCalibration : handleStartCalibration}
                        className={`px-10 py-3 rounded-xl font-bold transition-all shadow-glow ${isCalibrating
                            ? 'bg-red-500 text-white hover:opacity-90'
                            : 'bg-primary text-primary-contrast hover:opacity-90 hover:translate-y-[-2px]'
                            }`}
                    >
                        {isCalibrating ? 'Stop Calibration' : 'Start Calibration'}
                    </button>
                </div>

                <div className="h-[400px]">
                    <SignalChart
                        title={`${activeSensor} Signal Stream`}
                        byChannel={{ active: sweepData.active, history: sweepData.history }}
                        channelColors={{ active: activeSensor === 'EMG' ? '#3b82f6' : (activeSensor === 'EOG' ? '#10b981' : '#f59e0b'), history: 'rgba(255,255,255,0.1)' }}
                        timeWindowMs={timeWindowMs}
                        color={activeSensor === 'EMG' ? '#3b82f6' : (activeSensor === 'EOG' ? '#10b981' : '#f59e0b')}
                        height={400}
                        scannerX={sweepData.scanner}
                        markedWindows={markedWindows}
                        activeWindow={activeWindow}
                    />
                </div>

                <div className="flex justify-between items-center text-[10px] text-muted font-mono uppercase tracking-widest pt-2">
                    <div className="flex gap-4">
                        <span>Status: <span className={isCalibrating ? 'text-primary' : ''}>{isCalibrating ? 'Active Collection' : 'Idle'}</span></span>
                        <span>Windows: {markedWindows.length}</span>
                    </div>
                    <div className="flex gap-4">
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-primary/20"></span> Active Window</span>
                        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500/20"></span> Labeled Window</span>
                    </div>
                </div>
            </div>

            {/* Bottom Row: Config & Windows */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-fit">
                <ConfigPanel config={config} sensor={activeSensor} onSave={setConfig} />
                <WindowListPanel
                    windows={markedWindows}
                    onDelete={deleteWindow}
                    onMarkMissed={markMissed}
                    activeSensor={activeSensor}
                />
            </div>

            {/* Diagnostic Overlay */}
            <div className="card bg-surface/80 border border-primary/20 p-2 rounded-lg fixed bottom-4 right-4 text-[9px] font-mono z-50 max-w-xs shadow-xl backdrop-blur-md">
                <div className="font-bold text-primary mb-1 uppercase tracking-wider">Debug Info</div>
                <div>Status: <span className={wsData ? 'text-emerald-400' : 'text-red-400'}>{wsData ? '✅ DATA ACTIVE' : '❌ NO DATA'}</span></div>
                <div>Sample Rate: {config.sampling_rate || 250}Hz</div>
                <div>Mapped Channel Val: {chartData.length > 0 ? chartData[chartData.length - 1].value.toFixed(2) : 'N/A'}</div>
                <div className="mt-1 opacity-50 truncate">Last Payload: {wsData ? JSON.stringify(wsData.raw).slice(0, 50) + '...' : 'none'}</div>
            </div>
        </div>
    );
}
