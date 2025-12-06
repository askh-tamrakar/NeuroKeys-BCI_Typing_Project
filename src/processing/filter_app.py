"""
EMG Filter & Envelope App
Combines acquisition logic from chords_serial.py and processing from emgenvelope.py
into a Tkinter-based GUI similar to acquisition.py.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import numpy as np
from collections import deque
from datetime import datetime
from pathlib import Path
import json

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from scipy.signal import butter, filtfilt, lfilter

# Ensure we can import from chords directory
# Project root is two levels up from src/processing
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from chords.chords_serial import Chords_USB
except ImportError as e:
    print(f"Warning: could not import Chords_USB: {e}")
    # Dummy mock for testing if hardware not available or import fails
    class Chords_USB:
        def __init__(self):
            self.streaming_active = False
            self.board = "MOCK_BOARD"
        def detect_hardware(self):
            return False
        def connect_hardware(self, port, baud):
            return True
        def start_streaming(self):
            self.streaming_active = True
        def stop_streaming(self):
            self.streaming_active = False
        def read_data(self):
            time.sleep(0.01)

class EMGFilterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EMG Filter & Envelope Processing - Real-Time")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # --- Hardware / State ---
        self.usb_client = Chords_USB()
        self.is_running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Display Buffers (Store last N seconds for plotting)
        self.window_seconds = 10
        self.sampling_rate = 250 # Default, will update on connect
        self.buffer_size = self.sampling_rate * self.window_seconds
        
        # Data Buffers (Channels 0 and 1)
        # Using deque for efficient append/pop, but will convert to list/np for filtering
        self.raw_ch0 = deque(maxlen=self.buffer_size)
        self.raw_ch1 = deque(maxlen=self.buffer_size)
        
        # Filter parameters (Butterworth High-pass)
        self.filter_cutoff = 70.0 
        self.filter_order = 4
        self.b, self.a = None, None # To be calculated based on SR

        # Envelope parameters (RMS moving window)
        self.rms_window_ms = 100 # 100ms window
        
        # UI Setup
        self.setup_ui()
        self.update_port_list()
        
        # Animation Loop
        self.root.after(50, self.update_plots)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # -- Left Control Panel --
        control_panel = ttk.Frame(main_frame, width=300)
        control_panel.pack(side="left", fill="y", padx=5)
        
        # Connection Box
        conn_group = ttk.LabelFrame(control_panel, text="Connection", padding=10)
        conn_group.pack(fill="x", pady=5)
        
        ttk.Label(conn_group, text="Port:").pack(anchor="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_group, textvariable=self.port_var)
        self.port_combo.pack(fill="x", pady=2)
        
        ttk.Button(conn_group, text="Refresh", command=self.update_port_list).pack(fill="x", pady=2)
        
        self.connect_btn = ttk.Button(conn_group, text="Connect & Start", command=self.toggle_connection)
        self.connect_btn.pack(fill="x", pady=5)
        
        self.status_label = ttk.Label(conn_group, text="Status: Disconnected", foreground="red")
        self.status_label.pack(anchor="w")

        # Stats Box
        stats_group = ttk.LabelFrame(control_panel, text="Signal Stats", padding=10)
        stats_group.pack(fill="x", pady=5)
        self.lbl_ch0_raw = ttk.Label(stats_group, text="Ch0 Raw: 0")
        self.lbl_ch0_raw.pack(anchor="w")
        self.lbl_ch0_filt = ttk.Label(stats_group, text="Ch0 Filt: 0")
        self.lbl_ch0_filt.pack(anchor="w")
        self.lbl_ch0_env = ttk.Label(stats_group, text="Ch0 Env: 0")
        self.lbl_ch0_env.pack(anchor="w")

        # -- Right Graph Panel --
        graph_panel = ttk.Frame(main_frame)
        graph_panel.pack(side="right", fill="both", expand=True, padx=5)
        
        # Matplotlib Figure
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        
        # Subplots: 1. Raw, 2. Filtered, 3. Envelope
        self.ax1 = self.fig.add_subplot(311)
        self.ax1.set_title("Raw EMG Signal")
        self.ax1.set_ylabel("ADC")
        self.line_raw, = self.ax1.plot([], [], 'b-', lw=0.8)
        self.ax1.grid(True, alpha=0.3)
        
        self.ax2 = self.fig.add_subplot(312)
        self.ax2.set_title(f"Filtered (High-pass > {self.filter_cutoff}Hz)")
        self.ax2.set_ylabel("Amplitude")
        self.line_filt, = self.ax2.plot([], [], 'g-', lw=0.8)
        self.ax2.grid(True, alpha=0.3)
        
        self.ax3 = self.fig.add_subplot(313)
        self.ax3.set_title("RMS Envelope")
        self.ax3.set_ylabel("Amplitude")
        self.ax3.set_xlabel("Time (samples within buffer)")
        self.line_env, = self.ax3.plot([], [], 'r-', lw=1.2)
        self.ax3.grid(True, alpha=0.3)
        
        self.fig.tight_layout()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_panel)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def update_port_list(self):
        import serial.tools.list_ports
        ports = [f"{p.device}" for p in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)

    def toggle_connection(self):
        if not self.is_running:
            self.start_acquisition()
        else:
            self.stop_acquisition()

    def start_acquisition(self):
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port.")
            return

        # Attempt connection
        try:
            success = self.usb_client.connect_hardware(port, 230400) # Trying common baud first
            if not success:
                 # Fallback provided by chords logic or retry logic could be added here
                 # For now, explicit error
                 pass 
            
            # If successfully connected (or assumed for mocked wrapper)
            if self.usb_client.ser or hasattr(self.usb_client, 'board'): # Check if connected
                self.is_running = True
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text=f"Connected: {self.usb_client.board}", foreground="green")
                
                # Update Sampling Rate based on board
                if hasattr(self.usb_client, 'supported_boards') and self.usb_client.board in self.usb_client.supported_boards:
                    self.sampling_rate = self.usb_client.supported_boards[self.usb_client.board]['sampling_rate']
                
                # Re-calc buffer size
                self.buffer_size = int(self.sampling_rate * self.window_seconds)
                self.raw_ch0 = deque(maxlen=self.buffer_size)
                self.raw_ch1 = deque(maxlen=self.buffer_size)
                
                # Re-calc filter co-effs
                nyq = 0.5 * self.sampling_rate
                normal_cutoff = self.filter_cutoff / nyq
                if normal_cutoff >= 1.0: normal_cutoff = 0.99 # Safety
                self.b, self.a = butter(self.filter_order, normal_cutoff, btype='high', analog=False)

                # Start Thread
                self.thread = threading.Thread(target=self.acquisition_loop, daemon=True)
                self.thread.start()
            else:
                messagebox.showerror("Failed", "Could not connect/identify board.")

        except Exception as e:
            messagebox.showerror("Error", f"Connection error: {e}")

    def stop_acquisition(self):
        self.is_running = False
        if self.usb_client:
            self.usb_client.cleanup()
        self.connect_btn.config(text="Connect & Start")
        self.status_label.config(text="Disconnected", foreground="red")

    def acquisition_loop(self):
        # Manually start via command
        if self.usb_client.ser and self.usb_client.ser.is_open:
            self.usb_client.send_command('START')
        
        buffer = bytearray()
        # Grab constants from client if available, else standard Chord defaults
        SYNC1 = getattr(self.usb_client, 'SYNC_BYTE1', 0xc7)
        SYNC2 = getattr(self.usb_client, 'SYNC_BYTE2', 0x7c)
        END = getattr(self.usb_client, 'END_BYTE', 0x01)
        HEADER_LEN = getattr(self.usb_client, 'HEADER_LENGTH', 3)
        PACKET_LEN = getattr(self.usb_client, 'packet_length', 16) # Fallback, should be set
        NUM_CHANNELS = getattr(self.usb_client, 'num_channels', 2)

        if not PACKET_LEN: # Should be set by connect_hardware
             # Fallback calculation
             PACKET_LEN = (2 * NUM_CHANNELS) + HEADER_LEN + 1

        while self.is_running:
            try:
                if not self.usb_client.ser or not self.usb_client.ser.is_open:
                    time.sleep(0.1)
                    continue
                
                # Direct read
                if self.usb_client.ser.in_waiting > 0:
                    raw = self.usb_client.ser.read(self.usb_client.ser.in_waiting)
                    buffer.extend(raw)
                else:
                    time.sleep(0.001)
                    continue

                # Parse
                while len(buffer) >= PACKET_LEN:
                    # Find sync
                    idx = -1
                    # Search for sync bytes
                    # Simple search:
                    for i in range(len(buffer) - 1):
                        if buffer[i] == SYNC1 and buffer[i+1] == SYNC2:
                            idx = i
                            break
                    
                    if idx == -1:
                        # No sync found, keep last byte just in case it's part of sync
                        del buffer[:-1]
                        break
                    
                    # Check if full packet available
                    if len(buffer) < idx + PACKET_LEN:
                        # Wait for more data
                        break
                        
                    # Check end byte
                    if buffer[idx + PACKET_LEN - 1] == END:
                        # Valid packet
                        packet = buffer[idx:idx + PACKET_LEN]
                        
                        # Extract data
                        # Structure: SYNC1 SYNC2 COUNT CH1H CH1L CH2H CH2L ... END
                        ch_data = []
                        for ch in range(NUM_CHANNELS):
                            high = packet[HEADER_LEN + 2*ch]
                            low = packet[HEADER_LEN + 2*ch + 1]
                            val = (high << 8) | low
                            ch_data.append(val)
                        
                        # Add to deque
                        with self.lock:
                            # Assuming Ch0 is first
                            if len(ch_data) > 0:
                                self.raw_ch0.append(ch_data[0])
                            if len(ch_data) > 1:
                                self.raw_ch1.append(ch_data[1])
                                
                        # Remove processed bytes
                        del buffer[:idx + PACKET_LEN]
                    else:
                        # Invalid, remove sync bytes and continue search
                        del buffer[:idx+1]

            except Exception as e:
                print(f"Acq Error: {e}")
                time.sleep(0.1)

    def calculate_rms(self, signal, window_size):
        # Moving RMS
        if len(signal) < window_size:
            return np.zeros_like(signal)
        # Fast convolution for moving average of squares
        window = np.ones(int(window_size)) / float(window_size)
        return np.sqrt(np.convolve(signal**2, window, 'same'))

    def update_plots(self):
        if self.is_running and len(self.raw_ch0) > self.sampling_rate:
            with self.lock:
                data_np = np.array(self.raw_ch0)
            
            # 1. Raw
            x_data = np.arange(len(data_np))
            self.line_raw.set_data(x_data, data_np)
            self.ax1.set_xlim(0, len(data_np))
            self.ax1.set_ylim(np.min(data_np)-100, np.max(data_np)+100)

            # 2. Filter
            if self.b is not None:
                try:
                    # Apply filtfilt for zero-phase (good format display, adds latency if buffer large)
                    filt_data = filtfilt(self.b, self.a, data_np)
                    self.line_filt.set_data(x_data, filt_data)
                    self.ax2.set_xlim(0, len(data_np))
                    self.ax2.set_ylim(np.min(filt_data)-50, np.max(filt_data)+50)
                    
                    # 3. Envelope
                    # Window size in samples
                    w_size = int((self.rms_window_ms / 1000.0) * self.sampling_rate)
                    env_data = self.calculate_rms(filt_data, w_size)
                    self.line_env.set_data(x_data, env_data)
                    self.ax3.set_xlim(0, len(data_np))
                    self.ax3.set_ylim(0, np.max(env_data)+50)

                    # Update labels
                    self.lbl_ch0_raw.config(text=f"Ch0 Raw: {data_np[-1]:.1f}")
                    self.lbl_ch0_filt.config(text=f"Ch0 Filt: {filt_data[-1]:.1f}")
                    self.lbl_ch0_env.config(text=f"Ch0 Env: {env_data[-1]:.1f}")

                except Exception as e:
                    print(f"Proc Error: {e}")

            self.canvas.draw_idle()

        # Schedule next update
        if self.root.winfo_exists():
            self.root.after(100, self.update_plots) # 10fps refresh

def main():
    root = tk.Tk()
    app = EMGFilterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
