"""
EOG Signal Acquisition System
=============================
Professional EOG data acquisition from Arduino Uno R4
Sampling Rate: 512 Hz | Baud Rate: 230400 | 2-Channel EOG

Features:
- Real-time signal acquisition and filtering
- Live signal visualization
- Automatic eye movement detection
- Data export and analysis
- Signal quality monitoring

Author: EOG Research Team
Version: 3.5
Date: December 2024
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import serial
import serial.tools.list_ports
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from collections import deque
import struct


try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: NumPy not available - some features disabled")

try:
    from scipy.signal import butter, filtfilt, iirnotch
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: SciPy not available - filtering disabled")


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Application configuration constants"""
    
    # Serial communication
    BAUD_RATE = 230400
    SERIAL_TIMEOUT = 1.0
    
    # Packet format
    PACKET_LENGTH = 8
    SYNC_BYTE_1 = 0xC7
    SYNC_BYTE_2 = 0x7C
    END_BYTE = 0x01
    
    # Sampling
    SAMPLING_RATE = 512.0
    
    # Filtering
    FILTER_BUFFER_SIZE = 2048
    BANDPASS_LOW = 0.5
    BANDPASS_HIGH = 35.0
    NOTCH_QUALITY = 30
    
    # Display
    PREVIEW_PACKETS = 25
    UPDATE_INTERVAL_MS = 200
    DEBUG_MAX_LINES = 1000
    
    # Data
    OUTPUT_DIR = Path("data/eog_sessions")


# ============================================================================
# REAL-TIME FILTER
# ============================================================================

class EOGFilter:
    """Real-time EOG signal filtering"""
    
    def __init__(self, fs=512, buffer_size=2048):
        self.fs = fs
        self.nyquist = fs / 2
        self.buffer_size = buffer_size
        
        # Channel buffers
        self.ch0_buffer = deque(maxlen=buffer_size)
        self.ch1_buffer = deque(maxlen=buffer_size)
        
        # Design filters
        self.filters_ready = False
        if SCIPY_AVAILABLE:
            self._design_filters()
    
    def _design_filters(self):
        """Design all filter coefficients"""
        try:
            # Bandpass filter
            low = Config.BANDPASS_LOW / self.nyquist
            high = Config.BANDPASS_HIGH / self.nyquist
            self.bp_b, self.bp_a = butter(4, [low, high], btype='band')
            
            # Notch filters
            self.notch50_b, self.notch50_a = iirnotch(50, Config.NOTCH_QUALITY, self.fs)
            self.notch60_b, self.notch60_a = iirnotch(60, Config.NOTCH_QUALITY, self.fs)
            
            self.filters_ready = True
        except Exception as e:
            print(f"Filter design failed: {e}")
            self.filters_ready = False
    
    def add_sample(self, ch0, ch1):
        """Add samples to buffers"""
        self.ch0_buffer.append(ch0)
        self.ch1_buffer.append(ch1)
    
    def get_filtered(self, notch_freq=50):
        """Get filtered signal values"""
        if not self.filters_ready or len(self.ch0_buffer) < 200:
            return None, None
        
        try:
            # Convert to arrays
            if NUMPY_AVAILABLE:
                ch0_arr = np.array(self.ch0_buffer)
                ch1_arr = np.array(self.ch1_buffer)
            else:
                ch0_arr = list(self.ch0_buffer)
                ch1_arr = list(self.ch1_buffer)
            
            # Apply bandpass
            ch0_filt = filtfilt(self.bp_b, self.bp_a, ch0_arr)
            ch1_filt = filtfilt(self.bp_b, self.bp_a, ch1_arr)
            
            # Apply notch
            if notch_freq == 50:
                ch0_filt = filtfilt(self.notch50_b, self.notch50_a, ch0_filt)
                ch1_filt = filtfilt(self.notch50_b, self.notch50_a, ch1_filt)
            elif notch_freq == 60:
                ch0_filt = filtfilt(self.notch60_b, self.notch60_a, ch0_filt)
                ch1_filt = filtfilt(self.notch60_b, self.notch60_a, ch1_filt)
            
            return float(ch0_filt[-1]), float(ch1_filt[-1])
            
        except Exception as e:
            return None, None
    
    def reset(self):
        """Clear buffers"""
        self.ch0_buffer.clear()
        self.ch1_buffer.clear()


