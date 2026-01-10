<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
import React, { useState, useEffect, useRef } from 'react';
import Tree from 'react-d3-tree';
import { useWebSocket } from '../../hooks/useWebSocket';
=======
import Tree from 'react-d3-tree';
import { useState, useEffect } from 'react';
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx

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

<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
const Pacer = () => {
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
        0: { text: "BLINK!", color: "text-green-400 font-black", bg: "bg-green-900/50", scale: "scale-150" }
    }[count] || { text: "", color: "" };

    return (
        <div className={`flex flex-col items-center justify-center p-4 rounded-xl border border-[var(--border)] transition-all duration-300 ${phaseParams.bg} min-h-[120px]`}>
            <div className="text-xs text-[var(--muted)] uppercase tracking-widest mb-2">Pacing Guide</div>
            <div className={`text-4xl transition-all duration-300 transform ${phaseParams.scale} ${phaseParams.color} font-bold`}>
                {phaseParams.text}
            </div>
            {count === 0 && <div className="text-xs text-green-400 mt-2">Hold for 1s</div>}
=======
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

// BENTO COMPONENTS
const AccuracyCard = ({ accuracy, n_samples, source }) => (
    <div className="card h-full flex flex-col justify-center items-center p-6 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm hover:shadow-md transition-shadow">
        <h3 className="text-xl font-bold text-[var(--muted)] uppercase tracking-widest mb-2">Model Accuracy</h3>
        {accuracy !== null && accuracy !== undefined ? (
            <>
                <div className="text-5xl font-black text-[var(--primary)] mb-2">{(accuracy * 100).toFixed(1)}%</div>
                <p className="text-base text-[var(--text)] opacity-70">on {n_samples} test samples</p>
                {source && <p className="text-xs text-[var(--muted)] mt-2 font-mono bg-[var(--bg)] px-2 py-1 rounded border border-[var(--border)]">{source}</p>}
            </>
        ) : (
            <div className="text-center">
                <div className="text-3xl text-[var(--muted)] mb-1">N/A</div>
                <p className="text-sm text-[var(--muted)] opacity-60">No data to evaluate</p>
                <p className="text-xs text-[var(--muted)] opacity-40 mt-1">Select a valid session</p>
            </div>
        )}
    </div>
);

const FeatureImportanceCard = ({ importances }) => (
    <div className="card h-full flex flex-col p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm">
        <h3 className="text-base font-bold text-[var(--muted)] uppercase tracking-widest mb-4 border-b border-[var(--border)] pb-2">Top Features</h3>
        <ul className="h-full overflow-y-auto custom-scrollbar flex-grow flex flex-col justify-between pr-2 pb-1">
            {Object.entries(importances).sort(([, a], [, b]) => b - a).slice(0, 8).map(([name, imp]) => (
                <li key={name} className="flex items-center text-[var(--text)] group ">
                    <span className="w-16 font-mono text-[15px] text-[var(--muted)] truncate">{name}</span>
                    <div className="flex-1 h-3.5 bg-[var(--bg)] rounded-full ml-2 overflow-hidden border border-[var(--border)]">
                        <div className="h-full bg-[var(--primary)] group-hover:bg-[var(--accent)] transition-colors" style={{ width: `${imp * 100}%` }}></div>
                    </div>
                    <span className="ml-2 text-[16px] w-8 text-right font-mono">{(imp * 100).toFixed(0)}%</span>
                </li>
            ))}
        </ul>
    </div>
);

// New Component for Hyperparameters
const HyperparametersCard = ({ params, onChange }) => (
    <div className="card h-full flex flex-col p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm">
        <h3 className="text-base font-bold text-[var(--muted)] uppercase tracking-widest border-b border-[var(--border)] pb-2">Hyperparameters</h3>
        <div className="py-4 space-y-4 flex-grow flex flex-col justify-between">
            <div>
                <div className="flex justify-between mb-1">
                    <span className="text-xs text-[var(--text)]">Trees</span>
                    <span className="text-xs font-mono text-[var(--primary)]">{params.n_estimators}</span>
                </div>
                <input type="range" min="10" max="500" step="10" name="n_estimators" value={params.n_estimators} onChange={onChange} className="w-full accent-[var(--primary)]" />
            </div>
            <div>
                <div className="flex justify-between mb-1">
                    <span className="text-xs text-[var(--text)]">Max Depth</span>
                    <span className="text-xs font-mono text-[var(--primary)]">{params.max_depth}</span>
                </div>
                <input type="range" min="1" max="20" step="1" name="max_depth" value={params.max_depth} onChange={onChange} className="w-full accent-[var(--primary)]" />
            </div>
            <div>
                <div className="flex justify-between mb-1">
                    <span className="text-xs text-[var(--text)]">Test Size</span>
                    <span className="text-xs font-mono text-[var(--primary)]">{params.test_size}</span>
                </div>
                <input type="range" min="0.1" max="0.9" step="0.05" name="test_size" value={params.test_size} onChange={onChange} className="w-full accent-[var(--primary)]" />
            </div>
        </div>
    </div>
);

const ConfusionMatrixCard = ({ matrix, labels, n_samples }) => (
    <div className="card h-full flex flex-col p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm">
        <div className="flex justify-between items-center border-b border-[var(--border)] pb-2">
            <h3 className="text-sm font-bold text-[var(--muted)] uppercase tracking-widest">
                Confusion Matrix
                {n_samples !== undefined && <span className="ml-2 text-xs normal-case opacity-70">({n_samples} samples)</span>}
            </h3>
            <div className="flex items-center gap-2 text-[10px] bg-[var(--bg)] px-2 py-0.5 rounded border border-[var(--border)]">
                <span className="font-bold text-[var(--text)]">Actual</span>
                <span className="text-[var(--muted)]">→</span>
                <span className="font-bold text-[var(--primary)]">Pred</span>
            </div>
        </div>
        <div className="flex-grow overflow-hidden flex flex-col h-full py-4 relative">
            {matrix ? (
                <table className="w-full h-full text-[16px] text-center text-[var(--text)] border-collapse table-fixed">
                    <thead>
                        <tr>
                            <th className="p-2 w-24 text-left text-[var(--muted)] font-normal italic border-b border-[var(--border)] bg-[var(--bg)]/30">Class</th>
                            {labels.map((l, i) => (
                                <th key={i} className="p-2 font-bold text-[var(--primary)] border-b border-[var(--border)] bg-[var(--bg)]/10 truncate" title={l}>
                                    {l}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {matrix.map((row, i) => (
                            <tr key={i} className="hover:bg-[var(--surface)]/50 transition-colors group">
                                <td className="p-2 font-bold text-[var(--text)] text-left border-r border-[var(--border)] bg-[var(--bg)]/20 truncate" title={labels[i]}>
                                    {labels[i]}
                                </td>
                                {row.map((cell, j) => (
                                    <td key={j} className={`p-2 border border-[var(--border)] transition-all ${i === j
                                        ? 'bg-[var(--primary)]/20 font-black text-[var(--primary)]'
                                        : cell > 0 ? 'bg-red-500/10 text-red-400 font-medium' : 'text-[var(--muted)] opacity-20'
                                        }`}>
                                        {cell}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <div className="text-3xl text-[var(--muted)] mb-1">N/A</div>
                    <p className="text-sm text-[var(--muted)] opacity-60">No confusion data</p>
                </div>
            )}
        </div>
    </div>
);

const getDepth = (node) => {
    if (!node) return 0;
    if (!node.children || node.children.length === 0) return 1;
    return 1 + Math.max(...node.children.map(getDepth));
};

const DecisionTreeCard = ({ structure }) => {
    const depth = getDepth(structure);
    return (
        <div className="card h-full flex flex-col p-0 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm overflow-hidden relative group">
            <div className="absolute top-4 left-4 z-10 bg-[var(--bg)]/80 backdrop-blur px-3 py-1 rounded border border-[var(--border)]">
                <h3 className="text-sm font-bold text-[var(--text)]">Decision Tree Visualization</h3>
            </div>
            <div className="w-full h-full bg-[var(--bg)]" style={{ minHeight: '400px' }}>
                <Tree
                    data={structure}
                    orientation="vertical"
                    translate={{ x: 400, y: 50 }}
                    pathFunc="step"
                    depthFactor={depth < 10 ? 100 : undefined}
                    separation={{ siblings: 1.5, nonSiblings: 2 }}
                    zoomable={true}
                    renderCustomNodeElement={renderCustomNodeElement}
                />
            </div>
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
        </div>
    );
};

<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
export default function MLTrainingView() {
    const [activeTab, setActiveTab] = useState('EMG'); // 'EMG' or 'EOG'

    // --- SOCKET & PREDICTION STATE ---
    const { connect, lastEvent } = useWebSocket('http://localhost:5000');
    const [isPredicting, setIsPredicting] = useState(false);
    const [predictionHistory, setPredictionHistory] = useState([]);

    // --- CHANNEL & CONFIG STATE ---
    const [eogChannels, setEogChannels] = useState([]);
    const [selectedEogChannel, setSelectedEogChannel] = useState(null);

    // Initial Fetch: Config for channels
    useEffect(() => {
        connect();
        fetch('http://localhost:5000/api/config')
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
                }
            })
            .catch(err => console.error("Failed to load config", err));
    }, []);

    useEffect(() => { connect(); }, []);

    useEffect(() => {
        if (lastEvent && lastEvent.event === 'prediction' && lastEvent.type === 'EOG') {
            setPredictionHistory(prev => [{
                ...lastEvent,
                timeRel: new Date().toLocaleTimeString()
            }, ...prev].slice(0, 5));
        }
    }, [lastEvent]);

    // Auto-switch to "Rest" state if no event for 2 seconds
    useEffect(() => {
        if (predictionHistory.length > 0 && predictionHistory[0].label !== 'Rest') {
            const timer = setTimeout(() => {
                setPredictionHistory(prev => [{
                    label: 'Rest',
                    event: 'prediction',
                    type: 'EOG',
                    timeRel: new Date().toLocaleTimeString(),
                    timestamp: Date.now() / 1000
                }, ...prev].slice(0, 5));
            }, 2000);
            return () => clearTimeout(timer);
        }
    }, [predictionHistory]);

    const togglePrediction = async () => {
        try {
            const endpoint = isPredicting ? 'stop' : 'start';
            await fetch(`http://localhost:5000/api/eog/predict/${endpoint}`, {
                method: 'POST',
                body: JSON.stringify({ channel: selectedEogChannel }),
                headers: { 'Content-Type': 'application/json' }
            });
            setIsPredicting(!isPredicting);
        } catch (e) { console.error("Prediction toggle failed", e); }
    };

=======
// Updated ControlPanel (Removed Hyperparameters)
const ControlPanel = ({
    onTrain,
    loading,
    onEval,
    evalLoading,
    sessions,
    selectedSession,
    onSessionSelect,
    onRefreshSessions,
    activeTab,
    setActiveTab
}) => (
    <div className="space-y-4">
        {/* Session Select */}
        <div className="card p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl flex flex-col gap-2">
            <span className="flex flex-row justify-between">
                <label className="text-xl font-bold text-[var(--muted)] uppercase tracking-wide mb-2 block">Training Data</label>
                {/* TABS */}
                <span className="flex bg-[var(--surface)] rounded-lg p-1 border border-[var(--border)]">
                    <button
                        onClick={() => { setActiveTab('EMG'); onSessionSelect(null); }}
                        className={`px-2 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'EMG' ? 'bg-[var(--primary)] text-white shadow' : 'text-[var(--text)] hover:text-[var(--primary)]'} `}
                    >
                        EMG (Gestures)
                    </button>
                    <button
                        onClick={() => { setActiveTab('EOG'); onSessionSelect(null); }}
                        className={`px-2 py-1.5 rounded-md text-sm font-medium transition-all ${activeTab === 'EOG' ? 'bg-[var(--primary)] text-white shadow' : 'text-[var(--text)] hover:text-[var(--primary)]'} `}
                    >
                        EOG (Blinks)
                    </button>
                </span>
            </span>

            <div className="flex gap-2">
                <select
                    className="flex-1 bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] rounded p-2 text-lg focus:border-[var(--primary)] outline-none"
                    value={selectedSession || ''}
                    onChange={(e) => onSessionSelect(e.target.value)}
                >
                    <option value="">All Available Data</option>
                    {sessions.map(s => (
                        <option key={s.table} value={s.table}>{s.name}</option>
                    ))}
                </select>
                <button onClick={onRefreshSessions} className="p-2.5 border border-[var(--border)] rounded hover:bg-[var(--bg)] text-[var(--text)]" title="Refresh Sessions">🔄</button>
            </div>
        </div>

        {/* Actions */}
        <div className="grid grid-cols-1 gap-3">
            <button
                onClick={onTrain}
                disabled={loading}
                className="btn py-3 bg-[var(--primary)] text-white hover:opacity-90 font-bold rounded-xl shadow-lg hover:translate-y-[-1px] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {loading ? 'Training...' : '🚀 Train New Model'}
            </button>

            <button
                onClick={onEval}
                disabled={evalLoading}
                className="btn py-2 bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] hover:bg-[var(--surface)] font-medium rounded-xl transition-all"
            >
                {evalLoading ? '📂 Loading...' : '📂 Load Saved Model'}
            </button>
        </div>
    </div>
);

export default function MLTrainingView() {
    const [activeTab, setActiveTab] = useState('EMG');

    // --- SESSIONS ---
    const [availableSessions, setAvailableSessions] = useState([]);
    const [selectedSession, setSelectedSession] = useState(null);

    // Fetch sessions
    const fetchSessions = async () => {
        try {
            const sensor = activeTab;
            const res = await fetch(`/api/sessions/${sensor}`);
            if (res.ok) {
                const data = await res.json();
                if (data.tables) {
                    const formatted = data.tables.map(t => ({
                        table: t,
                        name: t.replace(`${sensor.toLowerCase()}_session_`, '')
                    }));
                    setAvailableSessions(formatted.reverse());
                } else if (Array.isArray(data)) {
                    setAvailableSessions(data);
                }
            }
        } catch (e) {
            console.error("Failed to list sessions:", e);
        }
    };

    useEffect(() => {
        fetchSessions();
        // Auto-load model when tab or session changes
        if (activeTab === 'EMG') evalEmg();
        else evalEog();
    }, [activeTab, selectedSession]);


>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
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

    // --- EOG STATE ---
    const [eogParams, setEogParams] = useState({
        n_estimators: 100,
        max_depth: 5,
        test_size: 0.2
    });
    const [eogResult, setEogResult] = useState(null);
    const [eogEvalResult, setEogEvalResult] = useState(null);
<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
    const [eogStatus, setEogStatus] = useState({ recording: false, current_label: 0, counts: {} });
    const eogStatusInterval = useRef(null);
=======
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx


    // --- HELPERS ---
    const handleEmgChange = (e) => {
        const { name, value } = e.target;
        setEmgParams(prev => ({ ...prev, [name]: name === 'test_size' ? parseFloat(value) : parseInt(value) }));
    };

    const handleEogChange = (e) => {
        const { name, value } = e.target;
        setEogParams(prev => ({ ...prev, [name]: name === 'test_size' ? parseFloat(value) : parseInt(value) }));
    };

<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
=======
    const getSourceName = (isTrain) => {
        const name = selectedSession
            ? (availableSessions.find(s => s.table === selectedSession)?.name || selectedSession)
            : 'All Available Data';
        return `${isTrain ? 'Trained' : 'Evaluated'} on: ${name}`;
    };

>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
    // --- API CALLS ---

    // EMG TRAIN
    const trainEmg = async () => {
        setLoading(true); setError(null); setEmgResult(null);
        try {
<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
            const res = await fetch('http://localhost:5000/api/train-emg-rf', {
                method: 'POST', body: JSON.stringify(emgParams), headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Training failed');
            setEmgResult(data);
=======
            const res = await fetch('/api/train-emg-rf', {
                method: 'POST',
                body: JSON.stringify({
                    ...emgParams,
                    table_name: selectedSession || undefined
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Training failed');
            setEmgResult({ ...data, source: getSourceName(true) });
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
        } catch (e) { setError(e.message); } finally { setLoading(false); }
    };

    // EMG EVAL
    const evalEmg = async () => {
        setEvalLoading(true); setError(null); setEmgEvalResult(null);
        try {
<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
            const res = await fetch('http://localhost:5000/api/model/evaluate', { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEmgEvalResult(data);
=======
            const res = await fetch('/api/model/evaluate', {
                method: 'POST',
                body: JSON.stringify({
                    table_name: selectedSession || undefined
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEmgEvalResult({ ...data, source: getSourceName(false) });
            if (data.hyperparameters) {
                setEmgParams(prev => ({ ...prev, ...data.hyperparameters }));
                if (data.hyperparameters.table_name && selectedSession === null) setSelectedSession(data.hyperparameters.table_name);
            }
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
        } catch (e) { setError(e.message); } finally { setEvalLoading(false); }
    };

    // EOG TRAIN
    const trainEog = async () => {
        setLoading(true); setError(null); setEogResult(null);
        try {
<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
            const res = await fetch('http://localhost:5000/api/train-eog-rf', {
                method: 'POST', body: JSON.stringify(eogParams), headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Training failed');
            setEogResult(data);
=======
            const res = await fetch('/api/train-eog-rf', {
                method: 'POST', body: JSON.stringify({
                    ...eogParams,
                    table_name: selectedSession || undefined
                }), headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Training failed');
            setEogResult({ ...data, source: getSourceName(true) });
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
        } catch (e) { setError(e.message); } finally { setLoading(false); }
    };

    // EOG EVAL
    const evalEog = async () => {
        setEvalLoading(true); setError(null); setEogEvalResult(null);
        try {
<<<<<<< HEAD:frontend/src/components/views/MLTrainingView.jsx
            const res = await fetch('http://localhost:5000/api/model/evaluate/eog', { method: 'POST' });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEogEvalResult(data);
        } catch (e) { setError(e.message); } finally { setEvalLoading(false); }
    };

    // EOG RECORDING
    const updateEogStatus = async () => {
        try {
            const res = await fetch('http://localhost:5000/api/eog/status');
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
            await fetch('http://localhost:5000/api/eog/start', {
                method: 'POST',
                body: JSON.stringify({ label, channel: selectedEogChannel }),
                headers: { 'Content-Type': 'application/json' }
            });
            updateEogStatus();
        } catch (e) { setError(e.message); }
    };

    const stopEogRec = async () => {
        try {
            await fetch('http://localhost:5000/api/eog/stop', { method: 'POST' });
            updateEogStatus();
        } catch (e) { setError(e.message); }
    };

    const deleteEogData = async () => {
        if (!window.confirm("Are you sure you want to DELETE ALL EOG data? This cannot be undone.")) return;
        try {
            const res = await fetch('http://localhost:5000/api/eog/data', { method: 'DELETE' });
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
                    {/* Controls */}
                    <div className="card mb-8 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
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

                    {/* Evals */}
                    <div className="card mb-8 flex justify-between items-center">
                        <div>
                            <h2 className="text-xl font-semibold text-[var(--text)]">Evaluate Saved Model</h2>
                            <p className="text-sm text-[var(--muted)]">Test `emg_rf.joblib` against full dataset.</p>
                        </div>
                        <button onClick={evalEmg} disabled={evalLoading} className="btn bg-[var(--surface)] text-[var(--text)] border border-[var(--border)]">
                            {evalLoading ? 'Evaluating...' : 'Run Full Evaluation'}
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
            {activeTab === 'EOG' && (
                <div>
                    {/* Live Prediction */}
                    <div className="card mb-8 border-l-4 border-l-purple-500">
                        <div className="flex justify-between items-center mb-4">
                            <h2 className="text-xl font-semibold text-[var(--text)]">Real-time Classification</h2>
                            <button
                                onClick={togglePrediction}
                                className={`btn ${isPredicting ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} min-w-[120px] shadow-lg`}
                            >
                                {isPredicting ? 'STOP LIVE' : 'START LIVE'}
                            </button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            {/* Current Prediction Display */}
                            <div className="bg-[var(--bg)] rounded-xl p-6 flex flex-col items-center justify-center min-h-[160px] border border-[var(--border)] relative overflow-hidden">
                                {isPredicting ? (
                                    <>
                                        {predictionHistory[0] ? (
                                            <>
                                                <div className="text-sm text-[var(--muted)] uppercase tracking-widest mb-2">Detected Event</div>
                                                <div className={`text-5xl font-black ${predictionHistory[0].label === 'DoubleBlink' ? 'text-purple-400' :
                                                    predictionHistory[0].label === 'SingleBlink' ? 'text-blue-400' : 'text-gray-500/50'
                                                    } animate-pulse-fast transition-all`}>
                                                    {predictionHistory[0].label === 'Rest' ? 'Resting...' : predictionHistory[0].label.replace(/Blink/, ' Blink')}
                                                </div>
                                                <div className="text-xs text-[var(--muted)] mt-2 font-mono">{predictionHistory[0].timeRel}</div>
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
                                {predictionHistory.length > 0 ? (
                                    <ul className="space-y-2">
                                        {predictionHistory.map((evt, i) => (
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
                                <Pacer />
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
                            <h2 className="text-xl font-semibold text-[var(--text)]">Evaluate Saved Model</h2>
                            <p className="text-sm text-[var(--muted)]">Test `eog_rf.joblib` against full dataset.</p>
                        </div>
                        <button onClick={evalEog} disabled={evalLoading} className="btn bg-[var(--surface)] text-[var(--text)] border border-[var(--border)]">
                            {evalLoading ? 'Evaluating...' : 'Run Full Evaluation'}
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
            )}
=======
            const res = await fetch('/api/model/evaluate/eog', {
                method: 'POST',
                body: JSON.stringify({ table_name: selectedSession || undefined }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEogEvalResult({ ...data, source: getSourceName(false) });
            if (data.hyperparameters) {
                setEogParams(prev => ({ ...prev, ...data.hyperparameters }));
                if (data.hyperparameters.table_name && selectedSession === null) setSelectedSession(data.hyperparameters.table_name);
            }
        } catch (e) { setError(e.message); } finally { setEvalLoading(false); }
    };


    return (
        <div className="font-sans w-full h-[calc(100vh-120px)] p-4 flex flex-col items-stretch overflow-hidden">
            {/* ERROR DISPLAY */}
            {error && <div className="w-full bg-red-900/20 border border-red-500 text-red-200 py-2 rounded mb-4 flex justify-between items-center shrink-0 text-sm px-4">
                <span><strong>Error:</strong> {error}</span>
                <button onClick={() => setError(null)} className="underline">Dismiss</button>
            </div>}

            {/* CONTENT scrollable container */}
            <div className="flex-1 w-full min-h-0 overflow-y-auto custom-scrollbar">
                <div className="h-full min-h-[800px] grid grid-cols-12 grid-rows-6 gap-4 pb-2">
                    {/* LEFT SIDEBAR CONTROLS (Span 3) - NOW CONTAINS ACCURACY & FEATURES TOO */}
                    <div className="col-span-12 lg:col-span-3 row-span-6 flex flex-col gap-4">
                        {/* 1. CONTROLS */}
                        <div className="shrink-0">
                            <ControlPanel
                                onTrain={activeTab === 'EMG' ? trainEmg : trainEog}
                                loading={loading}
                                onEval={activeTab === 'EMG' ? evalEmg : evalEog}
                                evalLoading={evalLoading}
                                sessions={availableSessions}
                                selectedSession={selectedSession}
                                onSessionSelect={setSelectedSession}
                                onRefreshSessions={fetchSessions}
                                activeTab={activeTab}
                                setActiveTab={setActiveTab}
                            />
                        </div>

                        {/* 2. ACCURACY */}
                        {((activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult))?.accuracy) !== undefined && (
                            <div className="shrink-0 h-48">
                                <AccuracyCard
                                    accuracy={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).accuracy}
                                    n_samples={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).n_samples}
                                    source={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).source}
                                />
                            </div>
                        )}

                        {/* 3. TOP FEATURES */}
                        {((activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult))?.feature_importances) && (
                            <div className="flex-1 flex-grow-4 min-h-0">
                                <FeatureImportanceCard importances={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).feature_importances} />
                            </div>
                        )}
                    </div>

                    {/* MAIN BENTO GRID (Span 9) */}
                    {(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)) ? (
                        <>
                            {/* TOP ROW: Hyperparams + Confusion Matrix */}

                            {/* BOTTOM ROW: Tree Viz */}
                            {/* Tree Viz (Span 9, Row 4) - Extended full width */}
                            {(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).tree_structure && (
                                <div className="col-span-12 md:col-span-9 row-span-4">
                                    <DecisionTreeCard structure={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).tree_structure} />
                                </div>
                            )}
                            {/* Hyperparameters (Span 3, Row 2) - Replaces old Accuracy spot */}
                            <div className="col-span-12 md:col-span-3 row-span-2">
                                <HyperparametersCard
                                    params={activeTab === 'EMG' ? emgParams : eogParams}
                                    onChange={activeTab === 'EMG' ? handleEmgChange : handleEogChange}
                                />
                            </div>

                            {/* Confusion Matrix (Span 6, Row 2) - Replaces old Features spot */}
                            <div className="col-span-12 md:col-span-6 row-span-2">
                                <ConfusionMatrixCard
                                    matrix={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).confusion_matrix}
                                    labels={activeTab === 'EMG' ? ['Rest', 'Rock', 'Paper', 'Scissors'] : ['DoubleBlink', 'SingleBlink', 'Rest']}
                                    n_samples={(activeTab === 'EMG' ? (emgResult || emgEvalResult) : (eogResult || eogEvalResult)).n_samples}
                                />
                            </div>
                        </>
                    ) : (
                        <div className="col-span-12 lg:col-span-9 row-span-6 card border-2 border-dashed border-[var(--border)] rounded-xl flex flex-col items-center justify-center text-[var(--muted)] bg-[var(--surface)]/50">
                            {/* Empty state showing Hyperparams Card as preview/setup if desired, or just empty */}
                            <div className="text-center">
                                <div className="text-6xl mb-6 opacity-20">📊</div>
                                <p className="text-lg font-medium">Model workspace empty</p>
                                <p className="text-sm opacity-70">Train a new model or load an existing one from the sidebar.</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
>>>>>>> rps-implement:src/web/frontend/src/components/views/MLTrainingView.jsx
        </div>
    );
}
