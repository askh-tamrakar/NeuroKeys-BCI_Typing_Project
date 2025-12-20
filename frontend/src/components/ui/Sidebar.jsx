import React from 'react'

export default function Sidebar({
    config,
    setConfig,
    isPaused,
    setIsPaused,
    onSave,
    className = ''
}) {

    const handleFilterChange = (type, field, value) => {
        setConfig(prev => ({
            ...prev,
            filters: {
                ...prev.filters,
                [type]: { ...prev.filters[type], [field]: value }
            }
        }))
    }

    const handleChannelMapping = (chKey, sensorType) => {
        setConfig(prev => ({
            ...prev,
            channel_mapping: {
                ...prev.channel_mapping,
                [chKey]: { ...prev.channel_mapping[chKey], sensor: sensorType }
            }
        }))
    }

    return (
        <aside className={`w-80 bg-surface border-r border-border h-full flex flex-col overflow-y-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none'] ${className}`}>
            <div className="p-6 border-b border-border">
                <h2 className="text-xl font-bold text-text mb-1">Controls</h2>
                <p className="text-xs text-muted">LSL Stream Configuration</p>
            </div>

            <div className="p-6 space-y-8">

                {/* Stream Control */}
                <section>
                    <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4">Stream Status</h3>
                    <button
                        onClick={() => setIsPaused(!isPaused)}
                        className={`w-full py-3 rounded-xl font-bold transition-all flex items-center justify-center gap-2 ${isPaused
                            ? 'bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20'
                            : 'bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20'
                            }`}
                    >
                        <span className={`w-2 h-2 rounded-full ${isPaused ? 'bg-accent' : 'bg-primary animate-pulse'}`}></span>
                        {isPaused ? 'RESUME STREAM' : 'PAUSE STREAM'}
                    </button>
                </section>

                {/* Time Window */}
                <section>
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-sm font-bold text-muted uppercase tracking-wider">Time Window</h3>
                        <span className="text-xs font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">{config.display?.timeWindowMs / 1000}s</span>
                    </div>
                    <input
                        type="range"
                        min="1000"
                        max="30000"
                        step="1000"
                        value={config.display?.timeWindowMs || 10000}
                        onChange={(e) => setConfig(prev => ({
                            ...prev,
                            display: { ...prev.display, timeWindowMs: Number(e.target.value) }
                        }))}
                        className="w-full accent-primary h-2 bg-bg rounded-lg appearance-none cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-muted font-mono mt-2">
                        <span>1s</span>
                        <span>30s</span>
                    </div>
                </section>

                {/* Channel Mapping */}
                <section>
                    <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4">Channel Mapping</h3>

                    {/* Channel 0 */}
                    <div className="mb-3">
                        <label className="text-xs font-medium text-text block mb-1">Graph 1</label>
                        <select
                            value={config.channel_mapping?.ch0?.sensor || 'EMG'}
                            onChange={(e) => handleChannelMapping('ch0', e.target.value)}
                            className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm outline-none focus:border-primary/50"
                        >
                            <option value="EMG">EMG</option>
                            <option value="EOG">EOG</option>
                            <option value="EEG">EEG</option>
                        </select>
                    </div>

                    {/* Channel 1 */}
                    <div className="mb-4">
                        <label className="text-xs font-medium text-text block mb-1">Graph 2</label>
                        <select
                            value={config.channel_mapping?.ch1?.sensor || 'EOG'}
                            onChange={(e) => handleChannelMapping('ch1', e.target.value)}
                            className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-sm outline-none focus:border-primary/50"
                        >
                            <option value="EMG">EMG</option>
                            <option value="EOG">EOG</option>
                            <option value="EEG">EEG</option>
                        </select>
                    </div>

                    <button
                        onClick={() => {
                            if (onSave) {
                                onSave();
                            } else {
                                console.warn("Sidebar: No onSave handler provided");
                            }
                        }}
                        className="w-full py-2 bg-primary text-primary-contrast rounded-lg font-bold text-sm shadow-glow hover:opacity-90 active:scale-95 transition-all"
                    >
                        🔄 Map Sensors
                    </button>
                </section>

                {/* Filters */}
                <section className="space-y-6">
                    <h3 className="text-sm font-bold text-muted uppercase tracking-wider">Signal Filters</h3>

                    {/* Channel 0 Filters */}
                    <div className="space-y-3 p-3 rounded-lg border border-border bg-surface/50">
                        <div className="flex items-center justify-between border-b border-border/50 pb-2 mb-2">
                            <h4 className="text-xs font-bold text-primary">Channel 0 ({(config.channel_mapping?.ch0?.sensor || 'EMG')})</h4>
                            <button onClick={() => onSave?.()} className="px-2 py-0.5 text-[10px] bg-primary text-primary-contrast rounded font-bold hover:opacity-90">APPLY</button>
                        </div>

                        {/* Noise Filter (Notch) */}
                        <div className="flex items-center justify-between">
                            <label className="text-xs text-text flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={config.filters?.ch0?.notch_enabled || false}
                                    onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch0: { ...prev.filters?.ch0, notch_enabled: e.target.checked } } }))}
                                    className="accent-primary"
                                />
                                Noise Filter
                            </label>
                            {config.filters?.ch0?.notch_enabled && (
                                <div className="flex items-center gap-1">
                                    <input
                                        type="number"
                                        className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-xs text-right"
                                        value={config.filters?.ch0?.notch_freq || 50}
                                        onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch0: { ...prev.filters?.ch0, notch_freq: Number(e.target.value) } } }))}
                                    />
                                    <span className="text-[10px] text-muted">Hz</span>
                                </div>
                            )}
                        </div>

                        {/* Bandpass */}
                        <div className="space-y-1">
                            <label className="text-xs text-text flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={config.filters?.ch0?.bandpass_enabled || false}
                                    onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch0: { ...prev.filters?.ch0, bandpass_enabled: e.target.checked } } }))}
                                    className="accent-primary"
                                />
                                Bandpass
                            </label>
                            {config.filters?.ch0?.bandpass_enabled && (
                                <div className="flex gap-2 items-center pl-5">
                                    <input
                                        type="number"
                                        className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-xs"
                                        value={config.filters?.ch0?.bandpass_low || 20}
                                        onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch0: { ...prev.filters?.ch0, bandpass_low: Number(e.target.value) } } }))}
                                    />
                                    <span className="text-[10px] text-muted">-</span>
                                    <input
                                        type="number"
                                        className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-xs"
                                        value={config.filters?.ch0?.bandpass_high || 450}
                                        onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch0: { ...prev.filters?.ch0, bandpass_high: Number(e.target.value) } } }))}
                                    />
                                    <span className="text-[10px] text-muted">Hz</span>
                                </div>
                            )}
                        </div>

                        {/* High Pass Cutoff */}
                        <div className="space-y-1 pt-2 border-t border-border/30">
                            <label className="text-[10px] text-muted block flex justify-between">
                                <span>High Pass Cutoff</span>
                                <span>{config.filters?.ch0?.cutoff || 70} Hz</span>
                            </label>
                            <input
                                type="range" min="1" max="100"
                                value={config.filters?.ch0?.cutoff || 70}
                                onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch0: { ...prev.filters?.ch0, cutoff: Number(e.target.value) } } }))}
                                className="w-full accent-primary h-1 bg-bg rounded-lg appearance-none cursor-pointer"
                            />
                        </div>
                    </div>

                    {/* Channel 1 Filters */}
                    <div className="space-y-3 p-3 rounded-lg border border-border bg-surface/50">
                        <div className="flex items-center justify-between border-b border-border/50 pb-2 mb-2">
                            <h4 className="text-xs font-bold text-emerald-500">Channel 1 ({(config.channel_mapping?.ch1?.sensor || 'EOG')})</h4>
                            <button onClick={() => onSave?.()} className="px-2 py-0.5 text-[10px] bg-emerald-500 text-white rounded font-bold hover:opacity-90">APPLY</button>
                        </div>

                        {/* Noise Filter (Notch) */}
                        <div className="flex items-center justify-between">
                            <label className="text-xs text-text flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={config.filters?.ch1?.notch_enabled || false}
                                    onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch1: { ...prev.filters?.ch1, notch_enabled: e.target.checked } } }))}
                                    className="accent-emerald-500"
                                />
                                Noise Filter
                            </label>
                            {config.filters?.ch1?.notch_enabled && (
                                <div className="flex items-center gap-1">
                                    <input
                                        type="number"
                                        className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-xs text-right"
                                        value={config.filters?.ch1?.notch_freq || 50}
                                        onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch1: { ...prev.filters?.ch1, notch_freq: Number(e.target.value) } } }))}
                                    />
                                    <span className="text-[10px] text-muted">Hz</span>
                                </div>
                            )}
                        </div>

                        {/* Bandpass */}
                        <div className="space-y-1">
                            <label className="text-xs text-text flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    checked={config.filters?.ch1?.bandpass_enabled || false}
                                    onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch1: { ...prev.filters?.ch1, bandpass_enabled: e.target.checked } } }))}
                                    className="accent-emerald-500"
                                />
                                Bandpass
                            </label>
                            {config.filters?.ch1?.bandpass_enabled && (
                                <div className="flex gap-2 items-center pl-5">
                                    <input
                                        type="number"
                                        className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-xs"
                                        value={config.filters?.ch1?.bandpass_low || 0.5}
                                        onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch1: { ...prev.filters?.ch1, bandpass_low: Number(e.target.value) } } }))}
                                    />
                                    <span className="text-[10px] text-muted">-</span>
                                    <input
                                        type="number"
                                        className="w-12 bg-bg border border-border rounded px-1 py-0.5 text-xs"
                                        value={config.filters?.ch1?.bandpass_high || 10}
                                        onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch1: { ...prev.filters?.ch1, bandpass_high: Number(e.target.value) } } }))}
                                    />
                                    <span className="text-[10px] text-muted">Hz</span>
                                </div>
                            )}
                        </div>

                        {/* High Pass Cutoff */}
                        <div className="space-y-1 pt-2 border-t border-border/30">
                            <label className="text-[10px] text-muted block flex justify-between">
                                <span>High Pass Cutoff</span>
                                <span>{config.filters?.ch1?.cutoff || 10} Hz</span>
                            </label>
                            <input
                                type="range" min="1" max="100"
                                value={config.filters?.ch1?.cutoff || 10}
                                onChange={(e) => setConfig(prev => ({ ...prev, filters: { ...prev.filters, ch1: { ...prev.filters?.ch1, cutoff: Number(e.target.value) } } }))}
                                className="w-full accent-emerald-500 h-1 bg-bg rounded-lg appearance-none cursor-pointer"
                            />
                        </div>
                    </div>
                </section>

                {/* Save Config Removed (Auto-save enabled) */}

            </div>
        </aside>
    )
}
