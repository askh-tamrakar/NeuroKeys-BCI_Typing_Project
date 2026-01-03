import React, { useState, useEffect, useRef, useCallback } from 'react';

// ==========================================
// SSVEP STIMULATION VIEW
// ==========================================
// Features:
// - High-precision timing using requestAnimationFrame
// - Direct DOM manipulation for performance (bypassing React render loop for flicker)
// - 3x2 Grid layout
// - Photodiode sync marker
// - Experiment protocol support
// - VSync / Monitor Refresh Lock support (Frame Counting)
// - Theme Aware (Uses CSS Variables)

export default function SSVEPView() {
    // --- Configuration State ---
    const [configs, setConfigs] = useState([
        { id: 0, freq: 8, label: 'Target 1' },
        { id: 1, freq: 10, label: 'Target 2' },
        { id: 2, freq: 12, label: 'Target 3' },
        { id: 3, freq: 15, label: 'Target 4' },
        { id: 4, freq: 18, label: 'Target 5' },
        { id: 5, freq: 20, label: 'Target 6' },
    ]);

    const [brightness, setBrightness] = useState(1.0);
    const [globalRunning, setGlobalRunning] = useState(false);

    // VSync / Refresh Rate State
    const [refreshRate, setRefreshRate] = useState(60);

    // Experiment Protocol State
    const [protocolMode, setProtocolMode] = useState(false);
    const [protocolState, setProtocolState] = useState('IDLE'); // IDLE, CUE, STIM, REST
    const [currentTrialIdx, setCurrentTrialIdx] = useState(0);
    const [trials, setTrials] = useState([]);

    // --- Refs for Animation Loop ---
    const requestRef = useRef();
    const startTimeRef = useRef();
    const frameCountRef = useRef(0);

    // Refs to DOM elements for direct manipulation
    const ledRefs = useRef([]);
    const photoDiodeRef = useRef();

    // Experiment timing refs
    const lastStateChangeRef = useRef(0);
    const protocolConfig = useRef({
        cueDuration: 2000,
        stimDuration: 5000,
        restDuration: 2000,
        rounds: 3 // rounds per target
    });

    // --- Measure Refresh Rate on Mount ---
    useEffect(() => {
        let frames = 0;
        let start = performance.now();
        let active = true;

        const measureLoop = (now) => {
            if (!active) return;
            frames++;
            if (now - start >= 1000) {
                const rate = Math.round(frames * 1000 / (now - start));
                console.log(`[SSVEP] Measured Refresh Rate: ${rate}Hz`);
                // Snap to common rates to avoid jitter noise
                if (rate > 58 && rate < 62) setRefreshRate(60);
                else if (rate > 118 && rate < 122) setRefreshRate(120);
                else if (rate > 142 && rate < 146) setRefreshRate(144);
                else setRefreshRate(rate);

                active = false;
            } else {
                requestAnimationFrame(measureLoop);
            }
        };
        requestAnimationFrame(measureLoop);
        return () => { active = false; };
    }, []);

    // --- Experiment Logic ---
    const startProtocol = () => {
        // Generate randomized trials
        const newTrials = [];
        for (let r = 0; r < protocolConfig.current.rounds; r++) {
            // Shuffle targets for each round
            const roundTargets = [...configs].sort(() => Math.random() - 0.5);
            roundTargets.forEach(t => newTrials.push(t.id));
        }

        setTrials(newTrials);
        setCurrentTrialIdx(0);
        setProtocolMode(true);
        setProtocolState('REST'); // Start with rest
        lastStateChangeRef.current = performance.now();
        setGlobalRunning(true);
    };

    const stopProtocol = () => {
        setProtocolMode(false);
        setProtocolState('IDLE');
        setGlobalRunning(false);
    };

    // --- Animation Loop ---
    const animate = useCallback((time) => {
        if (!startTimeRef.current) startTimeRef.current = time;
        const elapsed = time - startTimeRef.current;
        frameCountRef.current++;

        // 1. Handle Protocol State Transitions
        if (protocolMode && globalRunning) {
            const stateElapsed = time - lastStateChangeRef.current;

            if (protocolState === 'REST') {
                if (stateElapsed > protocolConfig.current.restDuration) {
                    setProtocolState('CUE');
                    lastStateChangeRef.current = time;
                }
            } else if (protocolState === 'CUE') {
                if (stateElapsed > protocolConfig.current.cueDuration) {
                    setProtocolState('STIM');
                    lastStateChangeRef.current = time;
                }
            } else if (protocolState === 'STIM') {
                if (stateElapsed > protocolConfig.current.stimDuration) {
                    // Next trial
                    if (currentTrialIdx < trials.length - 1) {
                        setCurrentTrialIdx(prev => prev + 1);
                        setProtocolState('REST');
                    } else {
                        stopProtocol(); // Finished
                    }
                    lastStateChangeRef.current = time;
                }
            }
        }

        // 2. Flicker Logic
        const isFlickering = (globalRunning && !protocolMode) || (protocolMode && protocolState === 'STIM');

        configs.forEach((cfg, idx) => {
            const el = ledRefs.current[idx];
            if (!el) return;

            if (isFlickering) {
                let isOn = false;

                // --- Frame Counting (Monitor Locked) ---
                // Always use frame counting for best phase stability in SSVEP
                // Calculate period in frames. e.g. 60Hz / 10Hz = 6 frames period.
                const period = Math.max(2, Math.round(refreshRate / cfg.freq));
                // 50% duty cycle
                isOn = (frameCountRef.current % period) < (period / 2);

                // Scientific Color Standards
                // ON: Near-White (245, 245, 245) scaled by brightness
                // OFF: Near-Black (5, 5, 5)
                if (isOn) {
                    el.style.backgroundColor = `rgba(245, 245, 245, ${brightness})`;
                    el.style.opacity = 1;
                } else {
                    el.style.backgroundColor = 'rgb(5, 5, 5)';
                    el.style.opacity = 1;
                }
                el.style.boxShadow = 'none';

            } else {
                // If not flickering, handle cue/rest visualization
                if (protocolMode && protocolState === 'CUE') {
                    // Highlight target during cue
                    const isTarget = trials[currentTrialIdx] === cfg.id;
                    el.style.backgroundColor = isTarget ? 'rgb(245, 245, 245)' : 'rgb(20, 20, 20)';
                    el.style.borderColor = isTarget ? '#ffffff' : '#333333';
                    el.style.borderWidth = isTarget ? '4px' : '1px';
                } else if (protocolMode && protocolState === 'REST') {
                    el.style.backgroundColor = 'rgb(0, 0, 0)';
                    el.style.border = '1px solid #111';
                } else {
                    // Stopped state - Dim Static White
                    el.style.backgroundColor = 'rgb(40, 40, 40)';
                    el.style.border = '1px solid #333';
                }
                el.style.boxShadow = 'none';
            }
        });

        // 3. Photodiode Logic
        // Flips every frame when stimulating to signal active data collection
        if (photoDiodeRef.current) {
            if (isFlickering) {
                // Toggle every frame for max temporal resolution or sync trial events
                // We use frame count parity for simple 1/2 refresh rate sync check
                const isWhite = frameCountRef.current % 2 === 0;
                photoDiodeRef.current.style.backgroundColor = isWhite ? '#ffffff' : '#000000';
            } else {
                photoDiodeRef.current.style.backgroundColor = '#000000';
            }
        }

        requestRef.current = requestAnimationFrame(animate);
    }, [configs, brightness, globalRunning, protocolMode, protocolState, currentTrialIdx, trials, refreshRate]);

    useEffect(() => {
        if (globalRunning) {
            requestRef.current = requestAnimationFrame(animate);
        } else {
            // Reset styles when stopped
            ledRefs.current.forEach(el => {
                if (el) {
                    el.style.backgroundColor = 'rgb(40, 40, 40)';
                    el.style.opacity = 1;
                    el.style.border = 'none';
                }
            });
            cancelAnimationFrame(requestRef.current);
        }
        return () => cancelAnimationFrame(requestRef.current);
    }, [globalRunning, animate]);

    // --- UI State ---
    const [showControls, setShowControls] = useState(true);

    return (
        <div
            className="w-full h-full relative overflow-hidden flex flex-col font-mono"
            style={{ backgroundColor: '#000000', color: '#ffffff' }}
        >
            {/* --- Photodiode Marker (Bottom Left) --- */}
            <div
                ref={photoDiodeRef}
                className="absolute bottom-0 left-0 w-16 h-16 bg-black z-50"
            />

            {/* --- Toggle Controls Button (Top Right, Fades Out) --- */}
            <button
                onClick={() => setShowControls(!showControls)}
                className={`absolute top-4 right-4 z-50 p-2 rounded-lg border transition-opacity duration-300 ${globalRunning ? 'opacity-20 hover:opacity-100' : 'opacity-100'}`}
                style={{
                    backgroundColor: 'rgba(20, 20, 20, 0.8)',
                    borderColor: '#333',
                    color: '#fff'
                }}
            >
                {showControls ? 'Hide Controls' : 'Show Controls'}
            </button>

            {/* --- Grid Layout --- */}
            <div className="flex-grow grid grid-cols-3 grid-rows-2 gap-8 p-12 relative z-10 w-full max-h-[90vh] mx-auto">
                {configs.map((cfg, idx) => {
                    // Calculate effective frequency (Frame Locked)
                    const effectiveFreq = (refreshRate / Math.max(2, Math.round(refreshRate / cfg.freq))).toFixed(1);

                    return (
                        <div key={cfg.id} className="flex flex-col items-center justify-center p-4 relative group">
                            {/* The LED Tile */}
                            <div
                                ref={el => ledRefs.current[idx] = el}
                                className="w-48 h-48 md:w-64 md:h-64 rounded-xl transition-none"
                                style={{
                                    backgroundColor: 'rgb(40, 40, 40)', // Initial static color
                                    boxShadow: 'none'
                                }}
                            >
                                {/* Center Fixation Cross (Always visible for focus) */}
                                <div className="w-full h-full flex items-center justify-center">
                                    <span className="font-bold text-4xl opacity-50" style={{ color: '#000000' }}>+</span>
                                </div>
                            </div>

                            {/* Controls (visible ONLY when NOT running) */}
                            {(!globalRunning || showControls) && (
                                <div className={`mt-4 flex flex-col items-center gap-2 transition-opacity duration-300 ${globalRunning ? 'opacity-50' : ''}`}>
                                    <span className="text-sm font-bold" style={{ color: 'var(--muted)' }}>{cfg.label}</span>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number"
                                            value={cfg.freq}
                                            onChange={(e) => updateFreq(cfg.id, e.target.value)}
                                            disabled={globalRunning}
                                            className="w-16 border rounded px-2 py-1 text-center font-bold outline-none disabled:opacity-50"
                                            style={{
                                                backgroundColor: 'color-mix(in srgb, var(--bg) 90%, var(--primary))',
                                                borderColor: 'var(--border)',
                                                color: 'var(--primary)'
                                            }}
                                        />
                                        <span className="text-xs" style={{ color: 'var(--muted)' }}>Hz</span>
                                    </div>
                                    {Math.abs(effectiveFreq - cfg.freq) > 0.1 && (
                                        <span className="text-[10px] text-yellow-500">
                                            Act: {effectiveFreq}Hz
                                        </span>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* --- Global Controls (Bottom Overlay) --- */}
            {showControls && (
                <div
                    className="absolute bottom-8 right-8 z-40 flex flex-col gap-4 p-6 rounded-2xl border backdrop-blur-sm transition-all duration-300"
                    style={{
                        backgroundColor: 'color-mix(in srgb, var(--bg) 90%, transparent)',
                        borderColor: 'var(--border)'
                    }}
                >
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="font-bold text-lg" style={{ color: 'var(--primary)' }}>SSVEP Control</h3>
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: globalRunning ? '#00ff00' : '#ff0000' }} />
                    </div>

                    {/* Manual Start/Stop */}
                    <button
                        onClick={() => {
                            if (globalRunning) {
                                stopProtocol();
                                setGlobalRunning(false);
                            } else {
                                // Manual mode (just flicker)
                                setGlobalRunning(true);
                                // Optional: Auto-hide controls on start? 
                                // setShowControls(false); 
                            }
                        }}
                        className={`px-8 py-3 rounded-lg font-bold uppercase tracking-wider transition-all border`}
                        style={{
                            backgroundColor: globalRunning ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)',
                            color: globalRunning ? '#ef4444' : '#22c55e',
                            borderColor: globalRunning ? 'rgba(239, 68, 68, 0.5)' : 'rgba(34, 197, 94, 0.5)'
                        }}
                    >
                        {globalRunning ? 'Stop All' : 'Start Flicker'}
                    </button>

                    {/* Protocol Start */}
                    {!globalRunning && (
                        <button
                            onClick={startProtocol}
                            className="px-8 py-2 rounded-lg font-bold uppercase tracking-wider text-sm border"
                            style={{
                                backgroundColor: 'color-mix(in srgb, var(--primary) 20%, transparent)',
                                color: 'var(--primary)',
                                borderColor: 'var(--primary)'
                            }}
                        >
                            Run Protocol
                        </button>
                    )}

                    {/* Options Grid */}
                    <div className="grid grid-cols-2 gap-4 mt-2 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                        {/* Brightness */}
                        <div className="space-y-1">
                            <label className="text-xs uppercase font-bold" style={{ color: 'var(--muted)' }}>Brightness</label>
                            <input
                                type="range"
                                min="0.1"
                                max="1"
                                step="0.05"
                                value={brightness}
                                onChange={(e) => setBrightness(parseFloat(e.target.value))}
                                className="w-full"
                                style={{ accentColor: 'var(--primary)' }}
                            />
                        </div>

                        {/* Monitor Hz */}
                        <div className="space-y-1 flex flex-col">
                            <label className="text-xs uppercase font-bold" style={{ color: 'var(--muted)' }}>
                                Monitor Hz
                            </label>
                            <input
                                type="number"
                                value={refreshRate}
                                onChange={(e) => setRefreshRate(parseInt(e.target.value) || 60)}
                                className="w-full text-xs border rounded px-2 py-1 text-center font-bold outline-none bg-transparent"
                                style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}
                            />
                        </div>
                    </div>

                    {/* Status Info */}
                    {protocolMode && (
                        <div className="mt-2 p-2 rounded text-xs font-mono space-y-1" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
                            <div className="flex justify-between" style={{ color: 'var(--muted)' }}>
                                <span>State:</span>
                                <span className="font-bold" style={{ color: 'var(--text)' }}>{protocolState}</span>
                            </div>
                            <div className="flex justify-between" style={{ color: 'var(--muted)' }}>
                                <span>Trial:</span>
                                <span style={{ color: 'var(--text)' }}>{currentTrialIdx + 1} / {trials.length}</span>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
