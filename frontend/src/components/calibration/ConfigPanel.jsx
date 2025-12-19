import React, { useState } from 'react';

/**
 * ConfigPanel
 * Sidebar for viewing and editing sensor thresholds/parameters.
 */
export default function ConfigPanel({ config, sensor, onSave }) {
    const [localConfig, setLocalConfig] = useState(config || {});
    const sensorFeatures = localConfig.features?.[sensor] || {};

    const handleFeatureChange = (key, subKey, value) => {
        const updated = { ...localConfig };
        if (!updated.features) updated.features = {};
        if (!updated.features[sensor]) updated.features[sensor] = {};

        // Handle array values (e.g., [min, max])
        if (Array.isArray(updated.features[sensor][key]?.[subKey])) {
            // Simplified: just update first or second element?
            // For now, let's assume flat key-value for simplicity in mock UI
        } else {
            updated.features[sensor][key] = value;
        }

        setLocalConfig(updated);
    };

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card">
            <div className="px-5 py-4 border-b border-border bg-bg/50">
                <h3 className="font-bold text-text flex items-center gap-2 uppercase tracking-wider text-xs">
                    <span className="w-2 h-4 bg-accent rounded-sm"></span>
                    {sensor} Configuration
                </h3>
            </div>

            <div className="flex-grow overflow-y-auto p-4 space-y-6">
                {Object.entries(sensorFeatures).map(([key, value]) => (
                    <div key={key} className="space-y-2">
                        <label className="text-[10px] font-bold text-muted uppercase tracking-widest block">
                            {key}
                        </label>
                        {typeof value === 'object' && !Array.isArray(value) ? (
                            <div className="pl-3 border-l border-border space-y-3">
                                {Object.entries(value).map(([subK, subV]) => (
                                    <div key={subK}>
                                        <div className="flex justify-between items-center mb-1">
                                            <span className="text-[10px] text-text font-mono">{subK}</span>
                                        </div>
                                        <div className="flex gap-2">
                                            {Array.isArray(subV) ? (
                                                <>
                                                    <input
                                                        type="number"
                                                        value={subV[0]}
                                                        className="w-1/2 bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none"
                                                        readOnly
                                                    />
                                                    <input
                                                        type="number"
                                                        value={subV[1]}
                                                        className="w-1/2 bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none"
                                                        readOnly
                                                    />
                                                </>
                                            ) : (
                                                <input
                                                    type="number"
                                                    value={subV}
                                                    className="w-full bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none"
                                                    readOnly
                                                />
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="bg-bg/50 p-2 rounded border border-border">
                                <span className="text-xs text-text font-mono">{JSON.stringify(value)}</span>
                            </div>
                        )}
                    </div>
                ))}

                {Object.keys(sensorFeatures).length === 0 && (
                    <div className="text-sm text-muted italic p-4 text-center border border-dashed border-border rounded-lg">
                        No parameters found for this sensor
                    </div>
                )}
            </div>

            <div className="p-4 border-t border-border bg-bg/30 space-y-2">
                <button
                    onClick={() => onSave?.(localConfig)}
                    className="w-full py-2 bg-accent text-primary-contrast rounded-lg font-bold text-xs hover:opacity-90 transition-all shadow-glow uppercase tracking-wider"
                >
                    Update Config
                </button>
                <p className="text-[8px] text-center text-muted uppercase tracking-tighter">
                    Changes will be saved to sensor_config.json
                </p>
            </div>
        </div>
    );
}
