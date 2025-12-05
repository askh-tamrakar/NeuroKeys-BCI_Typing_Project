"""
EOG Signal Acquisition System v3.5
Complete working version with real-time plotting
Arduino Uno R4 | 512 Hz | 2-Channel | 8-byte packets
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from collections import deque

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from scipy.signal import butter, lfilter
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Configuration constants"""
    BAUD_RATE = 230400
    PACKET_LENGTH = 8
    SYNC_BYTE_1 = 0xC7
    SYNC_BYTE_2 = 0x7C
    END_BYTE = 0x01
    SAMPLING_RATE = 512.0
    PLOT_WINDOW_S = 5.0
    PLOT_MAX_SAMPLES = int(512.0 * 5.0)
    OUTPUT_DIR = Path("data/eog_sessions")


# ============================================================================
# PACKET PARSER
# ============================================================================

class PacketParser:
    """Parse 8-byte EOG packets"""
    
    def __init__(self):
        self.buffer = bytearray()
        self.packet_count = 0
        self.error_count = 0
    
    def add_byte(self, byte_val):
        """Add byte to buffer and check for complete packet"""
        self.buffer.extend(byte_val)
        
        if len(self.buffer) >= Config.PACKET_LENGTH:
            if (self.buffer[0] == Config.SYNC_BYTE_1 and 
                self.buffer[1] == Config.SYNC_BYTE_2 and 
                self.buffer[7] == Config.END_BYTE):
                
                # Valid packet
                packet = self.buffer[:Config.PACKET_LENGTH]
                self.buffer = self.buffer[Config.PACKET_LENGTH:]
                return self.parse_packet(packet)
            else:
                # Invalid, shift buffer
                self.buffer = self.buffer[1:]
                self.error_count += 1
        
        return None
    
    def parse_packet(self, packet):
        """Parse 8-byte packet to voltage values"""
        try:
            counter = packet[2]
            ch0_raw = (packet[3] << 8) | packet[4]
            ch1_raw = (packet[5] << 8) | packet[6]
            
            ch0_uv = (ch0_raw / 16384.0) * 5.0 * 1e6
            ch1_uv = (ch1_raw / 16384.0) * 5.0 * 1e6
            
            self.packet_count += 1
            
            return {
                'timestamp': datetime.now().isoformat(),
                'counter': counter,
                'ch0_adc': ch0_raw,
                'ch1_adc': ch1_raw,
                'ch0_uv': ch0_uv,
                'ch1_uv': ch1_uv
            }
        except Exception as e:
            self.error_count += 1
            return None


# ============================================================================
# SIGNAL FILTER
# ============================================================================

class EOGFilter:
    """Simple EOG signal filtering"""
    
    def __init__(self, fs=512.0):
        self.fs = fs
        self.buffer_size = int(fs * 2)
        self.ch0_buffer = deque(maxlen=self.buffer_size)
        self.ch1_buffer = deque(maxlen=self.buffer_size)
        
        # Design bandpass filter (0.5-35 Hz)
        if SCIPY_AVAILABLE:
            try:
                nyquist = fs / 2
                b, a = butter(2, [0.5/nyquist, 35/nyquist], btype='band')
                self.b = b
                self.a = a
            except:
                self.b = None
                self.a = None
    
    def filter_sample(self, ch0, ch1):
        """Apply filtering to raw samples"""
        self.ch0_buffer.append(ch0)
        self.ch1_buffer.append(ch1)
        
        if not SCIPY_AVAILABLE or self.b is None:
            return ch0, ch1
        
        try:
            ch0_filtered = lfilter(self.b, self.a, list(self.ch0_buffer))[-1]
            ch1_filtered = lfilter(self.b, self.a, list(self.ch1_buffer))[-1]
            return ch0_filtered, ch1_filtered
        except:
            return ch0, ch1


# ============================================================================
# LIVE PLOT
# ============================================================================

