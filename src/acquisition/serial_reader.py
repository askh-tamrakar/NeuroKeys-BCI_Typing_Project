# src/acquisition/serial_reader.py
"""
SerialPacketReader - Fixed & Production-Ready
- Robust threaded serial reader with packet sync
- Proper connection management
- Complete parenthesis and error handling
"""

from typing import Optional, Dict
import time
import queue
import threading
import serial

class SerialPacketReader:
    def __init__(
        self, 
        port: str, 
        baud: int = 230400, 
        packet_len: int = 8,
        sync1: int = 0xC7, 
        sync2: int = 0x7C, 
        end_byte: int = 0x01,
        connect_timeout: float = 3.0, 
        max_queue: int = 10000
    ):
        """Initialize serial reader"""
        self.port = port
        self.baud = baud
        self.packet_len = packet_len
        self.sync1 = sync1
        self.sync2 = sync2
        self.end_byte = end_byte
        self.connect_timeout = connect_timeout
        self.ser: Optional[serial.Serial] = None
        self.is_running = False
        self.data_queue: queue.Queue = queue.Queue(maxsize=max_queue)
        
        # Stats
        self.packets_received = 0
        self.packets_dropped = 0
        self.sync_errors = 0
        self.bytes_received = 0
        self.duplicates = 0
        self.last_packet_time = None
        
        # Internal
        self._read_thread: Optional[threading.Thread] = None

    def connect(self) -> bool:
        """Connect to serial port"""
        try:
            print(f"[SerialReader] Connecting to {self.port} at {self.baud} baud...")
            self.ser = serial.Serial(
                self.port,
                self.baud,
                timeout=0.1,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE
            )
            
            print(f"[SerialReader] Port opened, waiting {self.connect_timeout}s for Arduino...")
            time.sleep(self.connect_timeout)
            
            # Clear buffers
            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            except Exception:
                pass
            
            print(f"[SerialReader] ✅ Connected to {self.port}")
            return True
        except Exception as e:
            print(f"[SerialReader] ❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from serial port"""
        self.is_running = False
        if self.ser and getattr(self.ser, "is_open", False):
            try:
                self.ser.close()
            except Exception:
                pass

    def start(self):
        """Start reading thread"""
        if self.is_running:
            return
        self.is_running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        print("[SerialReader] Reading thread started")

    def stop(self):
        """Stop reading thread"""
        self.is_running = False
        if self._read_thread:
            self._read_thread.join(timeout=0.1)

    def send_command(self, cmd: str) -> bool:
        """Send command to device"""
        if not (self.ser and getattr(self.ser, "is_open", False)):
            return False
        try:
            self.ser.write(f"{cmd}\n".encode())
            self.ser.flush()
            return True
        except Exception as e:
            print(f"[SerialReader] Send failed: {e}")
            return False

    def _read_loop(self):
        """Main reading loop"""
        buffer = bytearray()
        while self.is_running:
            if not (self.ser and getattr(self.ser, "is_open", False)):
                time.sleep(0.1)
                continue
            try:
                available = self.ser.in_waiting
                if available:
                    chunk = self.ser.read(min(available, 4096))
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                        self._process_buffer(buffer)
                else:
                    time.sleep(0.001)
            except Exception as e:
                print(f"[SerialReader] Read error: {e}")
                time.sleep(0.05)

    def _process_buffer(self, buffer: bytearray):
        """Process incoming buffer for valid packets"""
        while len(buffer) >= self.packet_len:
            if buffer[0] == self.sync1 and buffer[1] == self.sync2:
                # Candidate packet
                if buffer[self.packet_len - 1] == self.end_byte:
                    packet_bytes = bytes(buffer[:self.packet_len])
                    try:
                        self.data_queue.put_nowait(packet_bytes)
                        self.packets_received += 1
                        self.last_packet_time = time.time()
                    except queue.Full:
                        self.packets_dropped += 1
                    del buffer[:self.packet_len]
                else:
                    # Bad end byte
                    del buffer[0]
                    self.sync_errors += 1
            else:
                # Not synced
                del buffer[0]
                self.sync_errors += 1

    def get_packet(self, timeout: float = 0.1) -> Optional[bytes]:
        """Get next packet from queue"""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_stats(self) -> Dict:
        """Get reader statistics"""
        elapsed = time.time() - self.last_packet_time if self.last_packet_time else 0
        rate = self.packets_received / elapsed if elapsed > 0 else 0
        speed_kbps = (self.bytes_received / elapsed / 1024) if elapsed > 0 else 0
        return {
            "packets_received": self.packets_received,
            "packets_dropped": self.packets_dropped,
            "sync_errors": self.sync_errors,
            "duplicates": self.duplicates,
            "rate_hz": rate,
            "speed_kbps": speed_kbps,
            "queue_size": self.data_queue.qsize(),
        }
