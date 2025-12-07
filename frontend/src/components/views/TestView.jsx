import React, { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
    LineChart,
    Line,
    ResponsiveContainer,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
} from "recharts";

// ----- CONFIG -----
const DEFAULT_WS = (typeof process !== "undefined" && process?.env?.NEXT_PUBLIC_BCI_WS) ? process.env.NEXT_PUBLIC_BCI_WS : "ws://localhost:8000/ws";
const SAMPLE_RATE = 250; // Hz (assumption) - adjust to your hardware
const MAX_POINTS = 1024; // points kept per channel for plotting
const EEG_CHANNELS = ["Fp1", "Fp2", "F7", "F8", "C3", "C4", "P3", "P4", "O1", "O2"];
const EOG_CHANNELS = ["Left", "Right"];
const EMG_CHANNELS = ["Arm", "Forearm"];

// ----- Small Biquad implementation (RBJ cookbook) -----
class Biquad {
    constructor(type = "bandpass", fs = SAMPLE_RATE, f0 = 50, Q = 1) {
        this.type = type;
        this.fs = fs;
        this.f0 = f0;
        this.Q = Q;
        this.x1 = 0;
        this.x2 = 0;
        this.y1 = 0;
        this.y2 = 0;
        this.updateCoeffs();
    }

    updateCoeffs() {
        const omega = (2 * Math.PI * this.f0) / this.fs;
        const alpha = Math.sin(omega) / (2 * this.Q);
        const cosw = Math.cos(omega);
        let b0, b1, b2, a0, a1, a2;

        switch (this.type) {
            case "notch":
                b0 = 1; b1 = -2 * cosw; b2 = 1;
                a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha;
                break;
            case "bandpass":
                b0 = alpha; b1 = 0; b2 = -alpha;
                a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha;
                break;
            default:
                b0 = 1; b1 = 0; b2 = 0; a0 = 1; a1 = 0; a2 = 0; break;
        }

        this.b0 = b0 / a0; this.b1 = b1 / a0; this.b2 = b2 / a0;
        this.a1 = a1 / a0; this.a2 = a2 / a0;
    }

    setParams({ type, f0, Q, fs }) {
        if (type) this.type = type;
        if (f0) this.f0 = f0;
        if (Q) this.Q = Q;
        if (fs) this.fs = fs;
        this.updateCoeffs();
    }

    processSample(x) {
        const y = this.b0 * x + this.b1 * this.x1 + this.b2 * this.x2 - this.a1 * this.y1 - this.a2 * this.y2;
        this.x2 = this.x1;
        this.x1 = x;
        this.y2 = this.y1;
        this.y1 = y;
        return y;
    }

    processBlock(xs) {
        return xs.map((v) => this.processSample(v));
    }
}

