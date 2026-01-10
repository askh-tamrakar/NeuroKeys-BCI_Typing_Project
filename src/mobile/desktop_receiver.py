import socket
import threading
import sys
import os
import time
import numpy as np
import struct


# Ensure we can import from src/acquisition
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from acquisition.packet_parser import PacketParser
from acquisition.packet_parser import PacketParser


class DesktopReceiver:
    def __init__(self, port=5000):
        self.port = port
        self.packet_parser = PacketParser()
        self.lsl_stream = None
        self.running = False
        self.client_sock = None
        self.stats = {"packets": 0, "bytes": 0}
        
        self.stats = {"packets": 0, "bytes": 0}
        
        # Connect to Stream Manager
        self.stream_socket = None
        self._connect_stream()
        
    def _connect_stream(self):
        try:
            self.stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.stream_socket.connect(('localhost', 6000))
            print("[Receiver] ✅ Connected to Stream Manager (Raw)")
        except Exception as e:
            print(f"[Receiver] ⚠️ Could not connect to Stream Manager: {e}")
            self.stream_socket = None


    def start(self):
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.bind(('0.0.0.0', self.port))
        self.server_sock.listen(1)
        
        print(f"[Receiver] 🎧 Listening on 0.0.0.0:{self.port}")
        print("[Receiver] Press Ctrl+C to stop.")
        
        threading.Thread(target=self._stats_loop, daemon=True).start()
        
        try:
            while self.running:
                print("[Receiver] Waiting for mobile connection...")
                client, addr = self.server_sock.accept()
                print(f"[Receiver] ✅ Connected to {addr}")
                self._handle_client(client)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.server_sock:
            self.server_sock.close()

    def _handle_client(self, conn):
        self.client_sock = conn
        buffer = bytearray()
        
        try:
            while self.running:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                
                self.stats["bytes"] += len(chunk)
                buffer.extend(chunk)
                
                # Parse
                i = 0
                packet_len = 8
                # We trust the mobile app sends valid packets, but we still parse 
                # because TCP stream boundaries are arbitrary.
                # However, mobile app sends RAW bytes with headers.
                # Use existing packet parser logic or simple sync check.
                
                # Re-use the robust parsing logic from serial_reader concept
                # "MobileSerialReader" on phone sends raw bytes.
                # So we expect Sync1, Sync2...
                
                while i <= len(buffer) - packet_len:
                    if buffer[i] == 0xC7 and buffer[i+1] == 0x7C:
                        pkt_bytes = buffer[i : i + packet_len]
                        try:
                            pkt = self.packet_parser.parse(pkt_bytes)
                            
                            # Push to Stream Manager
                            if self.stream_socket:
                                try:
                                    # Samples are Ch0, Ch1 (Raw ADC but treated as uV or raw)
                                    # Assuming PacketParser returns raw ADC. The mobile app sends raw.
                                    # Acquisition App converts to uV. Receiver implies input is Raw-uV?
                                    # Line 30 was "BioSignals-Raw-uV".
                                    # Line 112: sample = [float(pkt.ch0_raw), float(pkt.ch1_raw)]
                                    # Let's send what we have.
                                    v0 = float(pkt.ch0_raw)
                                    v1 = float(pkt.ch1_raw)
                                    self.stream_socket.sendall(struct.pack('<ff', v0, v1))
                                except Exception:
                                    self.stream_socket = None # Stop trying if broken

                                
                            self.stats["packets"] += 1
                            i += packet_len
                        except Exception:
                            i += 1
                    else:
                        i += 1
                
                if i > 0:
                    del buffer[:i]
                    
        except Exception as e:
            print(f"[Receiver] Error: {e}")
        finally:
            print("[Receiver] ❌ Client disconnected")
            conn.close()

    def _stats_loop(self):
        while self.running:
            time.sleep(1)
            if self.stats["packets"] > 0:
                print(f"[Receiver] Rate: {self.stats['packets']} samples/sec | Total: {self.stats['bytes']/1024:.1f} KB")
                self.stats["packets"] = 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 5000
    
    server = DesktopReceiver(port)
    server.start()
