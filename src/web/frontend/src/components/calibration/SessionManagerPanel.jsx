import React, { useState, useEffect, useMemo, useRef } from 'react';
import AnimatedList from '../ui/AnimatedList';
import { Trash, ClipboardX, Trash2, FolderPlus, RefreshCw } from 'lucide-react';

export default function SessionManagerPanel({
    activeSensor,
    currentSessionName,
    onSessionChange,
    refreshTrigger = 0
}) {
    const SENSOR_LABEL_MAP = {
        'EMG': { 0: 'Rest', 1: 'Rock', 2: 'Paper', 3: 'Scissors' },
        'EOG': { 0: 'Rest', 1: 'SingleBlink', 2: 'DoubleBlink' },
        'EEG': { 0: 'Rest', 1: 'Concentration', 2: 'Relaxation' }
    };

    const getLabelName = (sensor, val) => {
        if (typeof val === 'string' && isNaN(Number(val))) return val;

        const map = SENSOR_LABEL_MAP[sensor] || {};
        const num = Number(val);
        return map[num] !== undefined ? map[num] : val;
    };

    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedSessionRows, setSelectedSessionRows] = useState([]);
    const [rowsLoading, setRowsLoading] = useState(false);
    const [newSessionInput, setNewSessionInput] = useState("");
    const lastSessionRef = useRef(null);

    const handleCreate = () => {
        const name = newSessionInput.trim();
        if (!name) return;

        // Optimistically add to list (sanitize to match backend roughly)
        // Backend uses: re.sub(r'[^a-zA-Z0-9]', '_', name)
        const safeName = name.replace(/[^a-zA-Z0-9]/g, '_');
        const fullName = `${activeSensor.toLowerCase()}_session_${safeName}`;

        if (!sessions.includes(fullName)) {
            setSessions(prev => [fullName, ...prev]);
        }

        onSessionChange(safeName);
        setNewSessionInput("");
    };

    // Calculate active session index for AnimatedList
    const activeSessionIndex = useMemo(() => {
        if (!sessions || sessions.length === 0) return -1;
        // Find exact match or partial if consistent
        const idx = sessions.findIndex(s => s === currentSessionName || s.includes(currentSessionName));
        return idx !== -1 ? idx : -1;
    }, [sessions, currentSessionName]);

    // Handler for AnimatedList selection
    const handleSessionSelect = (sessionName, index) => {
        // Extract clean name logic can be moved here if needed
        // For now just pass the raw name or parse it as before
        const parts = sessionName.split('_session_');
        const clean = parts.length > 1 ? parts[1] : sessionName;
        onSessionChange(clean);
    };

    const handleDeleteSession = async (sessionName, e) => {
        e.stopPropagation();

        try {
            const res = await fetch(`/api/sessions/${activeSensor}/${sessionName}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                // Remove from list immediately
                setSessions(prev => prev.filter(s => s !== sessionName));

                // If current, clear
                if (sessionName === currentSessionName || sessionName.includes(currentSessionName)) {
                    onSessionChange("Default");
                }
            } else {
                console.error("Failed to delete session");
            }
        } catch (err) {
            console.error("Error deleting session:", err);
        }
    };

    // Clear session rows but keep the session itself active (Emptying it)
    const handleClearSessionData = async (e) => {
        e.stopPropagation();
        if (!fullCurrentSessionName) return;

        try {
            await setLoading(true); // Reuse loading or new state
            // 1. Delete the session
            const res = await fetch(`/api/sessions/${activeSensor}/${fullCurrentSessionName}`, {
                method: 'DELETE'
            });

            if (res.ok) {
                setSelectedSessionRows([]);

                if (!sessions.find(s => s === fullCurrentSessionName)) {
                    setSessions(prev => [fullCurrentSessionName, ...prev]);
                }
            }
        } catch (err) {
            console.error("Error clearing session:", err);
        } finally {
            setLoading(false);
        }
    };

    // Fetch list of sessions
    const fetchSessions = async () => {
        setLoading(true);
        try {
            const res = await fetch(`/api/sessions/${activeSensor}`);
            const data = await res.json();
            if (data.tables) {
                setSessions(data.tables.reverse());
            }
        } catch (err) {
            console.error("Failed to fetch sessions:", err);
        } finally {
            setLoading(false);
        }
    };

    // Initial fetch of sessions list
    useEffect(() => {
        fetchSessions();
    }, [activeSensor]);

    // Helper to get full table name from the current short name or partial match
    const fullCurrentSessionName = useMemo(() => {
        if (!sessions || sessions.length === 0) return null;
        return sessions.find(s => s === currentSessionName || s.includes(currentSessionName)) || null;
    }, [sessions, currentSessionName]);

    // Fetch session details when selection changes
    useEffect(() => {
        const fetchSessionDetails = async () => {
            if (!fullCurrentSessionName) {
                setSelectedSessionRows([]);
                return;
            }

            if (lastSessionRef.current !== fullCurrentSessionName || selectedSessionRows.length === 0) {
                setRowsLoading(true);
            }

            lastSessionRef.current = fullCurrentSessionName;

            try {
                // Assuming GET returns the rows for the session table
                const res = await fetch(`/api/sessions/${activeSensor}/${fullCurrentSessionName}`);
                if (res.ok) {
                    const data = await res.json();
                    setSelectedSessionRows(Array.isArray(data) ? data : (data.rows || []));
                } else {
                    console.error("Failed to fetch session details");
                    setSelectedSessionRows([]);
                }
            } catch (err) {
                console.error("Error fetching session details:", err);
                setSelectedSessionRows([]);
            } finally {
                setRowsLoading(false);
            }
        };

        fetchSessionDetails();
    }, [activeSensor, fullCurrentSessionName, refreshTrigger]);

    const handleDeleteRow = async (rowId, e) => {
        e.stopPropagation();
        if (!fullCurrentSessionName) return;

        try {
            // Optimistic update
            const prevRows = [...selectedSessionRows];
            setSelectedSessionRows(prev => prev.filter(r => r.id !== rowId));

            const res = await fetch(`/api/sessions/${activeSensor}/${fullCurrentSessionName}/rows/${rowId}`, {
                method: 'DELETE'
            });

            if (!res.ok) {
                console.error("Failed to delete row");
                // Revert on failure
                setSelectedSessionRows(prevRows);
            }
        } catch (err) {
            console.error("Error deleting row:", err);
        }
    };

    return (
        <div className="flex h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card p-1 gap-1">

            {/* LEFT PANE: Selected Session Table View */}
            <div className="flex-grow flex flex-col min-w-0 bg-bg/50 rounded-lg border border-muted overflow-hidden relative">
                {/* Table Header / Title */}
                <div className="px-3 py-2 border-b border-muted bg-surface/50 flex justify-between items-center">
                    <span className="text-xs font-bold text-muted uppercase tracking-wider">
                        {currentSessionName ? currentSessionName.replace(`${activeSensor.toLowerCase()}_session_`, '') : 'Select a Session'}
                    </span>
                    <span className="text-xs font-mono text-muted">
                        {selectedSessionRows.length} samples
                    </span>
                </div>

                {/* Table Content */}
                <div className="flex-grow overflow-auto no-scrollbar relative">
                    {rowsLoading ? (
                        <div className="absolute inset-0 flex items-center justify-center text-muted text-xs animate-pulse">
                            Loading data...
                        </div>
                    ) : selectedSessionRows.length === 0 ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-muted text-xl opacity-50 gap-2">
                            <span className="text-6xl">📋</span>
                            <span >No data available</span>
                        </div>
                    ) : (
                        <table className="w-full text-left border-collapse">
                            <thead className="bg-surface/50 sticky top-0 z-10 backdrop-blur-sm">
                                <tr>
                                    <th className="px-3 py-1.5 text-xs font-bold text-primary uppercase border-b border-text w-12">S.No</th>
                                    <th className="px-3 py-1.5 text-xs font-bold text-primary uppercase border-b border-text w-24">Class</th>
                                    {/* Dynamic Feature Headers */}
                                    {selectedSessionRows.length > 0 && selectedSessionRows[0].features && !Array.isArray(selectedSessionRows[0].features) ? (
                                        Object.keys(selectedSessionRows[0].features).map(key => (
                                            <th key={key} className="px-3 py-1.5 text-xs font-bold text-primary uppercase border-b border-text">
                                                {key}
                                            </th>
                                        ))
                                    ) : (
                                        <th className="px-3 py-1.5 text-xs font-bold text-muted uppercase border-b border-border">Features</th>
                                    )}
                                    <th className="pr-1 py-1 text-xs text-left font-bold text-primary uppercase border-b border-text w-10">
                                        <button
                                            title="Clear Rows"
                                            onClick={handleClearSessionData}
                                            className="p-0.5 hover:bg-red-500/20 text-muted hover:text-red-500 rounded transition-colors"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </th>
                                </tr>
                            </thead>
                            <tbody className="text-xs font-mono">
                                {selectedSessionRows.map((row, idx) => (
                                    <tr key={idx} className="border-b border-border hover:bg-border transition-colors group">
                                        <td className="px-3 py-1.5 text-primary">{idx + 1}</td>
                                        {/* Assuming row has 'label' or 'class' and 'features' */}
                                        <td className="px-3 py-1.5 font-bold text-text">
                                            {getLabelName(activeSensor, row.label !== undefined ? row.label : (row.class !== undefined ? row.class : 'Unknown'))}
                                        </td>

                                        {/* Dynamic Feature Cells */}
                                        {row.features && !Array.isArray(row.features) ? (
                                            Object.keys(selectedSessionRows[0].features).map(key => (
                                                <td key={key} className="px-3 py-1.5 text-muted font-mono">
                                                    {(typeof row.features[key] === 'number') ? row.features[key].toFixed(2) : row.features[key]}
                                                </td>
                                            ))
                                        ) : (
                                            <td className="px-3 py-1.5 text-muted truncate max-w-[200px]" title={JSON.stringify(row.features)}>
                                                {Array.isArray(row.features)
                                                    ? row.features.map(f => f.toFixed(2)).join(', ')
                                                    : JSON.stringify(row.features)}
                                            </td>
                                        )}

                                        <td className="pr-1 py-1 text-xs text-left font-bold text-primary uppercase border-b border-border w-10  opacity-0 group-hover:opacity-100 transition-opacity ">
                                            <button
                                                title="Clear Rows"
                                                onClick={(e) => handleDeleteRow(row.id, e)}
                                                className="p-0.5 hover:bg-red-500/20 text-muted hover:text-red-500 rounded transition-colors"
                                            >
                                                <ClipboardX size={20} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}

                </div>
            </div>

            {/* RIGHT PANE: Session List */}
            <div className="w-1/3 min-w-[180px] max-w-[250px] flex flex-col bg-surface rounded-lg border border-muted overflow-hidden">
                <div className="p-3 border-b border-muted bg-bg/30">
                    <h3 className="font-bold text-base text-text uppercase tracking-wide flex items-center justify-between pr-2 mb-2">
                        <span>Sessions</span>
                        <button onClick={fetchSessions} className="text-muted hover:text-primary text-xs">
                            <RefreshCw size={24} />
                        </button>
                    </h3>

                    {/* Create New */}
                    <div className="flex gap-1">
                        <input
                            className="w-full bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none font-mono"
                            placeholder="New Session..."
                            value={newSessionInput}
                            onChange={e => setNewSessionInput(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleCreate()}
                        />
                        <button
                            onClick={handleCreate}
                            className="px-2 bg-primary text-white text-xs font-bold rounded hover:opacity-90"
                        >
                            <FolderPlus size={20} />
                        </button>
                    </div>
                </div>

                <div className="flex-grow overflow-hidden relative p-0 bg-surface/30">
                    {sessions.length === 0 ? (
                        <div className="text-center text-muted text-base italic py-4">No saved sessions</div>
                    ) : (
                        <AnimatedList
                            items={sessions}
                            selectedIndex={activeSessionIndex}
                            onItemSelect={handleSessionSelect}
                            className="h-full"
                            itemClassName="text-xs font-mono py-1 px-2 mb-0.5"
                            renderItem={(sessionName, index, isSelected) => (
                                <div className={`flex justify-between items-center pr-2 py-0.5 rounded-md cursor-pointer transition-all ${isSelected
                                    ? 'bg-primary/10 border border-primary/20 text-primary'
                                    : 'hover:bg-white/5 border border-transparent text-muted hover:text-text'
                                    }`}>
                                    <span className={`text-base truncate ${isSelected ? 'font-bold' : ''}`}>
                                        {sessionName.replace(`${activeSensor.toLowerCase()}_session_`, '')}
                                    </span>
                                    <button
                                        onClick={(e) => handleDeleteSession(sessionName, e)}
                                        className={`p-0.5 rounded hover:bg-red-500/10 hover:text-red-400 transition-all ${isSelected ? 'text-primary/50' : 'text-border group-hover:text-muted'}`}
                                        title="Delete Session"
                                    >
                                        <Trash size={22} />
                                    </button>
                                </div>
                            )}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}
