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
    activeSensor
}) {
    const stats = {
        total: windows.length,
        correct: windows.filter(w => w.status === 'correct').length,
        missed: windows.filter(w => w.isMissedActual).length,
    };

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card">
            <div className="px-5 py-4 border-b border-border bg-bg/50 flex flex-col gap-1">
                <h3 className="font-bold text-text flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                    Calibration Windows
                </h3>
                <div className="flex gap-4 text-[10px] font-mono text-muted uppercase tracking-widest mt-1">
                    <span>Total: <span className="text-text">{stats.total}</span></span>
                    <span>Correct: <span className="text-emerald-400">{stats.correct}</span></span>
                    <span>Missed: <span className="text-red-400">{stats.missed}</span></span>
                </div>
            </div>

            <div className="flex-grow overflow-y-auto p-2 space-y-2">
                {windows.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted text-sm italic opacity-50">
                        No windows collected yet
                    </div>
                ) : (
                    windows.map((win) => (
                        <div
                            key={win.id}
                            className={`p-3 rounded-lg border transition-all cursor-pointer group ${win.isMissedActual
                                    ? 'bg-red-500/5 border-red-500/20 hover:border-red-500/40'
                                    : win.status === 'correct'
                                        ? 'bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/40'
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
                                        title="Mark as missed actual signal"
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
                                    <span className={`w-1.5 h-1.5 rounded-full ${win.isMissedActual ? 'bg-red-500' : (win.status === 'correct' ? 'bg-emerald-500' : 'bg-gray-400')
                                        }`}></span>
                                    <span className="text-[10px] text-muted uppercase font-bold">
                                        Prediction: <span className={win.predictedLabel === win.label ? 'text-emerald-400' : 'text-red-400'}>
                                            {win.predictedLabel || 'None'}
                                        </span>
                                    </span>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            <div className="p-4 border-t border-border bg-bg/30">
                <button
                    className="w-full py-2 bg-primary text-primary-contrast rounded-lg font-bold text-xs hover:opacity-90 transition-all shadow-glow uppercase tracking-wider"
                    disabled={windows.length === 0}
                >
                    Run Calibration Logic
                </button>
            </div>
        </div>
    );
}
