# scripts/simulate_client.py
import asyncio, websockets, json, numpy as np

async def run(ws_url="ws://localhost:8000/ws"):
    async with websockets.connect(ws_url) as ws:
        while True:
            # wait for messages from server (if server broadcasts)
            msg = await ws.recv()
            print("RECV:", msg)

if __name__ == "__main__":
    asyncio.run(run())
