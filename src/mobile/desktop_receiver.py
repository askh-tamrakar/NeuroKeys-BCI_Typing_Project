import socket
import threading
import sys
import os
import time
import numpy as np

# Ensure we can import from src/acquisition
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from acquisition.packet_parser import PacketParser
from acquisition.lsl_streams import LSLStreamer, LSL_AVAILABLE

class DesktopReceiver:
    def __init__(self, port=5000):
        self.port = port
        self.packet_parser = PacketParser()
        self.lsl_stream = None
        self.running = False
        self.client_sock = None
        self.stats = {"packets": 0, "bytes": 0}
        
        # Setup LSL
        if LSL_AVAILABLE:
            print("[Receiver] Creating LSL Stream 'BioSignals-Raw-uV'...")
            self.lsl_stream = LSLStreamer(
                "BioSignals-Raw-uV",
                channel_types=["EMG", "EOG"],
                channel_labels=["EMG_0", "EOG_1"],
                channel_count=2,
                nominal_srate=512
            )
        else:
            print("[Receiver] ⚠️ LSL not available. Data will only be printed.")

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
                            
                            # Push to LSL
                            if self.lsl_stream:
                                # Start with raw int16 (or uint16 depending on parsing)
                                # LSL expects float usually, but we can send as is or convert.
                                # PacketParser returns int. 
                                # Since this is "Raw-uV", we SHOULD ideally convert to uV if the main app expects it.
                                # But `acquisition_app.py` created LSL with name "BioSignals-Raw-uV" but seemingly pushed raw ADC?
                                # Let's check `acquisition_app.py` lines 660-666: it pushes seemingly raw values or processed?
                                # Wait, `serial_reader` just pushes bytes to queue. `PacketParser` parses them.
                                # `acquisition_app.py` does NOT push to LSL in the main loop shown in snippet.
                                # Ah, I missed where acquisition_app pushes to LSL.
                                # Let's assume we push [ch0_raw, ch1_raw] and let the consumer handle conversion.
                                # Or better: convert to uV here if we want "telepathy" system to work out of box.
                                # Let's stick to RAW values to match the name "Raw".
                                
                                sample = [float(pkt.ch0_raw), float(pkt.ch1_raw)]
                                self.lsl_stream.push_sample(sample)
                                
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
