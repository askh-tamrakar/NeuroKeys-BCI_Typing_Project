import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import socket
import struct
import queue
from datetime import datetime
import sys
import os

# Try to import serial, but handle if missing (for testing on non-mobile envs)
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

# Try to import matplotlib (Pydroid 3 usually has it)
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# -----------------------------------------------------------------------------
# SERIAL READER (Simplified copy to avoid dependency issues on mobile)
# -----------------------------------------------------------------------------
class MobileSerialReader:
    def __init__(self, port, baud=230400, packet_len=8):
        self.port = port
        self.baud = baud
        self.packet_len = packet_len
        self.ser = None
        self.is_running = False
        self.data_queue = queue.Queue(maxsize=1000) # Tuples of (raw_bytes, timestamp)
        self.raw_queue = queue.Queue(maxsize=2000)  # Pure bytes for TCP streaming
        
        # Stats
        self.packets_read = 0
    
    def connect(self):
        if not SERIAL_AVAILABLE:
            raise Exception("pyserial not installed")
        self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
        return True

    def start(self):
        self.is_running = True
        threading.Thread(target=self._read_loop, daemon=True).start()

    def stop(self):
        self.is_running = False
        if self.ser:
            try:
                self.ser.close()
            except:
                pass

    def _read_loop(self):
        buffer = bytearray()
        sync1, sync2 = 0xC7, 0x7C
        end_byte = 0x01
        
        while self.is_running:
            if not self.ser or not self.ser.is_open:
                time.sleep(0.1)
                continue
                
            try:
                if self.ser.in_waiting:
                    chunk = self.ser.read(self.ser.in_waiting)
                    buffer.extend(chunk)
                    
                    # Process
                    i = 0
                    while i <= len(buffer) - self.packet_len:
                        if buffer[i] == sync1 and buffer[i+1] == sync2:
                            if buffer[i + self.packet_len - 1] == end_byte:
                                pkt = bytes(buffer[i : i + self.packet_len])
                                
                                # Send to Queues
                                try:
                                    self.raw_queue.put_nowait(pkt)
                                    # Also decode for local plot (if queue not full)
                                    if self.data_queue.qsize() < 500:
                                        self.data_queue.put_nowait((pkt, time.time()))
                                    self.packets_read += 1
                                except queue.Full:
                                    pass
                                    
                                i += self.packet_len
                            else:
                                i += 1
                        else:
                            i += 1
                    
                    if i > 0:
                        del buffer[:i]
                else:
                    time.sleep(0.005)
            except Exception as e:
                print(f"Serial Error: {e}")
                time.sleep(1)

# -----------------------------------------------------------------------------
# TCP STREAMER
# -----------------------------------------------------------------------------
class TCPStreamer:
    def __init__(self, ip, port=5000):
        self.ip = ip
        self.port = port
        self.sock = None
        self.is_connected = False
        self.queue = queue.Queue(maxsize=5000)
        self.running = False
        self.bytes_sent = 0
        
    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.is_connected = True
            self.running = True
            threading.Thread(target=self._send_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"TCP Connect Error: {e}")
            return False

    def disconnect(self):
        self.running = False
        self.is_connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

    def send_packet(self, data):
        if not self.is_connected:
            return
        try:
            self.queue.put_nowait(data)
        except queue.Full:
            pass

    def _send_loop(self):
        batch = bytearray()
        while self.running:
            try:
                # Small batching for network efficiency
                try:
                    data = self.queue.get(timeout=0.2)
                    batch.extend(data)
                    
                    # Drain queue
                    while len(batch) < 1024:
                        try:
                            d = self.queue.get_nowait()
                            batch.extend(d)
                        except queue.Empty:
                            break
                            
                    if batch:
                        self.sock.sendall(batch)
                        self.bytes_sent += len(batch)
                        batch.clear()
                        
                except queue.Empty:
                    pass # Keep alive check?
                    
            except Exception as e:
                print(f"TCP Send Error: {e}")
                self.is_connected = False
                self.running = False
                break

