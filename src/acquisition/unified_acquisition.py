"""
OPTIMIZED UNIFIED ACQUISITION SYSTEM FOR EMG, EOG, EEG
========================================================
Features:
- Robust serial packet synchronization with error recovery
- Queue-based threading for reliable high-speed data collection
- LSL integration for real-time streaming to game applications
- Comprehensive data logging and session management
- Production-ready error handling and recovery

Modifications for pipeline:
- Publishes raw ADC stream "BioSignals-Raw" for external filter processes.
- Publishes processed µV stream "BioSignals" (if LSL available).
- Duplicate suppression (by packet counter).
- Session data now stores raw ADC values + converted µV.
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
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import queue
import sys
from dataclasses import dataclass, asdict
from typing import Optional, Dict

# LSL integration (optional - graceful fallback)
try:
    import pylsl
    LSL_AVAILABLE = True
except Exception:
    LSL_AVAILABLE = False
    print("⚠️  LSL not available - install with: pip install pylsl")

# Filtering (optional)
try:
    from scipy.signal import butter, sosfilt, sosfilt_zi, iirnotch, tf2sos
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False
    print("⚠️  scipy not available - filters disabled. Install with: pip install scipy")

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


# ============================================================================
# DATA STRUCTURES & CONSTANTS
# ============================================================================

@dataclass
class Packet:
    """Parsed packet structure"""
    counter: int
    ch0_raw: int
    ch1_raw: int
    timestamp: datetime

    def to_dict(self):
        return asdict(self)


class PacketConfig:
    """Hardware packet configuration"""
    PACKET_LEN = 8
    SYNC_BYTE_1 = 0xC7
    SYNC_BYTE_2 = 0x7C
    END_BYTE = 0x01
    SAMPLING_RATE = 512.0
    BAUD_RATE = 230400
    NUM_CHANNELS = 2

    # Timeouts
    CONNECT_TIMEOUT = 2.0
    STREAM_IDLE_TIMEOUT = 3.0
    PACKET_TIMEOUT = 5.0


class SignalProcessing:
    """Convert raw ADC to physical units"""

    @staticmethod
    def adc_to_uv(adc_value: int, adc_bits: int = 14, vref: float = 3300.0) -> float:
        """
        Convert ADC reading to µV

        Standard formula:
        V = (ADC / 2^bits) * Vref - (Vref/2)
        """
        return ((adc_value / (2 ** adc_bits)) * vref) - (vref / 2.0)

    @staticmethod
    def validate_value(value: float, signal_type: str) -> bool:
        """Check if value is physically reasonable"""
        limits = {
            'EMG': (-5000, 5000),      # ±5mV typical
            'EOG': (-2000, 2000),      # ±2mV typical
            'EEG': (-1000, 1000)       # ±1mV typical
        }
        if signal_type in limits:
            low, high = limits[signal_type]
            return low <= value <= high
        return True


# ============================================================================
# SERIAL COMMUNICATION & PACKET SYNC
# ============================================================================

class SerialPacketReader:
    """Thread-safe serial reader with robust packet synchronization"""

    def __init__(self, port: str, baud: int = 230400, packet_config: PacketConfig = None):
        self.port = port
        self.baud = baud
        self.config = packet_config or PacketConfig()

        self.ser: Optional[serial.Serial] = None
        self.is_running = False
        self.data_queue: queue.Queue = queue.Queue(maxsize=10000)

        # Statistics
        self.packets_received = 0
        self.packets_dropped = 0
        self.sync_errors = 0
        self.crc_errors = 0
        self.duplicates = 0
        self.bytes_received = 0
        self.last_packet_time = None

    def connect(self) -> bool:
        """Establish serial connection"""
        try:
            self.ser = serial.Serial(
                self.port,
                self.baud,
                timeout=0.1,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE
            )
            time.sleep(self.config.CONNECT_TIMEOUT)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"✅ Connected to {self.port} @ {self.baud} baud")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        """Close serial connection"""
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
                print("✅ Disconnected")
            except Exception:
                pass

    def start(self):
        """Start packet reading thread"""
        self.is_running = True
        thread = threading.Thread(target=self._read_loop, daemon=True)
        thread.start()

    def stop(self):
        """Stop packet reading thread"""
        self.is_running = False

    def send_command(self, cmd: str) -> bool:
        """Send command to device"""
        if not (self.ser and self.ser.is_open):
            return False
        try:
            self.ser.write(f"{cmd}\n".encode())
            self.ser.flush()
            return True
        except Exception as e:
            print(f"❌ Send command failed: {e}")
            return False

    def _read_loop(self):
        """Main packet reading loop (runs in background thread)"""
        buffer = bytearray()

        while self.is_running:
            if not (self.ser and self.ser.is_open):
                time.sleep(0.1)
                continue

            try:
                # Read available data
                available = self.ser.in_waiting
                if available > 0:
                    chunk = self.ser.read(min(available, 4096))
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                        self._process_buffer(buffer)
                else:
                    time.sleep(0.001)

            except Exception as e:
                print(f"❌ Read error: {e}")
                time.sleep(0.1)

    def _process_buffer(self, buffer: bytearray) -> None:
        """Extract valid packets from buffer"""
        while len(buffer) >= self.config.PACKET_LEN:
            # Look for sync bytes
            if (buffer[0] == self.config.SYNC_BYTE_1 and
                    buffer[1] == self.config.SYNC_BYTE_2):

                # Check end byte
                if buffer[self.config.PACKET_LEN - 1] == self.config.END_BYTE:
                    # Valid packet found
                    packet_bytes = bytes(buffer[:self.config.PACKET_LEN])
                    try:
                        self.data_queue.put_nowait(packet_bytes)
                        self.packets_received += 1
                        self.last_packet_time = time.time()
                    except queue.Full:
                        self.packets_dropped += 1

                    del buffer[:self.config.PACKET_LEN]
                else:
                    # Invalid end byte - drop one byte and retry
                    del buffer[0]
                    self.sync_errors += 1
            else:
                # No sync - drop first byte
                del buffer[0]
                self.sync_errors += 1

    def get_packet(self, timeout: float = 0.1) -> Optional[bytes]:
        """Retrieve parsed packet"""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_stats(self) -> Dict:
        """Return read statistics"""
        elapsed = time.time() - self.last_packet_time if self.last_packet_time else 0
        rate = self.packets_received / elapsed if elapsed > 0 else 0
        speed_kbps = (self.bytes_received / elapsed / 1024) if elapsed > 0 else 0

        return {
            'packets_received': self.packets_received,
            'packets_dropped': self.packets_dropped,
            'sync_errors': self.sync_errors,
            'duplicates': self.duplicates,
            'rate_hz': rate,
            'speed_kbps': speed_kbps,
            'queue_size': self.data_queue.qsize()
        }


# ============================================================================
# PACKET PARSING & DATA CONVERSION
# ============================================================================

class PacketParser:
    """Parse binary packets into physical units"""

    def __init__(self, config: PacketConfig = None):
        self.config = config or PacketConfig()

    def parse(self, packet_bytes: bytes) -> Packet:
        """
        Parse packet: [SYNC1, SYNC2, CTR, CH0_H, CH0_L, CH1_H, CH1_L, END]

        Returns: Packet with converted ADC values
        """
        if len(packet_bytes) != self.config.PACKET_LEN:
            raise ValueError(f"Invalid packet length: {len(packet_bytes)}")

        counter = packet_bytes[2]
        ch0_raw = (packet_bytes[3] << 8) | packet_bytes[4]
        ch1_raw = (packet_bytes[5] << 8) | packet_bytes[6]

        return Packet(
            counter=counter,
            ch0_raw=int(ch0_raw),
            ch1_raw=int(ch1_raw),
            timestamp=datetime.now()
        )


# ============================================================================
# LSL INTEGRATION (OPTIONAL)
# ============================================================================

class LSLStreamer:
    """Stream data via Lab Streaming Layer"""

    def __init__(self, name: str, channel_types: list, channel_count: int = 2):
        self.name = name
        self.channel_types = channel_types
        self.channel_count = channel_count
        self.outlet: Optional[pylsl.StreamOutlet] = None

        if not LSL_AVAILABLE:
            print(f"⚠️  LSL not available - cannot create stream '{name}'")
            return

        try:
            # Create info
            info = pylsl.StreamInfo(
                name=name,
                type='EEG',
                channel_count=self.channel_count,
                nominal_srate=PacketConfig.SAMPLING_RATE,
                channel_format='float32',
                source_id=name
            )

            # Add channel names
            channels = info.desc().append_child("channels")
            for i, ch_type in enumerate(self.channel_types):
                channels.append_child("channel") \
                    .append_child_value("label", f"{ch_type}_{i}") \
                    .append_child_value("type", ch_type)

            self.outlet = pylsl.StreamOutlet(info)
            print(f"✅ LSL stream '{name}' created (channels={self.channel_count})")
        except Exception as e:
            print(f"❌ LSL setup failed for '{name}': {e}")

    def push_sample(self, sample: list, ts: float = None):
        """Push data sample to LSL"""
        if self.outlet:
            try:
                if ts is not None:
                    self.outlet.push_sample(sample, ts)
                else:
                    self.outlet.push_sample(sample)
            except Exception as e:
                print(f"LSL push error ({self.name}): {e}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class UnifiedAcquisitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Unified Signal Acquisition (EMG/EOG/EEG) - Optimized")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Hardware config
        self.config = PacketConfig()

        # Serial reader
        self.serial_reader: Optional[SerialPacketReader] = None
        self.packet_parser = PacketParser(self.config)

        # LSL streamers
        self.lsl_raw = None       # publishes raw ADC values to BioSignals-Raw
        self.lsl_streamer = None  # publishes processed µV to BioSignals

        # State
        self.is_connected = False
        self.is_acquiring = False
        self.is_recording = False
        self.session_start_time = None
        self.packet_count = 0
        self.latest_packet: Optional[dict] = None

        # Packet deduplication
        self.last_packet_counter: Optional[int] = None

        # Channel mapping
        self.channel_mapping = {0: 'EEG', 1: 'EOG'}

        # Visualization Buffers (Sweep Mode - 4 seconds)
        self.window_seconds = 4.0
        self.buffer_size = int(self.config.SAMPLING_RATE * self.window_seconds)
        self.vis_ch0 = np.zeros(self.buffer_size)
        self.vis_ch1 = np.zeros(self.buffer_size)
        self.vis_ptr = 0  # Current write index
        self.x_axis = np.linspace(0, self.window_seconds, self.buffer_size)

        # Session data
        self.session_data = []
        self.save_path = Path("data/raw/session")

        # Batch update control
        self.pending_updates = 0
        self.last_update_time = time.time()
        self.update_interval = 0.1  # 100ms batch updates

        # Filter state
        self.filter_enabled_var = tk.BooleanVar(value=False)
        self.bp_low_var = tk.DoubleVar(value=1.0)
        self.bp_high_var = tk.DoubleVar(value=100.0)
        self.notch_freq_var = tk.DoubleVar(value=50.0)
        self.notch_q_var = tk.DoubleVar(value=30.0)
        self.sos_bandpass = None
        self.sos_notch = None
        self.sos_combined = None
        self.zi_ch0 = None
        self.zi_ch1 = None

        # UI Control Vars
        self.show_graph_var = tk.BooleanVar(value=True)

        # UI
        self.setup_ui()
        self.update_port_list()

        # Main loop
        self.root.after(30, self.main_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """Build UI"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # ---- LEFT PANEL (Scrollable) ----
        left_container = ttk.Frame(main_frame, width=360)
        left_container.pack(side="left", fill="both", expand=False, padx=5)

        canvas = tk.Canvas(left_container, width=340, highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)

        # Create the inner frame that will hold the widgets
        left_frame = ttk.Frame(canvas)

        left_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=left_frame, anchor="nw")

        # Ensure inner frame expands to canvas width
        def configure_canvas(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", configure_canvas)

        canvas.configure(yscrollcommand=scrollbar.set, bg='#f0f0f0')
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        left_container.bind('<Enter>', lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        left_container.bind('<Leave>', lambda e: canvas.unbind_all("<MouseWheel>"))

        # Connection
        conn_frame = ttk.LabelFrame(left_frame, text="Connection", padding=10)
        conn_frame.pack(fill="x", pady=5)
        ttk.Label(conn_frame, text="COM Port:").pack(anchor="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var,
                                       width=30, state="readonly")
        self.port_combo.pack(fill="x", pady=2)
        ttk.Button(conn_frame, text="Refresh", command=self.update_port_list).pack(fill="x", pady=2)

        # Status
        status_frame = ttk.LabelFrame(left_frame, text="Status", padding=10)
        status_frame.pack(fill="x", pady=5)
        ttk.Label(status_frame, text="Connection:").pack(anchor="w")
        self.status_label = ttk.Label(status_frame, text="Disconnected",
                                      foreground="red", font=("Arial", 10, "bold"))
        self.status_label.pack(anchor="w", pady=2)
        ttk.Label(status_frame, text="Packets:").pack(anchor="w")
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w")
        ttk.Label(status_frame, text="Duration:").pack(anchor="w")
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w")
        ttk.Label(status_frame, text="Rate (Hz):").pack(anchor="w")
        self.rate_label = ttk.Label(status_frame, text="0 Hz")
        self.rate_label.pack(anchor="w")
        ttk.Label(status_frame, text="Speed (KBps):").pack(anchor="w")
        self.speed_label = ttk.Label(status_frame, text="0 KBps")
        self.speed_label.pack(anchor="w")

        # Channel mapping
        mapping_frame = ttk.LabelFrame(left_frame, text="Channel Mapping", padding=10)
        mapping_frame.pack(fill="x", pady=5)
        ttk.Label(mapping_frame, text="Channel 0:").pack(anchor="w", pady=5)
        self.ch0_var = tk.StringVar(value='EEG')
        ch0_combo = ttk.Combobox(mapping_frame, textvariable=self.ch0_var,
                                 values=['EMG', 'EOG', 'EEG'], state="readonly", width=20)
        ch0_combo.pack(fill="x", pady=2)
        ch0_combo.bind('<<ComboboxSelected>>', self.on_mapping_changed)

        ttk.Label(mapping_frame, text="Channel 1:").pack(anchor="w", pady=5)
        self.ch1_var = tk.StringVar(value='EOG')
        ch1_combo = ttk.Combobox(mapping_frame, textvariable=self.ch1_var,
                                 values=['EMG', 'EOG', 'EEG'], state="readonly", width=20)
        ch1_combo.pack(fill="x", pady=2)
        ch1_combo.bind('<<ComboboxSelected>>', self.on_mapping_changed)

        # Control
        control_frame = ttk.LabelFrame(left_frame, text="Control", padding=10)
        control_frame.pack(fill="x", pady=5)
        self.connect_btn = ttk.Button(control_frame, text="Connect",
                                      command=self.connect_device)
        self.connect_btn.pack(fill="x", pady=2)
        self.disconnect_btn = ttk.Button(control_frame, text="Disconnect",
                                         command=self.disconnect_device, state="disabled")
        self.disconnect_btn.pack(fill="x", pady=2)
        self.start_btn = ttk.Button(control_frame, text="Start",
                                    command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", pady=2)
        self.stop_btn = ttk.Button(control_frame, text="Stop",
                                   command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", pady=2)

        # Visuals Toggle
        ttk.Checkbutton(control_frame, text="Enable Real-time Graph",
                       variable=self.show_graph_var).pack(fill="x", pady=5)

        # Recording
        rec_frame = ttk.LabelFrame(left_frame, text="Recording", padding=10)
        rec_frame.pack(fill="x", pady=5)
        self.rec_btn = ttk.Button(rec_frame, text="Start Recording",
                                  command=self.toggle_recording, state="disabled")
        self.rec_btn.pack(fill="x", pady=2)

        # Save
        save_frame = ttk.LabelFrame(left_frame, text="Save", padding=10)
        save_frame.pack(fill="x", pady=5)
        ttk.Button(save_frame, text="Choose Path", command=self.choose_save_path).pack(fill="x", pady=2)
        self.path_label = ttk.Label(save_frame, text=str(self.save_path),
                                    wraplength=250, justify="left", foreground="gray")
        self.path_label.pack(fill="x", pady=4)
        self.save_btn = ttk.Button(save_frame, text="Save Session",
                                   command=self.save_session, state="disabled")
        self.save_btn.pack(fill="x", pady=2)

        # Filtering controls
        filter_frame = ttk.LabelFrame(left_frame, text="Filters (real-time)", padding=10)
        filter_frame.pack(fill="x", pady=5)

        ttk.Checkbutton(filter_frame, text="Enable Filtering", variable=self.filter_enabled_var,
                        command=self.on_filter_toggle).pack(anchor="w", pady=4)

        # Bandpass low
        low_frame = ttk.Frame(filter_frame)
        low_frame.pack(fill="x", pady=2)
        ttk.Label(low_frame, text="Bandpass low (Hz):").pack(side="left")
        self.bp_low_scale = ttk.Scale(low_frame, from_=0.1, to=200.0, variable=self.bp_low_var, orient="horizontal",
                                      command=lambda e: self.on_filter_param_change())
        self.bp_low_scale.pack(side="right", fill="x", expand=True)

        # Bandpass high
        high_frame = ttk.Frame(filter_frame)
        high_frame.pack(fill="x", pady=2)
        ttk.Label(high_frame, text="Bandpass high (Hz):").pack(side="left")
        self.bp_high_scale = ttk.Scale(high_frame, from_=1.0, to=250.0, variable=self.bp_high_var, orient="horizontal",
                                       command=lambda e: self.on_filter_param_change())
        self.bp_high_scale.pack(side="right", fill="x", expand=True)

        # Notch frequency
        notch_frame = ttk.Frame(filter_frame)
        notch_frame.pack(fill="x", pady=2)
        ttk.Label(notch_frame, text="Notch (Hz):").pack(side="left")
        self.notch_scale = ttk.Scale(notch_frame, from_=40.0, to=70.0, variable=self.notch_freq_var, orient="horizontal",
                                     command=lambda e: self.on_filter_param_change())
        self.notch_scale.pack(side="right", fill="x", expand=True)

        # Notch Q
        q_frame = ttk.Frame(filter_frame)
        q_frame.pack(fill="x", pady=2)
        ttk.Label(q_frame, text="Notch Q:").pack(side="left")
        self.notch_q_scale = ttk.Scale(q_frame, from_=5.0, to=60.0, variable=self.notch_q_var, orient="horizontal",
                                       command=lambda e: self.on_filter_param_change())
        self.notch_q_scale.pack(side="right", fill="x", expand=True)

        # Latest packet
        latest_frame = ttk.LabelFrame(left_frame, text="Latest packet", padding=8)
        latest_frame.pack(fill="x", pady=5)
        self.latest_text = tk.Text(latest_frame, height=8, width=40, wrap="word", font=("Courier", 9))
        self.latest_text.insert("1.0", "No packet yet.")
        self.latest_text.configure(state="disabled")
        self.latest_text.pack(fill="both", expand=True)

        # ---- RIGHT PANEL ----
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)

        graph_frame = ttk.LabelFrame(right_frame, text="Real-Time Signals", padding=5)
        graph_frame.pack(fill="both", expand=True)

        self.fig = Figure(figsize=(10, 6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')

        self.ax_ch0 = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_ch0.plot(self.x_axis, self.vis_ch0, linewidth=1.0, label='Ch0 (Raw)')
        self.cursor_ch0 = self.ax_ch0.axvline(0, color='red', alpha=0.5, linestyle='--')
        self.ax_ch0.set_ylabel('Voltage (µV)', fontsize=10)
        self.ax_ch0.set_xlim(0, self.window_seconds)
        self.ax_ch0.grid(True, alpha=0.3)
        self.ax_ch0.legend(loc='upper right')

        self.ax_ch1 = self.fig.add_subplot(212)
        self.line_ch1, = self.ax_ch1.plot(self.x_axis, self.vis_ch1, linewidth=1.0, label='Ch1 (Raw)')
        self.cursor_ch1 = self.ax_ch1.axvline(0, color='red', alpha=0.5, linestyle='--')
        self.ax_ch1.set_ylabel('Voltage (µV)', fontsize=10)
        self.ax_ch1.set_xlabel('Time (s)', fontsize=10)
        self.ax_ch1.set_xlim(0, self.window_seconds)
        self.ax_ch1.grid(True, alpha=0.3)
        self.ax_ch1.legend(loc='upper right')

        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # initialize filters if possible
        if SCIPY_AVAILABLE:
            self.design_filters()
        else:
            print("Filters disabled: scipy not found")

    def update_port_list(self):
        """Refresh COM port list"""
        ports = []
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{port} - {desc}")
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)

    def on_mapping_changed(self, event=None):
        """Handle channel mapping change"""
        self.channel_mapping[0] = self.ch0_var.get()
        self.channel_mapping[1] = self.ch1_var.get()
        print(f"Channel mapping: {self.channel_mapping}")

    def connect_device(self):
        """Establish serial connection"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return

        port_name = self.port_var.get().split(" ")[0]

        try:
            self.serial_reader = SerialPacketReader(port_name, self.config.BAUD_RATE, self.config)
            if self.serial_reader.connect():
                self.serial_reader.start()
                self.is_connected = True
                self.status_label.config(text="Connected", foreground="green")
                self.connect_btn.config(state="disabled")
                self.disconnect_btn.config(state="normal")
                self.start_btn.config(state="normal")

                # Initialize LSL outlets
                if LSL_AVAILABLE:
                    ch_types = [self.channel_mapping[0], self.channel_mapping[1]]
                    # raw ADC stream for pipeline consumers
                    self.lsl_raw = LSLStreamer("BioSignals-Raw", ch_types, channel_count=2)
                    # processed µV stream
                    self.lsl_streamer = LSLStreamer("BioSignals", ch_types, channel_count=2)

                messagebox.showinfo("Success", f"Connected to {port_name}")
            else:
                messagebox.showerror("Error", "Connection failed")
        except Exception as e:
            messagebox.showerror("Error", f"Connection error: {e}")

    def disconnect_device(self):
        """Close serial connection"""
        if self.is_acquiring:
            self.stop_acquisition()

        self.is_connected = False
        if self.serial_reader:
            self.serial_reader.disconnect()

        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")

    def start_acquisition(self):
        """Begin data acquisition"""
        if not (self.serial_reader and self.is_connected):
            messagebox.showerror("Error", "Device not connected")
            return

        try:
            # Send START command
            if self.serial_reader.send_command("START"):
                time.sleep(0.05)
            else:
                messagebox.showwarning("Warning", "Could not send START command")

            self.is_acquiring = True
            self.is_recording = True
            self.session_start_time = datetime.now()
            self.packet_count = 0
            self.session_data = []
            self.vis_ch0.fill(0)
            self.vis_ch1.fill(0)
            self.vis_ptr = 0
            self.last_packet_counter = None
            # reset filter states
            if SCIPY_AVAILABLE:
                self.reset_filter_state()
            print("Acquisition started")
        except Exception as e:
            messagebox.showerror("Error", f"Start failed: {e}")

    def stop_acquisition(self):
        """End data acquisition"""
        try:
            if self.serial_reader:
                self.serial_reader.send_command("STOP")
        except Exception:
            pass

        self.is_acquiring = False
        self.is_recording = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.rec_btn.config(state="normal", text="Start Recording")
        self.status_label.config(text="Connected", foreground="green")
        print("Acquisition stopped")

    def toggle_recording(self):
        """Toggle recording on/off"""
        if not self.is_acquiring:
            messagebox.showerror("Error", "Start acquisition first")
            return

        self.is_recording = not self.is_recording
        if self.is_recording:
            self.rec_btn.config(text="Stop Recording")
            print("Recording ON")
        else:
            self.rec_btn.config(text="Start Recording")
            print("Recording OFF")

    def choose_save_path(self):
        """Select save directory"""
        path = filedialog.askdirectory(title="Select save directory", initialdir=str(self.save_path))
        if path:
            self.save_path = Path(path)
            self.path_label.config(text=str(self.save_path))

    def save_session(self):
        """Save session data to JSON"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return

        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            folder = self.save_path
            folder.mkdir(parents=True, exist_ok=True)

            filename = f"session_{timestamp}.json"
            filepath = folder / filename

            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat() if self.session_start_time else None,
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0,
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.config.SAMPLING_RATE,
                    "channel_0_type": self.channel_mapping[0],
                    "channel_1_type": self.channel_mapping[1],
                    "filters_enabled": bool(self.filter_enabled_var.get()),
                    "bp_low_hz": float(self.bp_low_var.get()),
                    "bp_high_hz": float(self.bp_high_var.get()),
                    "notch_hz": float(self.notch_freq_var.get()),
                    "notch_q": float(self.notch_q_var.get())
                },
                "data": self.session_data
            }

            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)

            messagebox.showinfo("Saved", f"Saved {len(self.session_data)} packets\nFile: {filepath}")
            print(f"Session saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")

    # ---------------- FILTER HELPERS ----------------
    def on_filter_toggle(self):
        if not SCIPY_AVAILABLE and self.filter_enabled_var.get():
            messagebox.showwarning("Filters unavailable", "scipy not installed — filtering disabled.")
            self.filter_enabled_var.set(False)
            return
        # (re)design filters when toggled
        if SCIPY_AVAILABLE:
            self.design_filters()
            self.reset_filter_state()

    def on_filter_param_change(self):
        # Called continuously as sliders move; re-design filters but not too often
        if SCIPY_AVAILABLE and self.filter_enabled_var.get():
            self.design_filters()
            # reset to avoid transient artifacts
            self.reset_filter_state()

    def design_filters(self):
        """Design bandpass and notch SOS filters based on UI params"""
        fs = self.config.SAMPLING_RATE
        low = float(self.bp_low_var.get())
        high = float(self.bp_high_var.get())
        notch_freq = float(self.notch_freq_var.get())
        q = float(self.notch_q_var.get())

        # Validate band edges
        nyq = 0.5 * fs
        if low <= 0:
            low = 0.1
        if high <= low + 0.1:
            high = min(low + 0.1, nyq - 0.1)

        # Bandpass (4th order Butterworth using SOS)
        try:
            if low < (nyq * 0.0001):
                low = 0.1
            if high >= nyq:
                high = nyq - 0.1
            bp_sos = butter(N=4, Wn=[low / nyq, high / nyq], btype='bandpass', output='sos')
            self.sos_bandpass = bp_sos
        except Exception as e:
            print(f"Bandpass design failed: {e}")
            self.sos_bandpass = None

        # Notch
        try:
            b, a = iirnotch(notch_freq / nyq, q)
            notch_sos = tf2sos(b, a)
            self.sos_notch = notch_sos
        except Exception as e:
            print(f"Notch design failed: {e}")
            self.sos_notch = None

        # Compose combined SOS (notch -> bandpass)
        if self.sos_bandpass is not None and self.sos_notch is not None:
            try:
                self.sos_combined = np.vstack((self.sos_notch, self.sos_bandpass))
            except Exception:
                self.sos_combined = self.sos_bandpass
        elif self.sos_bandpass is not None:
            self.sos_combined = self.sos_bandpass
        elif self.sos_notch is not None:
            self.sos_combined = self.sos_notch
        else:
            self.sos_combined = None

    def reset_filter_state(self):
        """Initialize zi (filter states) for streaming sosfilt"""
        if not SCIPY_AVAILABLE or self.sos_combined is None:
            self.zi_ch0 = None
            self.zi_ch1 = None
            return
        try:
            self.zi_ch0 = sosfilt_zi(self.sos_combined) * 0.0
            self.zi_ch1 = sosfilt_zi(self.sos_combined) * 0.0
        except Exception as e:
            print(f"Error initializing filter state: {e}")
            self.zi_ch0 = None
            self.zi_ch1 = None

    def apply_filter_sample(self, sample_value: float, ch: int) -> float:
        """Apply configured sos filter to a single sample, preserving zi."""
        if not SCIPY_AVAILABLE or not self.filter_enabled_var.get() or getattr(self, 'sos_combined', None) is None:
            return sample_value

        try:
            if ch == 0:
                if self.zi_ch0 is None:
                    self.reset_filter_state()
                y, zf = sosfilt(self.sos_combined, [sample_value], zi=self.zi_ch0)
                self.zi_ch0 = zf
                return float(y[0])
            else:
                if self.zi_ch1 is None:
                    self.reset_filter_state()
                y, zf = sosfilt(self.sos_combined, [sample_value], zi=self.zi_ch1)
                self.zi_ch1 = zf
                return float(y[0])
        except Exception as e:
            print(f"Filter apply error: {e}")
            return sample_value

    # ---------------- END FILTER HELPERS ----------------

    def main_loop(self):
        """Main update loop - batch processes packets"""
        try:
            if self.is_acquiring and self.serial_reader:
                # Process all queued packets
                while True:
                    packet_bytes = self.serial_reader.get_packet(timeout=0.001)
                    if packet_bytes is None:
                        break

                    try:
                        packet = self.packet_parser.parse(packet_bytes)
                        self._handle_packet(packet)
                        self.pending_updates += 1
                    except Exception as e:
                        print(f"Parse error: {e}")

            # Batch UI updates (every 100ms or 200+ packets)
            current_time = time.time()
            if (current_time - self.last_update_time >= self.update_interval or
                    self.pending_updates > 200):
                self._update_ui()
                self.last_update_time = current_time
                self.pending_updates = 0

        except Exception as e:
            print(f"Main loop error: {e}")

        if self.root.winfo_exists():
            self.root.after(30, self.main_loop)

    def _handle_packet(self, packet: Packet):
        """Process single packet"""

        # Simple duplicate suppression: ignore exact repeated counter values
        if self.last_packet_counter is not None and packet.counter == self.last_packet_counter:
            # register duplicate and skip processing
            if self.serial_reader:
                self.serial_reader.duplicates += 1
            return
        self.last_packet_counter = packet.counter

        # Convert to µV
        ch0_uv = SignalProcessing.adc_to_uv(packet.ch0_raw)
        ch1_uv = SignalProcessing.adc_to_uv(packet.ch1_raw)

        # Apply filters if enabled
        if SCIPY_AVAILABLE and self.filter_enabled_var.get():
            try:
                ch0_uv = self.apply_filter_sample(ch0_uv, ch=0)
                ch1_uv = self.apply_filter_sample(ch1_uv, ch=1)
            except Exception as e:
                print(f"Filter processing error: {e}")

        # Update visualization buffers (Circular overwrite)
        self.vis_ch0[self.vis_ptr] = ch0_uv
        self.vis_ch1[self.vis_ptr] = ch1_uv
        self.vis_ptr = (self.vis_ptr + 1) % self.buffer_size

        # Create data entry with both raw ADC and µV (processed)
        data_entry = {
            "timestamp": packet.timestamp.isoformat(),
            "packet_seq": int(packet.counter),
            "ch0_raw_adc": int(packet.ch0_raw),
            "ch1_raw_adc": int(packet.ch1_raw),
            "ch0_uv": float(ch0_uv),
            "ch1_uv": float(ch1_uv),
            "ch0_type": self.channel_mapping[0],
            "ch1_type": self.channel_mapping[1]
        }

        # Record if active
        if self.is_recording:
            self.session_data.append(data_entry)

        # LSL streaming:
        # - push raw ADC to BioSignals-Raw for external filter processors
        if self.lsl_raw:
            try:
                self.lsl_raw.push_sample([float(packet.ch0_raw), float(packet.ch1_raw)], None)
            except Exception as e:
                print(f"LSL raw push error: {e}")

        # - push processed µV to BioSignals
        if self.lsl_streamer:
            try:
                self.lsl_streamer.push_sample([float(ch0_uv), float(ch1_uv)], None)
            except Exception as e:
                print(f"LSL processed push error: {e}")

        self.latest_packet = data_entry
        self.packet_count += 1

    def _update_ui(self):
        """Batch UI updates"""
        # Status labels
        if self.session_start_time:
            elapsed = (datetime.now() - self.session_start_time).total_seconds()
            hours, remainder = divmod(int(elapsed), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.duration_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

            if elapsed > 0 and self.serial_reader:
                stats = self.serial_reader.get_stats()
                self.rate_label.config(text=f"{stats['rate_hz']:.1f} Hz")
                self.speed_label.config(text=f"{stats['speed_kbps']:.2f} KBps")

        self.packet_label.config(text=str(self.packet_count))

        # Latest packet display
        if self.latest_packet:
            try:
                self.latest_text.configure(state="normal")
                self.latest_text.delete("1.0", "end")
                self.latest_text.insert("1.0", json.dumps(self.latest_packet, indent=2))
                self.latest_text.configure(state="disabled")
            except Exception:
                pass

        # Graph update
        if self.show_graph_var.get():
            try:
                # Update lines
                self.line_ch0.set_ydata(self.vis_ch0)
                self.line_ch1.set_ydata(self.vis_ch1)

                # Update cursor position
                current_time = self.x_axis[self.vis_ptr]
                self.cursor_ch0.set_xdata([current_time])
                self.cursor_ch1.set_xdata([current_time])

                # Auto-scale Y occasionally
                if self.packet_count % 10 == 0:
                    try:
                        min0, max0 = np.min(self.vis_ch0), np.max(self.vis_ch0)
                        min1, max1 = np.min(self.vis_ch1), np.max(self.vis_ch1)
                        if max0 - min0 > 1e-6:
                            self.ax_ch0.set_ylim(min0 - 100, max0 + 100)
                        if max1 - min1 > 1e-6:
                            self.ax_ch1.set_ylim(min1 - 100, max1 + 100)
                    except Exception:
                        pass

                self.canvas.draw_idle()
            except Exception as e:
                print(f"Graph error: {e}")

    def on_closing(self):
        """Cleanup on exit"""
        try:
            self.is_connected = False
            if self.is_acquiring:
                self.stop_acquisition()
            if self.serial_reader:
                self.serial_reader.disconnect()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = UnifiedAcquisitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
