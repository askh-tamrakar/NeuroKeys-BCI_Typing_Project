import React, { useEffect, useState } from 'react';

export default function App() {
  const [messages, setMessages] = useState([]);
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8765');
    ws.onmessage = (evt) => {
      try {
        const d = JSON.parse(evt.data);
        setMessages((m) => [d, ...m].slice(0, 50));
      } catch {}
    };
    return () => ws.close();
  }, []);
  return (
    <div style={{padding:20}}>
      <h2>BCI Live Dashboard</h2>
      <div style={{border:'1px solid #ddd', padding:10, height:400, overflow:'auto'}}>
        {messages.map((m,i)=>(<div key={i}><b>{m.source}</b>: {m.pred?.label}</div>))}
      </div>
    </div>
  );
}
