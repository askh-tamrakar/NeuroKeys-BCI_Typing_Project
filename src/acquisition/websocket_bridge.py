"""
WebSocket Bridge - Sends filtered data to web frontend via WebSocket
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')  # Windows emoji fix
import asyncio
import websockets
import json
import threading
from queue import Queue
from datetime import datetime


class WebSocketBridge:
    """Manages WebSocket connection to broadcast filtered data to web clients"""
    
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.data_queue = Queue()
        self.clients = set()
        self.running = False
        self.thread = None
        self.loop = None
        
    def start(self):
        """Start WebSocket server in background thread"""
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        print(f"🔌 WebSocket server starting on ws://{self.host}:{self.port}")
    
    def stop(self):
        """Stop WebSocket server"""
        self.running = False
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)
    
    def send_data(self, data):
        """Queue data to be sent to all connected clients"""
        self.data_queue.put(data)
    
    def _run_server(self):
        """Run the WebSocket server event loop"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._start_server())
            # Keep broadcasting while running
            while self.running:
                try:
                    self.loop.run_until_complete(self._broadcast_data())
                except Exception as e:
                    print(f"Broadcast error: {e}")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.loop.close()
    
    async def _start_server(self):
        """Start WebSocket server"""
        async with websockets.serve(self._handle_client, self.host, self.port):
            print(f"✅ WebSocket server listening on ws://{self.host}:{self.port}")
            # Keep server running
            while self.running:
                await asyncio.sleep(0.1)
    
    async def _handle_client(self, websocket):
        """Handle new client connection"""
        self.clients.add(websocket)
        print(f"✅ Client connected. Total: {len(self.clients)}")
        
        try:
            async for message in websocket:
                # Handle incoming messages (e.g., commands)
                try:
                    data = json.loads(message)
                    print(f"📨 Received from client: {data}")
                except json.JSONDecodeError:
                    pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            print(f"❌ Client disconnected. Total: {len(self.clients)}")
    
    async def _broadcast_data(self):
        """Broadcast queued data to all connected clients"""
        if not self.data_queue.empty():
            try:
                data = self.data_queue.get_nowait()
                
                # Format for WebSocket transmission
                message = {
                    "type": "signal_data",
                    "timestamp": datetime.now().isoformat(),
                    "data": data
                }
                
                # Send to all connected clients
                if self.clients:
                    message_str = json.dumps(message)
                    # Create tasks for all clients
                    tasks = [client.send(message_str) for client in self.clients]
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                print(f"Error broadcasting: {e}")
        
        await asyncio.sleep(0.001)  # Small delay to prevent busy waiting
    
    async def _shutdown(self):
        """Shutdown server"""
        self.running = False


if __name__ == "__main__":
    # Test the WebSocket bridge
    bridge = WebSocketBridge()
    bridge.start()
    
    import time
    try:
        for i in range(10):
            bridge.send_data({
                "ch0": {"type": "EEG", "filtered": float(i)},
                "ch1": {"type": "EOG", "filtered": float(i*2)}
            })
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
