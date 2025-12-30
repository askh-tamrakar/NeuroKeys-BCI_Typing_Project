import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, Minus, Plus } from 'lucide-react';
import ElectricBorder from './ElectricBorder';
import ElasticSlider from './ElasticSlider';
import CustomSelect from './CustomSelect';
import { soundHandler } from '../../handlers/SoundHandler';
export default function Sidebar({
    config,
    setConfig,
    isPaused,
    setIsPaused,
    onSave,
    className = ''
}) {
    // Safety check to prevent crash if config is not yet loaded
    if (!config) return null;
    const handleSensorFilterChange = (sensorType, field, value) => {
        setConfig(prev => ({
            ...prev,
            filters: {
                ...prev.filters,
                [sensorType]: {
                    ...prev.filters?.[sensorType],
                    [field]: value
                }
            }
        }))
    }

    const handleChannelMapping = (chKey, sensorType) => {
        setConfig(prev => ({
            ...prev,
            channel_mapping: {
                ...prev.channel_mapping,
                [chKey]: {
                    ...prev.channel_mapping?.[chKey],
                    sensor: sensorType
                }
            }
        }))
    }

    /*
    * Get the sensor type for a given channel
    * E.g., getSensorTypeForChannel('ch0') returns 'EMG'
    */
    const getSensorTypeForChannel = (chKey) => {
        return config.channel_mapping?.[chKey]?.sensor || 'EMG'
    }

    /*
     * Get filter config for a sensor type
     * E.g., getFilterConfig('EMG') returns the EMG filter settings
     */
    const getFilterConfig = (sensorType) => {
        return config.filters?.[sensorType] || {}
    }

    const handleChannelToggle = (chKey, enabled) => {
        // Calculate new config based on current prop to avoid stale state issues
        const newConfig = {
            ...config,
            channel_mapping: {
                ...config.channel_mapping,
                [chKey]: {
                    ...config.channel_mapping?.[chKey],
                    enabled: enabled
                }
            }
        }

        setConfig(newConfig)

        // Auto-save the change immediately
        if (onSave) {
            onSave(newConfig)
        }
    }

    return (
        <aside className={`w-80 bg-surface border-r border-border h-full flex flex-col overflow-y-auto overflow-x-hidden [&::-webkit-scrollbar]:hidden [-ms-overflow-style:'none'] [scrollbar-width:'none'] ${className}`}>
            <div className="p-6 border-b border-border">
                <h2 className="text-3xl font-bold text-text mb-1">Controls</h2>
                <p className="text-lg text-muted">LSL Stream Configuration</p>
            </div>

            <div className="p-6 space-y-8">

                {/* Stream Control */}
                <ElectricBorder
                    color={isPaused ? "#ef4444" : "#10b981"}
                    speed={isPaused ? .5 : 1.1}
                    chaos={isPaused ? .025 : .035}
                    thickness={2}
                    borderRadius={12}

                >
                    <button
                        onClick={() => {
                            soundHandler.playToggle(!isPaused);
                            setIsPaused(!isPaused);
                        }}
                        className={`w-full py-3 font-bold transition-all flex items-center justify-center gap-2 ${isPaused
                            ? 'bg-accent/10 text-accent hover:bg-accent/20'
                            : 'bg-primary/10 text-primary hover:bg-primary/20'
                            }`}
                    >
                        <span className={`w-2 h-2 rounded-full ${isPaused ? 'bg-accent' : 'bg-primary animate-pulse'}`}></span>
                        {isPaused ? 'RESUME STREAM' : 'PAUSE STREAM'}
                    </button>
                </ElectricBorder>

                {/* Time Window */}
                <section>
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-base font-bold text-muted uppercase tracking-wider">Time Window</h3>
                        <span className="text-lg font-mono text-primary bg-primary/10 px-2 py-0.5 rounded">{config.display?.timeWindowMs / 1000}s</span>
                    </div>
                    <ElasticSlider
                        defaultValue={(config.display?.timeWindowMs || 10000) / 1000}
                        startingValue={1}
                        maxValue={30}
                        stepSize={1}
                        isStepped={true}
                        onChange={(val) => setConfig(prev => ({
                            ...prev,
                            display: { ...prev.display, timeWindowMs: val * 1000 }
                        }))}
                        leftIcon={<Minus size={14} className="text-muted" />}
                        rightIcon={<Plus size={14} className="text-muted" />}
                        className="w-full"
                    />
                </section>

                {/* Channel Mapping */}
                <section>
                    <h3 className="text-sm font-bold text-muted uppercase tracking-wider mb-4">Channel Mapping</h3>

                    {/* Channel 0 */}
                    <div className="mb-3">
                        <div className="flex justify-between items-center mb-1">
                            <label className="text-xs font-medium text-text">Graph 1</label>
                            <label className="text-[10px] text-muted flex items-center gap-1 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={config.channel_mapping?.ch0?.enabled !== false}
                                    onChange={(e) => handleChannelToggle('ch0', e.target.checked)}
                                    className="accent-primary"
                                />
                                Enable
                            </label>
                        </div>
                        <SensorSelector
                            value={getSensorTypeForChannel('ch0')}
                            onChange={(val) => handleChannelMapping('ch0', val)}
                            disabled={config.channel_mapping?.ch0?.enabled === false}
                        />
                    </div>

                    {/* Channel 1 */}
                    <div className="mb-4">
                        <div className="flex justify-between items-center mb-1">
                            <label className="text-xs font-medium text-text">Graph 2</label>
                            <label className="text-[10px] text-muted flex items-center gap-1 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={config.channel_mapping?.ch1?.enabled !== false}
                                    onChange={(e) => handleChannelToggle('ch1', e.target.checked)}
                                    className="accent-primary"
                                />
                                Enable
                            </label>
                        </div>
                        <SensorSelector
                            value={getSensorTypeForChannel('ch1')}
                            onChange={(val) => handleChannelMapping('ch1', val)}
                            disabled={config.channel_mapping?.ch1?.enabled === false}
                        />
                    </div>

                    {/* Channel 2 */}
                    <div className="mb-4">
                        <div className="flex justify-between items-center mb-1">
                            <label className="text-xs font-medium text-text">Graph 3</label>
                            <label className="text-[10px] text-muted flex items-center gap-1 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={config.channel_mapping?.ch2?.enabled !== false}
                                    onChange={(e) => handleChannelToggle('ch2', e.target.checked)}
                                    className="accent-primary"
                                />
                                Enable
                            </label>
                        </div>
                        <SensorSelector
                            value={getSensorTypeForChannel('ch2')}
                            onChange={(val) => handleChannelMapping('ch2', val)}
                            disabled={config.channel_mapping?.ch2?.enabled === false}
                        />
                    </div>

                    {/* Channel 3 */}
                    <div className="mb-4">
                        <div className="flex justify-between items-center mb-1">
                            <label className="text-xs font-medium text-text">Graph 4</label>
                            <label className="text-[10px] text-muted flex items-center gap-1 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={config.channel_mapping?.ch3?.enabled !== false}
                                    onChange={(e) => handleChannelToggle('ch3', e.target.checked)}
                                    className="accent-primary"
                                />
                                Enable
                            </label>
                        </div>
                        <SensorSelector
                            value={getSensorTypeForChannel('ch3')}
                            onChange={(val) => handleChannelMapping('ch3', val)}
                            disabled={config.channel_mapping?.ch3?.enabled === false}
                        />
                    </div>

                    <button
                        onClick={() => {
                            soundHandler.playClick();
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

                {/* SENSOR-BASED FILTERS (Not Channel-Based) */}
                <section className="space-y-6">
                    <h3 className="text-sm font-bold text-muted uppercase tracking-wider">Signal Filters</h3>

                    {/* EMG FILTER (applies to all EMG channels) */}
                    <FilterSection
                        sensorType="EMG"
                        filterConfig={getFilterConfig('EMG')}
                        onFilterChange={handleSensorFilterChange}
                        colorClass="text-primary"
                        accentColor="primary"
                        channelsUsingThis={
                            (getSensorTypeForChannel('ch0') === 'EMG' ? ['ch0'] : [])
                                .concat(getSensorTypeForChannel('ch1') === 'EMG' ? ['ch1'] : [])
                                .concat(getSensorTypeForChannel('ch2') === 'EMG' ? ['ch2'] : [])
                                .concat(getSensorTypeForChannel('ch3') === 'EMG' ? ['ch3'] : [])
                        }
                        onSave={onSave}
                    />

                    {/* EOG FILTER (applies to all EOG channels) */}
                    <FilterSection
                        sensorType="EOG"
                        filterConfig={getFilterConfig('EOG')}
                        onFilterChange={handleSensorFilterChange}
                        colorClass="text-emerald-500"
                        accentColor="emerald"
                        channelsUsingThis={
                            (getSensorTypeForChannel('ch0') === 'EOG' ? ['ch0'] : [])
                                .concat(getSensorTypeForChannel('ch1') === 'EOG' ? ['ch1'] : [])
                                .concat(getSensorTypeForChannel('ch2') === 'EOG' ? ['ch2'] : [])
                                .concat(getSensorTypeForChannel('ch3') === 'EOG' ? ['ch3'] : [])
                        }
                        onSave={onSave}
                    />

                    {/* EEG FILTER (applies to all EEG channels) */}
                    <FilterSection
                        sensorType="EEG"
                        filterConfig={getFilterConfig('EEG')}
                        onFilterChange={handleSensorFilterChange}
                        colorClass="text-orange-500"
                        accentColor="orange"
                        channelsUsingThis={
                            (getSensorTypeForChannel('ch0') === 'EEG' ? ['ch0'] : [])
                                .concat(getSensorTypeForChannel('ch1') === 'EEG' ? ['ch1'] : [])
                                .concat(getSensorTypeForChannel('ch2') === 'EEG' ? ['ch2'] : [])
                                .concat(getSensorTypeForChannel('ch3') === 'EEG' ? ['ch3'] : [])
                        }
                        onSave={onSave}
                    />
                </section>
            </div>
        </aside >
    )
}

function SensorSelector({ value, onChange, disabled }) {
    return (
        <CustomSelect
            value={value}
            onChange={onChange}
            disabled={disabled}
            options={['EMG', 'EOG', 'EEG']}
            placeholder="Select Sensor"
        />
    );
}

/**
 * FilterSection Component
 * 
 * Renders filter controls for a SENSOR TYPE (EMG, EOG, or EEG)
 * 
 * KEY CHANGE: This section appears ONCE per sensor type
 * If multiple channels use the same sensor, they share this config
 * 
 * Example:
 *   - ch0 = EMG
 *   - ch1 = EMG
 *   - → Only ONE "EMG Filter" section appears
 *   - → All EMG channels use this config
 */
function FilterSection({
    sensorType,
    filterConfig,
    onFilterChange,
    colorClass,
    accentColor,
    channelsUsingThis,
    onSave
}) {
    // If no channels use this sensor, don't render it
    if (channelsUsingThis.length === 0) {
        return (
            <div className="space-y-3 p-3 rounded-lg border border-border/30 bg-surface/30 opacity-50">
                <div className="text-xs text-muted italic">
                    No channels using {sensorType}
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-3 p-3 rounded-lg border border-border bg-surface/50">
            {/* Header: Sensor Type + Which Channels Use It */}
            <div className="flex items-center justify-between border-b border-border/50 pb-2 mb-2">
                <div>
                    <h4 className={`text-xs font-bold ${colorClass}`}>
                        {sensorType} Filter
                    </h4>
                    <p className="text-[10px] text-muted mt-0.5">
                        Used by: {channelsUsingThis.map(ch => ch.toUpperCase()).join(', ')}
                    </p>
                </div>
                <button
                    onClick={() => onSave?.()}
                    className={`px-2 py-0.5 text-[10px] bg-${accentColor}-500 text-white rounded font-bold hover:opacity-90`}
                >
                    APPLY
                </button>
            </div>

            {/* Filter Type - shows which kind of filter this sensor uses */}
            {filterConfig.type && (
                <div className="text-[10px] text-muted bg-bg rounded px-2 py-1 inline-block mb-2">
                    Type: <span className="font-bold text-text">{filterConfig.type}</span>
                </div>
            )}

            {/* NOTCH FILTER (for 50/60Hz mains interference) */}
            <div className="flex items-center justify-between">
                <label className="text-xs text-text flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={filterConfig.notch_enabled || false}
                        onChange={(e) => onFilterChange(sensorType, 'notch_enabled', e.target.checked)}
                        className={`accent-${accentColor}-500`}
                    />
                    Notch Filter (Mains)
                </label>
                {filterConfig.notch_enabled && (
                    <div className="flex items-center gap-1">
                        <input
                            type="number"
                            step="0.1"
                            className="w-16 bg-bg border border-border rounded px-1 py-0.5 text-xs text-right"
                            value={filterConfig.notch_freq || 50}
                            onChange={(e) => onFilterChange(sensorType, 'notch_freq', Number(e.target.value))}
                        />
                        <span className="text-[10px] text-muted">Hz</span>
                    </div>
                )}
            </div>

            {/* BANDPASS FILTER */}
            <div className="space-y-1">
                <label className="text-xs text-text flex items-center gap-2">
                    <input
                        type="checkbox"
                        checked={filterConfig.bandpass_enabled || false}
                        onChange={(e) => onFilterChange(sensorType, 'bandpass_enabled', e.target.checked)}
                        className={`accent-${accentColor}-500`}
                    />
                    Bandpass Filter
                </label>
                {filterConfig.bandpass_enabled && (
                    <div className="flex gap-2 items-center pl-5">
                        <input
                            type="number"
                            step="0.1"
                            className="w-14 bg-bg border border-border rounded px-1 py-0.5 text-xs"
                            value={filterConfig.bandpass_low || 1}
                            onChange={(e) => onFilterChange(sensorType, 'bandpass_low', Number(e.target.value))}
                        />
                        <span className="text-[10px] text-muted">-</span>
                        <input
                            type="number"
                            step="0.1"
                            className="w-14 bg-bg border border-border rounded px-1 py-0.5 text-xs"
                            value={filterConfig.bandpass_high || 100}
                            onChange={(e) => onFilterChange(sensorType, 'bandpass_high', Number(e.target.value))}
                        />
                        <span className="text-[10px] text-muted">Hz</span>
                    </div>
                )}
            </div>

            {/* HIGH-PASS FILTER CUTOFF */}
            <div className="space-y-1 pt-2 border-t border-border/30">
                <label className="text-[10px] text-muted flex justify-between">
                    <span>High-Pass Cutoff</span>
                    <span className={colorClass} style={{ fontWeight: 'bold' }}>
                        {filterConfig.cutoff || 1} Hz
                    </span>
                </label>
                <input
                    type="range"
                    min="0.1"
                    max="200"
                    step="1"
                    value={filterConfig.cutoff || 1}
                    onChange={(e) => onFilterChange(sensorType, 'cutoff', Number(e.target.value))}
                    className={`w-full accent-${accentColor}-500 h-1 bg-bg rounded-lg appearance-none cursor-pointer`}
                />
                <div className="flex justify-between text-[10px] text-muted font-mono">
                    <span>0.1 Hz</span>
                    <span>200 Hz</span>
                </div>
            </div>

            {/* FILTER ORDER */}
            {filterConfig.order && (
                <div className="space-y-1 pt-2 border-t border-border/30">
                    <label className="text-[10px] text-muted flex justify-between">
                        <span>Filter Order</span>
                        <span className={colorClass} style={{ fontWeight: 'bold' }}>
                            {filterConfig.order}
                        </span>
                    </label>
                    <input
                        type="range"
                        min="1"
                        max="8"
                        step="1"
                        value={filterConfig.order || 4}
                        onChange={(e) => onFilterChange(sensorType, 'order', Number(e.target.value))}
                        className={`w-full accent-${accentColor}-500 h-1 bg-bg rounded-lg appearance-none cursor-pointer`}
                    />
                    <div className="flex justify-between text-[10px] text-muted font-mono">
                        <span>1st</span>
                        <span>8th</span>
                    </div>
                </div>
            )}
        </div>
    )
}
