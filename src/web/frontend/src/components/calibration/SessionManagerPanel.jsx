import React, { useState, useEffect, useMemo } from 'react';
import AnimatedList from '../ui/AnimatedList';

export default function SessionManagerPanel({
    activeSensor,
    currentSessionName,
    onSessionChange
}) {
    const [sessions, setSessions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [newSessionInput, setNewSessionInput] = useState("");

    const fetchSessions = async () => {
        setLoading(true);
        try {
            const res = await fetch(`/api/sessions/${activeSensor}`);
            const data = await res.json();
            if (data.tables) {
                // Remove prefix if standard naming used, or just show full table name?
                // db_manager returns full table names e.g. "emg_session_run1"
                // User input "run1" -> becomes "emg_session_run1".
                // We should probably display the clean name if possible, or just the table name.
                // Let's show full table name for clarity.
                setSessions(data.tables.reverse());
            }
        } catch (err) {
            console.error("Failed to fetch sessions:", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSessions();
    }, [activeSensor]);

    const handleCreate = () => {
        if (!newSessionInput.trim()) return;
        onSessionChange(newSessionInput.trim());
        setNewSessionInput("");
        // Typically the table isn't created until we save data, 
        // but we can add it to the list visually or just let the user know 'Pending'.
        // Actually, we should just set the current session name.
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

    const isCurrent = (name) => {
        // Simple check: does the current session name appear in the table name?
        // Or exact match if user typed it?
        // Let's just match exact string for now.
        return name === currentSessionName || name.includes(currentSessionName);
    };

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card">
            <div className="p-4 border-b border-border bg-bg/50">
                <h3 className="font-bold text-text uppercase tracking-wide flex items-center justify-between">
                    <span>Sessions</span>
                    <button onClick={fetchSessions} className="text-muted hover:text-primary text-xs">↻</button>
                </h3>

                {/* Create New */}
                <div className="mt-3 flex gap-2">
                    <input
                        className="flex-grow bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none"
                        placeholder="New Session Name..."
                        value={newSessionInput}
                        onChange={e => setNewSessionInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleCreate()}
                    />
                    <button
                        onClick={handleCreate}
                        className="px-3 py-1 bg-primary text-white text-xs font-bold rounded hover:opacity-90"
                    >
                        +
                    </button>
                </div>

                <div className="mt-2 text-[10px] text-muted font-mono">
                    Active: <span className="text-emerald-400 font-bold">{currentSessionName}</span>
                </div>
            </div>

            <div className="flex-grow overflow-hidden relative p-0">
                {sessions.length === 0 ? (
                    <div className="text-center text-muted text-xs italic py-4">No saved sessions found</div>
                ) : (
                    <AnimatedList
                        items={sessions}
                        selectedIndex={activeSessionIndex}
                        onItemSelect={handleSessionSelect}
                        className="h-full"
                        itemClassName="text-xs font-mono py-1"
                    />
                )}
            </div>
        </div>
    );
}
