import React from 'react';

/**
 * WindowListPanel
 * Shows a list of labeled calibration windows with their status.
 */
export default function WindowListPanel({
    windows = [],
    onDelete,
    onMarkMissed,
    onHighlight,
    activeSensor,
    onCalibrate,
    calibrating = false,
    calibrationResult = null,
    autoCalibrateSamples = 20,
    onAutoCalibrateSamplesChange,
    running = false,
    windowProgress = {}
}) {
    const stats = {
        total: windows.length,
        correct: windows.filter(w => w.status === 'correct').length,
        missed: windows.filter(w => w.status === 'incorrect').length,
    };

    // Recommended samples based on sensor
    const recommendedSamples = {
        'EOG': 20,
        'EMG': 30,
        'EEG': 25
    }[activeSensor] || 20;

    // Calculate progress toward auto-calibration
    const progress = Math.min(100, (stats.total / recommendedSamples) * 100);
    const readyToCalibrate = stats.total >= 3 && windows.some(w => w.features);

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card animate-in fade-in duration-300">
            {/* Header with stats */}
            <div className="px-5 py-4 border-b border-border bg-bg/50 flex flex-col gap-2">
                <h3 className="font-bold text-text flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                    Calibration Windows
                </h3>
                <div className="flex gap-4 text-[10px] font-mono text-muted uppercase tracking-widest">
                    <span>Total: <span className="text-text">{stats.total}</span></span>
                    <span>Correct: <span className="text-emerald-400">{stats.correct}</span></span>
                    <span>Missed: <span className="text-red-400">{stats.missed}</span></span>
                </div>
            </div>

            {/* Window list - scrollable */}
            <div className="flex-grow min-h-0 overflow-y-auto p-2 space-y-2 scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-primary/50 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
                {windows.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-40 text-muted text-sm italic opacity-50 space-y-2">
                        <span className="text-2xl">📉</span>
                        <span>No windows collected yet</span>
                    </div>
                ) : (
                    windows.slice().reverse().map((win) => ( // Show newest first
                        <div
                            key={win.id}
                            className={`p-3 rounded-lg border transition-all cursor-pointer group hover:translate-x-1 ${win.status === 'correct'
                                ? 'bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/40'
                                : win.status === 'incorrect'
                                    ? 'bg-red-500/5 border-red-500/20 hover:border-red-500/40'
                                    : 'bg-bg border-border hover:border-primary/50'
                                }`}
                            onClick={() => onHighlight?.(win)}
                        >
                            <div className="flex justify-between items-start mb-2">
                                <div className="flex flex-col">
                                    <span className="font-bold text-sm text-text uppercase">{win.label}</span>
                                    <span className="text-[10px] text-muted font-mono">
                                        {(win.endTime - win.startTime).toFixed(0)}ms duration
                                    </span>
                                </div>
                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={(e) => { e.stopPropagation(); onMarkMissed?.(win.id); }}
                                        className="p-1 hover:bg-red-500/10 rounded text-red-400 text-xs transition-colors"
                                        title="Flag as missed signal"
                                    >
                                        🚩
                                    </button>
                                    <button
                                        onClick={(e) => { e.stopPropagation(); onDelete?.(win.id); }}
                                        className="p-1 hover:bg-red-500/10 rounded text-red-400 text-xs transition-colors"
                                        title="Delete window"
                                    >
                                        🗑️
                                    </button>
                                </div>
                            </div>

                            <div className="flex items-center justify-between mt-2 pt-2 border-t border-border/30">
                                <div className="flex items-center gap-2">
                                    <span className={`w-1.5 h-1.5 rounded-full ${win.status === 'correct' ? 'bg-emerald-500' :
                                        win.status === 'incorrect' ? 'bg-red-500' : 'bg-gray-400'
                                        }`}></span>
                                    <span className="text-[10px] text-muted uppercase font-bold">
                                        Prediction: <span className={win.predictedLabel === win.label ? 'text-emerald-400' : 'text-red-400'}>
                                            {win.predictedLabel || 'None'}
                                        </span>
                                    </span>
                                </div>

                                <div className="text-[11px] font-mono">
                                    {(() => {
                                        const wp = windowProgress?.[win.id];
                                        if (!wp) return null;
                                        if (wp.status === 'saving') return <span className="text-yellow-400 animate-pulse">Saving…</span>;
                                        if (wp.status === 'saved') return <span className="text-emerald-400">✓</span>;
                                        if (wp.status === 'error') return <span className="text-red-400">Error</span>;
                                        return null;
                                    })()}
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Calibration Controls moved to parent */}
        </div>
    );
}
