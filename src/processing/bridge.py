import asyncio
import json
import threading
import websockets
from queue import Queue, Empty

class DataBridge:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.clients = set()
        self.running = False
        self.msg_queue = Queue()

    def start(self):
        if not self.running:
            self.running = True
            self.thread.start()
            print(f"WebSocket Bridge started on ws://{self.host}:{self.port}")

    def stop(self):
        self.running = False
        # The loop runs in a daemon thread, so it will die with main, 
        # but a clean shutdown would be better in production.

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        # Serve the websocket
        start_server = websockets.serve(self._handler, self.host, self.port)
        self.loop.run_until_complete(start_server)
        
        # Start a broadcaster task
        self.loop.create_task(self._broadcaster())
        
        self.loop.run_forever()

    async def _handler(self, websocket, path):
        # Register
        self.clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)

    async def _broadcaster(self):
        while True:
            try:
                # Check for messages in the queue non-blocking via asyncio.sleep polling
                # Or use an async queue. Here we use a simple poll for simplicity with thread queue.
                while not self.msg_queue.empty():
                    msg = self.msg_queue.get_nowait()
                    if self.clients:
                        # Broadcast to all
                        payload = json.dumps(msg)
                        await asyncio.gather(
                            *[client.send(payload) for client in self.clients],
                            return_exceptions=True
                        )
                await asyncio.sleep(0.01) # 100Hz max poll rate
            except Exception as e:
                print(f"Broadcast error: {e}")
                await asyncio.sleep(1)

    def broadcast(self, data):
        """Thread-safe method to queue data for broadcasting"""
        if self.running:
            self.msg_queue.put(data)
