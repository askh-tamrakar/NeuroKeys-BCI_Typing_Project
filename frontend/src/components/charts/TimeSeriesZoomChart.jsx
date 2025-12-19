import React, { useState, useMemo, useRef, useEffect } from 'react';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceArea,
    ReferenceLine
} from 'recharts';

/**
 * TimeSeriesZoomChart
 * Reusable chart for calibration with zoom, pan, and window selection support.
 */
export default function TimeSeriesZoomChart({
    data = [],
    title = "Signal Preview",
    height = 300,
    timeWindowMs = 5000,
    showGrid = true,
    color = "#3b82f6",
    markedWindows = [],
    onWindowSelect = null, // (startTime, endTime) => void
    activeWindow = null, // { startTime, endTime }
    mode = 'realtime',
    scannerX = null
}) {
    // Zoom and Pan state
    const [left, setLeft] = useState('dataMin');
    const [right, setRight] = useState('dataMax');
    const [refAreaLeft, setRefAreaLeft] = useState('');
    const [refAreaRight, setRefAreaRight] = useState('');
    const [top, setTop] = useState('auto');
    const [bottom, setBottom] = useState('auto');

    // Handle recording mode selection
    const handleMouseDown = (e) => {
        if (mode !== 'recording') return;
        if (e && e.activeLabel) {
            setRefAreaLeft(e.activeLabel);
        }
    };

    const handleMouseMove = (e) => {
        if (mode !== 'recording') return;
        if (refAreaLeft && e && e.activeLabel) {
            setRefAreaRight(e.activeLabel);
        }
    };

    const handleMouseUp = () => {
        if (mode !== 'recording') return;
        if (refAreaLeft && refAreaRight) {
            let [s, e] = [Number(refAreaLeft), Number(refAreaRight)];
            if (s > e) [s, e] = [e, s];
            if (onWindowSelect) onWindowSelect(s, e);
        }
        setRefAreaLeft('');
        setRefAreaRight('');
    };

    const zoom = () => {
        if (refAreaLeft === refAreaRight || refAreaRight === '') {
            setRefAreaLeft('');
            setRefAreaRight('');
            return;
        }

        // Zoom logic (if we wanted to use drag-to-zoom instead of drag-to-select)
        // For this UI, drag-to-select is prioritized in recording mode.
    };

    const zoomOut = () => {
        setLeft('dataMin');
        setRight('dataMax');
        setTop('auto');
        setBottom('auto');
    };

    // Helper to get color for window status
    const getWindowColor = (status, isMissed) => {
        if (isMissed) return 'rgba(239, 68, 68, 0.2)'; // Red
        if (status === 'correct') return 'rgba(16, 185, 129, 0.2)'; // Green
        if (status === 'incorrect') return 'rgba(245, 158, 11, 0.2)'; // Orange
        return 'rgba(156, 163, 175, 0.1)'; // Gray
    };

    return (
        <div className="flex flex-col h-full bg-surface border border-border mt-1 rounded-xl overflow-hidden shadow-sm">
            <div className="px-4 py-2 border-b border-border bg-bg/30 flex justify-between items-center">
                <h4 className="text-sm font-bold text-text flex items-center gap-2">
                    <span className="w-1.5 h-4 rounded-full" style={{ backgroundColor: color }}></span>
                    {title}
                </h4>
                <div className="flex gap-2">
                    {mode === 'recording' && (
                        <button
                            onClick={zoomOut}
                            className="text-[10px] px-2 py-1 bg-primary/10 text-primary rounded border border-primary/20 hover:bg-primary/20 transition-all font-bold uppercase tracking-wider"
                        >
                            Reset View
                        </button>
                    )}
                </div>
            </div>

            <div className="flex-grow p-2 select-none" style={{ height }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                        data={data}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                    >
                        {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.2} />}

                        <XAxis
                            dataKey="time"
                            type="number"
                            domain={mode === 'recording' ? [left, right] : ['auto', 'auto']}
                            tickFormatter={(t) => {
                                if (!t || isNaN(t)) return '';
                                const date = new Date(t);
                                return `${date.getMinutes()}:${date.getSeconds().toString().padStart(2, '0')}.${date.getMilliseconds().toString().padStart(3, '0').slice(0, 1)}`;
                            }}
                            stroke="var(--muted)"
                            fontSize={10}
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis
                            domain={['auto', 'auto']}
                            stroke="var(--muted)"
                            fontSize={10}
                            tickLine={false}
                            axisLine={false}
                            width={40}
                        />

                        <Tooltip
                            labelFormatter={(t) => new Date(t).toLocaleTimeString() + '.' + new Date(t).getMilliseconds()}
                            contentStyle={{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)', borderRadius: '8px', color: 'var(--text)' }}
                        />

                        {/* Render Marked Windows */}
                        {markedWindows.map((win) => (
                            <ReferenceArea
                                key={win.id}
                                x1={win.startTime}
                                x2={win.endTime}
                                fill={getWindowColor(win.status, win.isMissedActual)}
                                stroke={win.isMissedActual ? '#ef4444' : (win.status === 'correct' ? '#10b981' : '#9ca3af')}
                                strokeOpacity={0.5}
                                label={{ position: 'top', value: win.label, fill: 'var(--muted)', fontSize: 10 }}
                            />
                        ))}

                        {/* Real-time scanner or current active window */}
                        {scannerX && <ReferenceLine x={scannerX} stroke="var(--primary)" strokeWidth={2} />}

                        {activeWindow && (
                            <ReferenceArea
                                x1={activeWindow.startTime}
                                x2={activeWindow.endTime}
                                fill="var(--primary)"
                                fillOpacity={0.1}
                                stroke="var(--primary)"
                                strokeDasharray="3 3"
                            />
                        )}

                        {/* Interactive Selection Area */}
                        {refAreaLeft && refAreaRight && (
                            <ReferenceArea x1={refAreaLeft} x2={refAreaRight} strokeOpacity={0.3} fill="var(--accent)" fillOpacity={0.2} />
                        )}

                        <Line
                            type="monotone"
                            dataKey="value"
                            stroke={color}
                            dot={false}
                            strokeWidth={2}
                            isAnimationActive={false}
                            connectNulls
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>

            {mode === 'recording' && (
                <div className="px-4 py-1 text-[10px] text-muted font-mono bg-bg/20 border-t border-border">
                    Tip: Click and drag to select a region to label.
                </div>
            )}
        </div>
    );
}
