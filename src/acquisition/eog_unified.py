"""
EOG Signal Acquisition System - Unified v5.0
Real-time visualization with JSON data logging (NO FILTER)
Features: Scrollable panel, Pause/Resume, Latest packet details
Author: BCI Team
Date: 2024-12-05
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import json
import threading
import time
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import deque
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import queue

class EOGAcquisitionApp:
    """EOG Acquisition System with Full Layout - Scrollable Panel, Pause/Resume, Latest Packet Details (NO FILTER)"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Signal Acquisition - v5.0")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')
        
        # Serial connection
        self.ser = None
        self.acquisition_active = False
        self.recording_active = False
        self.acquisition_thread = None
        
        # Data storage
        self.session_data = []
        self.session_start_time = None
        self.packet_count = 0
        self.bytes_received = 0
        self.last_packet = None
        
        # Graph buffers
        self.graph_buffer_ch0 = deque(maxlen=1024)
        self.graph_buffer_ch1 = deque(maxlen=1024)
        self.graph_time_buffer = deque(maxlen=1024)
        self.graph_index = 0
        self.last_graph_update_index = 0
        
        # Packet format constants
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = 512.0
        self.BAUD_RATE = 230400
        self.NUM_CHANNELS = 2
        
        # Default save path
        self.save_path = Path("data/raw/session/eog")
        
        # Queue for thread-safe communication
        self.data_queue = queue.Queue()
        
        # Setup UI
        self.setup_ui()
        self.update_port_list()
        self.root.after(30, self.update_graph_display)
        self.root.after(100, self.process_queue)
    
    def setup_ui(self):
        """Create the user interface with scrollable left panel"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # LEFT COLUMN: Controls (with scrollbar)
        left_wrapper = ttk.Frame(main_frame)
        left_wrapper.pack(side="left", fill="both", expand=False, padx=5)
        
        # Create canvas with scrollbar
        self.canvas = tk.Canvas(left_wrapper, bg='#f0f0f0', highlightthickness=0, width=350)
        scrollbar = ttk.Scrollbar(left_wrapper, orient="vertical", command=self.canvas.yview)
        scrollable_frame = ttk.Frame(self.canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        left_frame = scrollable_frame
        
        # RIGHT COLUMN: Graph
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        
        # ===== CONNECTION SECTION =====
        connection_frame = ttk.LabelFrame(left_frame, text="🔌 Connection", padding="10")
        connection_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(connection_frame, text="COM Port:", font=("Arial", 9)).pack(anchor="w", padx=5, pady=2)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=25, state="readonly")
        self.port_combo.pack(fill="x", padx=5, pady=2)
        
        self.refresh_btn = ttk.Button(connection_frame, text="🔄 Refresh Ports", command=self.update_port_list)
        self.refresh_btn.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(connection_frame, text="Baud: 230400 (Fixed) | 512 Hz", font=("Arial", 8)).pack(anchor="w", padx=5)
        
        # ===== STATUS SECTION =====
        status_frame = ttk.LabelFrame(left_frame, text="📊 Status", padding="10")
        status_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(status_frame, text="Connection:", font=("Arial", 9)).pack(anchor="w", padx=5, pady=1)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial", 10, "bold"))
        self.status_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Packets:", font=("Arial", 9)).pack(anchor="w", padx=5, pady=1)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Duration:", font=("Arial", 9)).pack(anchor="w", padx=5, pady=1)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Rate (Hz):", font=("Arial", 9)).pack(anchor="w", padx=5, pady=1)
        self.rate_label = ttk.Label(status_frame, text="0 Hz", font=("Arial", 10, "bold"))
        self.rate_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Speed (KBps):", font=("Arial", 9)).pack(anchor="w", padx=5, pady=1)
        self.speed_label = ttk.Label(status_frame, text="0 KBps", font=("Arial", 10, "bold"))
        self.speed_label.pack(anchor="w", padx=5, pady=1)
        
        # ===== CONTROL BUTTONS =====
        control_frame = ttk.LabelFrame(left_frame, text="⚙️ Control", padding="10")
        control_frame.pack(fill="x", padx=0, pady=5)
        
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_arduino)
        self.connect_btn.pack(fill="x", padx=2, pady=2)
        
        self.disconnect_btn = ttk.Button(control_frame, text="❌ Disconnect", command=self.disconnect_arduino, state="disabled")
        self.disconnect_btn.pack(fill="x", padx=2, pady=2)
        
        self.start_btn = ttk.Button(control_frame, text="▶️ Start", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", padx=2, pady=2)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", padx=2, pady=2)
        
        # ===== RECORDING CONTROL =====
        recording_frame = ttk.LabelFrame(left_frame, text="⏺️ Recording", padding="10")
        recording_frame.pack(fill="x", padx=0, pady=5)
        
        self.record_btn = ttk.Button(recording_frame, text="⏺️ Start Recording", command=self.start_recording, state="disabled")
        self.record_btn.pack(fill="x", padx=2, pady=2)
        
        self.pause_btn = ttk.Button(recording_frame, text="⏸️ Pause", command=self.pause_recording, state="disabled")
        self.pause_btn.pack(fill="x", padx=2, pady=2)
        
        self.resume_btn = ttk.Button(recording_frame, text="▶️ Resume", command=self.resume_recording, state="disabled")
        self.resume_btn.pack(fill="x", padx=2, pady=2)
        
        # ===== SAVE OPTIONS =====
        save_frame = ttk.LabelFrame(left_frame, text="💾 Save", padding="10")
        save_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Button(save_frame, text="📁 Choose Path", command=self.choose_save_path).pack(fill="x", padx=2, pady=2)
        
        self.path_label = ttk.Label(save_frame, text="data/raw/session/eog", font=("Arial", 8), wraplength=200, justify="left")
        self.path_label.pack(fill="x", padx=2, pady=5)
        
        self.save_data_btn = ttk.Button(save_frame, text="💾 Save Data", command=self.save_session_data, state="disabled")
        self.save_data_btn.pack(fill="x", padx=2, pady=2)
        
        self.export_btn = ttk.Button(save_frame, text="📊 Export Graph", command=self.export_graph, state="disabled")
        self.export_btn.pack(fill="x", padx=2, pady=2)
        
        # ===== STATISTICS =====
        stats_frame = ttk.LabelFrame(left_frame, text="📈 Stats", padding="10")
        stats_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(stats_frame, text="Channel 0 (Vertical):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2, pady=1)
        self.ch0_min_label = ttk.Label(stats_frame, text="Min: 0 µV", font=("Arial", 8))
        self.ch0_min_label.pack(anchor="w", padx=5, pady=0)
        self.ch0_max_label = ttk.Label(stats_frame, text="Max: 0 µV", font=("Arial", 8))
        self.ch0_max_label.pack(anchor="w", padx=5, pady=0)
        self.ch0_mean_label = ttk.Label(stats_frame, text="Mean: 0 µV", font=("Arial", 8))
        self.ch0_mean_label.pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(stats_frame, text="Channel 1 (Horizontal):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2, pady=1)
        self.ch1_min_label = ttk.Label(stats_frame, text="Min: 0 µV", font=("Arial", 8))
        self.ch1_min_label.pack(anchor="w", padx=5, pady=0)
        self.ch1_max_label = ttk.Label(stats_frame, text="Max: 0 µV", font=("Arial", 8))
        self.ch1_max_label.pack(anchor="w", padx=5, pady=0)
        self.ch1_mean_label = ttk.Label(stats_frame, text="Mean: 0 µV", font=("Arial", 8))
        self.ch1_mean_label.pack(anchor="w", padx=5, pady=2)
        
        # ===== LATEST PACKET DETAILS =====
        packet_frame = ttk.LabelFrame(left_frame, text="📋 Latest Packet", padding="10")
        packet_frame.pack(fill="both", expand=True, padx=0, pady=5)
        
        self.packet_tree = ttk.Treeview(packet_frame, columns=('Value',), height=8)
        self.packet_tree.column('#0', width=120)
        self.packet_tree.column('Value', width=80)
        self.packet_tree.heading('#0', text='Field')
        self.packet_tree.heading('Value', text='Value')
        self.packet_tree.pack(fill='both', expand=True)
        
        # ===== GRAPH PANEL =====
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EOG Signal (512 Hz - NO FILTER)", padding="5")
        graph_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')
        
        # Subplot for Ch0
        self.ax_ch0 = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_ch0.plot([], [], color='#FF6B6B', linewidth=1.5, label='Ch0 (Vertical)')
        self.ax_ch0.set_ylabel('Voltage (µV)', fontsize=10)
        self.ax_ch0.set_ylim(-100000, 100000)
        self.ax_ch0.grid(True, alpha=0.3, linestyle='--')
        self.ax_ch0.legend(loc='upper left', fontsize=9)
        self.ax_ch0.set_title('Channel 0: Vertical Eye Movement', fontsize=10, fontweight='bold')
        
        # Subplot for Ch1
        self.ax_ch1 = self.fig.add_subplot(212)
        self.line_ch1, = self.ax_ch1.plot([], [], color='#4ECDC4', linewidth=1.5, label='Ch1 (Horizontal)')
        self.ax_ch1.set_xlabel('Time (samples)', fontsize=10)
        self.ax_ch1.set_ylabel('Voltage (µV)', fontsize=10)
        self.ax_ch1.set_ylim(-100000, 100000)
        self.ax_ch1.grid(True, alpha=0.3, linestyle='--')
        self.ax_ch1.legend(loc='upper left', fontsize=9)
        self.ax_ch1.set_title('Channel 1: Horizontal Eye Movement', fontsize=10, fontweight='bold')
        
        self.fig.tight_layout()
        
        # Embed matplotlib in tkinter
        self.canvas_plot = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas_plot.draw()
        self.canvas_plot.get_tk_widget().pack(fill="both", expand=True)
    
    def update_port_list(self):
        """Refresh available COM ports"""
        ports = []
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{port} - {desc}")
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)
    
    def connect_arduino(self):
        """Connect to Arduino"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        
        port_name = self.port_var.get().split(" ")[0]
        try:
            self.ser = serial.Serial(port_name, self.BAUD_RATE, timeout=1)
            time.sleep(2)
            self.ser.reset_input_buffer()
            self.status_label.config(text="✅ Connected", foreground="green")
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.start_btn.config(state="normal")
            messagebox.showinfo("Success", f"Connected to {port_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")
            self.status_label.config(text="❌ Failed", foreground="red")
    
    def disconnect_arduino(self):
        """Close connection"""
        if self.acquisition_active:
            self.stop_acquisition()
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.status_label.config(text="❌ Disconnected", foreground="red")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
    
    def start_acquisition(self):
        """Start acquisition"""
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Arduino not connected")
            return
        
        self.session_data = []
        self.packet_count = 0
        self.bytes_received = 0
        self.session_start_time = datetime.now()
        self.graph_buffer_ch0.clear()
        self.graph_buffer_ch1.clear()
        self.graph_time_buffer.clear()
        self.graph_index = 0
        self.last_graph_update_index = 0
        
        try:
            self.ser.write(b"START\n")
            print("[✅] START command sent")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send START: {e}")
            return
        
        self.acquisition_active = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.record_btn.config(state="normal")
        
        self.acquisition_thread = threading.Thread(target=self.acquisition_loop, daemon=True)
        self.acquisition_thread.start()
    
    def acquisition_loop(self):
        """Read and parse packets"""
        buffer = bytearray()
        while self.acquisition_active and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                    
                    while len(buffer) >= self.PACKET_LEN:
                        if (buffer[0] == self.SYNC_BYTE_1 and buffer[1] == self.SYNC_BYTE_2):
                            if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                self.data_queue.put(bytes(buffer[:self.PACKET_LEN]))
                                del buffer[:self.PACKET_LEN]
                            else:
                                del buffer[0]
                        else:
                            del buffer[0]
                else:
                    time.sleep(0.001)
            except Exception as e:
                print(f"[❌] Error: {e}")
                break
    
    def process_queue(self):
        """Process packets from queue in main thread"""
        try:
            while True:
                packet = self.data_queue.get_nowait()
                self.parse_and_store_packet(packet)
        except queue.Empty:
            pass
        
        if self.root.winfo_exists():
            self.root.after(10, self.process_queue)
    
    def parse_and_store_packet(self, packet):
        """Parse 8-byte packet and convert to µV (NO FILTER)"""
        try:
            counter = packet[2]
            ch0_raw = (packet[4] << 8) | packet[3]
            ch1_raw = (packet[6] << 8) | packet[5]
            
            # Convert to µV (assuming ADC reference) - NO FILTERING
            ch0_uv = (ch0_raw / 16384.0) * 5.0 * 1e6
            ch1_uv = (ch1_raw / 16384.0) * 5.0 * 1e6
            
            timestamp = datetime.now()
            elapsed_time = (timestamp - self.session_start_time).total_seconds()
            
            data_entry = {
                "timestamp": timestamp.isoformat(),
                "elapsed_time_s": round(elapsed_time, 6),
                "packet_number": self.packet_count,
                "sequence_counter": counter,
                "ch0_adc": ch0_raw,
                "ch1_adc": ch1_raw,
                "ch0_uv": round(ch0_uv, 2),
                "ch1_uv": round(ch1_uv, 2),
            }
            
            self.session_data.append(data_entry)
            self.packet_count += 1
            
            if self.recording_active:
                self.last_packet = data_entry
            
            self.graph_buffer_ch0.append(ch0_uv)
            self.graph_buffer_ch1.append(ch1_uv)
            self.graph_time_buffer.append(self.graph_index)
            self.graph_index += 1
            
            if self.packet_count % 50 == 0:
                self.root.after(0, self.update_status_labels)
            
        except Exception as e:
            print(f"[❌] Parse error: {e}")
    
    def update_status_labels(self):
        """Update status displays"""
        if self.acquisition_active and self.session_start_time:
            elapsed = (datetime.now() - self.session_start_time).total_seconds()
            hours, remainder = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.duration_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            if elapsed > 0:
                rate = self.packet_count / elapsed
                speed_kbps = (self.bytes_received / elapsed) / 1024
                self.rate_label.config(text=f"{rate:.1f} Hz")
                self.speed_label.config(text=f"{speed_kbps:.2f} KBps")
            
            self.packet_label.config(text=str(self.packet_count))
            
            # Update stats
            if len(self.graph_buffer_ch0) > 0:
                ch0_data = list(self.graph_buffer_ch0)
                self.ch0_min_label.config(text=f"Min: {min(ch0_data):.0f} µV")
                self.ch0_max_label.config(text=f"Max: {max(ch0_data):.0f} µV")
                self.ch0_mean_label.config(text=f"Mean: {np.mean(ch0_data):.0f} µV")
            
            if len(self.graph_buffer_ch1) > 0:
                ch1_data = list(self.graph_buffer_ch1)
                self.ch1_min_label.config(text=f"Min: {min(ch1_data):.0f} µV")
                self.ch1_max_label.config(text=f"Max: {max(ch1_data):.0f} µV")
                self.ch1_mean_label.config(text=f"Mean: {np.mean(ch1_data):.0f} µV")
            
            # Update latest packet details
            if self.last_packet:
                self.packet_tree.delete(*self.packet_tree.get_children())
                details = [
                    ('Timestamp', self.last_packet['timestamp'].split('T')[1][:8]),
                    ('Counter', str(self.last_packet['sequence_counter'])),
                    ('Ch0 µV', f"{self.last_packet['ch0_uv']:.0f}"),
                    ('Ch1 µV', f"{self.last_packet['ch1_uv']:.0f}"),
                    ('Packets', str(self.packet_count)),
                    ('Duration', f"{int((datetime.now() - self.session_start_time).total_seconds())}s"),
                ]
                for field, value in details:
                    self.packet_tree.insert('', 'end', text=field, values=(value,))
    
    def update_graph_display(self):
        """Update graph"""
        if self.graph_index == self.last_graph_update_index:
            if self.root.winfo_exists():
                self.root.after(30, self.update_graph_display)
            return
        
        try:
            x_data = list(self.graph_time_buffer)
            ch0_data = list(self.graph_buffer_ch0)
            ch1_data = list(self.graph_buffer_ch1)
            
            if len(x_data) > 1:
                self.line_ch0.set_data(x_data, ch0_data)
                self.ax_ch0.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                self.line_ch1.set_data(x_data, ch1_data)
                self.ax_ch1.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                self.canvas_plot.draw_idle()
            
            self.last_graph_update_index = self.graph_index
        except Exception as e:
            print(f"[❌] Graph error: {e}")
        
        if self.root.winfo_exists():
            self.root.after(30, self.update_graph_display)
    
    def start_recording(self):
        """Start recording session"""
        self.recording_active = True
        self.record_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
    
    def pause_recording(self):
        """Pause recording"""
        self.recording_active = False
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="normal")
    
    def resume_recording(self):
        """Resume recording"""
        self.recording_active = True
        self.pause_btn.config(state="normal")
        self.resume_btn.config(state="disabled")
    
    def stop_acquisition(self):
        """Stop acquisition"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"STOP\n")
                print("[✅] STOP command sent")
            except Exception as e:
                print(f"[❌] Failed to send STOP: {e}")
        
        self.acquisition_active = False
        self.recording_active = False
        time.sleep(0.5)
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.record_btn.config(state="disabled")
        self.pause_btn.config(state="disabled")
        self.resume_btn.config(state="disabled")
        self.save_data_btn.config(state="normal")
        self.export_btn.config(state="normal")
        self.update_status_labels()
    
    def choose_save_path(self):
        """Choose save directory"""
        path = filedialog.askdirectory(title="Select save directory", initialdir=str(self.save_path.parent))
        if path:
            self.save_path = Path(path)
            self.path_label.config(text=str(self.save_path))
    
    def save_session_data(self):
        """Save session to JSON"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            self.save_path.mkdir(parents=True, exist_ok=True)
            filename = f"EOG_session_{timestamp}.json"
            filepath = self.save_path / filename
            
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.SAMPLING_RATE,
                    "channels": self.NUM_CHANNELS,
                    "device": "Arduino Uno R4",
                    "sensor_type": "EOG",
                    "filter_applied": "NONE",
                    "channel_0": "Vertical Eye Movement",
                    "channel_1": "Horizontal Eye Movement"
                },
                "data": self.session_data
            }
            
            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            messagebox.showinfo("Success", f"Saved {len(self.session_data)} packets\nFile: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
    
    def export_graph(self):
        """Export graph to PNG"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to export")
            return
        
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            filename = f"EOG_graph_{timestamp}.png"
            filepath = filedialog.asksaveasfilename(defaultextension=".png", initialfile=filename)
            
            if filepath:
                self.fig.savefig(filepath, dpi=150, bbox_inches='tight')
                messagebox.showinfo("Success", f"Graph exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

def main():
    root = tk.Tk()
    app = EOGAcquisitionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
