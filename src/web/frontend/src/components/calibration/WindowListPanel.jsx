export default function WindowListPanel({
    windows = [], // Fallback if old prop used
    bufferWindows = [], // Red / History (Top)
    readyWindows = [],  // Green / Pending (Bottom)
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
    // If separate lists not provided, fall back to filtering 'windows' (though CalibrationView should pass them)
    // This maintains backward compatibility if needed, but we assume new usage.
    const effectiveBuffer = bufferWindows.length > 0 ? bufferWindows : windows.filter(w => w.status === 'saved' || w.status === 'correct');
    const effectiveReady = readyWindows.length > 0 ? readyWindows : windows.filter(w => w.status === 'pending');

    const stats = {
        total: effectiveBuffer.length + effectiveReady.length,
        saved: effectiveBuffer.length,
        pending: effectiveReady.length
    };

    // Helper for sparkline
    const Sparkline = ({ data, color = '#10b981' }) => {
        if (!data || data.length < 2) return null;
        const width = 100;
        const height = 30;
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;

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

    const targetCount = autoLimit || 30;
    // Progress based on READY items filling the batch? Or SAVED items?
    // "When readyToAppend reaches limits".
    // So progress bar should reflect READY count vs Limit?
    // Or Buffer count? Use Ready count to show "Next Append".
    const progress = Math.min(100, (effectiveReady.length / targetCount) * 100);

    const renderWindowItem = (win, isBuffer) => (
        <div
            key={win.id}
            onClick={() => onHighlight?.(win)}
            className={`p-2 py-1 rounded-lg border transition-all cursor-pointer group hover:translate-x-1 mb-1 ${isBuffer
                    ? 'bg-red-500/5 border-red-500/10 hover:border-red-500/30'
                    : 'bg-emerald-500/5 border-emerald-500/20 hover:border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.1)]'
                }`}
        >
            <div className="flex justify-between items-center mb-1">
                <div className="flex flex-col">
                    <span className="font-bold text-sm text-text uppercase">{win.label}</span>
                    <span className="text-[10px] text-muted font-mono">
                        {(win.endTime - win.startTime).toFixed(0)}fs
                    </span>
                </div>
                <div className="flex gap-1 opacity-100">
                    <div className="w-20 h-6 mr-2">
                        <Sparkline data={win.samples} color={isBuffer ? '#ef4444' : '#10b981'} />
                    </div>
                    <button
                        onClick={(e) => { e.stopPropagation(); onDelete?.(win.id); }}
                        className="p-1 hover:bg-red-500/10 rounded text-red-400 text-xs transition-colors"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>
            </div>
            {/* Status Footer */}
            <div className="flex items-center gap-1">
                <div className={`w-1.5 h-1.5 rounded-full ${isBuffer ? 'bg-red-500' : 'bg-emerald-500 animate-pulse'}`}></div>
                <span className={`text-[10px] uppercase font-bold ${isBuffer ? 'text-red-500/70' : 'text-emerald-500'}`}>
                    {isBuffer ? 'Saved (Buffer)' : 'Pending (Ready)'}
                </span>
            </div>
        </div>
    );

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card">
            {/* Header */}
            <div className="px-5 py-4 border-b border-border bg-bg/50 flex flex-col gap-2 shrink-0">
                <div className="flex justify-between items-center">
                    <h3 className="font-bold text-text flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                        Windows
                    </h3>
                    {/* Auto Controls */}
                    <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 bg-bg/30 px-2 py-1 rounded border border-border/50">
                            <span className="text-xs font-bold text-muted uppercase">Batch:</span>
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

                <div className="flex justify-between items-end text-xs font-mono text-muted uppercase tracking-widest">
                    <span>Buffer: <span className="text-red-400">{stats.saved}</span></span>
                    <span>Ready: <span className="text-emerald-400">{stats.pending}</span></span>
                </div>

                {/* Progress Bar (Visible in Both modes effectively, showing Batch status) */}
                <div className="h-1 w-full bg-bg rounded-full overflow-hidden mt-1">
                    <div
                        className={`h-full transition-all duration-300 ${autoCalibrate ? 'bg-primary' : 'bg-emerald-500'}`}
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {/* Split List View */}
            <div className="flex-grow min-h-0 flex flex-col relative">

                {/* TOP: Buffer (Red) */}
                {/* "Buffer Windows (History) - Contains Red items" */}
                {/* "standard log view... Buffer (Oldest) is Top." */}
                {/* So start of list = Oldest. End of list = Newest. */}
                {/* If we render standard <div> list, first child is Top. */}
                {/* So we map bufferWindows directly (index 0 is Oldest). */}

                <div className="flex-1 min-h-0 overflow-y-auto p-2 border-b border-border/50 bg-red-500/5 custom-scrollbar">
                    <div className="text-[10px] font-bold text-red-500/50 uppercase mb-2 sticky top-0 bg-surface/95 backdrop-blur z-10 p-1 border-b border-red-500/10">
                        Buffer (History)
                    </div>
                    {effectiveBuffer.length === 0 && <div className="text-center text-xs text-muted/50 py-4 italic">Empty Buffer</div>}
                    {effectiveBuffer.map(w => renderWindowItem(w, true))}
                </div>

                {/* BOTTOM: Ready (Green) */}
                {/* "Ready to Append (Bottom)" */}
                <div className="flex-1 min-h-0 overflow-y-auto p-2 bg-emerald-500/5 custom-scrollbar">
                    <div className="text-[10px] font-bold text-emerald-500/50 uppercase mb-2 sticky top-0 bg-surface/95 backdrop-blur z-10 p-1 border-b border-emerald-500/10">
                        Ready ({effectiveReady.length})
                    </div>
                    {effectiveReady.length === 0 && <div className="text-center text-xs text-muted/50 py-4 italic">No Pending Samples</div>}
                    {effectiveReady.map(w => renderWindowItem(w, false))}
                </div>
            </div>

            {/* Footer with Append Sample */}
            <div className="p-3 border-t border-border bg-bg/50 shrink-0">
                <button
                    onClick={onClearSaved}
                    disabled={effectiveReady.length === 0 && !autoCalibrate} // Allow click if manual pending exist
                    className={`w-full py-2 rounded-lg font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2 ${(effectiveReady.length === 0 && !autoCalibrate)
                            ? 'bg-bg text-muted border border-border cursor-not-allowed opacity-50'
                            : 'bg-emerald-500 text-white hover:opacity-90 shadow-glow hover:scale-[1.02]'
                        }`}
                >
                    {autoCalibrate ? 'Auto-Appending...' : `Append ${effectiveReady.length} Sample${effectiveReady.length !== 1 ? 's' : ''}`}
                </button>
            </div>
        </div>
    );
}
