import React from 'react';
import AnimatedList from '../ui/AnimatedList';
import { Trash2 } from 'lucide-react';

/**
 * WindowListPanel
 * Shows a list of labeled calibration windows with their status.
 */
export default function WindowListPanel({
    windows = [],
    onDelete,
    onHighlight,
    activeSensor,
    autoLimit = 30,
    onAutoLimitChange,
    autoCalibrate = false,
    onAutoCalibrateChange,
    onClearSaved,
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

    // Use autoLimit for progress target
    const targetCount = autoLimit || 30;
    const progress = Math.min(100, (stats.saved / targetCount) * 100);

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card animate-in fade-in duration-300">
            {/* Header with stats and controls */}
            <div className="px-5 py-4 border-b border-border bg-bg/50 flex flex-col gap-2">
                <div className="flex justify-between items-center">
                    <h3 className="font-bold text-text flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                        Calibration Windows
                    </h3>

                    {/* Auto-Calibration/Limit Toggle */}
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 bg-bg/30 px-2 py-1 rounded border border-border/50">
                            <span className="text-xs font-bold text-muted uppercase">Limit:</span>
                            <input
                                type="number"
                                className="w-8 bg-transparent text-xs font-mono text-center outline-none text-text"
                                value={autoLimit}
                                onChange={(e) => onAutoLimitChange?.(Number(e.target.value))}
                            />
                        </div>
                        <div className="h-4 w-[1px] bg-border mx-1"></div>
                        <span className={`text-xs font-bold uppercase ${autoCalibrate ? 'text-primary' : 'text-muted'}`}>Auto</span>
                        <button
                            onClick={() => onAutoCalibrateChange?.(!autoCalibrate)}
                            className={`w-8 h-4 rounded-full relative transition-colors ${autoCalibrate ? 'bg-primary' : 'bg-muted/30'}`}
                        >
                            <div className={`absolute top-0.5 bottom-0.5 w-3 rounded-full bg-white shadow transition-all ${autoCalibrate ? 'left-[calc(100%-14px)]' : 'left-0.5'}`} />
                        </button>
                    </div>
                </div>

                <div className="flex justify-between items-end">
                    <div className="flex gap-4 text-xs font-mono text-muted uppercase tracking-widest">
                        <span>Total: <span className="text-text">{stats.total}</span></span>
                        <span>Saved: <span className="text-emerald-400">{stats.saved}</span></span>
                    </div>
                    <div className="text-xs text-muted font-mono">{progress.toFixed(0)}%</div>
                </div>

                {/* Progress Bar (Only visible in Auto mode) */}
                {autoCalibrate && (
                    <div className="h-1 w-full bg-bg rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary transition-all duration-500 ease-out"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                )}
            </div>

            {/* Window list - scrollable */}
            <div className="flex-grow min-h-0 flex flex-col justify-center overflow-hidden relative pt-2">
                {windows.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-40 text-muted text-xl italic opacity-50 space-y-2">
                        <span className="text-2xl">📉</span>
                        <span>No windows collected yet</span>
                    </div>
                ) : (
                    <AnimatedList
                        items={windows.slice().reverse()}
                        className="h-full"
                        itemClassName="px-2 bg-transparent border-0"
                        onItemSelect={(win) => onHighlight?.(win)}
                        renderItem={(win, index, isSelected) => (
                            <div
                                className={`p-2 py-1 rounded-lg border transition-all cursor-pointer group hover:translate-x-1 ${win.status === 'saved' || win.status === 'correct'
                                    ? 'bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/20'
                                    : win.status === 'pending'
                                        ? 'bg-yellow-500/5 border-border hover:border-border'
                                        : 'bg-red-500/5 border-red-500/20 hover:border-red-500/20'
                                    }`}
                            >
                                <div className="flex justify-between items-center mb-2">
                                    <div className="flex flex-col">
                                        <span className="font-bold text-sm text-text uppercase">{win.label}</span>
                                        <span className="text-xs text-muted font-mono">
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
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>

                                {/* Status Indicator (Simplified) */}
                                <div className="flex items-center gap-1 mt-1">
                                    <span className={`w-1.5 h-1.5 rounded-full ${win.status === 'saved' ? 'bg-emerald-500' :
                                        win.status === 'pending' ? 'bg-yellow-500' : 'bg-gray-400'
                                        }`}></span>
                                    <span className={`text-xs uppercase ${win.status === 'pending' ? 'text-yellow-500' : 'text-muted'
                                        }`}>
                                        {win.status === 'saved' ? 'Saved' : win.status}
                                    </span>
                                </div>
                            </div>
                        )}
                    />
                )}
            </div>

            {/* Footer with Append Sample */}
            <div className="p-3 border-t border-border bg-bg/50">
                <button
                    onClick={onClearSaved}
                    disabled={autoCalibrate}
                    className={`w-full py-2 rounded-lg font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 ${autoCalibrate
                        ? 'bg-bg text-muted border border-border cursor-not-allowed opacity-50'
                        : 'bg-emerald-500 text-white hover:opacity-90 shadow-glow'
                        }`}
                >
                    Append Sample
                </button>
            </div>
        </div>
    );
}
