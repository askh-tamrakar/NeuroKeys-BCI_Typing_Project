
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
from typing import List
import serial

chords_serial = None
app = FastAPI(title="BCI Mock Server")

# Simple in-memory list of connected websockets
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        if not self.active:
            return
        data = json.dumps(message)
        # send concurrently
        await asyncio.gather(*(ws.send_text(data) for ws in self.active), return_exceptions=True)

manager = ConnectionManager()

# Health endpoint
@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})

# Simple inference REST endpoint: upload a window (channels x samples)
@app.post("/infer")
async def infer(payload: dict):
    # payload = {"modality":"EEG", "data":[[...],[...]], "fs":250}
    # This mock returns a random label and confidence.
    mod = payload.get("modality", "unknown")
    # a deterministic-ish dummy based on mean
    arr = np.array(payload.get("data", [[0]]))
    score = float(np.abs(arr.mean())) % 1.0
    label = "EVENT" if score > 0.5 else "NO_EVENT"
    return {"source": mod, "pred": {"label": label, "prob": round(score, 3)}}

# WebSocket endpoint: clients connect here to receive live decoded messages
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # This server expects no messages from clients; keep connection alive
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        manager.disconnect(ws)

# Background simulator task (starts when app starts)
async def sensor_simulator_task():
    """
    Periodically generate per-modality windows, run dummy per-modality 'predict',
    then broadcast JSON messages via manager.broadcast().
    """
    modalities = ["EEG", "EMG", "EOG"]
    fs = 250
    chans = {"EEG": 8, "EMG": 2, "EOG": 2}
    while True:
        for mod in modalities:
            # simulate window: channels x samples (1s window)
            samples = fs
            ch = chans[mod]
            # generate a band-limited (pseudo) signal with occasional events
            t = np.linspace(0, 1, samples, endpoint=False)
            base = 0.1 * np.random.randn(ch, samples)
            # sometimes add a stronger transient (simulate blink/jaw/motor)
            if np.random.rand() < 0.15:
                transient = np.outer(np.ones(ch), np.exp(-((t-0.5)**2)/(2*(0.05**2))))
                base += 2.0 * transient
            window = base.tolist()
            # fake model scoring
            mean_abs = float(np.mean(np.abs(base)))
            prob = min(1.0, mean_abs / 0.5)
            label = "ACTIVITY" if prob > 0.3 else "REST"
            message = {
                "source": mod,
                "timestamp": int(asyncio.get_event_loop().time() * 1000),
                "pred": {"label": label, "prob": round(prob, 3)},
                "window": window,
                "fs": fs
            }
            await manager.broadcast(message)
            await asyncio.sleep(0.2)  # small gap between modality messages
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    # launch simulator background task
    asyncio.create_task(sensor_simulator_task())

if __name__ == "__main__":
    # Windows selector policy sometimes avoids asyncio quirks (optional)
    try:
        import os, asyncio
        if os.name == "nt":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


def init_chords_serial(port='/dev/pts/2', baudrate=115200):
    """Initialize serial connection to Chords"""
    global chords_serial
    try:
        chords_serial = serial.Serial(port, baudrate, timeout=1)
        print(f"✓ Chords serial connected: {port}")
    except Exception as e:
        print(f"✗ Chords serial failed: {e}")

async def send_to_chords(window, channels=8):
    """Send data window to Chords via serial"""
    if chords_serial is None:
        return
    
    try:
        # Send each sample in the window
        for i in range(window.shape[1]):  # Iterate over time samples
            sample = window[:channels, i]  # Get all channels at time i
            line = ",".join([f"{int(v*100)}" for v in sample]) + "\n"
            chords_serial.write(line.encode('utf-8'))
            await asyncio.sleep(0.004)  # 250 Hz = 4ms between samples
    except Exception as e:
        print(f"Chords send error: {e}")

# Add to sensor_simulator_task():
# await send_to_chords(base)