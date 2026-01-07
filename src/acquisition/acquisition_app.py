import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import time
import threading
from pathlib import Path
from datetime import datetime
import numpy as np
import sys
import os
import queue
import subprocess # Added explicit import
import struct



# Ensure we can import sibling packages
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from utils.config import config_manager, ConfigWriter

# Local imports
from .serial_reader import SerialPacketReader
from .packet_parser import PacketParser, Packet
from .lsl_streams import LSLStreamer, LSL_AVAILABLE

# matplotlib imports
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# scipy for filtering
try:
    from scipy.signal import butter, sosfilt, sosfilt_zi
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False

# pylsl import
try:
    import pylsl
    LSL_AVAILABLE = True
except ImportError:
    pylsl = None
    LSL_AVAILABLE = False

# UTF-8 encoding
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def adc_to_uv(adc_value: int, adc_bits: int = 14, vref: float = 3300.0) -> float:
    """Convert ADC to microvolts"""
    return ((adc_value / (2 ** adc_bits)) * vref) - (vref / 2.0)

class AcquisitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Acquisition App")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')
        
        # Load configuration
        self.config = self._load_config()
        
        # Paths
        # Resolve project root relative to this file: src/acquisition -> src -> root
        project_root = Path(__file__).resolve().parent.parent.parent
        self.save_path = project_root / "data" / "raw" / "session"
        self.config_path = project_root / "config" / "sensor_config.json"
        
        # Serial reader & parser
        self.serial_reader = None
        self.packet_parser = PacketParser()
        
        # LSL streams
        self.lsl_raw_uV = None
        self.lsl_processed = None
        
        # State
        self.is_connected = False
        self.is_acquiring = False
        self.is_paused = False
        self.is_recording = False
        self.is_recording = False
        self.session_start_time = None
        self.packet_count = 0
        self.retry_counter = 0
        self.last_packet_counter = None

        self.pipeline_process = None # Process handle for filter_router
        
        # Stream Manager Connection
        self.stream_socket = None
        self.stream_connected = False


        # Processed Data Stream State
        self.processed_inlet = None
        self.processed_stream_name = "BioSignals-Processed"
        self.searching_processed = False
        
        # Channel mapping
        channel_map = self.config.get("channel_mapping", {})
        self.ch0_type = channel_map.get("ch0", {}).get("sensor", "EMG")
        self.ch1_type = channel_map.get("ch1", {}).get("sensor", "EOG")

        
        self.ch0_var = tk.StringVar(value=self.ch0_type)
        self.ch1_var = tk.StringVar(value=self.ch1_type)

         # Data buffers for real-time plotting
        self.window_seconds = (
            self.config.get("ui_settings", {}).get("window_seconds", 5.0)
        )
        self.buffer_size = int(
            self.config.get("sampling_rate", 512) * self.window_seconds
        )
        
        # Ring buffers (Raw)
        self.ch0_buffer = np.zeros(self.buffer_size)
        self.ch1_buffer = np.zeros(self.buffer_size)
        
        # Ring buffers (Processed)
        self.ch0_proc_buffer = np.zeros(self.buffer_size)
        self.ch1_proc_buffer = np.zeros(self.buffer_size)
        
        self.buffer_ptr = 0
        self.proc_buffer_ptr = 0  # Separate pointer for processed stream if rates differ slightly
        
        # Time axis
        self.time_axis = np.linspace(0, self.window_seconds, self.buffer_size)
        
        # Session data
        self.session_data = []
        self.latest_packet = {}
        
        # Build UI
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start Sync Thread
        self.start_sync_thread()
        
        # Start Processed Stream Discovery
        self.start_processed_discovery()

        # Start main loop
        self.main_loop()

    def _load_config(self) -> dict:
        """
        Load configuration with proper fallback chain:
        1. Try API endpoint
        2. Fall back to sensor_config.json
        3. Fall back to defaults
        """
        
        # 1. Try API first (optional)
        try:
            import urllib.request
            import urllib.error
            
            url = "http://localhost:5000/api/config"
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    print("[App] ✅ Loaded config from API")
                    return data
        except Exception as e:
            print(f"[App] ⚠️ API load failed ({e}), falling back to files")
        
        # 2. Fall back to file-based config using config_manager
        try:
            sensor_cfg = config_manager.sensor_config.get_all()
            if sensor_cfg:
                print("[App] ✅ Loaded config from sensor_config.json")
                return sensor_cfg
        except Exception as e:
            print(f"[App] ⚠️ File load failed: {e}")
        
        # 3. Fall back to defaults
        print("[App] Using default configuration")
        return self._default_config()

    def _default_config(self) -> dict:
        """Default configuration with proper structure."""
        return {
            "sampling_rate": 512,
            "channel_mapping": {
                "ch0": {
                    "sensor": "EMG",
                    "enabled": True,
                    "label": "EMG Channel 0"
                },
                "ch1": {
                    "sensor": "EOG",
                    "enabled": True,
                    "label": "EOG Channel 1"
                }
            },
            "adc_settings": {
                "bits": 14,
                "vref": 3300.0,
                "sync_byte_1": "0xC7",
                "sync_byte_2": "0x7C",
                "end_byte": "0x01"
            },
            "ui_settings": {
                "window_seconds": 5.0,
                "update_interval_ms": 30,
                "graph_height": 8,
                "y_axis_limits": [-2000, 2000]
            }
        }


    def _save_config(self):
        """
        Save configuration properly using config_manager.
        
        Updates BOTH sensor_config.json and calibration_config.json
        """
        try:
            # 1. Update Sensor Config
            # Fetch current state to avoid overwriting unrelated fields
            sensor_config = config_manager.sensor_config.get_all()
            
            # HARDENING: Ensure 'features' is NOT in sensor_config (it belongs in feature_config)
            if "features" in sensor_config:
                del sensor_config["features"]
            
            # Update specific fields controlled by this UI
            sensor_config["sampling_rate"] = self.config.get("sampling_rate", 512)
            
            # Update Channel Mapping
            channel_mapping = sensor_config.get("channel_mapping", {})
            channel_mapping["ch0"] = {
                "sensor": self.ch0_var.get(),
                "enabled": True,
                "label": f"{self.ch0_var.get()} Channel 0"
            }
            channel_mapping["ch1"] = {
                "sensor": self.ch1_var.get(),
                "enabled": True,
                "label": f"{self.ch1_var.get()} Channel 1"
            }
            sensor_config["channel_mapping"] = channel_mapping
            
            # Update other settings (merge if they exist)
            if "adc_settings" in self.config:
                sensor_config["adc_settings"] = self.config["adc_settings"]
            if "ui_settings" in self.config:
                sensor_config["ui_settings"] = self.config["ui_settings"]
                
             # Save
            if config_manager.save_sensor_config(sensor_config):
                print("[App] ✅ Sensor config saved")
            else:
                 raise Exception("Failed to save sensor config")

            # 2. Update Calibration Config
            calibration_config = config_manager.calib_config.get_all()
            
            # Update entries for ch0 and ch1
            calibration_config["ch0"] = {
                "sensor": self.ch0_var.get(),
                "enabled": True,
                "offset": 0.0,
                "gain": 1.0,
                "calibration_date": datetime.now().strftime("%Y-%m-%d"),
                "calibrated": True
            }
            calibration_config["ch1"] = {
                "sensor": self.ch1_var.get(),
                "enabled": True,
                "offset": 0.0,
                "gain": 1.0,
                "calibration_date": datetime.now().strftime("%Y-%m-%d"),
                "calibrated": True
            }

            # Save
            if config_manager.save_calibration_config(calibration_config):
                print("[App] ✅ Calibration config saved")
            else:
                 print("[App] ⚠️ Warning: Calibration config save failed")

        except Exception as e:
            print(f"[App] ❌ Error saving configs: {e}")
            messagebox.showerror("Error", f"Failed to save config: {e}")
            return
    
        def push_to_api(cfg):
            try:
                import urllib.request
                
                # We need to push the FULL config (Facade) because the API expects it for hot-reload notifications
                # The API will then split it again and save, but since we already saved to disk, 
                # the file watchers on the backend might pick it up before this push arrives.
                # Actually, API save_config does write to disk. This is double writing.
                # However, the API serves as the event bus for the Frontend.
                
                # Let's construct the facade object to push
                facade = config_manager.get_all_configs()
                
                url = "http://localhost:5000/api/config"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(facade).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=1) as response:
                    if response.status == 200:
                        print(f"[App] 📤 Config pushed to API: {response.status}")
            
            except Exception as e:
                print(f"[App] ⚠️ Could not push to API: {e}")
        
        import threading
        threading.Thread(
            target=push_to_api,
            args=(sensor_config,), # Argument not used inside, but kept for signature compatibility if needed
            daemon=True
        ).start()
        
        print("[App] ✅ Configuration saved successfully")
        messagebox.showinfo("Success", "Configuration saved successfully")

    def start_sync_thread(self):
        """Poll API for config changes"""
        def loop():
            import urllib.request
            last_check = 0
            consecutive_errors = 0
            
            while True:
                # Exponential backoff for sleep: 2s normal, up to 30s max on error
                sleep_time = min(30, 2 * (1.5 ** consecutive_errors)) if consecutive_errors > 0 else 2
                time.sleep(sleep_time)
                
                try:
                    # Don't interrupt if we are actively recording/streaming to avoid jitter
                    # (optional trade-off)
                    
                    url = "http://localhost:5000/api/config"
                    # Short timeout to avoid blocking threads for long
                    with urllib.request.urlopen(url, timeout=0.2) as response:
                        if response.status == 200:
                            if consecutive_errors > 0:
                                print(f"[App] ✅ Sync connection restored")
                            consecutive_errors = 0
                            
                            new_cfg = json.loads(response.read().decode())
                            
                            # Simple check if channel mapping changed
                            current_map = self.config.get("channel_mapping", {})
                            new_map = new_cfg.get("channel_mapping", {})
                            
                            if json.dumps(current_map, sort_keys=True) != json.dumps(new_map, sort_keys=True):
                                print(f"[App] 🔄 Remote config change detected!")
                                self.root.after(0, self.update_config_from_remote, new_cfg)
                                
                except Exception as e:
                    consecutive_errors += 1
                    # Only print the error the first time it happens (or if it changes), to avoid spam
                    if consecutive_errors == 1:
                        print(f"[App] Sync loop warning: {e} (Supressing further errors until connection restored)")
        
        threading.Thread(target=loop, daemon=True).start()

    def start_processed_discovery(self):
        """Start a thread to find the processed stream"""
        if not LSL_AVAILABLE:
            return

        def discover():
            self.searching_processed = True
            print("[App] 🔍 Searching for Processed Stream...")
            while self.processed_inlet is None:
                streams = pylsl.resolve_streams(wait_time=1.0)
                for s in streams:
                    if s.name() == self.processed_stream_name:
                        try:
                            self.processed_inlet = pylsl.StreamInlet(s, max_buflen=5)
                            print(f"[App] ✅ Connected to {self.processed_stream_name}")
                            # Only enable toggle if we found the stream
                            self.root.after(0, lambda: self.view_toggle.config(state="normal"))
                            return
                        except Exception as e:
                            print(f"[App] Error connecting to processed stream: {e}")
                time.sleep(2)
            self.searching_processed = False

        threading.Thread(target=discover, daemon=True).start()

    def update_config_from_remote(self, new_config):
        """Update UI and internal state from remote config"""
        self.config = new_config
        
        # Update Channel vars
        mapping = self.config.get("channel_mapping", {})
        
        if "ch0" in mapping:
            self.ch0_var.set(mapping["ch0"].get("sensor", "EMG"))
        if "ch1" in mapping:
            self.ch1_var.set(mapping["ch1"].get("sensor", "EOG"))
            
        print("[App] UI Updated from Remote")

    def _build_ui(self):
        """Build the entire UI"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # LEFT PANEL - Scrollable
        left_container = ttk.Frame(main_frame)
        left_container.pack(side="left", fill="y", expand=False)
        left_panel = self._make_scrollable_panel(left_container, width=350)
        self._build_control_panel(left_panel)
        
        # RIGHT PANEL - Graphs
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=5)
        self._build_graph_panel(right_panel)

    def _make_scrollable_panel(self, parent, width=320):
        """Create a scrollable frame"""
        canvas = tk.Canvas(parent, width=width, highlightthickness=0, bg='white')
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)
        
        canvas.pack(side="left", fill="y", expand=False)
        scrollbar.pack(side="right", fill="y")
        return scrollable_frame

        return scrollable_frame

    def _build_control_panel(self, parent):
        """Build left control panel"""
        # GRAPH CONTROLS
        view_frame = ttk.LabelFrame(parent, text="👁️ View Settings", padding=10)
        view_frame.pack(fill="x", pady=5)
        
        self.view_var = tk.StringVar(value="Raw")
        self.view_toggle = ttk.Checkbutton(
            view_frame, 
            text="Show Processed Data", 
            variable=self.view_var, 
            onvalue="Processed", 
            offvalue="Raw",
            state="disabled", # Disabled until stream found
            command=self.on_view_toggle
        )
        self.view_toggle.pack(anchor="w")
        
        # CONNECTION SECTION
        conn_frame = ttk.LabelFrame(parent, text="🔌 Connection", padding=10)
        conn_frame.pack(fill="x", pady=5)
        
        ttk.Label(conn_frame, text="COM Port:").pack(anchor="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            conn_frame, textvariable=self.port_var, width=30, state="readonly"
        )
        self.port_combo.pack(fill="x", pady=5)
        ttk.Button(conn_frame, text="Refresh Ports", command=self.update_port_list).pack(fill="x", pady=2)
        
        # CHANNEL MAPPING
        map_frame = ttk.LabelFrame(parent, text="📊 Channel Mapping", padding=10)
        map_frame.pack(fill="x", pady=5)
        
        ttk.Label(map_frame, text="Channel 0:").pack(anchor="w")
        self.ch0_var = tk.StringVar(value="EMG")
        ttk.Combobox(
            map_frame, textvariable=self.ch0_var, values=['EMG', 'EOG', 'EEG'], state="readonly"
        ).pack(fill="x", pady=2)
        
        ttk.Label(map_frame, text="Channel 1:").pack(anchor="w")
        self.ch1_var = tk.StringVar(value="EOG")
        ttk.Combobox(
            map_frame, textvariable=self.ch1_var, values=['EMG', 'EOG', 'EEG'], state="readonly"
        ).pack(fill="x", pady=2)
        
        # CONTROL BUTTONS
        btn_frame = ttk.LabelFrame(parent, text="⚙️ Control", padding=10)
        btn_frame.pack(fill="x", pady=5)
        
        self.connect_btn = ttk.Button(
            btn_frame, text="🔌 Connect", command=self.connect_device
        )
        self.connect_btn.pack(fill="x", pady=3)
        
        self.disconnect_btn = ttk.Button(
            btn_frame, text="❌ Disconnect", command=self.disconnect_device, state="disabled"
        )
        self.disconnect_btn.pack(fill="x", pady=3)
        
        self.start_btn = ttk.Button(
            btn_frame, text="▶️ Start Acquisition", command=self.start_acquisition, state="disabled"
        )
        self.start_btn.pack(fill="x", pady=3)
        
        self.stop_btn = ttk.Button(
            btn_frame, text="⏹️ Stop Acquisition", command=self.stop_acquisition, state="disabled"
        )
        self.stop_btn.pack(fill="x", pady=3)
        
        self.pause_btn = ttk.Button(
            btn_frame, text="⏸️ Pause", command=self.toggle_pause, state="disabled"
        )
        self.pause_btn.pack(fill="x", pady=3)
        
        # RECORDING
        rec_frame = ttk.LabelFrame(parent, text="🔴 Recording", padding=10)
        rec_frame.pack(fill="x", pady=5)
        
        self.rec_btn = ttk.Button(
            rec_frame, text="⚫ Start Recording", command=self.toggle_recording, state="disabled"
        )
        self.rec_btn.pack(fill="x", pady=3)
        
        # SAVE
        save_frame = ttk.LabelFrame(parent, text="💾 Save", padding=10)
        save_frame.pack(fill="x", pady=5)
        
        ttk.Button(save_frame, text="Choose Path", command=self.choose_save_path).pack(fill="x", pady=2)
        self.path_label = ttk.Label(save_frame, text=str(self.save_path), wraplength=250)
        self.path_label.pack(fill="x", pady=2)
        
        self.save_btn = ttk.Button(
            save_frame, text="💾 Save Session", command=self.save_session, state="disabled"
        )
        self.save_btn.pack(fill="x", pady=3)
        
        ttk.Button(save_frame, text="⚙️ Map Sensors", command=self._save_config).pack(fill="x", pady=2)
        
        # STATUS
        status_frame = ttk.LabelFrame(parent, text="📈 Status", padding=10)
        status_frame.pack(fill="x", pady=5)
        
        ttk.Label(status_frame, text="Connection:").pack(anchor="w")
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red")
        self.status_label.pack(anchor="w", pady=2)
        
        ttk.Label(status_frame, text="Packets:").pack(anchor="w")
        self.packet_label = ttk.Label(status_frame, text="0")
        self.packet_label.pack(anchor="w", pady=2)
        
        ttk.Label(status_frame, text="Recording:").pack(anchor="w")
        self.recording_label = ttk.Label(status_frame, text="❌ No", foreground="red")
        self.recording_label.pack(anchor="w")

    def on_view_toggle(self):
        """Handle view toggle change"""
        mode = self.view_var.get()
        print(f"[App] View switched to: {mode}")
        if mode == "Processed" and self.processed_inlet is None:
            messagebox.showwarning("Stream Not Found", "Processed stream not connected yet.")
            self.view_var.set("Raw")

    def _build_graph_panel(self, parent):
        """Build right graph panel - FIXED: No overlapping labels"""
        fig = Figure(figsize=(12, 8), dpi=100)
        fig.subplots_adjust(left=0.06, right=0.98, top=0.96, bottom=0.08, hspace=0.35)
        
        # Subplot 1: Channel 0
        self.ax0 = fig.add_subplot(211)
        # Use position to move title up and away from bottom subplot
        self.ax0.set_title("📍 Channel 0 (EMG)", fontsize=12, fontweight='bold', pad=10)
        self.ax0.set_xlabel("Time (seconds)")
        self.ax0.set_ylabel("Amplitude (µV)")
        self.ax0.grid(True, alpha=0.3)
        y_limits = self.config.get("ui_settings", {}).get("y_axis_limits", [-2000, 2000])
        self.ax0.set_ylim(y_limits[0], y_limits[1])
        self.ax0.set_xlim(0, self.window_seconds)  # Set X-axis to start at 0
        self.line0, = self.ax0.plot(self.time_axis, self.ch0_buffer,
                                    color='red', linewidth=1.5, label='CH0')
        self.ax0.legend(loc='upper right', fontsize=9)
        
        # Subplot 2: Channel 1
        self.ax1 = fig.add_subplot(212)
        # Use position to move title down and away from top subplot
        self.ax1.set_title("📍 Channel 1 (EOG)", fontsize=12, fontweight='bold', pad=10)
        self.ax1.set_xlabel("Time (seconds)")
        self.ax1.set_ylabel("Amplitude (µV)")
        self.ax1.grid(True, alpha=0.3)
        self.ax1.set_ylim(y_limits[0], y_limits[1])
        self.ax1.set_xlim(0, self.window_seconds)  # Set X-axis to start at 0
        self.line1, = self.ax1.plot(self.time_axis, self.ch1_buffer,
                                    color='blue', linewidth=1.5, label='CH1')
        self.ax1.legend(loc='upper right', fontsize=9)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.fig = fig

    def update_port_list(self):
        """Update available COM ports"""
        try:
            import serial.tools.list_ports
            ports = []
            for p, desc, hwid in serial.tools.list_ports.comports():
                ports.append(f"{p} - {desc}")
            self.port_combo['values'] = ports if ports else ["No ports found"]
            if ports:
                self.port_combo.current(0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan ports: {e}")

    def connect_device(self):
        """Connect to Arduino"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        
        port = self.port_var.get().split(" ")[0]
        
        # Create serial reader
        self.serial_reader = SerialPacketReader(port=port)
        if not self.serial_reader.connect():
            messagebox.showerror("Error", f"Failed to connect to {port}")
            return
        
        self.serial_reader.start()
        
        # Send Handshake to trigger "Connected" state (Yellow LED)
        time.sleep(0.1) # Brief pause to ensure thread is ready
        self.serial_reader.send_command("WHORU")
        
        self.is_connected = True
        
        # Update UI
        self.status_label.config(text="✅ Connected", foreground="green")
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="normal")
        self.start_btn.config(state="normal")
        
        # Store channel types
        self.ch0_type = self.ch0_var.get()
        self.ch1_type = self.ch1_var.get()
        
        # Create LSL outlets if available
        
        # Connect to Stream Manager
        self._connect_to_stream_manager()
        
    def _connect_to_stream_manager(self):
        """Connect to local Stream Manager for raw data streaming"""
        try:
            import socket
            self.stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Port 6000 is for RAW data as defined in stream_manager.py
            self.stream_socket.connect(('localhost', 6000))
            self.stream_connected = True
            print("[App] ✅ Connected to Stream Manager (Raw)")
        except Exception as e:
            print(f"[App] ⚠️ Could not connect to Stream Manager: {e}")
            self.stream_connected = False
            self.stream_socket = None

        
    def disconnect_device(self):
        """Disconnect from Arduino"""
        if self.is_acquiring:
            self.stop_acquisition()
        
        self.is_connected = False
        if self.serial_reader:
            self.serial_reader.disconnect()
            
        if self.stream_socket:
            try:
                self.stream_socket.close()
            except:
                pass
            self.stream_socket = None
            self.stream_connected = False
            print("[App] Disconnected from Stream Manager")

        
        self.status_label.config(text="❌ Disconnected", foreground="red")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")

    def start_acquisition(self):
        """Start acquiring data"""
        if not (self.serial_reader and self.is_connected):
            messagebox.showerror("Error", "Device not connected")
            return
        
        self.serial_reader.send_command("START")
        self.is_acquiring = True
        self.is_recording = True
        self.session_start_time = datetime.now()
        self.packet_count = 0
        self.session_data = []
        self.last_packet_counter = None
        
        # Clear buffers
        self.ch0_buffer.fill(0)
        self.ch1_buffer.fill(0)
        self.ch0_proc_buffer.fill(0)
        self.ch1_proc_buffer.fill(0)
        self.buffer_ptr = 0
        self.proc_buffer_ptr = 0
        
        # Update UI
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.pause_btn.config(state="normal")
        self.rec_btn.config(state="normal")
        self.save_btn.config(state="normal")
        self.recording_label.config(text="✅ Yes", foreground="green")

    def stop_acquisition(self):
        """Stop acquiring data"""
        try:
            if self.serial_reader:
                self.serial_reader.send_command("STOP")
        except:
            pass
        
        self.is_acquiring = False
        self.is_paused = False
        self.is_recording = False
        
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.pause_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")
        self.recording_label.config(text="❌ No", foreground="red")

    def toggle_recording(self):
        """Toggle recording"""
        if not self.is_acquiring:
            messagebox.showerror("Error", "Start acquisition first")
            return
        
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.rec_btn.config(text="⚫ Stop Recording")
            self.recording_label.config(text="✅ Yes", foreground="green")
        else:
            self.rec_btn.config(text="⚫ Start Recording")
            self.recording_label.config(text="⏸️ Paused", foreground="orange")

    def toggle_pause(self):
        """Toggle pause/resume"""
        if not self.is_acquiring:
            return
        
        self.is_paused = not self.is_paused
        if self.is_paused:
            if self.serial_reader:
                self.serial_reader.send_command("PAUSE")
            self.pause_btn.config(text="▶️ Resume")
            self.status_label.config(text="⏸️ Paused", foreground="orange")
        else:
            if self.serial_reader:
                self.serial_reader.send_command("RESUME")
            self.pause_btn.config(text="⏸️ Pause")
            self.status_label.config(text="✅ Connected", foreground="green")

    def choose_save_path(self):
        """Choose save directory"""
        path = filedialog.askdirectory(
            title="Select save directory",
            initialdir=str(self.save_path)
        )
        if path:
            self.save_path = Path(path)
            self.path_label.config(text=str(self.save_path))

    def save_session(self):
        """Save session data"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        
        timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
        self.save_path.mkdir(parents=True, exist_ok=True)
        filepath = self.save_path / f"session_{timestamp}.json"
        
        metadata = {
            "session_info": {
                "timestamp": self.session_start_time.isoformat(),
                "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
                "total_packets": self.packet_count,
                "sampling_rate_hz": self.config.get("sampling_rate", 512),
                "channel_0_type": self.ch0_type,
                "channel_1_type": self.ch1_type
            },
            "sensor_config": self.config.get("sensor_mapping", {}),
            "filters": self.config.get("filters", {}),
            "data": self.session_data
        }
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        messagebox.showinfo("Saved", f"Saved {len(self.session_data)} packets to {filepath}")


    def main_loop(self):
        """Main acquisition and update loop (Optimized)"""
        try:
            # --- 0. CHECK ARDUINO MESSAGES (Switches) ---
            if self.serial_reader:
                while True:
                    msg = self.serial_reader.get_message()
                    if not msg:
                        break
                    
                    # DEBUG: Print everything we get
                    print(f"[App] DEBUG: Processing message '{msg}'")

                    if "SWITCH_2_PRESSED" in msg:
                        # SW2: Start Acquisition & Pipeline
                        print("[App] 🎮 Switch 2 Pressed -> Starting...")
                        if not self.is_acquiring:
                            self.start_acquisition()
                        
                        # Start Pipeline if not running
                        if self.pipeline_process is None:
                            try:
                                print("[App] 🚀 Launching Full Pipeline (pipeline.py)...")
                                # Launch independent python process
                                cmd = [sys.executable, "pipeline.py"]
                                self.pipeline_process = subprocess.Popen(
                                    cmd, 
                                    cwd=str(self.save_path.parent.parent.parent), # Project root
                                    creationflags=subprocess.CREATE_NEW_CONSOLE # Windows specific: Open new terminal
                                )
                            except Exception as e:
                                print(f"[App] ❌ Failed to launch pipeline: {e}")

                    elif "SWITCH_1_PRESSED" in msg:
                        # SW1: Stop Acquisition & Pipeline
                        print("[App] 🛑 Switch 1 Pressed -> Stopping...")
                        if self.is_acquiring:
                            self.stop_acquisition()
                        
                        # Kill Pipeline
                        if self.pipeline_process:
                            print("[App] 💀 Killing Filter Pipeline...")
                            self.pipeline_process.terminate()
                            self.pipeline_process = None

            if self.is_acquiring and not self.is_paused:
                # --- RAW DATA Handling ---
                if self.serial_reader:
                    # 1. Collect all packets currently in queue
                    batch_raw = []
                    while True:
                        pkt_bytes = self.serial_reader.get_packet(timeout=0)
                        if pkt_bytes is None:
                            break
                        batch_raw.append(pkt_bytes)
                    
                    if batch_raw:
                        # 2. Batch parse
                        ctrs, r0, r1 = self.packet_parser.parse_batch(batch_raw)
                        
                        # 3. Convert to uV
                        u0 = adc_to_uv(r0)
                        u1 = adc_to_uv(r1)
                        
                        # 4. Push to Stream Manager (Chunks)
                        if self.stream_connected and self.stream_socket:
                            try:
                                # Pack all samples efficiently
                                # u0 and u1 are numpy arrays
                                byte_data = bytearray()
                                for v0, v1 in zip(u0, u1):
                                    byte_data.extend(struct.pack('<ff', float(v0), float(v1)))
                                self.stream_socket.sendall(byte_data)
                            except Exception as e:
                                print(f"[App] Stream send error: {e}")
                                self.stream_connected = False

                        
                        # 5. Update buffers efficiently
                        n = len(u0)
                        for i in range(n):
                            # Simple duplicate check (last counter)
                            if self.last_packet_counter == ctrs[i]:
                                continue
                            self.last_packet_counter = ctrs[i]
                            
                            self.ch0_buffer[self.buffer_ptr] = u0[i]
                            self.ch1_buffer[self.buffer_ptr] = u1[i]
                            self.buffer_ptr = (self.buffer_ptr + 1) % self.buffer_size
                            
                            if self.is_recording:
                                # Still using dict for now, but batching parser already saved time
                                self.session_data.append({
                                    "packet_seq": int(ctrs[i]),
                                    "ch0_raw_adc": int(r0[i]),
                                    "ch1_raw_adc": int(r1[i]),
                                    "ch0_uv": float(u0[i]),
                                    "ch1_uv": float(u1[i])
                                })
                            
                            self.packet_count += 1

            # --- PROCESSED DATA Handling ---
            if self.processed_inlet:
                try:
                    # Pull all available processed samples
                    chunk, timestamps = self.processed_inlet.pull_chunk(timeout=0.0)
                    if chunk:
                        n_proc = len(chunk)
                        chunk = np.array(chunk) # Shape (n_samples, n_channels)
                        
                        # Assuming CH0 is index 0, CH1 is index 1
                        p0 = chunk[:, 0]
                        p1 = chunk[:, 1]
                        
                        # Update Processed Buffers
                        for i in range(n_proc):
                            self.ch0_proc_buffer[self.proc_buffer_ptr] = p0[i]
                            self.ch1_proc_buffer[self.proc_buffer_ptr] = p1[i]
                            self.proc_buffer_ptr = (self.proc_buffer_ptr + 1) % self.buffer_size
                            
                except Exception as e:
                    print(f"[App] Processed stream error: {e}")

            # Update UI labels
            self.packet_label.config(text=str(self.packet_count))
            
            # Update plots (every 30ms call, but update_plots itself is faster now)
            self.update_plots()
        
        except Exception as e:
            print(f"Main loop error: {e}")
        
        # Schedule next update
        if self.root.winfo_exists():
            self.root.after(30, self.main_loop)
            
        # Retry connection if needed (approx every 2 seconds)
        self.retry_counter = (self.retry_counter + 1) % 60
        if self.retry_counter == 0 and not self.stream_connected:
             self._connect_to_stream_manager()


    def update_plots(self):
        """Update the plot lines (Optimized)"""
        try:
            if not self.is_acquiring or self.is_paused:
                return

            # Rotate buffers so latest data is on the right
            if self.view_var.get() == "Processed" and self.processed_inlet:
                # Use Processed Buffers
                ch0_rotated = np.roll(self.ch0_proc_buffer, -self.proc_buffer_ptr)
                ch1_rotated = np.roll(self.ch1_proc_buffer, -self.proc_buffer_ptr)
                color0, color1 = 'darkred', 'darkblue' # Darker colors for processed
                title_suffix = " (Processed)"
            else:
                # Use Raw Buffers
                ch0_rotated = np.roll(self.ch0_buffer, -self.buffer_ptr)
                ch1_rotated = np.roll(self.ch1_buffer, -self.buffer_ptr)
                color0, color1 = 'red', 'blue'
                title_suffix = " (Raw)"
            
            # Update line data
            self.line0.set_ydata(ch0_rotated)
            self.line0.set_color(color0)
            self.ax0.set_title(f"📍 Channel 0 (EMG){title_suffix}")
            
            self.line1.set_ydata(ch1_rotated)
            self.line1.set_color(color1)
            self.ax1.set_title(f"📍 Channel 1 (EOG){title_suffix}")
            
            # Redraw only when needed
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Plot update error: {e}")

    def on_closing(self):
        """Handle window closing"""
        try:
            if self.is_acquiring:
                self.stop_acquisition()
            if self.serial_reader:
                self.serial_reader.disconnect()
        finally:
            self.root.destroy()

def main():
    root = tk.Tk()
    app = AcquisitionApp(root)
    app.update_port_list()
    root.mainloop()

if __name__ == "__main__":
    main()

