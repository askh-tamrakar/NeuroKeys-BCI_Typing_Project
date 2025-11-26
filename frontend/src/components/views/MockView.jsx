// frontend/src/App.jsx
import React, { useEffect, useState, useRef } from "react";

function LiveTrace({window}) {
  // window is [[ch1 samples],[ch2 samples],...]
  const canvasRef = useRef(null);
  useEffect(()=> {
    const canvas = canvasRef.current;
    if (!canvas || !window) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0,0,canvas.width,canvas.height);
    const ch = Math.min(5, window.length); // draw only first channel for simplicity
    const data = window[1];
    const w = canvas.width, h = canvas.height;
    ctx.beginPath();
    for (let i=0;i<data.length;i++){
      const x = (i / data.length) * w;
      const v = (data[i]); // small numbers
      const y = h/2 - v * (h/2) * 2; // scale
      if (i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.strokeStyle = "#0b7";
    ctx.lineWidth = 1;
    ctx.stroke();
  }, [window]);
  return <canvas ref={canvasRef} width={400} height={100} style={{border:"1px solid #ddd"}} />;
}

export default function MockView(){
  const [messages, setMessages] = useState([]);
  const wsRef = useRef(null);

  useEffect(()=>{
    const ws = new WebSocket("ws://localhost:8000/ws");
    ws.onopen = () => console.log("WS connected");
    ws.onmessage = (evt) => {
      try{
        const msg = JSON.parse(evt.data);
        // store limited messages
        setMessages(m => [msg, ...m].slice(0, 50));
      } catch(e){ console.error(e); }
    };
    ws.onerror = (e) => console.error("WS error", e);
    ws.onclose = () => console.log("WS closed");
    wsRef.current = ws;
    return ()=> ws.close();
  },[]);

  return (
    <div style={{fontFamily:"Arial, sans-serif", padding:20}}>
      <h2>BCI Mock Dashboard</h2>
      <div style={{display:'flex', gap:20}}>
        <div style={{flex:1}}>
          <h4>Recent predictions</h4>
          <div style={{height:400, overflow:'auto', border:'1px solid #eee', padding:8}}>
            {messages.length===0 && <div style={{color:"#666"}}>Waiting for messages...</div>}
            {messages.map((m, idx)=>(
              <div key={idx} style={{padding:8, borderBottom:"1px solid #f2f2f2"}}>
                <div><strong>{m.source}</strong> — {m.pred?.label} <span style={{color:"#888"}}>({m.pred?.prob})</span></div>
                <div style={{fontSize:12, color:"#777"}}>{new Date(m.timestamp || Date.now()).toLocaleTimeString()}</div>
                {m.window && <LiveTrace window={m.window} />}
              </div>
            ))}
          </div>
        </div>
        <div style={{width:320}}>
          <h4>Stats</h4>
          <div style={{border:'1px solid #eee', padding:10}}>
            <p><b>Total msgs:</b> {messages.length}</p>
            <p><b>Last source:</b> {messages[0]?.source ?? "n/a"}</p>
            <p><b>Last label:</b> {messages[0]?.pred?.label ?? "n/a"}</p>
            <p style={{color:"#777"}}>This demo uses the mock backend simulator — swap in real server URLs when hardware arrives.</p>
          </div>
        </div>
      </div>
    </div>
  );
}