# -----------------------------------------------------------------------------
# MAIN APP
# -----------------------------------------------------------------------------
class MobileApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NeuroAcq Mobile")
        self.root.geometry("400x800") # Mobile portrait aspect ratio
        
        # State
        self.serial = None
        self.tcp = None
        self.streaming = False
        
        # UI Setup
        self._setup_ui()
        
        # Update Loop
        self.root.after(100, self._update_stats_loop)
        if MATPLOTLIB_AVAILABLE:
            self._setup_plot()
            self.root.after(50, self._update_plot_loop)

    def _setup_ui(self):
        style = ttk.Style()
        style.configure('Big.TButton', font=('Helvetica', 12, 'bold'), padding=10)
        
        # 1. Connection Frame
        conn_frame = ttk.LabelFrame(self.root, text="Hardware & Network")
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        # Serial Port
        ttk.Label(conn_frame, text="Serial Port:").pack(anchor="w")
        self.port_var = tk.StringVar(value="/dev/ttyUSB0") # Default for Android OTG
        ttk.Entry(conn_frame, textvariable=self.port_var).pack(fill="x", pady=2)
        
        # TCP IP
        ttk.Label(conn_frame, text="Desktop IP:").pack(anchor="w")
        self.ip_var = tk.StringVar(value="192.168.1.5")
        ttk.Entry(conn_frame, textvariable=self.ip_var).pack(fill="x", pady=2)
        
        # Connect Buttons
        btn_frame = ttk.Frame(conn_frame)
        btn_frame.pack(fill="x", pady=5)
        
        self.btn_hw = ttk.Button(btn_frame, text="1. Connect HW", command=self.toggle_hw)
        self.btn_hw.pack(side="left", fill="x", expand=True, padx=2)
        
        self.btn_net = ttk.Button(btn_frame, text="2. Connect Net", command=self.toggle_net)
        self.btn_net.pack(side="left", fill="x", expand=True, padx=2)

        # 2. Control Frame
        ctrl_frame = ttk.LabelFrame(self.root, text="Acquisition")
        ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_stream = ttk.Button(ctrl_frame, text="START STREAMING", style='Big.TButton', command=self.toggle_stream, state="disabled")
        self.btn_stream.pack(fill="x", pady=5)
        
        # 3. Stats Frame
        stats_frame = ttk.LabelFrame(self.root, text="Status")
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_status = ttk.Label(stats_frame, text="Ready", foreground="blue")
        self.lbl_status.pack(anchor="w")
        self.lbl_packets = ttk.Label(stats_frame, text="Pkts Sent: 0")
        self.lbl_packets.pack(anchor="w")
        
        # 4. Graph Placeholder
        self.graph_frame = ttk.Frame(self.root)
        self.graph_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _setup_plot(self):
        if not MATPLOTLIB_AVAILABLE:
            ttk.Label(self.graph_frame, text="Matplotlib not found").pack()
            return

        self.fig = Figure(figsize=(4, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title("Live Signal (CH0)")
        self.ax.set_ylim(0, 4096)
        self.line, = self.ax.plot(np.zeros(200), 'r-')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.plot_buffer = np.zeros(200)

    def toggle_hw(self):
        if self.serial:
            # Disconnect
            self.serial.stop()
            self.serial = None
            self.btn_hw.config(text="1. Connect HW")
            self.lbl_status.config(text="Hardware Disconnected", foreground="red")
        else:
            # Connect
            port = self.port_var.get()
            try:
                self.serial = MobileSerialReader(port)
                self.serial.connect()
                self.serial.start()
                self.btn_hw.config(text="Disconnect HW")
                self.lbl_status.config(text="Hardware OK", foreground="green")
                self._check_ready()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def toggle_net(self):
        if self.tcp:
            # Disconnect
            self.tcp.disconnect()
            self.tcp = None
            self.btn_net.config(text="2. Connect Net")
            self.lbl_status.config(text="Network Disconnected", foreground="red")
        else:
            # Connect
            ip = self.ip_var.get()
            try:
                self.tcp = TCPStreamer(ip)
                if self.tcp.connect():
                    self.btn_net.config(text="Disconnect Net")
                    self.lbl_status.config(text="Network OK", foreground="green")
                    self._check_ready()
                else:
                    raise Exception("Connection Failed")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _check_ready(self):
        if self.serial and self.tcp and self.tcp.is_connected:
            self.btn_stream.config(state="normal")
        else:
            self.btn_stream.config(state="disabled")

    def toggle_stream(self):
        self.streaming = not self.streaming
        if self.streaming:
            self.btn_stream.config(text="STOP STREAMING")
            if self.serial and self.serial.ser:
                self.serial.ser.write(b"START\n")
        else:
            self.btn_stream.config(text="START STREAMING")
            if self.serial and self.serial.ser:
                self.serial.ser.write(b"STOP\n")

    def _update_stats_loop(self):
        if self.tcp:
            self.lbl_packets.config(text=f"Bytes Sent: {self.tcp.bytes_sent}")
        
        # Push from Serial to TCP
        if self.streaming and self.serial and self.tcp:
            try:
                # Move all available raw packets to TCP
                while True:
                    pkt = self.serial.raw_queue.get_nowait()
                    self.tcp.send_packet(pkt)
            except queue.Empty:
                pass
                
        self.root.after(100, self._update_stats_loop)

    def _update_plot_loop(self):
        if not self.streaming or not self.serial:
            self.root.after(100, self._update_plot_loop)
            return
            
        # Update plot buffer
        updated = False
        try:
            # Consume up to 50 packets to avoid lag
            for _ in range(50):
                pkt, ts = self.serial.data_queue.get_nowait()
                # Parse CH0 (bytes 2,3) -> >H
                val = struct.unpack_from(">H", pkt, 2)[0]
                self.plot_buffer = np.roll(self.plot_buffer, -1)
                self.plot_buffer[-1] = val
                updated = True
        except queue.Empty:
            pass
            
        if updated:
            self.line.set_ydata(self.plot_buffer)
            self.canvas.draw_idle()
            
        self.root.after(50, self._update_plot_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = MobileApp(root)
    root.mainloop()
