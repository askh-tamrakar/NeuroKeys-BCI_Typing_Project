import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
from typing import List
import serial  # kept in case you wire real hardware later

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

# Continuous streaming simulator task (starts when app starts)
async def sensor_streaming_task():
    """
    Instead of sending 1s windows, this function streams continuous chunks of samples
    for each modality. Each broadcast contains a small chunk (channels x chunk_samples).
    Clients can concatenate chunks to reconstruct the continuous signal.
    """
    modalities = ["EEG", "EMG", "EOG"]
    fs = 250  # samples per second
    chans = {"EEG": 8, "EMG": 2, "EOG": 2}
    # chunk duration in seconds (how often we send data). Choose small for continuous feeling.
    chunk_dur = 0.1  # 100 ms per chunk
    chunk_size = max(1, int(fs * chunk_dur))  # number of samples per chunk

    # Maintain phase (time offset) per modality so signal is continuous between chunks
    phase = {mod: 0.0 for mod in modalities}
    # occasionally inject a transient event that lasts several chunks
    transient_state = {mod: {"active": False, "remaining_samples": 0, "amplitude": 0.0} for mod in modalities}

    # Simple streaming loop
    loop = asyncio.get_event_loop()
    while True:
        start_time = loop.time()
        for mod in modalities:
            ch = chans[mod]
            # generate time vector for this chunk (relative)
            t = (np.arange(chunk_size) + phase[mod] * fs) / fs
            # base = small gaussian noise per channel
            base = 0.05 * np.random.randn(ch, chunk_size)

            # add a rhythmic component to make the signal look more realistic
            # different base frequency per modality
            if mod == "EEG":
                freq = 10.0  # alpha-ish
            elif mod == "EMG":
                freq = 60.0  # higher broadband
            else:  # EOG
                freq = 1.0  # slow drift / eye movement
            for c in range(ch):
                phase_shift = np.random.uniform(0, 2 * np.pi)
                base[c] += 0.02 * np.sin(2 * np.pi * freq * t + phase_shift)

            # transient injection logic (simulate blink/jaw/motor)
            if not transient_state[mod]["active"] and np.random.rand() < 0.02:
                # start a transient lasting 0.1-0.5s
                dur_secs = np.random.uniform(0.1, 0.5)
                transient_state[mod]["active"] = True
                transient_state[mod]["remaining_samples"] = int(fs * dur_secs)
                transient_state[mod]["amplitude"] = np.random.uniform(0.8, 2.5)

            if transient_state[mod]["active"]:
                # create an envelope for this chunk
                rem = transient_state[mod]["remaining_samples"]
                apply_samples = min(rem, chunk_size)
                env = np.zeros(chunk_size)
                # simple half-gaussian on the applied samples
                env_part = np.exp(-np.linspace(0, 3, apply_samples) ** 2)
                env[:apply_samples] = env_part
                # apply the transient across all channels
                for c in range(ch):
                    base[c, :chunk_size] += transient_state[mod]["amplitude"] * env
                transient_state[mod]["remaining_samples"] -= apply_samples
                if transient_state[mod]["remaining_samples"] <= 0:
                    transient_state[mod]["active"] = False
                    transient_state[mod]["amplitude"] = 0.0

            # update phase (advance time)
            phase[mod] += chunk_size / fs

            window = base.tolist()  # channels x samples for this chunk

            # compute a lightweight running score/pred on this chunk
            mean_abs = float(np.mean(np.abs(base)))
            prob = min(1.0, mean_abs / 0.5)
            label = "ACTIVITY" if prob > 0.3 else "REST"

            message = {
                "source": mod,
                "timestamp": int(loop.time() * 1000),
                "pred": {"label": label, "prob": round(prob, 3)},
                # Chunk-level streaming payload: 'chunk_samples' and data as channels x samples
                "chunk_samples": chunk_size,
                "fs": fs,
                "stream": True,
                "window": window,  # keep the same key name 'window' but now it's a short chunk
            }

            await manager.broadcast(message)

            # small gap between modalities so that combined streaming roughly matches real-time
            # sending per-modality chunk at the rate chunk_dur (we'll await per-mod below)
            await asyncio.sleep(0)  # yield to event loop

        # Wait until chunk_dur has elapsed since start of this iteration to maintain real-time rate
        elapsed = loop.time() - start_time
        wait_for = max(0.0, chunk_dur - elapsed)
        await asyncio.sleep(wait_for)

@app.on_event("startup")
async def startup_event():
    # launch streaming simulator background task
    asyncio.create_task(sensor_streaming_task())

if __name__ == "__main__":
    # Windows selector policy sometimes avoids asyncio quirks (optional)
    try:
        import os, asyncio as _asyncio
        if os.name == "nt":
            _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
