import asyncio
import json
import threading
import websockets
from queue import Queue, Empty
import time


class DataBridge:
    def __init__(self, host="0.0.0.0", port=8765):
        self.host = host
        self.port = port
        self.loop = None
        self.thread = None
        self.clients = set()
        self.running = False
        self.msg_queue = Queue()
        self.command_queue = Queue()
        self.server_ready = threading.Event()
        
    def get_command(self):
        try:
            return self.command_queue.get_nowait()
        except Empty:
            return None

    def start(self):
        """Start WebSocket server in background thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, daemon=False)
            self.thread.start()
            
            if self.server_ready.wait(timeout=5):
                print(f"✅ WebSocket Bridge ready on ws://{self.host}:{self.port}")
            else:
                print(f"⚠️  WebSocket Bridge may not be ready (timeout)")

    def stop(self):
        """Stop the WebSocket server"""
        self.running = False
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._shutdown(), self.loop)

    def _run_loop(self):
        """Run asyncio event loop in thread"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._main())
        except Exception as e:
            print(f"❌ Bridge loop error: {e}")
        finally:
            self.loop.close()

    async def _main(self):
        """Main async entry point"""
        try:
            print(f"🔌 Starting WebSocket server on ws://{self.host}:{self.port}...")
            
            # Start broadcaster task
            broadcaster_task = asyncio.create_task(self._broadcaster())
            
            # Start WebSocket server
            async with websockets.serve(
                self._handler, 
                self.host, 
                self.port,
                ping_interval=20,
                ping_timeout=10
            ):
                print(f"✅ WebSocket Server listening on ws://{self.host}:{self.port}")
                self.server_ready.set()
                
                # Keep server running
                await asyncio.Future()
                
        except Exception as e:
            print(f"❌ WebSocket server error: {e}")
            self.server_ready.set()
            raise

    async def _shutdown(self):
        """Graceful shutdown"""
        print("🛑 Shutting down WebSocket server...")
        self.running = False

    async def _handler(self, websocket):
        """Handle client connections
        
        Note: websockets >= v12 only passes (websocket), not (websocket, path)
        """
        client_addr = websocket.remote_address
        print(f"✨ Client connected: {client_addr}")
        self.clients.add(websocket)
        
        try:
            async for message in websocket:
                try:
                    # Try to parse JSON
                    data = json.loads(message)
                    # Queue for command processing
                    self.command_queue.put(data)
                    print(f"📥 Received command: {data.get('type', 'unknown')}")
                except json.JSONDecodeError:
                    print(f"⚠️  Received invalid JSON from {client_addr}")
                    
        except websockets.exceptions.ConnectionClosed:
            print(f"❌ Client disconnected: {client_addr}")
        finally:
            self.clients.discard(websocket)

    async def _broadcaster(self):
        """Broadcast queued messages to all connected clients"""
        print("📡 Broadcaster started")
        
        while self.running:
            try:
                # Non-blocking check for queued messages
                while not self.msg_queue.empty():
                    try:
                        msg_data = self.msg_queue.get_nowait()
                        
                        # Convert to JSON if it's a dict
                        if isinstance(msg_data, dict):
                            payload = json.dumps(msg_data)
                        elif isinstance(msg_data, str):
                            payload = msg_data
                        else:
                            payload = str(msg_data)
                        
                        # Broadcast to all connected clients
                        if self.clients:
                            await asyncio.gather(
                                *[client.send(payload) for client in self.clients],
                                return_exceptions=True
                            )
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        print(f"⚠️  Broadcast error: {e}")
                
                # Sleep briefly before checking queue again
                await asyncio.sleep(0.01)
                
            except asyncio.CancelledError:
                print("📡 Broadcaster stopped")
                break
            except Exception as e:
                print(f"❌ Broadcaster error: {e}")
                await asyncio.sleep(1)

    def broadcast(self, data):
        """Thread-safe method to queue data for broadcasting
        
        Args:
            data: dict, string (JSON), or any object that can be converted to string
        """
        if self.running and self.loop:
            try:
                self.msg_queue.put(data)
            except Exception as e:
                print(f"❌ Failed to queue broadcast: {e}")


if __name__ == "__main__":
    # Test the bridge
    bridge = DataBridge()
    bridge.start()
    
    try:
        # Keep running and send test messages
        for i in range(10):
            time.sleep(1)
            test_msg = {
                "source": "EMG",
                "fs": 512,
                "timestamp": int(time.time() * 1000),
                "window": [[8192], [8192]],
                "test_count": i
            }
            bridge.broadcast(test_msg)
            print(f"[Test] Sent message {i}")
        
        print("Test complete. Server running for 30 more seconds...")
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down...")
    finally:
        bridge.stop()
        time.sleep(1)