// ----- Simple FFT (radix-2, iterative) -----
function fft(re, im) {
    const n = re.length;
    if ((n & (n - 1)) !== 0) throw new Error("FFT size must be power of two");
    let j = 0;
    for (let i = 1; i < n - 1; i++) {
        let bit = n >> 1;
        while (j & bit) {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if (i < j) {
            [re[i], re[j]] = [re[j], re[i]];
            [im[i], im[j]] = [im[j], im[i]];
        }
    }
    for (let len = 2; len <= n; len <<= 1) {
        const ang = (-2 * Math.PI) / len;
        const wlen_r = Math.cos(ang);
        const wlen_i = Math.sin(ang);
        for (let i = 0; i < n; i += len) {
            let wr = 1;
            let wi = 0;
            for (let k = 0; k < len / 2; k++) {
                const u_r = re[i + k];
                const u_i = im[i + k];
                const v_r = re[i + k + len / 2] * wr - im[i + k + len / 2] * wi;
                const v_i = re[i + k + len / 2] * wi + im[i + k + len / 2] * wr;
                re[i + k] = u_r + v_r;
                im[i + k] = u_i + v_i;
                re[i + k + len / 2] = u_r - v_r;
                im[i + k + len / 2] = u_i - v_i;
                const tmp_r = wr * wlen_r - wi * wlen_i;
                wi = wr * wlen_i + wi * wlen_r;
                wr = tmp_r;
            }
        }
    }
}

function computeMagnitudeSpectrum(samples) {
    if (!samples || samples.length === 0) return [];
    let n = 1;
    while (n < samples.length) n <<= 1;
    const re = new Array(n).fill(0);
    const im = new Array(n).fill(0);
    for (let i = 0; i < samples.length; i++) re[i] = samples[i];
    fft(re, im);
    const mags = new Array(n / 2);
    for (let i = 0; i < n / 2; i++) mags[i] = Math.sqrt(re[i] * re[i] + im[i] * im[i]) / n;
    return mags;
}

// ----- Helper: downsample for plotting -----
function downsample(data, maxPoints) {
    const arr = data || [];
    if (arr.length <= maxPoints) return arr.map((d, i) => ({ index: i, value: d.value }));
    const step = arr.length / maxPoints;
    const out = [];
    for (let i = 0; i < maxPoints; i++) {
        const idx = Math.floor(i * step);
        out.push({ index: i, value: arr[idx].value });
    }
    return out;
}

// ----- Main Component -----
export default function TestView() {
    const [wsUrl, setWsUrl] = useState(DEFAULT_WS);
    const wsRef = useRef(null);
    const [connected, setConnected] = useState(false);
    const [isPaused, setIsPaused] = useState(false);

    // channel data store: { channelName: [{time, value}, ...] }
    const [channels, setChannels] = useState(() => {
        const m = {};
        [...EEG_CHANNELS, ...EOG_CHANNELS, ...EMG_CHANNELS].forEach((c) => (m[c] = []));
        return m;
    });

    const [selectedGroup, setSelectedGroup] = useState("EEG");
    const [selectedChannels, setSelectedChannels] = useState(EEG_CHANNELS.slice(0, 3));

    // filters
    const [bandpassEnabled, setBandpassEnabled] = useState(false);
    const [bpLow, setBpLow] = useState(1);
    const [bpHigh, setBpHigh] = useState(40);
    const [notchEnabled, setNotchEnabled] = useState(false);
    const [notchFreq, setNotchFreq] = useState(50);

    // biquad instances per channel
    const filtersRef = useRef({});
    useEffect(() => {
        Object.keys(filtersRef.current).forEach((ch) => {
            const obj = filtersRef.current[ch];
            if (!obj) return;
            if (bandpassEnabled) obj.bandpass.setParams({ type: "bandpass", f0: (bpLow + bpHigh) / 2, Q: Math.max(0.1, (bpHigh - bpLow) / ((bpLow + bpHigh) / 2)) });
            if (notchEnabled) obj.notch.setParams({ type: "notch", f0: notchFreq, Q: 30 });
        });
    }, [bpLow, bpHigh, notchFreq, bandpassEnabled, notchEnabled]);

    useEffect(() => {
        const f = {};
        Object.keys(channels).forEach((ch) => {
            f[ch] = {
                bandpass: new Biquad("bandpass", SAMPLE_RATE, (bpLow + bpHigh) / 2, 1),
                notch: new Biquad("notch", SAMPLE_RATE, notchFreq, 30),
            };
        });
        filtersRef.current = f;
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // spectrogram canvas refs
    const specCanvasRef = useRef(null);
    const specBufferRef = useRef({});

    useEffect(() => {
        Object.keys(channels).forEach((ch) => (specBufferRef.current[ch] = []));
    }, []);

    const handleMessage = (data) => {
        if (isPaused) return;

        let obj;
        try { obj = typeof data === "string" ? JSON.parse(data) : data; } catch (e) { return; }
        const ts = obj.timestamp || Date.now();

        if (obj.channels) {
            const updates = {};
            Object.entries(obj.channels).forEach(([ch, v]) => {
                if (!(ch in channels)) return;
                let val = v;
                const fset = filtersRef.current[ch];
                if (fset) {
                    if (notchEnabled) val = fset.notch.processSample(val);
                    if (bandpassEnabled) val = fset.bandpass.processSample(val);
                }
                updates[ch] = { time: ts, value: val };
            });

            setChannels((prev) => {
                const copy = { ...prev };
                Object.entries(updates).forEach(([ch, pt]) => {
                    const arr = copy[ch] ? copy[ch].slice() : [];
                    arr.push(pt);
                    if (arr.length > MAX_POINTS) arr.splice(0, arr.length - MAX_POINTS);
                    copy[ch] = arr;

                    const sb = specBufferRef.current[ch] || [];
                    sb.push(pt.value);
                    if (sb.length > 256) sb.splice(0, sb.length - 256);
                    specBufferRef.current[ch] = sb;
                });
                return copy;
            });

        } else if (obj.channel) {
            const ch = obj.channel;
            if (!(ch in channels)) return;
            let val = obj.value;
            const fset = filtersRef.current[ch];
            if (fset) {
                if (notchEnabled) val = fset.notch.processSample(val);
                if (bandpassEnabled) val = fset.bandpass.processSample(val);
            }
            setChannels((prev) => {
                const copy = { ...prev };
                const arr = copy[ch] ? copy[ch].slice() : [];
                arr.push({ time: ts, value: val });
                if (arr.length > MAX_POINTS) arr.splice(0, arr.length - MAX_POINTS);
                copy[ch] = arr;

                const sb = specBufferRef.current[ch] || [];
                sb.push(val);
                if (sb.length > 256) sb.splice(0, sb.length - 256);
                specBufferRef.current[ch] = sb;

                return copy;
            });
        }
    };

    // connect / disconnect
    const connectWS = () => {
        if (wsRef.current) return;
        try {
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;
            ws.onopen = () => setConnected(true);
            ws.onclose = () => { setConnected(false); wsRef.current = null; };
            ws.onerror = () => { setConnected(false); };
            ws.onmessage = (ev) => handleMessage(ev.data);
        } catch (e) {
            console.error("WebSocket error", e);
            setConnected(false);
        }
    };

    const disconnectWS = () => {
        if (!wsRef.current) return;
        wsRef.current.close();
        wsRef.current = null;
        setConnected(false);
    };

    // spectrogram draw loop
    useEffect(() => {
        let raf = null;
        const canvas = specCanvasRef.current;
        const ctx = canvas ? canvas.getContext("2d") : null;
        const draw = () => {
            if (!ctx) return;
            const width = canvas.width;
            const height = canvas.height;
            ctx.fillStyle = "var(--bg)";
            ctx.fillRect(0, 0, width, height);

            const ch = selectedChannels[0];
            if (ch && specBufferRef.current[ch] && specBufferRef.current[ch].length >= 32) {
                const mags = computeMagnitudeSpectrum(specBufferRef.current[ch]);
                const binCount = mags.length || 0;
                if (binCount > 0) {
                    const barW = Math.max(1, Math.floor(width / binCount));
                    for (let i = 0; i < binCount; i++) {
                        const m = mags[i];
                        const intensity = Math.min(1, m * 10);
                        const hue = Math.floor(240 - intensity * 240);
                        ctx.fillStyle = `hsl(${hue}, 100%, ${10 + intensity * 80}%)`;
                        ctx.fillRect(i * barW, height - intensity * height, barW, intensity * height);
                    }
                }
            } else {
                ctx.fillStyle = "var(--muted)";
                ctx.font = "14px Inter, Arial";
                ctx.fillText("Spectrogram (select a channel and stream data to see FFT)", 10, height / 2);
            }

            raf = requestAnimationFrame(draw);
        };
        raf = requestAnimationFrame(draw);
        return () => cancelAnimationFrame(raf);
    }, [selectedChannels]);

    // prepare recharts data for multi-line plot
    const chartData = (() => {
        const chs = selectedChannels;
        const maxLen = Math.max(...chs.map((c) => channels[c]?.length || 0), 0);
        const out = [];
        for (let i = Math.max(0, maxLen - 200); i < maxLen; i++) {
            const point = {};
            chs.forEach((c) => {
                const arr = channels[c] || [];
                const idx = i - (maxLen - (arr.length));
                point[c] = idx >= 0 && arr[idx] ? arr[idx].value : null;
            });
            out.push(point);
        }
        return out;
    })();

    // UI helpers
    const getGroupChannels = () => {
        switch (selectedGroup) {
            case "EEG": return EEG_CHANNELS;
            case "EOG": return EOG_CHANNELS;
            case "EMG": return EMG_CHANNELS;
            default: return [];
        }
    };

    const toggleChannel = (ch) => {
        setSelectedChannels((prev) => {
            if (prev.includes(ch)) return prev.filter((p) => p !== ch);
            return [...prev.slice(0, 7), ch];
        });
    };

    return (
        <div className="space-y-6">
            {/* Connection Controls */}
            <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div className="flex items-center gap-4">
                        <div className="bg-primary/10 p-3 rounded-xl border border-primary/20">
                            <div className={`w-4 h-4 rounded-full ${connected ? 'bg-primary' : 'bg-red-500'} ${connected && !isPaused ? 'animate-pulse' : ''} shadow-[0_0_10px_currentColor]`}></div>
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-text tracking-tight">Signal Testing & Analysis</h2>
                            <p className="text-xs text-muted font-mono uppercase tracking-widest">
                                {connected ? (isPaused ? 'PAUSED' : 'STREAMING ACTIVE') : 'DISCONNECTED'}
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                        <input
                            value={wsUrl}
                            onChange={(e) => setWsUrl(e.target.value)}
                            placeholder="WebSocket URL"
                            className="flex-1 min-w-[200px] px-4 py-2 bg-bg border border-border text-text rounded-xl focus:ring-2 focus:ring-primary/50 focus:border-primary outline-none transition-all"
                        />
                        {connected ? (
                            <>
                                <button
                                    onClick={() => setIsPaused(!isPaused)}
                                    className={`px-4 py-2 rounded-xl font-bold text-sm transition-all ${isPaused
                                        ? 'bg-accent/20 text-accent hover:bg-accent/30 border border-accent/20'
                                        : 'bg-primary/20 text-primary hover:bg-primary/30 border border-primary/20'
                                        }`}
                                >
                                    {isPaused ? '▶ Resume' : '⏸ Pause'}
                                </button>
                                <button
                                    onClick={disconnectWS}
                                    className="px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 rounded-xl font-bold text-sm transition-all"
                                >
                                    Disconnect
                                </button>
                            </>
                        ) : (
                            <button
                                onClick={connectWS}
                                className="px-4 py-2 bg-primary text-primary-contrast rounded-xl font-bold text-sm hover:opacity-90 transition-all"
                            >
                                Connect
                            </button>
                        )}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* LEFT: Controls */}
                <div className="col-span-1 space-y-6">
                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                        <h3 className="text-lg font-bold text-text mb-4">Channel Groups</h3>
                        <div className="flex flex-col gap-2 mb-4">
                            {['EEG', 'EOG', 'EMG'].map(group => (
                                <button
                                    key={group}
                                    onClick={() => setSelectedGroup(group)}
                                    className={`px-4 py-2 rounded-xl font-bold text-sm transition-all ${selectedGroup === group
                                        ? 'bg-primary text-primary-contrast'
                                        : 'bg-bg border border-border text-text hover:border-primary/50'
                                        }`}
                                >
                                    {group}
                                </button>
                            ))}
                        </div>

                        <h4 className="text-sm font-bold text-text mb-3">Channels (select up to 8)</h4>
                        <div className="grid grid-cols-2 gap-2">
                            {getGroupChannels().map((ch) => (
                                <button
                                    key={ch}
                                    onClick={() => toggleChannel(ch)}
                                    className={`p-2 rounded-lg text-sm font-medium transition-all ${selectedChannels.includes(ch)
                                        ? 'bg-primary text-primary-contrast'
                                        : 'bg-bg border border-border text-text hover:border-primary/50'
                                        }`}
                                >
                                    {ch}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                        <h3 className="text-lg font-bold text-text mb-4">Filters</h3>

                        <label className="flex items-center gap-3 mb-3 cursor-pointer group">
                            <input
                                type="checkbox"
                                checked={notchEnabled}
                                onChange={(e) => setNotchEnabled(e.target.checked)}
                                className="w-5 h-5 text-primary rounded focus:ring-2 focus:ring-primary/50 border-border bg-bg"
                            />
                            <span className="font-bold text-text group-hover:text-primary transition-colors">Notch Filter</span>
                        </label>
                        <div className="flex items-center gap-3 mb-4 pl-8">
                            <input
                                type="range"
                                min={40}
                                max={60}
                                value={notchFreq}
                                onChange={(e) => setNotchFreq(Number(e.target.value))}
                                className="flex-1"
                            />
                            <span className="w-16 text-right text-text font-mono">{notchFreq}Hz</span>
                        </div>

                        <label className="flex items-center gap-3 mb-3 cursor-pointer group">
                            <input
                                type="checkbox"
                                checked={bandpassEnabled}
                                onChange={(e) => setBandpassEnabled(e.target.checked)}
                                className="w-5 h-5 text-primary rounded focus:ring-2 focus:ring-primary/50 border-border bg-bg"
                            />
                            <span className="font-bold text-text group-hover:text-primary transition-colors">Bandpass Filter</span>
                        </label>
                        <div className="flex items-center gap-3 pl-8">
                            <input
                                type="number"
                                value={bpLow}
                                onChange={(e) => setBpLow(Number(e.target.value))}
                                className="w-20 px-2 py-1 bg-bg border border-border text-text rounded-lg focus:ring-2 focus:ring-primary/50 outline-none"
                            />
                            <span className="text-muted">—</span>
                            <input
                                type="number"
                                value={bpHigh}
                                onChange={(e) => setBpHigh(Number(e.target.value))}
                                className="w-20 px-2 py-1 bg-bg border border-border text-text rounded-lg focus:ring-2 focus:ring-primary/50 outline-none"
                            />
                            <span className="text-muted ml-2">Hz</span>
                        </div>

                        <p className="mt-4 text-xs text-muted">Filters use lightweight Biquad approximations for real-time visualization.</p>
                    </div>

                    <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                        <h3 className="text-lg font-bold text-text mb-4">Spectrogram</h3>
                        <canvas
                            ref={specCanvasRef}
                            width={400}
                            height={150}
                            className="w-full rounded-xl border border-border bg-bg"
                        />
                        <p className="mt-3 text-xs text-muted">Real-time FFT magnitude spectrum for the first selected channel.</p>
                    </div>
                </div>

                {/* RIGHT: Charts */}
                <div className="col-span-3 space-y-6">
                    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                        <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xl font-bold text-text">Live Signals</h2>
                                <div className="text-sm text-muted">Showing: {selectedChannels.join(', ')}</div>
                            </div>
                            <div style={{ width: '100%', height: 320 }}>
                                <ResponsiveContainer>
                                    <LineChart data={chartData}>
                                        <XAxis dataKey={(d, idx) => idx} hide />
                                        <YAxis domain={[-200, 200]} />
                                        <Tooltip />
                                        <Legend />
                                        {selectedChannels.map((ch, i) => (
                                            <Line key={ch} type="monotone" dataKey={ch} dot={false} strokeWidth={2} stroke={`hsl(${(i * 70) % 360}, 80%, 60%)`} />
                                        ))}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </motion.div>

                    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
                        <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
                            <h2 className="text-xl font-bold text-text mb-4">Per-Channel Preview</h2>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {selectedChannels.map((ch) => (
                                    <div key={ch} className="bg-bg/50 border border-border rounded-xl p-4">
                                        <div className="flex justify-between items-center mb-3">
                                            <strong className="text-text">{ch}</strong>
                                            <span className="text-xs text-muted">samples: {channels[ch]?.length || 0}</span>
                                        </div>
                                        <div style={{ width: '100%', height: 120 }}>
                                            <ResponsiveContainer>
                                                <LineChart data={downsample((channels[ch] || []).map(pt => ({ value: pt.value })), 120)}>
                                                    <XAxis dataKey="index" hide />
                                                    <YAxis domain={[-200, 200]} />
                                                    <Line type="monotone" dataKey="value" dot={false} strokeWidth={2} stroke="var(--primary)" />
                                                </LineChart>
                                            </ResponsiveContainer>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </motion.div>
                </div>
            </div>
        </div>
    );
}