# ============================================================================
# PACKET PARSER
# ============================================================================

class PacketParser:
    """Parse EOG data packets from Arduino"""
    
    def __init__(self):
        self.buffer = bytearray()
        self.packet_count = 0
        self.error_count = 0
    
    def add_bytes(self, data):
        """Add received bytes to buffer"""
        self.buffer.extend(data)
    
    def parse_next(self):
        """Parse next packet from buffer"""
        while len(self.buffer) >= Config.PACKET_LENGTH:
            # Check sync bytes
            if (self.buffer[0] == Config.SYNC_BYTE_1 and 
                self.buffer[1] == Config.SYNC_BYTE_2):
                
                # Check end byte
                if self.buffer[Config.PACKET_LENGTH - 1] == Config.END_BYTE:
                    # Valid packet found
                    packet = bytes(self.buffer[:Config.PACKET_LENGTH])
                    self.buffer = self.buffer[Config.PACKET_LENGTH:]
                    self.packet_count += 1
                    return self._decode_packet(packet)
                else:
                    # Invalid end byte
                    self.buffer = self.buffer[1:]
                    self.error_count += 1
            else:
                # Invalid sync
                self.buffer = self.buffer[1:]
                self.error_count += 1
        
        return None
    
    def _decode_packet(self, packet):
        """Decode packet bytes to data"""
        try:
            counter = packet[2]
            ch0_raw = (packet[3] << 8) | packet[4]
            ch1_raw = (packet[5] << 8) | packet[6]
            
            # Convert to microvolts
            ch0_uv = (ch0_raw / 16384.0) * 5.0 * 1e6
            ch1_uv = (ch1_raw / 16384.0) * 5.0 * 1e6
            
            return {
                'counter': counter,
                'ch0_raw': ch0_raw,
                'ch1_raw': ch1_raw,
                'ch0_uv': ch0_uv,
                'ch1_uv': ch1_uv,
                'timestamp': time.time()
            }
        except Exception as e:
            self.error_count += 1
            return None
    
    def reset(self):
        """Reset parser state"""
        self.buffer.clear()
        self.packet_count = 0
        self.error_count = 0


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class EOGAcquisitionApp:
    """Main EOG acquisition application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Signal Acquisition System v3.5")
        self.root.geometry("1500x950")
        
        # Serial connection
        self.serial_port = None
        self.is_acquiring = False
        self.acquisition_thread = None
        
        # Data structures
        self.parser = PacketParser()
        self.filter = EOGFilter()
        self.session_data = []
        self.session_start = None
        
        # UI variables
        self.port_var = tk.StringVar()
        self.filter_enabled = tk.BooleanVar(value=True)
        self.notch_freq = tk.IntVar(value=50)
        self.debug_enabled = tk.BooleanVar(value=True)
        
        # Statistics
        self.stats = {
            'packets': 0,
            'errors': 0,
            'duration': 0,
            'rate': 0
        }
        
        # Build UI
        self.create_ui()
        self.scan_ports()
        
        # Start update loop
        self.update_displays()
    
    def create_ui(self):
        """Build the user interface"""
        
        # Create tabs
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Tab 1: Main acquisition
        self.tab_main = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_main, text='📡 Acquisition')
        self.create_main_tab()
        
        # Tab 2: Statistics
        self.tab_stats = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_stats, text='📊 Statistics')
        self.create_stats_tab()
        
        # Tab 3: Debug
        self.tab_debug = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_debug, text='🔧 Debug')
        self.create_debug_tab()
        
        # Status bar
        self.create_status_bar()
    
    def create_main_tab(self):
        """Create main acquisition tab"""
        
        # Left panel
        left = ttk.Frame(self.tab_main)
        left.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        # Right panel
        right = ttk.Frame(self.tab_main)
        right.pack(side='right', fill='both', expand=True, padx=5, pady=5)
        
        # === LEFT PANEL ===
        
        # Connection
        conn_frame = ttk.LabelFrame(left, text='🔌 Connection', padding=10)
        conn_frame.pack(fill='x', pady=5)
        
        ttk.Label(conn_frame, text='Port:').grid(row=0, column=0, sticky='w', padx=5)
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, 
                                       width=35, state='readonly')
        self.port_combo.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Button(conn_frame, text='🔄', command=self.scan_ports, 
                  width=3).grid(row=0, column=2, padx=2)
        
        ttk.Label(conn_frame, text='Baud:').grid(row=1, column=0, sticky='w', padx=5)
        ttk.Label(conn_frame, text=f'{Config.BAUD_RATE}', 
                 font=('Arial', 9, 'bold')).grid(row=1, column=1, sticky='w', padx=5)
        
        ttk.Label(conn_frame, text='Rate:').grid(row=2, column=0, sticky='w', padx=5)
        ttk.Label(conn_frame, text=f'{Config.SAMPLING_RATE} Hz', 
                 font=('Arial', 9, 'bold')).grid(row=2, column=1, sticky='w', padx=5)
        
        # Status
        status_frame = ttk.LabelFrame(left, text='📊 Status', padding=10)
        status_frame.pack(fill='x', pady=5)
        
        status_labels = [
            ('Connection:', 'conn_status'),
            ('Device:', 'device_status'),
            ('Packets:', 'packet_status'),
            ('Errors:', 'error_status'),
            ('Duration:', 'duration_status'),
            ('Rate:', 'rate_status')
        ]
        
        self.status_labels = {}
        for i, (label, key) in enumerate(status_labels):
            ttk.Label(status_frame, text=label).grid(row=i, column=0, sticky='w', padx=5)
            self.status_labels[key] = ttk.Label(status_frame, text='---', 
                                               font=('Arial', 9))
            self.status_labels[key].grid(row=i, column=1, sticky='w', padx=5)
        
        self.status_labels['conn_status'].config(text='❌ Disconnected', foreground='red')
        
        # Filter settings
        filter_frame = ttk.LabelFrame(left, text='🔧 Filtering', padding=10)
        filter_frame.pack(fill='x', pady=5)
        
        ttk.Checkbutton(filter_frame, text='Enable Real-Time Filter', 
                       variable=self.filter_enabled).pack(anchor='w')
        
        ttk.Label(filter_frame, text=f'Bandpass: {Config.BANDPASS_LOW}-{Config.BANDPASS_HIGH} Hz',
                 font=('Arial', 8)).pack(anchor='w', padx=20)
        
        notch_frame = ttk.Frame(filter_frame)
        notch_frame.pack(anchor='w', padx=20)
        ttk.Label(notch_frame, text='Notch:').pack(side='left')
        ttk.Radiobutton(notch_frame, text='50 Hz', variable=self.notch_freq, 
                       value=50).pack(side='left', padx=5)
        ttk.Radiobutton(notch_frame, text='60 Hz', variable=self.notch_freq, 
                       value=60).pack(side='left', padx=5)
        
        # Controls
        ctrl_frame = ttk.LabelFrame(left, text='⚡ Control', padding=10)
        ctrl_frame.pack(fill='x', pady=5)
        
        btn_width = 18
        
        self.btn_connect = ttk.Button(ctrl_frame, text='🔌 Connect', 
                                      command=self.connect, width=btn_width)
        self.btn_connect.pack(fill='x', pady=2)
        
        self.btn_disconnect = ttk.Button(ctrl_frame, text='🔌 Disconnect', 
                                        command=self.disconnect, width=btn_width, 
                                        state='disabled')
        self.btn_disconnect.pack(fill='x', pady=2)
        
        self.btn_start = ttk.Button(ctrl_frame, text='▶️ Start Acquisition', 
                                    command=self.start_acquisition, width=btn_width, 
                                    state='disabled')
        self.btn_start.pack(fill='x', pady=2)
        
        self.btn_stop = ttk.Button(ctrl_frame, text='⏹️ Stop Acquisition', 
                                   command=self.stop_acquisition, width=btn_width, 
                                   state='disabled')
        self.btn_stop.pack(fill='x', pady=2)
        
        ttk.Separator(ctrl_frame, orient='horizontal').pack(fill='x', pady=5)
        
        self.btn_save = ttk.Button(ctrl_frame, text='💾 Save Data', 
                                   command=self.save_data, width=btn_width, 
                                   state='disabled')
        self.btn_save.pack(fill='x', pady=2)
        
        self.btn_clear = ttk.Button(ctrl_frame, text='🗑️ Clear Session', 
                                    command=self.clear_session, width=btn_width)
        self.btn_clear.pack(fill='x', pady=2)
        
        # === RIGHT PANEL ===
        
        preview_frame = ttk.LabelFrame(right, text='📈 Live Data Preview', padding=10)
        preview_frame.pack(fill='both', expand=True)
        
        self.preview_text = tk.Text(preview_frame, height=40, width=70,
                                   font=('Courier New', 9), bg='#f8f8f8')
        preview_scroll = ttk.Scrollbar(preview_frame, command=self.preview_text.yview)
        self.preview_text.config(yscrollcommand=preview_scroll.set)
        
        self.preview_text.pack(side='left', fill='both', expand=True)
        preview_scroll.pack(side='right', fill='y')
    
    def create_stats_tab(self):
        """Create statistics tab"""
        
        frame = ttk.Frame(self.tab_stats, padding=10)
        frame.pack(fill='both', expand=True)
        
        ttk.Button(frame, text='🔄 Refresh Statistics', 
                  command=self.update_stats_display).pack(pady=5)
        
        self.stats_text = tk.Text(frame, height=45, width=110,
                                 font=('Courier New', 9), bg='#f8f8f8')
        stats_scroll = ttk.Scrollbar(frame, command=self.stats_text.yview)
        self.stats_text.config(yscrollcommand=stats_scroll.set)
        
        self.stats_text.pack(side='left', fill='both', expand=True)
        stats_scroll.pack(side='right', fill='y')
    
    def create_debug_tab(self):
        """Create debug tab"""
        
        frame = ttk.Frame(self.tab_debug, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Controls
        ctrl = ttk.Frame(frame)
        ctrl.pack(fill='x', pady=5)
        
        ttk.Checkbutton(ctrl, text='Enable Debug Output', 
                       variable=self.debug_enabled).pack(side='left', padx=5)
        ttk.Button(ctrl, text='🗑️ Clear', command=self.clear_debug).pack(side='left', padx=5)
        ttk.Button(ctrl, text='💾 Export', command=self.export_debug).pack(side='left', padx=5)
        
        # Debug console
        self.debug_text = scrolledtext.ScrolledText(frame, height=45, width=120,
                                                    font=('Courier New', 9),
                                                    bg='#000000', fg='#00ff00')
        self.debug_text.pack(fill='both', expand=True)
        
        # Initial message
        self.log("=" * 80)
        self.log("EOG SIGNAL ACQUISITION SYSTEM v3.5")
        self.log("=" * 80)
        self.log("System ready. Connect Arduino to begin.")
        self.log("")
    
    def create_status_bar(self):
        """Create bottom status bar"""
        
        self.status_bar = ttk.Label(self.root, text='Ready', relief='sunken', 
                                   anchor='w', font=('Arial', 8))
        self.status_bar.pack(side='bottom', fill='x')
    
    # === Serial Communication ===
    
    def scan_ports(self):
        """Scan for available serial ports"""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append(f"{port.device} - {port.description}")
        
        self.port_combo['values'] = ports if ports else ['No ports found']
        if ports:
            self.port_combo.current(0)
            self.log(f"Found {len(ports)} port(s)")
        else:
            self.log("No serial ports detected")
    
    def connect(self):
        """Connect to Arduino"""
        if not self.port_var.get() or 'No ports' in self.port_var.get():
            messagebox.showerror("Error", "Select a valid port")
            return
        
        port = self.port_var.get().split(' - ')[0]
        
        try:
            self.log(f"\nConnecting to {port}...")
            
            self.serial_port = serial.Serial(port, Config.BAUD_RATE, 
                                            timeout=Config.SERIAL_TIMEOUT)
            
            time.sleep(2.5)  # Arduino reset delay
            self.serial_port.reset_input_buffer()
            
            self.log("✓ Connected successfully")
            self.status_labels['conn_status'].config(text='✅ Connected', 
                                                     foreground='green')
            self.status_labels['device_status'].config(text=f'Arduino @ {port}')
            
            self.btn_connect.config(state='disabled')
            self.btn_disconnect.config(state='normal')
            self.btn_start.config(state='normal')
            
            messagebox.showinfo("Success", f"Connected to {port}")
            
        except Exception as e:
            self.log(f"❌ Connection failed: {e}")
            messagebox.showerror("Error", f"Connection failed:\n{e}")
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if self.is_acquiring:
            self.stop_acquisition()
        
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.log("Disconnected")
        
        self.status_labels['conn_status'].config(text='❌ Disconnected', 
                                                 foreground='red')
        self.status_labels['device_status'].config(text='---')
        
        self.btn_connect.config(state='normal')
        self.btn_disconnect.config(state='disabled')
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='disabled')
    
    # === Acquisition ===
    
    def start_acquisition(self):
        """Start data acquisition"""
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showerror("Error", "Not connected")
            return
        
        self.log("\n" + "=" * 60)
        self.log("STARTING ACQUISITION")
        self.log("=" * 60)
        
        # Reset
        self.session_data = []
        self.session_start = time.time()
        self.parser.reset()
        self.filter.reset()
        self.serial_port.reset_input_buffer()
        
        filter_status = "ENABLED" if self.filter_enabled.get() else "DISABLED"
        self.log(f"Filtering: {filter_status}")
        if self.filter_enabled.get():
            self.log(f"  Bandpass: {Config.BANDPASS_LOW}-{Config.BANDPASS_HIGH} Hz")
            self.log(f"  Notch: {self.notch_freq.get()} Hz")
        
        # Start thread
        self.is_acquiring = True
        self.acquisition_thread = threading.Thread(target=self.acquisition_loop, 
                                                   daemon=True)
        self.acquisition_thread.start()
        
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.btn_save.config(state='disabled')
        
        self.log("✓ Acquisition started")
    
    def acquisition_loop(self):
        """Main acquisition loop"""
        self.log("Reading data from Arduino...")
        
        while self.is_acquiring and self.serial_port and self.serial_port.is_open:
            try:
                # Read available data
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self.parser.add_bytes(data)
                    
                    # Process packets
                    while True:
                        packet = self.parser.parse_next()
                        if packet is None:
                            break
                        self.process_packet(packet)
                else:
                    time.sleep(0.001)
                    
            except Exception as e:
                self.log(f"❌ Acquisition error: {e}")
                break
        
        self.log("Acquisition loop ended")
    
    def process_packet(self, packet):
        """Process received packet"""
        # Apply filtering
        ch0_filt = None
        ch1_filt = None
        
        if self.filter_enabled.get():
            self.filter.add_sample(packet['ch0_uv'], packet['ch1_uv'])
            ch0_filt, ch1_filt = self.filter.get_filtered(self.notch_freq.get())
        
        # Store data
        elapsed = packet['timestamp'] - self.session_start
        
        entry = {
            'timestamp': datetime.fromtimestamp(packet['timestamp']).isoformat(),
            'elapsed_s': round(elapsed, 6),
            'packet_num': len(self.session_data),
            'counter': packet['counter'],
            'ch0_raw': packet['ch0_raw'],
            'ch1_raw': packet['ch1_raw'],
            'ch0_uv': round(packet['ch0_uv'], 2),
            'ch1_uv': round(packet['ch1_uv'], 2)
        }
        
        if ch0_filt is not None:
            entry['ch0_filtered_uv'] = round(ch0_filt, 2)
            entry['ch1_filtered_uv'] = round(ch1_filt, 2)
        
        self.session_data.append(entry)
    
    def stop_acquisition(self):
        """Stop acquisition"""
        self.is_acquiring = False
        time.sleep(0.5)
        
        self.log("\n" + "=" * 60)
        self.log("ACQUISITION STOPPED")
        self.log("=" * 60)
        self.log(f"Packets: {len(self.session_data)}")
        self.log(f"Errors: {self.parser.error_count}")
        
        if self.session_data:
            duration = self.session_data[-1]['elapsed_s']
            rate = len(self.session_data) / duration if duration > 0 else 0
            self.log(f"Duration: {duration:.2f} s")
            self.log(f"Rate: {rate:.1f} Hz")
        
        self.btn_start.config(state='normal')
        self.btn_stop.config(state='disabled')
        self.btn_save.config(state='normal')
    
    # === Data Management ===
    
    def save_data(self):
        """Save session data to file"""
        if not self.session_data:
            messagebox.showwarning("No Data", "No data to save")
            return
        
        try:
            Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = Config.OUTPUT_DIR / f"eog_session_{timestamp}.json"
            
            duration = self.session_data[-1]['elapsed_s'] if self.session_data else 0
            
            output = {
                'session_info': {
                    'timestamp': datetime.now().isoformat(),
                    'duration_s': duration,
                    'total_packets': len(self.session_data),
                    'error_count': self.parser.error_count,
                    'sampling_rate_hz': Config.SAMPLING_RATE,
                    'channels': 2,
                    'device': 'Arduino Uno R4',
                    'filtering_enabled': self.filter_enabled.get(),
                    'notch_freq_hz': self.notch_freq.get() if self.filter_enabled.get() else None
                },
                'data': self.session_data
            }
            
            with open(filename, 'w') as f:
                json.dump(output, f, indent=2)
            
            self.log(f"✓ Saved: {filename}")
            messagebox.showinfo("Success", f"Saved {len(self.session_data)} packets to:\n{filename}")
            
        except Exception as e:
            self.log(f"❌ Save failed: {e}")
            messagebox.showerror("Error", f"Save failed:\n{e}")
    
    def clear_session(self):
        """Clear session data"""
        if self.is_acquiring:
            messagebox.showwarning("Warning", "Stop acquisition first")
            return
        
        if self.session_data:
            if messagebox.askyesno("Confirm", f"Clear {len(self.session_data)} packets?"):
                self.session_data = []
                self.parser.reset()
                self.session_start = None
                self.log("Session cleared")
    
    # === Display Updates ===
    
    def update_displays(self):
        """Periodic display update"""
        
        # Update statistics
        if self.session_data:
            self.stats['packets'] = len(self.session_data)
            self.stats['errors'] = self.parser.error_count
            
            if self.session_start:
                self.stats['duration'] = time.time() - self.session_start
                self.stats['rate'] = self.stats['packets'] / self.stats['duration']
        
        # Update status labels
        if self.is_acquiring:
            self.status_labels['packet_status'].config(text=str(self.stats['packets']))
            self.status_labels['error_status'].config(text=str(self.stats['errors']))
            
            duration = self.stats['duration']
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            self.status_labels['duration_status'].config(
                text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            self.status_labels['rate_status'].config(
                text=f"{self.stats['rate']:.1f} Hz")
        
        # Update preview
        if self.is_acquiring and self.session_data:
            self.update_preview_display()
        
        # Schedule next update
        self.root.after(Config.UPDATE_INTERVAL_MS, self.update_displays)
    
    def update_preview_display(self):
        """Update live preview"""
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', tk.END)
        
        text = "EOG LIVE DATA PREVIEW\n"
        text += "=" * 80 + "\n\n"
        
        text += f"Packets: {len(self.session_data)} | "
        text += f"Errors: {self.parser.error_count} | "
        text += f"Rate: {self.stats['rate']:.1f} Hz\n\n"
        
        text += "=" * 80 + "\n"
        text += "LATEST PACKETS:\n"
        text += "=" * 80 + "\n"
        
        # Header
        if self.filter_enabled.get() and self.session_data:
            if 'ch0_filtered_uv' in self.session_data[-1]:
                text += f"{'#':<6} {'Cnt':<4} {'Ch0(µV)':<10} {'Ch1(µV)':<10} {'Ch0-F':<10} {'Ch1-F':<10}\n"
            else:
                text += f"{'#':<6} {'Cnt':<4} {'Ch0(µV)':<10} {'Ch1(µV)':<10}\n"
        else:
            text += f"{'#':<6} {'Cnt':<4} {'Ch0(µV)':<10} {'Ch1(µV)':<10}\n"
        
        text += "-" * 80 + "\n"
        
        # Data rows
        for entry in self.session_data[-Config.PREVIEW_PACKETS:]:
            line = f"{entry['packet_num']:<6} {entry['counter']:<4} "
            line += f"{entry['ch0_uv']:<10.1f} {entry['ch1_uv']:<10.1f}"
            
            if 'ch0_filtered_uv' in entry:
                line += f" {entry['ch0_filtered_uv']:<10.1f} {entry['ch1_filtered_uv']:<10.1f}"
            
            text += line + "\n"
        
        self.preview_text.insert('1.0', text)
        self.preview_text.config(state='disabled')
    
    def update_stats_display(self):
        """Update statistics tab"""
        self.stats_text.config(state='normal')
        self.stats_text.delete('1.0', tk.END)
        
        text = "EOG SESSION STATISTICS\n"
        text += "=" * 80 + "\n\n"
        
        # Session info
        text += "SESSION INFORMATION:\n"
        text += "-" * 80 + "\n"
        
        if self.session_start:
            start_time = datetime.fromtimestamp(self.session_start)
            text += f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if self.session_data:
                duration = self.session_data[-1]['elapsed_s']
                text += f"Duration: {duration:.2f} s ({duration/60:.1f} min)\n"
        
        text += f"Total Packets: {len(self.session_data)}\n"
        text += f"Error Count: {self.parser.error_count}\n"
        
        if self.session_data:
            total = len(self.session_data) + self.parser.error_count
            error_rate = (self.parser.error_count / total) * 100 if total > 0 else 0
            text += f"Error Rate: {error_rate:.2f}%\n"
            
            duration = self.session_data[-1]['elapsed_s']
            if duration > 0:
                rate = len(self.session_data) / duration
                text += f"\nActual Rate: {rate:.2f} Hz\n"
                text += f"Target Rate: {Config.SAMPLING_RATE} Hz\n"
                text += f"Accuracy: {(rate/Config.SAMPLING_RATE)*100:.1f}%\n"
        
        text += "\n"
        
        # Channel statistics
        if self.session_data and NUMPY_AVAILABLE:
            text += "CHANNEL STATISTICS:\n"
            text += "-" * 80 + "\n\n"
            
            ch0_vals = np.array([d['ch0_uv'] for d in self.session_data])
            ch1_vals = np.array([d['ch1_uv'] for d in self.session_data])
            
            text += "Channel 0 (Horizontal EOG):\n"
            text += f"  Min:     {np.min(ch0_vals):>10.2f} µV\n"
            text += f"  Max:     {np.max(ch0_vals):>10.2f} µV\n"
            text += f"  Mean:    {np.mean(ch0_vals):>10.2f} µV\n"
            text += f"  Std Dev: {np.std(ch0_vals):>10.2f} µV\n"
            text += f"  Range:   {np.ptp(ch0_vals):>10.2f} µV\n\n"
            
            text += "Channel 1 (Vertical EOG):\n"
            text += f"  Min:     {np.min(ch1_vals):>10.2f} µV\n"
            text += f"  Max:     {np.max(ch1_vals):>10.2f} µV\n"
            text += f"  Mean:    {np.mean(ch1_vals):>10.2f} µV\n"
            text += f"  Std Dev: {np.std(ch1_vals):>10.2f} µV\n"
            text += f"  Range:   {np.ptp(ch1_vals):>10.2f} µV\n\n"
            
            # Filtered stats
            if self.filter_enabled.get() and 'ch0_filtered_uv' in self.session_data[-1]:
                ch0_filt = np.array([d['ch0_filtered_uv'] for d in self.session_data 
                                    if 'ch0_filtered_uv' in d])
                ch1_filt = np.array([d['ch1_filtered_uv'] for d in self.session_data 
                                    if 'ch1_filtered_uv' in d])
                
                if len(ch0_filt) > 0:
                    text += "FILTERED STATISTICS:\n"
                    text += "-" * 80 + "\n\n"
                    
                    text += "Channel 0 (Filtered):\n"
                    text += f"  Min:     {np.min(ch0_filt):>10.2f} µV\n"
                    text += f"  Max:     {np.max(ch0_filt):>10.2f} µV\n"
                    text += f"  Mean:    {np.mean(ch0_filt):>10.2f} µV\n"
                    text += f"  Std Dev: {np.std(ch0_filt):>10.2f} µV\n\n"
                    
                    text += "Channel 1 (Filtered):\n"
                    text += f"  Min:     {np.min(ch1_filt):>10.2f} µV\n"
                    text += f"  Max:     {np.max(ch1_filt):>10.2f} µV\n"
                    text += f"  Mean:    {np.mean(ch1_filt):>10.2f} µV\n"
                    text += f"  Std Dev: {np.std(ch1_filt):>10.2f} µV\n\n"
        
        self.stats_text.insert('1.0', text)
        self.stats_text.config(state='disabled')
    
    # === Debug ===
    
    def log(self, message):
        """Write to debug log"""
        if not self.debug_enabled.get():
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.debug_text.see(tk.END)
        
        # Limit lines
        lines = int(self.debug_text.index('end-1c').split('.')[0])
        if lines > Config.DEBUG_MAX_LINES:
            self.debug_text.delete('1.0', '100.0')
    
    def clear_debug(self):
        """Clear debug console"""
        self.debug_text.delete('1.0', tk.END)
        self.log("Debug console cleared")
    
    def export_debug(self):
        """Export debug log"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eog_debug_{timestamp}.txt"
            
            with open(filename, 'w') as f:
                f.write(self.debug_text.get('1.0', tk.END))
            
            messagebox.showinfo("Success", f"Debug log exported:\n{filename}")
            self.log(f"Exported to {filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{e}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Application entry point"""
    
    print("EOG Signal Acquisition System v3.5")
    print("=" * 50)
    
    # Check dependencies
    if not NUMPY_AVAILABLE:
        print("⚠ NumPy not installed - statistics limited")
    if not SCIPY_AVAILABLE:
        print("⚠ SciPy not installed - filtering disabled")
    
    print("\nStarting application...")
    
    root = tk.Tk()
    app = EOGAcquisitionApp(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nShutdown requested")
    finally:
        if app.serial_port and app.serial_port.is_open:
            app.serial_port.close()
        print("Application closed")


if __name__ == "__main__":
    main()