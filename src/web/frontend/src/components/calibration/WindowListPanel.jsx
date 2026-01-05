import React from 'react';
import AnimatedList from '../ui/AnimatedList';

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
        saved: windows.filter(w => w.status === 'saved' || w.status === 'correct').length,
    };

    // Helper for sparkline
    const Sparkline = ({ data, color = '#10b981' }) => {
        if (!data || data.length < 2) return null;
        const width = 100;
        const height = 30;
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;

        // Downsample for performance if needed
        const step = Math.ceil(data.length / 50);
        const points = data.filter((_, i) => i % step === 0).map((v, i, arr) => {
            const x = (i / (arr.length - 1)) * width;
            const y = height - ((v - min) / range) * height;
            return `${x},${y}`;
        }).join(' ');

        return (
            <svg width={width} height={height} className="overflow-visible">
                <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
            </svg>
        );
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
                    <span>Saved: <span className="text-emerald-400">{stats.saved}</span></span>
                </div>
            </div>

            {/* Window list - scrollable */}
            <div className="flex-grow min-h-0 overflow-hidden relative p-0">
                {windows.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-40 text-muted text-sm italic opacity-50 space-y-2">
                        <span className="text-2xl">📉</span>
                        <span>No windows collected yet</span>
                    </div>
                ) : (
                    <AnimatedList
                        items={windows.slice().reverse()}
                        className="h-full"
                        itemClassName="p-0 bg-transparent border-0 mb-2"
                        onItemSelect={(win) => onHighlight?.(win)}
                        renderItem={(win, index, isSelected) => (
                            <div
                                className={`p-3 rounded-lg border transition-all cursor-pointer group hover:translate-x-1 ${win.status === 'saved' || win.status === 'correct'
                                    ? 'bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/40'
                                    : win.status === 'pending'
                                        ? 'bg-yellow-500/5 border-yellow-500/20 hover:border-yellow-500/40'
                                        : 'bg-red-500/5 border-red-500/20 hover:border-red-500/40'
                                    }`}
                            >
                                <div className="flex justify-between items-center mb-2">
                                    <div className="flex flex-col">
                                        <span className="font-bold text-sm text-text uppercase">{win.label}</span>
                                        <span className="text-[10px] text-muted font-mono">
                                            {(win.endTime - win.startTime).toFixed(0)}ms
                                        </span>
                                    </div>
                                    <div className="flex gap-1 opacity-100">
                                        {/* Graph */}
                                        <div className="w-24 h-8 mr-2">
                                            <Sparkline data={win.samples} color={win.status === 'pending' ? '#eab308' : (win.status === 'saved' ? '#10b981' : '#6b7280')} />
                                        </div>

                                        <button
                                            onClick={(e) => { e.stopPropagation(); onDelete?.(win.id); }}
                                            className="p-1 hover:bg-red-500/10 rounded text-red-400 text-xs transition-colors"
                                            title="Delete window"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                </div>

                                {/* Status Indicator (Simplified) */}
                                <div className="flex items-center gap-1 mt-1">
                                    <span className={`w-1.5 h-1.5 rounded-full ${win.status === 'saved' ? 'bg-emerald-500' :
                                        win.status === 'pending' ? 'bg-yellow-500' : 'bg-gray-400'
                                        }`}></span>
                                    <span className={`text-[10px] uppercase ${win.status === 'pending' ? 'text-yellow-500' : 'text-muted'
                                        }`}>
                                        {win.status === 'saved' ? 'Saved' : win.status}
                                    </span>
                                </div>
                            </div>
                        )}
                    />
                )}
            </div>

            {/* Calibration Controls moved to parent */}
        </div>
    );
}
