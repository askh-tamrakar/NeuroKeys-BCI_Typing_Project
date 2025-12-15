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
                        <label className="text-xs font-medium text-text block mb-1">Graph 1 (Channel 0)</label>
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
                        <label className="text-xs font-medium text-text block mb-1">Graph 2 (Channel 1)</label>
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
                <section>
                    <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4">Signal Filters</h3>
                    <div className="space-y-3">
                        {/* Notch */}
                        <div className="bg-bg/50 p-3 rounded-lg border border-border">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-text">Notch Filter</span>
                                <input
                                    type="checkbox"
                                    checked={config.filters?.notch?.enabled || false}
                                    onChange={(e) => handleFilterChange('notch', 'enabled', e.target.checked)}
                                    className="accent-primary"
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="number"
                                    value={config.filters?.notch?.freq || 50}
                                    onChange={(e) => handleFilterChange('notch', 'freq', Number(e.target.value))}
                                    className="w-16 bg-surface border border-border rounded px-2 py-1 text-xs text-center"
                                />
                                <span className="text-xs text-muted">Hz</span>
                            </div>
                        </div>

                        {/* Bandpass */}
                        <div className="bg-bg/50 p-3 rounded-lg border border-border">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium text-text">Bandpass</span>
                                <input
                                    type="checkbox"
                                    checked={config.filters?.bandpass?.enabled || false}
                                    onChange={(e) => handleFilterChange('bandpass', 'enabled', e.target.checked)}
                                    className="accent-primary"
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="number"
                                    value={config.filters?.bandpass?.low || 0.5}
                                    onChange={(e) => handleFilterChange('bandpass', 'low', Number(e.target.value))}
                                    className="w-14 bg-surface border border-border rounded px-2 py-1 text-xs text-center"
                                />
                                <span className="text-xs text-muted">-</span>
                                <input
                                    type="number"
                                    value={config.filters?.bandpass?.high || 45}
                                    onChange={(e) => handleFilterChange('bandpass', 'high', Number(e.target.value))}
                                    className="w-14 bg-surface border border-border rounded px-2 py-1 text-xs text-center"
                                />
                                <span className="text-xs text-muted">Hz</span>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Save Config Removed (Auto-save enabled) */}

            </div>
        </aside>
    )
}
