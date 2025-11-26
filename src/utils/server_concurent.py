# server_concurrent.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio, json

app = FastAPI()

async def reader(ws: WebSocket, stop_event: asyncio.Event):
    try:
        while not stop_event.is_set():
            data = await ws.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                continue
            if payload.get("type") == "ping":
                server_recv = int(asyncio.get_event_loop().time() * 1000)
                resp = {
                    "type": "pong",
                    "id": payload.get("id"),
                    "t0": payload.get("t0"),
                    "server_recv": server_recv,
                    "server_send": server_recv
                }
                await ws.send_text(json.dumps(resp))
    except Exception:
        pass

async def writer_stub(ws: WebSocket, stop_event: asyncio.Event):
    # example: send periodic data (your simulator)
    try:
        while not stop_event.is_set():
            await asyncio.sleep(1.0)
            # optionally send sensor data here
            # await ws.send_text(json.dumps(...))
    except Exception:
        pass
