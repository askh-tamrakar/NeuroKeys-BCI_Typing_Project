"""
EMG Data Acquisition with Real-Time ECG-Style Visualization
Tkinter GUI + Matplotlib + Arduino Serial Communication
Production-Ready Application (8-Byte Packet Format)

Author: EMG Team
Date: 2024-12-05
Version: 3.1 (Fixed - with START/STOP and debug methods)
"""

import tkinter as tk
from tkinter import ttk, messagebox
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


class EMGVisualizationApp:
    """EMG Application with Real-Time ECG-Style Graph (8-Byte Packet)"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EMG Signal Acquisition - Real-Time Visualization")
        self.root.geometry("1600x900")
        self.root.configure(bg='#f0f0f0')
        
        # Serial connection
        self.ser = None
        self.acquisition_active = False
        self.acquisition_thread = None
        
        # Data storage
        self.session_data = []
        self.session_start_time = None
        self.packet_count = 0
        
        # Graph buffers (circular - last 1024 samples = 2 seconds @ 512 Hz)
        self.graph_buffer_ch0 = deque(maxlen=1024)
        self.graph_buffer_ch1 = deque(maxlen=1024)
        self.graph_time_buffer = deque(maxlen=1024)
        self.graph_index = 0
        self.last_graph_update_index = 0
        
        # Packet format constants (MATCHING YOUR 8-BYTE FIRMWARE)
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = 512.0
        self.BAUD_RATE = 230400
        
        # Setup UI
        self.setup_ui()
        self.update_port_list()
        
        # Start graph update timer (30ms = ~33 FPS)
        self.root.after(30, self.update_graph_display)
        
    def setup_ui(self):
        """Create the user interface with left control panel and right graph"""
        
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # LEFT COLUMN: Controls (narrower)
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=False, padx=5, ipadx=10)
        
        # RIGHT COLUMN: Graph (wider)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        
        # ===== LEFT COLUMN: CONNECTION & CONTROL =====
        
        # Connection settings
        connection_frame = ttk.LabelFrame(left_frame, text="🔌 Connection", padding="10")
        connection_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(connection_frame, text="COM Port:", font=("Arial", 9)).pack(anchor="w", padx=5, pady=2)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=25, state="readonly")
        self.port_combo.pack(fill="x", padx=5, pady=2)
        
        self.refresh_btn = ttk.Button(connection_frame, text="🔄 Refresh Ports", command=self.update_port_list)
        self.refresh_btn.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(connection_frame, text="Baud: 230400 (Fixed)", font=("Arial", 8)).pack(anchor="w", padx=5)
        
        # Status
        status_frame = ttk.LabelFrame(left_frame, text="📊 Status", padding="10")
        status_frame.pack(fill="x", padx=0, pady=5)
        
        ttk.Label(status_frame, text="Connection:").pack(anchor="w", padx=5, pady=1)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial", 10, "bold"))
        self.status_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Packets:").pack(anchor="w", padx=5, pady=1)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Duration:").pack(anchor="w", padx=5, pady=1)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w", padx=5, pady=1)
        
        ttk.Label(status_frame, text="Rate:").pack(anchor="w", padx=5, pady=1)
        self.rate_label = ttk.Label(status_frame, text="0 Hz", font=("Arial", 10, "bold"))
        self.rate_label.pack(anchor="w", padx=5, pady=1)
        
        # Control buttons
        control_frame = ttk.LabelFrame(left_frame, text="⚙️ Control", padding="10")
        control_frame.pack(fill="x", padx=0, pady=5)
        
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_arduino)
        self.connect_btn.pack(fill="x", padx=2, pady=2)
        
        self.disconnect_btn = ttk.Button(control_frame, text="❌ Disconnect", command=self.disconnect_arduino, state="disabled")
        self.disconnect_btn.pack(fill="x", padx=2, pady=2)
        
        self.start_btn = ttk.Button(control_frame, text="▶️  Start", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", padx=2, pady=2)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹️  Stop", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", padx=2, pady=2)
        
        self.save_btn = ttk.Button(control_frame, text="💾 Save", command=self.save_session_data, state="disabled")
        self.save_btn.pack(fill="x", padx=2, pady=2)
        
        # Statistics
        stats_frame = ttk.LabelFrame(left_frame, text="📈 Stats", padding="10")
        stats_frame.pack(fill="both", expand=True, padx=0, pady=5)
        
        ttk.Label(stats_frame, text="Channel 0 (Flexor):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2, pady=1)
        self.ch0_min_label = ttk.Label(stats_frame, text="Min: 0", font=("Arial", 8))
        self.ch0_min_label.pack(anchor="w", padx=5, pady=0)
        self.ch0_max_label = ttk.Label(stats_frame, text="Max: 0", font=("Arial", 8))
        self.ch0_max_label.pack(anchor="w", padx=5, pady=0)
        self.ch0_mean_label = ttk.Label(stats_frame, text="Mean: 0", font=("Arial", 8))
        self.ch0_mean_label.pack(anchor="w", padx=5, pady=2)
        
        ttk.Label(stats_frame, text="Channel 1 (Extensor):", font=("Arial", 8, "bold")).pack(anchor="w", padx=2, pady=1)
        self.ch1_min_label = ttk.Label(stats_frame, text="Min: 0", font=("Arial", 8))
        self.ch1_min_label.pack(anchor="w", padx=5, pady=0)
        self.ch1_max_label = ttk.Label(stats_frame, text="Max: 0", font=("Arial", 8))
        self.ch1_max_label.pack(anchor="w", padx=5, pady=0)
        self.ch1_mean_label = ttk.Label(stats_frame, text="Mean: 0", font=("Arial", 8))
        self.ch1_mean_label.pack(anchor="w", padx=5, pady=2)
        
        # ===== RIGHT COLUMN: REAL-TIME GRAPH =====
        
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EMG Signal (512 Hz)", padding="5")
        graph_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')
        
        # Subplot for Ch0 (Flexor)
        self.ax_ch0 = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_ch0.plot([], [], color='#2E86AB', linewidth=1.5, label='Ch0 (Flexor)')
        self.ax_ch0.set_ylabel('ADC Value', fontsize=10)
        self.ax_ch0.set_ylim(0, 16384)
        self.ax_ch0.grid(True, alpha=0.3, linestyle='--')
        self.ax_ch0.legend(loc='upper left', fontsize=9)
        self.ax_ch0.set_title('Channel 0: Forearm Flexor (Inside)', fontsize=10, fontweight='bold')
        
        # Subplot for Ch1 (Extensor)
        self.ax_ch1 = self.fig.add_subplot(212)
        self.line_ch1, = self.ax_ch1.plot([], [], color='#A23B72', linewidth=1.5, label='Ch1 (Extensor)')
        self.ax_ch1.set_xlabel('Time (samples)', fontsize=10)
        self.ax_ch1.set_ylabel('ADC Value', fontsize=10)
        self.ax_ch1.set_ylim(0, 16384)
        self.ax_ch1.grid(True, alpha=0.3, linestyle='--')
        self.ax_ch1.legend(loc='upper left', fontsize=9)
        self.ax_ch1.set_title('Channel 1: Forearm Extensor (Outside)', fontsize=10, fontweight='bold')
        
        self.fig.tight_layout()
        
        # Embed matplotlib in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
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
    
    def start_acquisition(self):
        """Start acquisition and send START command to Arduino"""
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Arduino not connected")
            return
        
        # Reset data
        self.session_data = []
        self.packet_count = 0
        self.session_start_time = datetime.now()
        
        # Reset graph buffers
        self.graph_buffer_ch0.clear()
        self.graph_buffer_ch1.clear()
        self.graph_time_buffer.clear()
        self.graph_index = 0
        self.last_graph_update_index = 0

        try:
            # CRITICAL: Send START command to firmware
            self.ser.write(b"START\n")
            print("[✅] Sent START command to Arduino")
        except Exception as e:
            print(f"[❌] Failed to send START: {e}")
            messagebox.showerror("Error", f"Failed to send START: {e}")
            return
        
        self.acquisition_active = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.save_btn.config(state="disabled")
        
        self.acquisition_thread = threading.Thread(target=self.acquisition_loop, daemon=True)
        self.acquisition_thread.start()

    def acquisition_loop(self):
        """Read and parse packets (8-Byte Version)"""
        buffer = bytearray()
        
        while self.acquisition_active and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    # Read available bytes
                    chunk = self.ser.read(self.ser.in_waiting)
                    if chunk:
                        buffer.extend(chunk)
                        
                        # Process buffer for complete packets
                        while len(buffer) >= self.PACKET_LEN:
                            # Check for SYNC bytes
                            if buffer[0] == self.SYNC_BYTE_1 and buffer[1] == self.SYNC_BYTE_2:
                                # Check END byte at index 7
                                if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                    # Valid packet found
                                    self.parse_and_store_packet(buffer[:self.PACKET_LEN])
                                    # Remove processed packet
                                    del buffer[:self.PACKET_LEN]
                                else:
                                    # Invalid end byte, shift by 1
                                    del buffer[0]
                            else:
                                # Not sync bytes, shift by 1
                                del buffer[0]
                else:
                    time.sleep(0.001)
                    
            except Exception as e:
                print(f"[❌] Error in acquisition loop: {e}")
                break

    def parse_and_store_packet(self, packet):
        """Parse 8-byte packet: [C7][7C][CTR][CH0_L][CH0_H][CH1_L][CH1_H][01]"""
        try:
            counter = packet[2]
            
            # Extract channel values (high byte << 8 | low byte)
            ch0_raw = (packet[4] << 8) | packet[3]
            ch1_raw = (packet[6] << 8) | packet[5]
            
            timestamp = datetime.now()
            elapsed_time = (timestamp - self.session_start_time).total_seconds()
            
            # Store data
            data_entry = {
                "timestamp": timestamp.isoformat(),
                "elapsed_time_s": round(elapsed_time, 6),
                "packet_number": self.packet_count,
                "sequence_counter": counter,
                "ch0_raw_adc": ch0_raw,
                "ch1_raw_adc": ch1_raw,
            }
            self.session_data.append(data_entry)
            self.packet_count += 1
            
            # Add to graph buffers
            self.graph_buffer_ch0.append(ch0_raw)
            self.graph_buffer_ch1.append(ch1_raw)
            self.graph_time_buffer.append(self.graph_index)
            self.graph_index += 1
            
            # Update status periodically
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
                self.rate_label.config(text=f"{rate:.1f} Hz")
            
            self.packet_label.config(text=str(self.packet_count))
            
            # Update channel statistics
            if len(self.graph_buffer_ch0) > 0:
                ch0_data = list(self.graph_buffer_ch0)
                self.ch0_min_label.config(text=f"Min: {min(ch0_data)}")
                self.ch0_max_label.config(text=f"Max: {max(ch0_data)}")
                self.ch0_mean_label.config(text=f"Mean: {int(np.mean(ch0_data))}")
            
            if len(self.graph_buffer_ch1) > 0:
                ch1_data = list(self.graph_buffer_ch1)
                self.ch1_min_label.config(text=f"Min: {min(ch1_data)}")
                self.ch1_max_label.config(text=f"Max: {max(ch1_data)}")
                self.ch1_mean_label.config(text=f"Mean: {int(np.mean(ch1_data))}")
    
    def update_graph_display(self):
        """Update graph with latest data"""
        # Only update if we have new data
        if self.graph_index == self.last_graph_update_index:
            if self.root.winfo_exists():
                self.root.after(30, self.update_graph_display)
            return

        try:
            x_data = list(self.graph_time_buffer)
            ch0_data = list(self.graph_buffer_ch0)
            ch1_data = list(self.graph_buffer_ch1)
            
            if len(x_data) > 1:
                # Update Channel 0
                self.line_ch0.set_data(x_data, ch0_data)
                self.ax_ch0.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                
                # Update Channel 1
                self.line_ch1.set_data(x_data, ch1_data)
                self.ax_ch1.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                
                # Redraw efficiently
                self.canvas.draw_idle()
                self.last_graph_update_index = self.graph_index
        
        except Exception as e:
            print(f"[❌] Graph update error: {e}")
        
        # Schedule next update
        if self.root.winfo_exists():
            self.root.after(30, self.update_graph_display)

    def stop_acquisition(self):
        """Stop acquisition and send STOP command"""
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"STOP\n")
                print("[✅] Sent STOP command to Arduino")
            except Exception as e:
                print(f"[❌] Failed to send STOP: {e}")

        self.acquisition_active = False
        time.sleep(0.5)
        
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.save_btn.config(state="normal")
        
        self.update_status_labels()
    
    def save_session_data(self):
        """Save session to JSON file"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path("data\raw\sessions\emg_sessions")
            out_dir.mkdir(parents=True, exist_ok=True)
            
            filename = out_dir / f"emg_session_{timestamp}.json"
            
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.SAMPLING_RATE,
                    "channels": 2,
                    "device": "Arduino Uno R4",
                    "channel_0": "Forearm Flexor (A0)",
                    "channel_1": "Forearm Extensor (A1)"
                },
                "data": self.session_data
            }
            
            with open(filename, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            messagebox.showinfo("Success", f"Saved {len(self.session_data)} packets\nFile: {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")


def main():
    root = tk.Tk()
    app = EMGVisualizationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()