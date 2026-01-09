import Tree from 'react-d3-tree';
import { useState, useEffect } from 'react';

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
const AccuracyCard = ({ accuracy, n_samples }) => (
    <div className="card h-full flex flex-col justify-center items-center p-6 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm hover:shadow-md transition-shadow">
        <h3 className="text-xl font-bold text-[var(--muted)] uppercase tracking-widest mb-2">Model Accuracy</h3>
        {accuracy !== null && accuracy !== undefined ? (
            <>
                <div className="text-5xl font-black text-[var(--primary)] mb-2">{(accuracy * 100).toFixed(1)}%</div>
                <p className="text-base text-[var(--text)] opacity-70">on {n_samples} test samples</p>
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

const ConfusionMatrixCard = ({ matrix, labels }) => (
    <div className="card h-full flex flex-col p-4 bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-sm">
        <div className="flex justify-between items-center border-b border-[var(--border)] pb-2">
            <h3 className="text-sm font-bold text-[var(--muted)] uppercase tracking-widest">Confusion Matrix</h3>
            <span className="text-[10px] text-[var(--muted)] bg-[var(--bg)] px-2 py-0.5 rounded border border-[var(--border)]">Row: Actual | Col: Pred</span>
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
        </div>
    );
};

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
            setEmgResult(data);
        } catch (e) { setError(e.message); } finally { setLoading(false); }
    };

    // EMG EVAL
    const evalEmg = async () => {
        setEvalLoading(true); setError(null); setEmgEvalResult(null);
        try {
            const res = await fetch('/api/model/evaluate', {
                method: 'POST',
                body: JSON.stringify({
                    table_name: selectedSession || undefined
                }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEmgEvalResult(data);
        } catch (e) { setError(e.message); } finally { setEvalLoading(false); }
    };

    // EOG TRAIN
    const trainEog = async () => {
        setLoading(true); setError(null); setEogResult(null);
        try {
            const res = await fetch('/api/train-eog-rf', {
                method: 'POST', body: JSON.stringify({
                    ...eogParams,
                    table_name: selectedSession || undefined
                }), headers: { 'Content-Type': 'application/json' }
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
            const res = await fetch('/api/model/evaluate/eog', {
                method: 'POST',
                body: JSON.stringify({ table_name: selectedSession || undefined }),
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Eval failed');
            setEogEvalResult(data);
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
        </div>
    );
}
