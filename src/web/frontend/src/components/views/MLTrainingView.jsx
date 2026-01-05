import Tree from 'react-d3-tree';
import { useState, useEffect, useRef } from 'react';
import { useWebSocket } from '../../hooks/useWebSocket';

const TabButton = ({ active, onClick, children }) => (
    <button
        onClick={onClick}
        className={`px-6 py-2 font-medium rounded-t-lg transition-colors ${active
            ? 'bg-[var(--surface)] text-[var(--accent)] border-t border-x border-[var(--border)]'
            : 'text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface)]/50'
            }`}
    >
        {children}
    </button>
);

const Pacer = ({ actionText = "BLINK!" }) => {
    const [phase, setPhase] = useState('relax'); // relax, ready, action
    const [count, setCount] = useState(3);

    useEffect(() => {
        const interval = setInterval(() => {
            setCount(c => {
                const next = c - 1;
                if (next < 0) return 3; // Reset to 3s cycle
                return next;
            });
        }, 1000);
        return () => clearInterval(interval);
    }, []);

    const phaseParams = {
        3: { text: "RELAX", color: "text-gray-500", bg: "bg-gray-900", scale: "scale-100" },
        2: { text: "RELAX", color: "text-gray-500", bg: "bg-gray-900", scale: "scale-100" },
        1: { text: "READY...", color: "text-yellow-400", bg: "bg-yellow-900/50", scale: "scale-110" },
        0: { text: actionText, color: "text-green-400 font-black", bg: "bg-green-900/50", scale: "scale-150" }
    }[count] || { text: "", color: "" };

    return (
        <div className={`flex flex-col items-center justify-center p-4 rounded-xl border border-[var(--border)] transition-all duration-300 ${phaseParams.bg} min-h-[120px]`}>
            <div className="text-xs text-[var(--muted)] uppercase tracking-widest mb-2">Pacing Guide</div>
            <div className={`text-4xl transition-all duration-300 transform ${phaseParams.scale} ${phaseParams.color} font-bold`}>
                {phaseParams.text}
            </div>
            {count === 0 && <div className="text-xs text-green-400 mt-2">Hold for 1s</div>}
        </div>
    );
};

