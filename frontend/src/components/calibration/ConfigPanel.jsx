import React, { useState } from 'react';

/**
 * ConfigPanel
 * Sidebar for viewing and editing sensor thresholds/parameters.
 */
export default function ConfigPanel({ config, sensor, onSave }) {
    const [localConfig, setLocalConfig] = useState(config || {});

    // Sync local state if prop changes (optional, but good for resets)
    React.useEffect(() => {
        setLocalConfig(config || {});
    }, [config]);

    const sensorFeatures = localConfig.features?.[sensor] || {};

    const handleFeatureChange = (path, value) => {
        // Deep clone to avoid mutation
        const updated = JSON.parse(JSON.stringify(localConfig));

        if (!updated.features) updated.features = {};
        if (!updated.features[sensor]) updated.features[sensor] = {};

        // Traverse to the parent of the target key
        let current = updated.features[sensor];
        for (let i = 0; i < path.length - 1; i++) {
            if (!current[path[i]]) current[path[i]] = {};
            current = current[path[i]];
        }

        // Update the value
        const lastKey = path[path.length - 1];

        // Handle numeric conversion if needed
        const numValue = parseFloat(value);
        current[lastKey] = isNaN(numValue) ? value : numValue;

        setLocalConfig(updated);
    };

    // Recursive helper to render config inputs
    const renderConfigNode = (node, path = []) => {
        if (typeof node === 'object' && node !== null && !Array.isArray(node)) {
            return (
                <div className="pl-3 border-l border-border space-y-3 mt-2">
                    {Object.entries(node).map(([key, value]) => (
                        <div key={key}>
                            {typeof value === 'object' && !Array.isArray(value) ? (
                                <div className="mb-1">
                                    <span className="text-[10px] text-muted uppercase font-bold tracking-wider">{key}</span>
                                    {renderConfigNode(value, [...path, key])}
                                </div>
                            ) : (
                                renderConfigNode(value, [...path, key])
                            )}
                        </div>
                    ))}
                </div>
            );
        }

        // It's a leaf value or an array (treated as leaf for now unless we want deep array editing)
        const label = path[path.length - 1];

        return (
            <div className="flex flex-col gap-1 mb-2">
                <span className="text-[10px] text-text font-mono">{label}</span>
                <div className="flex gap-2">
                    {Array.isArray(node) ? (
                        node.map((val, idx) => (
                            <input
                                key={idx}
                                type="number"
                                value={val}
                                onChange={(e) => {
                                    const newArray = [...node];
                                    newArray[idx] = e.target.value;
                                    handleFeatureChange(path, newArray);
                                }}
                                className="w-full bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none transition-colors focus:bg-primary/5"
                            />
                        ))
                    ) : (
                        <input
                            type="text" // Use text to allow typing decimals comfortably
                            value={node}
                            onChange={(e) => handleFeatureChange(path, e.target.value)}
                            className="w-full bg-bg border border-border rounded px-2 py-1 text-xs text-text focus:border-primary outline-none transition-colors focus:bg-primary/5"
                        />
                    )}
                </div>
            </div>
        );
    };

    return (
        <div className="flex flex-col h-full bg-surface border border-border rounded-xl overflow-hidden shadow-card animate-in fade-in duration-300">
            <div className="px-5 py-4 border-b border-border bg-bg/50 flex justify-between items-center ">
                <h3 className="font-bold text-text flex items-center gap-2 uppercase tracking-wider text-xs ">
                    <span className="w-2 h-4 bg-accent rounded-sm"></span>
                    {sensor} Configuration
                </h3>
                <span className="text-[10px] text-muted italic">
                    {Object.keys(sensorFeatures).length} params
                </span>
            </div>

            <div className="flex-grow min-h-0 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-border hover:scrollbar-thumb-primary/50 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none']">
                {Object.keys(sensorFeatures).length > 0 ? (
                    renderConfigNode(sensorFeatures)
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-muted space-y-2 opacity-60">
                        <span className="text-2xl">⚙️</span>
                        <span className="text-sm italic">No parameters available for {sensor}</span>
                    </div>
                )}
            </div>

            <div className="p-4 border-t border-border bg-bg/30 space-y-2">
                <button
                    onClick={() => onSave?.(localConfig)}
                    className="w-full py-2.5 bg-accent text-primary-contrast rounded-lg font-bold text-xs hover:opacity-90 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-glow uppercase tracking-wider"
                >
                    Save Configuration
                </button>
                <div className="flex justify-between items-center text-[8px] text-muted uppercase tracking-tighter">
                    <span>Target: feature_config.json</span>
                    <span>Unsaved changes will be lost</span>
                </div>
            </div>
        </div>
    );
}