class LivePlot:
    """Real-time Matplotlib plot"""
    
    def __init__(self, master_frame):
        if not MATPLOTLIB_AVAILABLE:
            self.canvas_widget = ttk.Label(master_frame, text="Matplotlib not available")
            self.canvas_widget.pack(fill='both', expand=True)
            return
        
        self.fig, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        self.ax.set_title("Real-Time EOG Signal")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (µV)")
        self.ax.grid(True, alpha=0.3)
        
        self.line_ch0, = self.ax.plot([], [], label='Ch0', color='blue', linewidth=1)
        self.line_ch1, = self.ax.plot([], [], label='Ch1', color='red', linewidth=1)
        self.ax.legend()
        
        self.ax.set_xlim(0, Config.PLOT_WINDOW_S)
        self.ax.set_ylim(-100000, 100000)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=master_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)
    
    def update(self, data):
        """Update plot with new data"""
        if not MATPLOTLIB_AVAILABLE or len(data) == 0:
            return
        
        recent = data[-Config.PLOT_MAX_SAMPLES:]
        
        times = [(d['timestamp'] if isinstance(d.get('timestamp'), (int, float)) 
                 else (datetime.fromisoformat(d['timestamp']) - datetime.fromisoformat(data[0]['timestamp'])).total_seconds())
                for d in recent]
        
        ch0_vals = [d.get('ch0_filtered_uv', d['ch0_uv']) for d in recent]
        ch1_vals = [d.get('ch1_filtered_uv', d['ch1_uv']) for d in recent]
        
        self.line_ch0.set_data(times, ch0_vals)
        self.line_ch1.set_data(times, ch1_vals)
        
        if times:
            self.ax.set_xlim(max(0, times[-1] - Config.PLOT_WINDOW_S), times[-1] + 1)
        
        if ch0_vals or ch1_vals:
            all_vals = ch0_vals + ch1_vals
            ymin, ymax = min(all_vals), max(all_vals)
            margin = max(1000, (ymax - ymin) * 0.1)
            self.ax.set_ylim(ymin - margin, ymax + margin)
        
        self.canvas.draw_idle()
    
    def clear(self):
        if MATPLOTLIB_AVAILABLE:
            self.line_ch0.set_data([], [])
            self.line_ch1.set_data([], [])
            self.canvas.draw_idle()


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class EOGAcquisitionApp:
    """Main application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Acquisition System v3.5 - 8-Byte Packets")
        self.root.geometry("1500x950")
        
        self.serial_port = None
        self.is_acquiring = False
        self.acquisition_thread = None
        
        self.parser = PacketParser()
        self.filter = EOGFilter()
        self.session_data = []
        self.session_start = None
        
        self.port_var = tk.StringVar()
        self.filter_enabled = tk.BooleanVar(value=True)
        self.debug_enabled = tk.BooleanVar(value=True)
        
        self.create_ui()
        self.scan_ports()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_displays()
    
    def on_close(self):
        if self.is_acquiring:
            self.stop_acquisition()
        self.root.destroy()
    
    def create_ui(self):
        """Create user interface"""
        
        # Main container
        main = ttk.Frame(self.root)
        main.pack(fill='both', expand=True, padx=5, pady=5)
        
        # LEFT PANEL: Controls
        left = ttk.Frame(main)
        left.pack(side='left', fill='both', padx=5)
        
        # Connection
        conn_frame = ttk.LabelFrame(left, text='Connection', padding=10)
        conn_frame.pack(fill='x', pady=10)
        
        ttk.Label(conn_frame, text='COM Port:').grid(row=0, column=0, sticky='w')
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=15, state='readonly')
        self.port_combo.grid(row=0, column=1, sticky='ew')
        ttk.Button(conn_frame, text='Refresh', command=self.scan_ports).grid(row=0, column=2)
        
        ttk.Label(conn_frame, text='230400 baud | 512 Hz | 8-byte').grid(row=1, column=0, columnspan=3, sticky='w', pady=5)
        conn_frame.columnconfigure(1, weight=1)
        
        # Status
        status_frame = ttk.LabelFrame(left, text='Status', padding=10)
        status_frame.pack(fill='x', pady=10)
        
        ttk.Label(status_frame, text='Connected:').grid(row=0, column=0, sticky='w')
        self.status_label = ttk.Label(status_frame, text='❌ No', foreground='red', font=('Arial', 10, 'bold'))
        self.status_label.grid(row=0, column=1, sticky='w')
        
        ttk.Label(status_frame, text='Packets:').grid(row=1, column=0, sticky='w')
        self.packets_label = ttk.Label(status_frame, text='0', font=('Arial', 10, 'bold'))
        self.packets_label.grid(row=1, column=1, sticky='w')
        
        ttk.Label(status_frame, text='Rate:').grid(row=2, column=0, sticky='w')
        self.rate_label = ttk.Label(status_frame, text='0 Hz', font=('Arial', 10))
        self.rate_label.grid(row=2, column=1, sticky='w')
        
        ttk.Label(status_frame, text='Signal:').grid(row=3, column=0, sticky='w')
        self.signal_label = ttk.Label(status_frame, text='Waiting...', font=('Arial', 10))
        self.signal_label.grid(row=3, column=1, sticky='w')
        
        status_frame.columnconfigure(1, weight=1)
        
        # Controls
        ctrl_frame = ttk.LabelFrame(left, text='Control', padding=10)
        ctrl_frame.pack(fill='x', pady=10)
        
        self.connect_btn = ttk.Button(ctrl_frame, text='🔌 Connect', command=self.connect)
        self.connect_btn.pack(side='left', padx=5)
        
        self.disconnect_btn = ttk.Button(ctrl_frame, text='🔌 Disconnect', command=self.disconnect, state='disabled')
        self.disconnect_btn.pack(side='left', padx=5)
        
        self.start_btn = ttk.Button(ctrl_frame, text='▶ Start', command=self.start_acquisition, state='disabled')
        self.start_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(ctrl_frame, text='⏹ Stop', command=self.stop_acquisition, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        self.save_btn = ttk.Button(ctrl_frame, text='💾 Save', command=self.save_data, state='disabled')
        self.save_btn.pack(side='left', padx=5)
        
        # Options
        opt_frame = ttk.LabelFrame(left, text='Options', padding=10)
        opt_frame.pack(fill='x', pady=10)
        
        ttk.Checkbutton(opt_frame, text='Enable Filtering', variable=self.filter_enabled).pack(anchor='w')
        ttk.Checkbutton(opt_frame, text='Debug Mode', variable=self.debug_enabled).pack(anchor='w')
        
        # Packets display
        pkt_frame = ttk.LabelFrame(left, text='Latest Packets', padding=10)
        pkt_frame.pack(fill='both', expand=True, pady=10)
        
        self.packets_text = tk.Text(pkt_frame, height=15, width=50, font=('Courier', 8), bg='#ffffff')
        self.packets_text.pack(fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(pkt_frame, orient='vertical', command=self.packets_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.packets_text.config(yscrollcommand=scrollbar.set)
        
        # RIGHT PANEL: Plot + Debug
        right = ttk.Frame(main)
        right.pack(side='right', fill='both', expand=True, padx=5)
        
        # Plot frame
        plot_frame = ttk.LabelFrame(right, text='Signal Plot', padding=5)
        plot_frame.pack(fill='both', expand=True, pady=10)
        
        self.live_plot = LivePlot(plot_frame)
        
        # Debug console
        debug_frame = ttk.LabelFrame(right, text='Debug Console', padding=5)
        debug_frame.pack(fill='x', pady=10, side='bottom')
        
        self.debug_text = scrolledtext.ScrolledText(debug_frame, height=8, width=60, bg='#000000', fg='#00FF00', font=('Courier', 8))
        self.debug_text.pack(fill='both', expand=True)
        
        self.debug_log("✅ EOG Acquisition System Ready")
    
    def debug_log(self, msg):
        if not self.debug_enabled.get():
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.debug_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.debug_text.see(tk.END)
    
    def scan_ports(self):
        ports = [f"{p} - {d}" for p, d, _ in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports if ports else ['No ports']
        if ports:
            self.port_combo.current(0)
        self.debug_log(f"Found {len(ports)} port(s)")
    
    def connect(self):
        if not self.port_var.get():
            messagebox.showerror('Error', 'Select port')
            return
        
        port = self.port_var.get().split()[0]
        try:
            self.serial_port = serial.Serial(port, Config.BAUD_RATE, timeout=1)
            time.sleep(2)
            self.serial_port.reset_input_buffer()
            
            self.status_label.config(text='✅ Yes', foreground='green')
            self.connect_btn.config(state='disabled')
            self.disconnect_btn.config(state='normal')
            self.start_btn.config(state='normal')
            
            self.debug_log(f"✅ Connected to {port}")
        except Exception as e:
            self.debug_log(f"❌ Connection failed: {e}")
            messagebox.showerror('Error', str(e))
    
    def disconnect(self):
        if self.is_acquiring:
            self.stop_acquisition()
        if self.serial_port:
            self.serial_port.close()
        
        self.status_label.config(text='❌ No', foreground='red')
        self.connect_btn.config(state='normal')
        self.disconnect_btn.config(state='disabled')
        self.start_btn.config(state='disabled')
        self.debug_log("Disconnected")
    
    def start_acquisition(self):
        if not self.serial_port or not self.serial_port.is_open:
            messagebox.showerror('Error', 'Not connected')
            return
        
        self.debug_log("\n=== ACQUISITION STARTED ===")
        self.session_data = []
        self.session_start = datetime.now()
        self.parser.packet_count = 0
        self.parser.error_count = 0
        
        self.serial_port.reset_input_buffer()
        self.is_acquiring = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.save_btn.config(state='disabled')
        
        self.live_plot.clear()
        
        self.acquisition_thread = threading.Thread(target=self.acquisition_loop, daemon=True)
        self.acquisition_thread.start()
    
    def acquisition_loop(self):
        """Main acquisition loop"""
        debug_count = 0
        
        while self.is_acquiring and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    byte = self.serial_port.read(1)
                    if byte:
                        debug_count += 1
                        if debug_count <= 50:
                            self.debug_log(f"Byte {debug_count}: {byte.hex().upper()}")
                        
                        packet = self.parser.add_byte(byte)
                        if packet:
                            elapsed = (datetime.now() - self.session_start).total_seconds()
                            packet['elapsed_s'] = elapsed
                            
                            # Apply filter if enabled
                            if self.filter_enabled.get():
                                ch0_f, ch1_f = self.filter.filter_sample(packet['ch0_uv'], packet['ch1_uv'])
                                packet['ch0_filtered_uv'] = ch0_f
                                packet['ch1_filtered_uv'] = ch1_f
                            
                            self.session_data.append(packet)
                else:
                    time.sleep(0.001)
            except Exception as e:
                self.debug_log(f"Error: {e}")
                break
        
        self.debug_log(f"Stopped. {self.parser.packet_count} packets, {self.parser.error_count} errors")
    
    def stop_acquisition(self):
        self.is_acquiring = False
        time.sleep(0.5)
        
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.save_btn.config(state='normal')
        
        self.debug_log(f"=== STOPPED: {len(self.session_data)} packets ===\n")
    
    def update_displays(self):
        """Update UI displays"""
        
        # Update packets
        self.packets_label.config(text=str(self.parser.packet_count))
        
        if self.parser.packet_count > 0 and self.session_start:
            elapsed = (datetime.now() - self.session_start).total_seconds()
            rate = self.parser.packet_count / elapsed if elapsed > 0 else 0
            self.rate_label.config(text=f'{rate:.1f} Hz')
        
        # Update packets table
        self.packets_text.config(state='normal')
        self.packets_text.delete('1.0', tk.END)
        
        text = 'LATEST PACKETS\n' + '='*45 + '\n'
        text += f"{'#':<5} {'Ctr':<4} {'Ch0 (µV)':<15} {'Ch1 (µV)':<15}\n"
        text += '-'*45 + '\n'
        
        for d in self.session_data[-10:]:
            text += f"{d['counter']:<5} {d['counter']:<4} {d['ch0_uv']:<15.0f} {d['ch1_uv']:<15.0f}\n"
        
        if len(self.session_data) > 0:
            ch0_vals = [d['ch0_uv'] for d in self.session_data]
            ch1_vals = [d['ch1_uv'] for d in self.session_data]
            
            text += '\n' + '='*45 + '\n'
            text += f"Ch0: {min(ch0_vals):.0f} - {max(ch0_vals):.0f} µV\n"
            text += f"Ch1: {min(ch1_vals):.0f} - {max(ch1_vals):.0f} µV\n"
        
        self.packets_text.insert('1.0', text)
        self.packets_text.config(state='disabled')
        
        # Update plot
        self.live_plot.update(self.session_data)
        
        # Schedule next update
        self.root.after(200, self.update_displays)
    
    def save_data(self):
        """Save session to JSON"""
        if not self.session_data:
            messagebox.showwarning('Empty', 'No data to save')
            return
        
        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            
            filepath = Config.OUTPUT_DIR / f'eog_{ts}.json'
            
            data = {
                'session': {
                    'start': self.session_start.isoformat(),
                    'duration_s': (datetime.now() - self.session_start).total_seconds(),
                    'packets': len(self.session_data),
                    'sampling_rate_hz': 512,
                    'packet_format': '8-byte: [0xC7][0x7C][CTR][Ch0H][Ch0L][Ch1H][Ch1L][0x01]'
                },
                'data': self.session_data
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.debug_log(f"✅ Saved to {filepath}")
            messagebox.showinfo('Saved', f'{len(self.session_data)} packets saved')
        except Exception as e:
            self.debug_log(f"❌ Save failed: {e}")
            messagebox.showerror('Error', str(e))


# ============================================================================
# MAIN
# ============================================================================

def main():
    root = tk.Tk()
    app = EOGAcquisitionApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()