export default function MLTrainingView() {
    const [activeTab, setActiveTab] = useState('EMG'); // 'EMG' or 'EOG'

    // --- SOCKET & PREDICTION STATE ---
    const { connect, lastEvent, lastMessage } = useWebSocket('http://localhost:1972');

    // EOG Prediction State
    const [isEogPredicting, setIsEogPredicting] = useState(false);
    const [eogPredictionHistory, setEogPredictionHistory] = useState([]);

    // EMG Prediction State
    const [isEmgPredicting, setIsEmgPredicting] = useState(false);
    const [emgPredictionHistory, setEmgPredictionHistory] = useState([]);


    // --- CHANNEL & CONFIG STATE ---
    const [eogChannels, setEogChannels] = useState([]);
    const [selectedEogChannel, setSelectedEogChannel] = useState(null);
    const [emgChannels, setEmgChannels] = useState([]);
    const [selectedEmgChannel, setSelectedEmgChannel] = useState(null);

    // --- SESSIONS ---
    const [availableSessions, setAvailableSessions] = useState([]);
    const [selectedSession, setSelectedSession] = useState(null);

    // Fetch sessions
    const fetchSessions = async () => {
        try {
            // Assume activeTab determines sensor
            const sensor = activeTab;
            const res = await fetch(`http://localhost:1972/api/sessions/${sensor}`);
            if (res.ok) {
                const list = await res.json();
                setAvailableSessions(list);
            }
        } catch (e) {
            console.error("Failed to list sessions:", e);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, [activeTab]);

    // Initial Fetch: Config for channels
    useEffect(() => {
        connect();
        fetch('http://localhost:1972/api/config')
            .then(res => res.json())
            .then(config => {
                if (config && config.channel_mapping) {
                    const channels = Object.entries(config.channel_mapping)
                        .filter(([k, v]) => (v.sensor || v.type || '').toUpperCase() === 'EOG' && v.enabled)
                        .map(([k, v]) => {
                            // Extract index if key is "ch0" -> "0"
                            // Assume backend handles "0" if we send integer, or "ch0" string?
                            // Backend uses int(channel) which expects integer.
                            // channel_mapping key "ch0" implies user must convert if needed.
                            // But wait, sensor_config.json user snippet shows "ch0".
                            // Let's assume idx corresponds to integer 0, 1 etc as per channel index.
                            const idx = k.replace(/^ch/, '');
                            return { id: idx, label: v.label || `Channel ${idx}` };
                        });
                    setEogChannels(channels);
                    if (channels.length > 0 && selectedEogChannel === null) {
                        setSelectedEogChannel(channels[0].id);
                    }

                    // EMG Channels
                    const emgChs = Object.entries(config.channel_mapping)
                        .filter(([k, v]) => (v.sensor || v.type || '').toUpperCase() === 'EMG' && v.enabled)
                        .map(([k, v]) => {
                            const idx = k.replace(/^ch/, '');
                            return { id: idx, label: v.label || `Channel ${idx}` };
                        });
                    setEmgChannels(emgChs);
                    if (emgChs.length > 0 && selectedEmgChannel === null) {
                        setSelectedEmgChannel(emgChs[0].id);
                    }
                }
            })
            .catch(err => console.error("Failed to load config", err));
    }, []);

    useEffect(() => { connect(); }, []);

    // Handle EOG Events
    useEffect(() => {
        if (lastEvent && lastEvent.event === 'prediction' && lastEvent.type === 'EOG') {
            setEogPredictionHistory(prev => [{
                ...lastEvent,
                timeRel: new Date().toLocaleTimeString()
            }, ...prev].slice(0, 5));
        }
    }, [lastEvent]);

    // Handle EMG Events
    useEffect(() => {
        if (lastEvent && lastEvent.event === 'prediction' && lastEvent.type === 'EMG') {
            setEmgPredictionHistory(prev => [{
                ...lastEvent,
                timeRel: new Date().toLocaleTimeString()
            }, ...prev].slice(0, 5));
        }
    }, [lastEvent]);

    // Auto-switch EOG to "Rest" state if no event for 2 seconds
    useEffect(() => {
        if (eogPredictionHistory.length > 0 && eogPredictionHistory[0].label !== 'Rest') {
            const timer = setTimeout(() => {
                setEogPredictionHistory(prev => [{
                    label: 'Rest',
                    event: 'prediction',
                    type: 'EOG',
                    timeRel: new Date().toLocaleTimeString(),
                    timestamp: Date.now() / 1000
                }, ...prev].slice(0, 5));
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [eogPredictionHistory]);

    // Auto-switch EMG to "Rest" state for visualization if needed (optional, depends on model)
    useEffect(() => {
        if (emgPredictionHistory.length > 0 && emgPredictionHistory[0].label !== 'Rest') {
            const timer = setTimeout(() => {
                setEmgPredictionHistory(prev => [{
                    label: 'Rest',
                    event: 'prediction',
                    type: 'EMG',
                    timeRel: new Date().toLocaleTimeString(),
                    timestamp: Date.now() / 1000
                }, ...prev].slice(0, 5));
            }, 2000); // 2s generic reset
            return () => clearTimeout(timer);
        }
    }, [emgPredictionHistory]);


    const toggleEogPrediction = async () => {
        try {
            const endpoint = isEogPredicting ? 'stop' : 'start';
            await fetch(`http://localhost:1972/api/eog/predict/${endpoint}`, {
                method: 'POST',
                body: JSON.stringify({ channel: selectedEogChannel }),
                headers: { 'Content-Type': 'application/json' }
            });
            setIsEogPredicting(!isEogPredicting);
        } catch (e) { console.error("EOG Prediction toggle failed", e); }
    };

    const toggleEmgPrediction = async () => {
        try {
            const endpoint = isEmgPredicting ? 'stop' : 'start';
            // Assuming EMG prediction endpoint exists similarly
            await fetch(`http://localhost:1972/api/emg/predict/${endpoint}`, {
                method: 'POST',
                body: JSON.stringify({}), // EMG usually multi-channel or auto-mapped, send config if needed
                headers: { 'Content-Type': 'application/json' }
            });
            setIsEmgPredicting(!isEmgPredicting);
        } catch (e) { console.error("EMG Prediction toggle failed", e); }
    };

    // --- SHARED STATE ---
    const [loading, setLoading] = useState(false);
    const [evalLoading, setEvalLoading] = useState(false);
    const [error, setError] = useState(null);

    // --- EMG STATE ---
    const [emgParams, setEmgParams] = useState({
        n_estimators: 300,
        max_depth: 8,
        test_size: 0.3
    });
    const [emgResult, setEmgResult] = useState(null);
    const [emgEvalResult, setEmgEvalResult] = useState(null);
    const [emgStatus, setEmgStatus] = useState({ recording: false, current_label: '', counts: {} });
    const emgStatusInterval = useRef(null);

    // --- EOG STATE ---
    const [eogParams, setEogParams] = useState({
        n_estimators: 100,
        max_depth: 5,
        test_size: 0.2
    });
    const [eogResult, setEogResult] = useState(null);
    const [eogEvalResult, setEogEvalResult] = useState(null);
    const [eogStatus, setEogStatus] = useState({ recording: false, current_label: 0, counts: {} });
    const eogStatusInterval = useRef(null);


    // --- HELPERS ---
    const handleEmgChange = (e) => {
        const { name, value } = e.target;
        setEmgParams(prev => ({ ...prev, [name]: name === 'test_size' ? parseFloat(value) : parseInt(value) }));
    };

    const handleEogChange = (e) => {
        const { name, value } = e.target;
        setEogParams(prev => ({ ...prev, [name]: name === 'test_size' ? parseFloat(value) : parseInt(value) }));
    };

    // --- API CALLS ---

    // EMG TRAIN
    const trainEmg = async () => {
        setLoading(true); setError(null); setEmgResult(null);
        try {
            const res = await fetch('http://localhost:1972/api/train-emg-rf', {
                method: 'POST',
                body: JSON.stringify({
                    ...emgParams,
                    table_name: selectedSession || undefined
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Training failed');
            setEmgResult(data);
        } catch (e) { setError(e.message); } finally { setLoading(false); }
    };

    // EMG EVAL
    const evalEmg = async () => {
        setEvalLoading(true); setError(null); setEmgEvalResult(null);
        try {
            const res = await fetch('http://localhost:1972/api/model/evaluate', { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEmgEvalResult(data);
        } catch (e) { setError(e.message); } finally { setEvalLoading(false); }
    };

    // EMG RECORDING
    const updateEmgStatus = async () => {
        try {
            const res = await fetch('http://localhost:1972/api/emg/status');
            if (res.ok) setEmgStatus(await res.json());
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        if (activeTab === 'EMG') {
            updateEmgStatus();
            emgStatusInterval.current = setInterval(updateEmgStatus, 1000);
        } else {
            if (emgStatusInterval.current) clearInterval(emgStatusInterval.current);
        }
        return () => { if (emgStatusInterval.current) clearInterval(emgStatusInterval.current); };
    }, [activeTab]);

    const startEmgRec = async (label) => {
        try {
            await fetch('http://localhost:1972/api/emg/start', {
                method: 'POST',
                body: JSON.stringify({ label, channel: selectedEmgChannel }),
                headers: { 'Content-Type': 'application/json' }
            });
            updateEmgStatus();
        } catch (e) { setError(e.message); }
    };

    const stopEmgRec = async () => {
        try {
            await fetch('http://localhost:1972/api/emg/stop', { method: 'POST' });
            updateEmgStatus();
        } catch (e) { setError(e.message); }
    };

    const deleteEmgData = async () => {
        if (!window.confirm("Are you sure you want to DELETE ALL EMG data? This cannot be undone.")) return;
        try {
            const res = await fetch('http://localhost:1972/api/emg/data', { method: 'DELETE' });
            if (res.ok) {
                updateEmgStatus();
                setEmgResult(null);
            } else {
                throw new Error("Failed to delete");
            }
        } catch (e) { setError(e.message); }
    };

    // EOG TRAIN
    const trainEog = async () => {
        setLoading(true); setError(null); setEogResult(null);
        try {
            const res = await fetch('http://localhost:1972/api/train-eog-rf', {
                method: 'POST', body: JSON.stringify(eogParams), headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Training failed');
            setEogResult(data);
        } catch (e) { setError(e.message); } finally { setLoading(false); }
    };

    // EOG EVAL
    const evalEog = async () => {
        setEvalLoading(true); setError(null); setEogEvalResult(null);
        try {
            const res = await fetch('http://localhost:1972/api/model/evaluate/eog', { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEogEvalResult(data);
        } catch (e) { setError(e.message); } finally { setEvalLoading(false); }
    };

    // EOG RECORDING
    const updateEogStatus = async () => {
        try {
            const res = await fetch('http://localhost:1972/api/eog/status');
            if (res.ok) setEogStatus(await res.json());
        } catch (e) { console.error(e); }
    };

    useEffect(() => {
        if (activeTab === 'EOG') {
            updateEogStatus();
            eogStatusInterval.current = setInterval(updateEogStatus, 1000);
        } else {
            if (eogStatusInterval.current) clearInterval(eogStatusInterval.current);
        }
        return () => { if (eogStatusInterval.current) clearInterval(eogStatusInterval.current); };
    }, [activeTab]);

    const startEogRec = async (label) => {
        try {
            await fetch('http://localhost:1972/api/eog/start', {
                method: 'POST',
                body: JSON.stringify({ label, channel: selectedEogChannel }),
                headers: { 'Content-Type': 'application/json' }
            });
            updateEogStatus();
        } catch (e) { setError(e.message); }
    };

    const stopEogRec = async () => {
        try {
            await fetch('http://localhost:1972/api/eog/stop', { method: 'POST' });
            updateEogStatus();
        } catch (e) { setError(e.message); }
    };

    const deleteEogData = async () => {
        if (!window.confirm("Are you sure you want to DELETE ALL EOG data? This cannot be undone.")) return;
        try {
            const res = await fetch('http://localhost:1972/api/eog/data', { method: 'DELETE' });
            if (res.ok) {
                updateEogStatus();
                setEogResult(null); // Clear previous training results
            } else {
                throw new Error("Failed to delete");
            }
        } catch (e) { setError(e.message); }
    };


    // Helper for tree
    const renderCustomNodeElement = ({ nodeDatum, toggleNode }) => (
        <g>
            <circle r="15" fill="var(--primary)" stroke="var(--border)" onClick={toggleNode} />
            <text fill="var(--text)" x="20" dy="5" strokeWidth="0">{nodeDatum.name}</text>
            {nodeDatum.attributes && (
                <text fill="var(--muted)" x="20" dy="25" strokeWidth="0" fontSize="10">
                    {Object.entries(nodeDatum.attributes).map(([k, v]) => `${k}: ${v}`).join(', ')}
                </text>
            )}
        </g>
    );

    const renderResults = (res, labelMap) => (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-6">
            <div className="space-y-6">
                <div className="card">
                    <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Performance</h2>
                    <div className="text-4xl font-bold text-[var(--primary)] mb-2">{(res.accuracy * 100).toFixed(2)}%</div>
                    <p className="text-[var(--muted)] uppercase text-xs tracking-wider">Overall Accuracy ({res.n_samples} samples)</p>
                </div>
                <div className="card">
                    <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Confusion Matrix</h2>
                    <div className="overflow-x-auto">
                        <table className="min-w-full text-sm text-left text-[var(--text)]">
                            <thead>
                                <tr className="bg-[var(--bg)]">
                                    <th className="p-2">Act \ Pred</th>
                                    {labelMap.map((l, i) => <th key={i} className="p-2">{l}</th>)}
                                </tr>
                            </thead>
                            <tbody>
                                {res.confusion_matrix.map((row, i) => (
                                    <tr key={i} className="border-b border-[var(--border)]">
                                        <td className="p-2 font-medium bg-[var(--surface)] text-[var(--accent)]">{labelMap[i]}</td>
                                        {row.map((cell, j) => (
                                            <td key={j} className={`p-2 ${i === j ? 'bg-[var(--primary)] text-[var(--primary-contrast)] font-bold' : ''}`}>{cell}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
                {res.feature_importances && (
                    <div className="card">
                        <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Feature Importances</h2>
                        <ul className="space-y-2">
                            {Object.entries(res.feature_importances).sort(([, a], [, b]) => b - a).map(([name, imp]) => (
                                <li key={name} className="flex items-center text-[var(--text)]">
                                    <span className="w-24 font-mono text-xs text-[var(--muted)] truncate">{name}</span>
                                    <div className="flex-1 h-3 bg-[var(--bg)] rounded-full ml-2 overflow-hidden border border-[var(--border)]">
                                        <div className="h-full bg-[var(--primary)]" style={{ width: `${imp * 100}%` }}></div>
                                    </div>
                                    <span className="ml-2 text-xs text-[var(--text)]">{(imp * 100).toFixed(1)}%</span>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
            {res.tree_structure && (
                <div className="card h-[600px] flex flex-col">
                    <h2 className="text-xl font-semibold mb-4 border-b border-[var(--border)] pb-2 text-[var(--text)]">Decision Tree</h2>
                    <div className="flex-1 border border-[var(--border)] rounded bg-[var(--bg)] overflow-hidden" style={{ minHeight: '500px' }}>
                        <Tree data={res.tree_structure} orientation="vertical" translate={{ x: 300, y: 50 }} pathFunc="step" separation={{ siblings: 1.5, nonSiblings: 2 }} zoomable={true} renderCustomNodeElement={renderCustomNodeElement} />
                    </div>
                </div>
            )}
        </div>
    );

    return (
        <div className="container py-8 font-sans">
            <h1 className="text-3xl font-bold mb-6 text-[var(--accent)]">Model Training & Evaluation</h1>

            {/* ERROR DISPLAY */}
            {error && <div className="bg-red-900/20 border border-red-500 text-red-200 px-4 py-3 rounded mb-6"><strong>Error:</strong> {error}</div>}

            {/* TABS */}
            <div className="flex border-b border-[var(--border)] mb-6">
                <TabButton active={activeTab === 'EMG'} onClick={() => setActiveTab('EMG')}>EMG (Gestures)</TabButton>
                <TabButton active={activeTab === 'EOG'} onClick={() => setActiveTab('EOG')}>EOG (Blinks)</TabButton>
            </div>

            {/* === EMG VIEW === */}
            {activeTab === 'EMG' && (
                <div>
                    {/* Live Prediction */}
                    <div className="card mb-8 border-l-4 border-l-blue-500">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-semibold text-[var(--text)]">Real-time Classification (EMG)</h2>
                            <button
                                onClick={toggleEmgPrediction}
                                className={`btn ${isEmgPredicting ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} min-w-[120px] shadow-lg`}
                            >
                                {isEmgPredicting ? 'STOP LIVE' : 'START LIVE'}
                            </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            {/* Current Prediction Display */}
                            <div className="bg-[var(--bg)] rounded-xl p-6 flex flex-col items-center justify-center min-h-[160px] border border-[var(--border)] relative overflow-hidden">
                                {isEmgPredicting ? (
                                    <>
                                        {emgPredictionHistory[0] ? (
                                            <>
                                                <div className="text-sm text-[var(--muted)] uppercase tracking-widest mb-2">Detected Event</div>
                                                <div className={`text-5xl font-black ${emgPredictionHistory[0].label === 'Rock' ? 'text-red-400' :
                                                    emgPredictionHistory[0].label === 'Paper' ? 'text-blue-400' :
                                                        emgPredictionHistory[0].label === 'Scissors' ? 'text-orange-400' :
                                                            'text-gray-500/50'
                                                    } animate-pulse-fast transition-all`}>
                                                    {emgPredictionHistory[0].label}
                                                </div>
                                                <div className="text-xs text-[var(--muted)] mt-2 font-mono">{emgPredictionHistory[0].timeRel}</div>
                                            </>
                                        ) : (
                                            <div className="text-[var(--muted)] animate-pulse">Waiting for gestures...</div>
                                        )}
                                        {/* Status Indicator */}
                                        <div className="absolute top-2 right-2 w-3 h-3 rounded-full bg-red-500 animate-ping"></div>
                                        <div className="absolute top-2 right-2 w-3 h-3 rounded-full bg-red-500"></div>
                                    </>
                                ) : (
                                    <div className="text-[var(--muted)]">Live classification is OFF</div>
                                )}
                            </div>

                            {/* History Log */}
                            <div className="bg-[var(--bg)] rounded-xl p-4 border border-[var(--border)] h-[160px] overflow-y-auto custom-scrollbar">
                                <h3 className="text-xs font-bold text-[var(--muted)] uppercase mb-2 sticky top-0 bg-[var(--bg)] pb-1">Recent Events</h3>
                                {emgPredictionHistory.length > 0 ? (
                                    <ul className="space-y-2">
                                        {emgPredictionHistory.map((evt, i) => (
                                            <li key={i} className="flex justify-between items-center text-sm p-2 rounded hover:bg-[var(--surface)] transition-colors border-b border-[var(--border)]/50 last:border-0">
                                                <span className={`font-bold ${evt.label === 'Rock' ? 'text-red-400' :
                                                    evt.label === 'Paper' ? 'text-blue-400' :
                                                        evt.label === 'Scissors' ? 'text-orange-400' : 'text-[var(--muted)]'
                                                    }`}>{evt.label}</span>
                                                <span className="font-mono text-xs text-[var(--muted)]">{evt.timeRel}</span>
                                            </li>
                                        ))}
                                    </ul>
                                ) : (
                                    <div className="flex h-full items-center justify-center text-xs text-[var(--muted)] italic">No recent events</div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Data Collection (Gestures) */}
                    <div className="card mb-8">
                        <div className="flex justify-between items-start mb-4">
                            <h2 className="text-xl font-semibold text-[var(--text)]">Data Collection (Gestures)</h2>
                            <button onClick={deleteEmgData} className="text-red-500 hover:text-red-400 text-sm font-bold border border-red-500 rounded px-2 py-1 uppercase hover:bg-red-500/10 transition-colors">
                                Delete All Data
                            </button>
                        </div>

                        {/* Channel Selector */}
                        <div className="mb-4 p-3 bg-[var(--bg)] rounded border border-[var(--border)]">
                            <label className="text-xs text-[var(--muted)] uppercase font-bold block mb-2">Target Channel</label>
                            {emgChannels.length > 1 ? (
                                <select
                                    className="w-full bg-[var(--surface)] text-[var(--text)] p-2 rounded border border-[var(--border)]"
                                    value={selectedEmgChannel || ''}
                                    onChange={(e) => setSelectedEmgChannel(e.target.value)}
                                >
                                    {emgChannels.map(ch => (
                                        <option key={ch.id} value={ch.id}>{ch.label} (CH{ch.id})</option>
                                    ))}
                                </select>
                            ) : emgChannels.length === 1 ? (
                                <div className="text-[var(--accent)] font-mono">{emgChannels[0].label} (CH{emgChannels[0].id})</div>
                            ) : (
                                <div className="text-red-500 font-bold">⚠️ No EMG Channels Configured</div>
                            )}
                        </div>

                        {/* Recording & Pacer UI */}
                        {emgStatus.recording ? (
                            <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4 animate-fadeIn">
                                <div className="p-4 bg-red-900/20 border border-red-500 rounded-lg flex flex-col items-center justify-center">
                                    <div className="text-red-400 font-bold text-lg mb-2 animate-pulse">🔴 RECORDING ACTIVE</div>
                                    <div className="text-[var(--muted)] mb-4 text-center">
                                        Recording Label: <strong className="text-white">{emgStatus.current_label}</strong>
                                        <br />
                                        <span className="text-xs">Ch: {emgStatus.channel_index !== null ? emgStatus.channel_index : 'Default'}</span>
                                    </div>
                                    <button
                                        onClick={stopEmgRec}
                                        className="btn bg-red-600 hover:bg-red-700 w-full"
                                    >
                                        STOP RECORDING
                                    </button>
                                </div>
                                <Pacer actionText={emgStatus.current_label || "ACTION!"} />
                            </div>
                        ) : null}

                        {/* Status Cards */}
                        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
                            {['Rest', 'Rock', 'Paper', 'Scissors'].map((label, idx) => (
                                <div key={label} className="card bg-[var(--bg)] borderable p-4 flex flex-col items-center justify-center">
                                    <div className="text-xs text-[var(--muted)] uppercase font-bold text-center mb-1">{label}</div>
                                    <div className="text-2xl font-bold text-[var(--text)]">
                                        {emgStatus.counts[String(idx)] || 0}
                                    </div>
                                    <div className="text-[10px] text-[var(--muted)]">samples</div>
                                </div>
                            ))}
                            <div className={`card flex flex-col items-center justify-center borderable p-4 ${emgStatus.recording ? 'bg-red-500/10 border-red-500 animate-pulse' : 'bg-[var(--bg)]'}`}>
                                <div className="text-xs text-[var(--muted)] uppercase font-bold text-center mb-1">Status</div>
                                <div className={`font-bold ${emgStatus.recording ? 'text-red-500' : 'text-[var(--text)]'}`}>
                                    {emgStatus.recording ? 'RECORDING' : 'IDLE'}
                                </div>
                            </div>
                        </div>

                        {/* Recording Buttons */}
                        {!emgStatus.recording ? (
                            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                {['Rest', 'Rock', 'Paper', 'Scissors'].map((label, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => startEmgRec(idx)}
                                        className="btn h-12 bg-[var(--surface)] hover:bg-[var(--primary)]/20 border border-[var(--border)] hover:border-[var(--primary)] text-[var(--text)] font-bold transition-all"
                                    >
                                        Record {label}
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <div className="p-4 bg-[var(--bg)]/50 border border-[var(--border)] border-dashed rounded-xl flex justify-center">
                                <button
                                    onClick={stopEmgRec}
                                    className="btn bg-red-600 hover:bg-red-500 w-full max-w-md animate-pulse shadow-lg"
                                >
                                    STOP RECORDING
                                </button>
                            </div>
                        )}
                        <p className="text-xs text-[var(--muted)] mt-4">* Select a gesture to interpret and record 3-second windows.</p>
                    </div>

                    {/* Channel Selector Placeholder (Removed from here, moved inside card) */}





                    {/* Controls */}
                    <div className="card mb-8">
                        <div className="mb-4 p-3 bg-bg/50 border border-border rounded flex flex-col gap-2">
                            <label className="text-sm font-bold text-text">Training Data Source (Session)</label>
                            <div className="flex gap-2">
                                <select
                                    className="flex-1 bg-surface text-text border border-border rounded p-2"
                                    value={selectedSession || ''}
                                    onChange={(e) => setSelectedSession(e.target.value)}
                                >
                                    <option value="">All Data / Default (emg_windows)</option>
                                    {availableSessions.map(s => (
                                        <option key={s.table} value={s.table}>{s.name}</option>
                                    ))}
                                </select>
                                <button onClick={fetchSessions} className="p-2 border border-border rounded hover:bg-surface">🔄</button>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                            <div>
                                <label className="block text-sm font-medium mb-1 text-[var(--text)]">Results (Trees)</label>
                                <input type="number" name="n_estimators" value={emgParams.n_estimators} onChange={handleEmgChange} className="input" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1 text-[var(--text)]">Max Depth</label>
                                <input type="number" name="max_depth" value={emgParams.max_depth} onChange={handleEmgChange} className="input" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1 text-[var(--text)]">Test Size</label>
                                <input type="number" step="0.05" name="test_size" value={emgParams.test_size} onChange={handleEmgChange} className="input" />
                            </div>
                            <button onClick={trainEmg} disabled={loading} className="btn w-full h-[46px]">
                                {loading ? 'Training...' : 'Train EMG Model'}
                            </button>
                        </div>
                    </div>

                    {/* Evals */}
                    <div className="card mb-8 flex justify-between items-center">
                        <div>
                            <h2 className="text-xl font-semibold text-[var(--text)]">Saved Model & Trees</h2>
                            <p className="text-sm text-[var(--muted)]">Load `emg_rf.joblib`, view decision trees, and evaluate against dataset.</p>
                        </div>
                        <button onClick={evalEmg} disabled={evalLoading} className="btn bg-[var(--surface)] text-[var(--text)] border border-[var(--border)]">
                            {evalLoading ? 'Loading...' : 'Load Model & Evaluate'}
                        </button>
                    </div>

                    {/* Results */}
                    {emgResult && renderResults(emgResult, ['Rest', 'Rock', 'Paper', 'Scissors'])}
                    {emgEvalResult && (
                        <div className="mt-8 border-t border-[var(--border)] pt-8">
                            <h3 className="text-2xl text-[var(--accent)] font-bold mb-4">Saved Model Evaluation</h3>
                            {renderResults(emgEvalResult, ['Rest', 'Rock', 'Paper', 'Scissors'])}
                        </div>
                    )}
                </div>
            )}

            {/* === EOG VIEW === */}
            {
                activeTab === 'EOG' && (
                    <div>
                        {/* Live Prediction */}
                        <div className="card mb-8 border-l-4 border-l-purple-500">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xl font-semibold text-[var(--text)]">Real-time Classification (EOG)</h2>
                                <button
                                    onClick={toggleEogPrediction}
                                    className={`btn ${isEogPredicting ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} min-w-[120px] shadow-lg`}
                                >
                                    {isEogPredicting ? 'STOP LIVE' : 'START LIVE'}
                                </button>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                {/* Current Prediction Display */}
                                <div className="bg-[var(--bg)] rounded-xl p-6 flex flex-col items-center justify-center min-h-[160px] border border-[var(--border)] relative overflow-hidden">
                                    {isEogPredicting ? (
                                        <>
                                            {eogPredictionHistory[0] ? (
                                                <>
                                                    <div className="text-sm text-[var(--muted)] uppercase tracking-widest mb-2">Detected Event</div>
                                                    <div className={`text-5xl font-black ${eogPredictionHistory[0].label === 'DoubleBlink' ? 'text-purple-400' :
                                                        eogPredictionHistory[0].label === 'SingleBlink' ? 'text-blue-400' : 'text-gray-500/50'
                                                        } animate-pulse-fast transition-all`}>
                                                        {eogPredictionHistory[0].label === 'Rest' ? 'Resting...' : eogPredictionHistory[0].label.replace(/Blink/, ' Blink')}
                                                    </div>
                                                    <div className="text-xs text-[var(--muted)] mt-2 font-mono">{eogPredictionHistory[0].timeRel}</div>
                                                </>
                                            ) : (
                                                <div className="text-[var(--muted)] animate-pulse">Waiting for blinks...</div>
                                            )}
                                            {/* Status Indicator */}
                                            <div className="absolute top-2 right-2 w-3 h-3 rounded-full bg-red-500 animate-ping"></div>
                                            <div className="absolute top-2 right-2 w-3 h-3 rounded-full bg-red-500"></div>
                                        </>
                                    ) : (
                                        <div className="text-[var(--muted)]">Live classification is OFF</div>
                                    )}
                                </div>

                                {/* History Log */}
                                <div className="bg-[var(--bg)] rounded-xl p-4 border border-[var(--border)] h-[160px] overflow-y-auto custom-scrollbar">
                                    <h3 className="text-xs font-bold text-[var(--muted)] uppercase mb-2 sticky top-0 bg-[var(--bg)] pb-1">Recent Events</h3>
                                    {eogPredictionHistory.length > 0 ? (
                                        <ul className="space-y-2">
                                            {eogPredictionHistory.map((evt, i) => (
                                                <li key={i} className="flex justify-between items-center text-sm p-2 rounded hover:bg-[var(--surface)] transition-colors border-b border-[var(--border)]/50 last:border-0">
                                                    <span className={`font-bold ${evt.label === 'DoubleBlink' ? 'text-purple-400' : 'text-blue-400'
                                                        }`}>{evt.label}</span>
                                                    <span className="font-mono text-xs text-[var(--muted)]">{evt.timeRel}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <div className="flex h-full items-center justify-center text-xs text-[var(--muted)] italic">No recent events</div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Data Collection */}
                        <div className="card mb-8">
                            <div className="flex justify-between items-start mb-4">
                                <h2 className="text-xl font-semibold text-[var(--text)]">Data Collection</h2>
                                <button onClick={deleteEogData} className="text-red-500 hover:text-red-400 text-sm font-bold border border-red-500 rounded px-2 py-1 uppercase hover:bg-red-500/10 transition-colors">
                                    Delete All Data
                                </button>
                            </div>

                            {/* Channel Selector */}
                            <div className="mb-4 p-3 bg-[var(--bg)] rounded border border-[var(--border)]">
                                <label className="text-xs text-[var(--muted)] uppercase font-bold block mb-2">Target Channel</label>
                                {eogChannels.length > 1 ? (
                                    <select
                                        className="w-full bg-[var(--surface)] text-[var(--text)] p-2 rounded border border-[var(--border)]"
                                        value={selectedEogChannel || ''}
                                        onChange={(e) => setSelectedEogChannel(e.target.value)}
                                    >
                                        {eogChannels.map(ch => (
                                            <option key={ch.id} value={ch.id}>{ch.label} (CH{ch.id})</option>
                                        ))}
                                    </select>
                                ) : eogChannels.length === 1 ? (
                                    <div className="text-[var(--accent)] font-mono">{eogChannels[0].label} (CH{eogChannels[0].id})</div>
                                ) : (
                                    <div className="text-red-500 font-bold">⚠️ No EOG Channels Configured</div>
                                )}
                            </div>

                            {/* Recording & Pacer UI */}
                            {eogStatus.recording ? (
                                <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4 animate-fadeIn">
                                    <div className="p-4 bg-red-900/20 border border-red-500 rounded-lg flex flex-col items-center justify-center">
                                        <div className="text-red-400 font-bold text-lg mb-2 animate-pulse">🔴 RECORDING ACTIVE</div>
                                        <div className="text-[var(--muted)] mb-4 text-center">
                                            Recording Label: <strong className="text-white">{eogStatus.current_label}</strong>
                                            <br />
                                            <span className="text-xs">Ch: {eogStatus.channel_index !== null ? eogStatus.channel_index : 'Default'}</span>
                                        </div>
                                        <button
                                            onClick={stopEogRec}
                                            className="btn bg-red-600 hover:bg-red-700 w-full"
                                        >
                                            STOP RECORDING
                                        </button>
                                    </div>
                                    <Pacer actionText="BLINK!" />
                                </div>
                            ) : null}

                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                                <div className="card bg-[var(--bg)] borderable">
                                    <div className="text-xs text-[var(--muted)] uppercase">Rest Samples</div>
                                    <div className="text-2xl font-bold text-[var(--text)]">{eogStatus.counts["0"] || 0}</div>
                                </div>
                                <div className="card bg-[var(--bg)] borderable">
                                    <div className="text-xs text-[var(--muted)] uppercase">Single Blink</div>
                                    <div className="text-2xl font-bold text-[var(--text)]">{eogStatus.counts["1"] || 0}</div>
                                </div>
                                <div className="card bg-[var(--bg)] borderable">
                                    <div className="text-xs text-[var(--muted)] uppercase">Double Blink</div>
                                    <div className="text-2xl font-bold text-[var(--text)]">{eogStatus.counts["2"] || 0}</div>
                                </div>
                                <div className={`card flex items-center justify-center ${eogStatus.recording ? 'bg-red-500/20 border-red-500 animate-pulse' : 'bg-[var(--bg)]'}`}>
                                    <div className="font-bold text-[var(--text)]">{eogStatus.recording ? `RECORDING...` : 'IDLE'}</div>
                                </div>
                            </div>

                            {!eogStatus.recording ? (
                                <div className="flex gap-4">
                                    <button onClick={() => startEogRec(0)} className="btn bg-gray-600 hover:bg-gray-500 flex-1">Record Rest</button>
                                    <button onClick={() => startEogRec(1)} className="btn bg-blue-600 hover:bg-blue-500 flex-1">Record Single</button>
                                    <button onClick={() => startEogRec(2)} className="btn bg-purple-600 hover:bg-purple-500 flex-1">Record Double</button>
                                </div>
                            ) : (
                                <button onClick={stopEogRec} className="btn bg-red-600 hover:bg-red-500 w-full animate-pulse">STOP RECORDING</button>
                            )}
                            <p className="text-xs text-[var(--muted)] mt-2">* Perform the action REPEATEDLY while recording. The system extracts detected events automatically.</p>
                        </div>

                        {/* Training Controls */}
                        <div className="card mb-8 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                            <div>
                                <label className="block text-sm font-medium mb-1 text-[var(--text)]">Results (Trees)</label>
                                <input type="number" name="n_estimators" value={eogParams.n_estimators} onChange={handleEogChange} className="input" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1 text-[var(--text)]">Max Depth</label>
                                <input type="number" name="max_depth" value={eogParams.max_depth} onChange={handleEogChange} className="input" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-1 text-[var(--text)]">Test Size</label>
                                <input type="number" step="0.05" name="test_size" value={eogParams.test_size} onChange={handleEogChange} className="input" />
                            </div>
                            <button onClick={trainEog} disabled={loading} className="btn w-full h-[46px]">
                                {loading ? 'Training...' : 'Train EOG Model'}
                            </button>
                        </div>

                        {/* Evals */}
                        <div className="card mb-8 flex justify-between items-center">
                            <div>
                                <h2 className="text-xl font-semibold text-[var(--text)]">Saved Model & Trees</h2>
                                <p className="text-sm text-[var(--muted)]">Load `eog_rf.joblib`, view decision trees, and evaluate against dataset.</p>
                            </div>
                            <button onClick={evalEog} disabled={evalLoading} className="btn bg-[var(--surface)] text-[var(--text)] border border-[var(--border)]">
                                {evalLoading ? 'Loading...' : 'Load Model & Evaluate'}
                            </button>
                        </div>

                        {/* Results */}
                        {eogResult && renderResults(eogResult, ['Rest', 'Single', 'Double'])}
                        {eogEvalResult && (
                            <div className="mt-8 border-t border-[var(--border)] pt-8">
                                <h3 className="text-2xl text-[var(--accent)] font-bold mb-4">Saved Model Evaluation</h3>
                                {renderResults(eogEvalResult, ['Rest', 'Single', 'Double'])}
                            </div>
                        )}
                    </div>
                )
            }
        </div>
    );
}

