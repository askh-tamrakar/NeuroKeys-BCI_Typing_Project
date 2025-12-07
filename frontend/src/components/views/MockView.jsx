import React, { useEffect, useState, useRef } from "react";

function LiveTrace({ window }) {
  // window is [[ch1 samples],[ch2 samples],...]
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !window) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const ch = Math.min(5, window.length); // draw only first channel for simplicity
    const data = window[1];
    const w = canvas.width, h = canvas.height;
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = (i / data.length) * w;
      const v = (data[i]); // small numbers
      const y = h / 2 - v * (h / 2) * 2; // scale
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = "var(--primary)";
    ctx.lineWidth = 2;
    ctx.stroke();
  }, [window]);
  return <canvas ref={canvasRef} width={400} height={100} className="border border-border rounded-lg" />;
}

export default function MockView() {
  const [messages, setMessages] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    ws.onopen = () => console.log("WS connected");
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        // store limited messages
        setMessages(m => [msg, ...m].slice(0, 50));
      } catch (e) { console.error(e); }
    };
    ws.onerror = (e) => console.error("WS error", e);
    ws.onclose = () => console.log("WS closed");
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  return (
    <div className="space-y-6">
      <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
        <h2 className="text-3xl font-bold text-text mb-2 flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse"></span>
          BCI Mock Dashboard
        </h2>
        <p className="text-muted">Real-time predictions from mock backend simulator</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
            <h4 className="text-xl font-bold text-text mb-4">Recent Predictions</h4>
            <div className="space-y-3 max-h-[600px] overflow-auto scrollbar-hide">
              {messages.length === 0 && (
                <div className="flex flex-col items-center justify-center py-12 text-muted space-y-3">
                  <div className="w-16 h-16 rounded-full bg-bg border border-border flex items-center justify-center">
                    <span className="text-2xl">⏳</span>
                  </div>
                  <p>Waiting for messages...</p>
                </div>
              )}
              {messages.map((m, idx) => (
                <div key={idx} className="p-4 bg-bg rounded-xl border border-border hover:border-primary/50 transition-all">
                  <div className="flex items-center justify-between mb-2">
                    <div className="font-bold text-text text-lg">{m.source}</div>
                    <div className="text-sm text-muted">{new Date(m.timestamp || Date.now()).toLocaleTimeString()}</div>
                  </div>
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-primary font-bold">{m.pred?.label}</span>
                    <span className="text-muted text-sm">({m.pred?.prob})</span>
                  </div>
                  {m.window && <LiveTrace window={m.window} />}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div>
          <div className="card bg-surface border border-border shadow-card rounded-2xl p-6">
            <h4 className="text-xl font-bold text-text mb-4">Stats</h4>
            <div className="bg-bg/50 backdrop-blur-sm rounded-xl p-5 space-y-4 border border-border">
              <div>
                <div className="text-muted text-sm mb-1">Total Messages</div>
                <div className="text-text font-bold text-2xl">{messages.length}</div>
              </div>
              <div>
                <div className="text-muted text-sm mb-1">Last Source</div>
                <div className="text-text font-bold">{messages[0]?.source ?? "n/a"}</div>
              </div>
              <div>
                <div className="text-muted text-sm mb-1">Last Label</div>
                <div className="text-primary font-bold">{messages[0]?.pred?.label ?? "n/a"}</div>
              </div>
              <div className="pt-4 border-t border-border">
                <p className="text-muted text-sm">This demo uses the mock backend simulator — swap in real server URLs when hardware arrives.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}