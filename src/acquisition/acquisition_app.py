# import tkinter as tk
# from tkinter import ttk, messagebox, filedialog
# import json
# import time
# import threading
# from pathlib import Path
# from datetime import datetime
# import numpy as np
# import sys
# import os
# import queue

# # Ensure we can import sibling packages
# current_dir = os.path.dirname(os.path.abspath(__file__))
# src_dir = os.path.abspath(os.path.join(current_dir, '..'))
# if src_dir not in sys.path:
#     sys.path.insert(0, src_dir)

# # Local imports
# from .serial_reader import SerialPacketReader
# from .packet_parser import PacketParser, Packet
# from .lsl_streams import LSLStreamer, LSL_AVAILABLE

# # matplotlib imports
# import matplotlib
# matplotlib.use('TkAgg')
# from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
# from matplotlib.figure import Figure

# # scipy for filtering
# try:
#     from scipy.signal import butter, sosfilt, sosfilt_zi
#     SCIPY_AVAILABLE = True
# except Exception:
#     SCIPY_AVAILABLE = False

# # UTF-8 encoding
# try:
#     sys.stdout.reconfigure(encoding='utf-8')
# except Exception:
#     pass

# def adc_to_uv(adc_value: int, adc_bits: int = 14, vref: float = 3300.0) -> float:
#     """Convert ADC to microvolts"""
#     return ((adc_value / (2 ** adc_bits)) * vref) - (vref / 2.0)

# class AcquisitionApp:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("Acquisition App")
#         self.root.geometry("1600x950")
#         self.root.configure(bg='#f0f0f0')
        
#         # Load configuration
#         self.config = self._load_config()
        
#         # Paths
#         # Resolve project root relative to this file: src/acquisition -> src -> root
#         project_root = Path(__file__).resolve().parent.parent.parent
#         self.save_path = project_root / "data" / "raw" / "session"
#         self.config_path = project_root / "config" / "sensor_config.json"
        
#         # Serial reader & parser
#         self.serial_reader = None
#         self.packet_parser = PacketParser()
        
#         # LSL streams
#         self.lsl_raw_uV = None
#         self.lsl_processed = None
        
#         # State
#         self.is_connected = False
#         self.is_acquiring = False
#         self.is_paused = False
#         self.is_recording = False
#         self.session_start_time = None
#         self.packet_count = 0
#         self.last_packet_counter = None
        
#         # Channel mapping
#         self.ch0_type = "EMG"
#         self.ch1_type = "EOG"
        
#         # Data buffers for real-time plotting
#         self.window_seconds = self.config.get("ui_settings", {}).get("window_seconds", 5.0)
#         self.buffer_size = int(self.config.get("sampling_rate", 512) * self.window_seconds)
        
#         # Ring buffers
#         self.ch0_buffer = np.zeros(self.buffer_size)
#         self.ch1_buffer = np.zeros(self.buffer_size)
#         self.buffer_ptr = 0
        
#         # Time axis
#         self.time_axis = np.linspace(0, self.window_seconds, self.buffer_size)
        
#         # Session data
#         self.session_data = []
#         self.latest_packet = {}
        
#         # Build UI
#         self._build_ui()
#         self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
#         # Start Sync Thread
#         self.start_sync_thread()

#         # Start main loop
#         self.main_loop()

#     def _load_config(self) -> dict:
#         """Load configuration from API or JSON file"""
#         # Try API first
#         try:
#             import urllib.request
#             import urllib.error
#             url = "http://localhost:5000/api/config"
#             with urllib.request.urlopen(url, timeout=0.5) as response:
#                 if response.status == 200:
#                     data = json.loads(response.read().decode())
#                     print("[App] ✅ Loaded config from API")
#                     return data
#         except Exception as e:
#             print(f"[App] ⚠️ API load failed ({e}), falling back to file")

#         # Fallback to local file
#         project_root = Path(__file__).resolve().parent.parent.parent
#         config_path = project_root / "config" / "sensor_config.json"
#         if config_path.exists():
#             try:
#                 with open(config_path, 'r') as f:
#                     return json.load(f)
#             except Exception as e:
#                 print(f"[App] Error loading config: {e}")
#                 return self._default_config()
#         return self._default_config()

#     def _default_config(self) -> dict:
#         """Default configuration"""
#         return {
#             "sampling_rate": 512,
#             "channel_mapping": {
#                 "ch0": {"sensor": "EMG", "enabled": True, "label": "EMG Channel 0"},
#                 "ch1": {"sensor": "EOG", "enabled": True, "label": "EOG Channel 1"}
#             },
#             "filters": {
#                 "EMG": {"type": "high_pass", "cutoff": 70.0, "order": 4, "enabled": True},
#                 "EOG": {"type": "low_pass", "cutoff": 10.0, "order": 4, "enabled": True}
#             },
#             "adc_settings": {
#                 "bits": 14,
#                 "vref": 3300.0,
#                 "sync_byte_1": "0xC7",
#                 "sync_byte_2": "0x7C",
#                 "end_byte": "0x01"
#             },
#             "ui_settings": {
#                 "window_seconds": 5.0,
#                 "update_interval_ms": 30,
#                 "graph_height": 8,
#                 "y_axis_limits": [-2000, 2000]
#             }
#         }

#     def _save_config(self):
#         """Save configuration to JSON file and API"""
        
#         # UPDATE channel mapping from UI BEFORE saving
#         self.config["channel_mapping"] = {
#             "ch0": {"sensor": self.ch0_var.get(), "enabled": True},
#             "ch1": {"sensor": self.ch1_var.get(), "enabled": True}
#         }
        
#         # 1. Save to Local File (Backup)
#         self.config_path.parent.mkdir(parents=True, exist_ok=True)
#         try:
#             with open(self.config_path, 'w') as f:
#                 json.dump(self.config, f, indent=2)
#             print(f"[App] Config saved to {self.config_path}")
#         except Exception as e:
#             print(f"[App] Error saving config locally: {e}")
#             messagebox.showerror("Error", f"Failed to save config: {e}")

#         # 2. Push to API (Primary)
#         def push_to_api(cfg):
#             try:
#                 import urllib.request
#                 url = "http://localhost:5000/api/config"
#                 req = urllib.request.Request(
#                     url,
#                     data=json.dumps(cfg).encode('utf-8'),
#                     headers={'Content-Type': 'application/json'},
#                     method='POST'
#                 )
#                 with urllib.request.urlopen(req, timeout=1) as response:
#                     print(f"[App] 📤 Config pushed to API: {response.status}")
#             except Exception as e:
#                 print(f"[App] ❌ Failed to push to API: {e}")
        
#         threading.Thread(target=push_to_api, args=(self.config,), daemon=True).start()

#     def start_sync_thread(self):
#         """Poll API for config changes"""
#         def loop():
#             import urllib.request
#             last_check = 0
#             while True:
#                 time.sleep(2)
#                 try:
#                     # Don't interrupt if we are actively recording/streaming to avoid jitter
#                     # (optional trade-off)
                    
#                     url = "http://localhost:5000/api/config"
#                     with urllib.request.urlopen(url, timeout=1) as response:
#                         if response.status == 200:
#                             new_cfg = json.loads(response.read().decode())
                            
#                             # Simple check if channel mapping changed
#                             current_map = self.config.get("channel_mapping", {})
#                             new_map = new_cfg.get("channel_mapping", {})
                            
#                             if json.dumps(current_map, sort_keys=True) != json.dumps(new_map, sort_keys=True):
#                                 print(f"[App] 🔄 Remote config change detected!")
#                                 print(f"[App] Local: {current_map}")
#                                 print(f"[App] Remote: {new_map}")
#                                 self.root.after(0, self.update_config_from_remote, new_cfg)
#                 except Exception as e:
#                     print(f"[App] Sync loop error: {e}")
        
#         threading.Thread(target=loop, daemon=True).start()

#     def update_config_from_remote(self, new_config):
#         """Update UI and internal state from remote config"""
#         self.config = new_config
        
#         # Update Channel vars
#         mapping = self.config.get("channel_mapping", {})
        
#         if "ch0" in mapping:
#             self.ch0_var.set(mapping["ch0"].get("sensor", "EMG"))
#         if "ch1" in mapping:
#             self.ch1_var.set(mapping["ch1"].get("sensor", "EOG"))
            
#         print("[App] UI Updated from Remote")

#     def _build_ui(self):
#         """Build the entire UI"""
#         main_frame = ttk.Frame(self.root)
#         main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
#         # LEFT PANEL - Scrollable
#         left_container = ttk.Frame(main_frame)
#         left_container.pack(side="left", fill="y", expand=False)
#         left_panel = self._make_scrollable_panel(left_container, width=350)
#         self._build_control_panel(left_panel)
        
#         # RIGHT PANEL - Graphs
#         right_panel = ttk.Frame(main_frame)
#         right_panel.pack(side="right", fill="both", expand=True, padx=5)
#         self._build_graph_panel(right_panel)

#     def _make_scrollable_panel(self, parent, width=320):
#         """Create a scrollable frame"""
#         canvas = tk.Canvas(parent, width=width, highlightthickness=0, bg='white')
#         scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
#         scrollable_frame = ttk.Frame(canvas)
        
#         scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
#         canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
#         canvas.configure(yscrollcommand=scrollbar.set)
        
#         def _on_mousewheel(event):
#             if event.num == 5 or event.delta < 0:
#                 canvas.yview_scroll(1, "units")
#             elif event.num == 4 or event.delta > 0:
#                 canvas.yview_scroll(-1, "units")
        
#         canvas.bind_all("<MouseWheel>", _on_mousewheel)
#         canvas.bind_all("<Button-4>", _on_mousewheel)
#         canvas.bind_all("<Button-5>", _on_mousewheel)
        
#         canvas.pack(side="left", fill="y", expand=False)
#         scrollbar.pack(side="right", fill="y")
#         return scrollable_frame

#     def _build_control_panel(self, parent):
#         """Build left control panel"""
#         # CONNECTION SECTION
#         conn_frame = ttk.LabelFrame(parent, text="🔌 Connection", padding=10)
#         conn_frame.pack(fill="x", pady=5)
        
#         ttk.Label(conn_frame, text="COM Port:").pack(anchor="w")
#         self.port_var = tk.StringVar()
#         self.port_combo = ttk.Combobox(
#             conn_frame, textvariable=self.port_var, width=30, state="readonly"
#         )
#         self.port_combo.pack(fill="x", pady=5)
#         ttk.Button(conn_frame, text="Refresh Ports", command=self.update_port_list).pack(fill="x", pady=2)
        
#         # CHANNEL MAPPING
#         map_frame = ttk.LabelFrame(parent, text="📊 Channel Mapping", padding=10)
#         map_frame.pack(fill="x", pady=5)
        
#         ttk.Label(map_frame, text="Channel 0:").pack(anchor="w")
#         self.ch0_var = tk.StringVar(value="EMG")
#         ttk.Combobox(
#             map_frame, textvariable=self.ch0_var, values=['EMG', 'EOG', 'EEG'], state="readonly"
#         ).pack(fill="x", pady=2)
        
#         ttk.Label(map_frame, text="Channel 1:").pack(anchor="w")
#         self.ch1_var = tk.StringVar(value="EOG")
#         ttk.Combobox(
#             map_frame, textvariable=self.ch1_var, values=['EMG', 'EOG', 'EEG'], state="readonly"
#         ).pack(fill="x", pady=2)
        
#         # CONTROL BUTTONS
#         btn_frame = ttk.LabelFrame(parent, text="⚙️ Control", padding=10)
#         btn_frame.pack(fill="x", pady=5)
        
#         self.connect_btn = ttk.Button(
#             btn_frame, text="🔌 Connect", command=self.connect_device
#         )
#         self.connect_btn.pack(fill="x", pady=3)
        
#         self.disconnect_btn = ttk.Button(
#             btn_frame, text="❌ Disconnect", command=self.disconnect_device, state="disabled"
#         )
#         self.disconnect_btn.pack(fill="x", pady=3)
        
#         self.start_btn = ttk.Button(
#             btn_frame, text="▶️ Start Acquisition", command=self.start_acquisition, state="disabled"
#         )
#         self.start_btn.pack(fill="x", pady=3)
        
#         self.stop_btn = ttk.Button(
#             btn_frame, text="⏹️ Stop Acquisition", command=self.stop_acquisition, state="disabled"
#         )
#         self.stop_btn.pack(fill="x", pady=3)
        
#         self.pause_btn = ttk.Button(
#             btn_frame, text="⏸️ Pause", command=self.toggle_pause, state="disabled"
#         )
#         self.pause_btn.pack(fill="x", pady=3)
        
#         # RECORDING
#         rec_frame = ttk.LabelFrame(parent, text="🔴 Recording", padding=10)
#         rec_frame.pack(fill="x", pady=5)
        
#         self.rec_btn = ttk.Button(
#             rec_frame, text="⚫ Start Recording", command=self.toggle_recording, state="disabled"
#         )
#         self.rec_btn.pack(fill="x", pady=3)
        
#         # SAVE
#         save_frame = ttk.LabelFrame(parent, text="💾 Save", padding=10)
#         save_frame.pack(fill="x", pady=5)
        
#         ttk.Button(save_frame, text="Choose Path", command=self.choose_save_path).pack(fill="x", pady=2)
#         self.path_label = ttk.Label(save_frame, text=str(self.save_path), wraplength=250)
#         self.path_label.pack(fill="x", pady=2)
        
#         self.save_btn = ttk.Button(
#             save_frame, text="💾 Save Session", command=self.save_session, state="disabled"
#         )
#         self.save_btn.pack(fill="x", pady=3)
        
#         ttk.Button(save_frame, text="⚙️ Map Sensors", command=self._save_config).pack(fill="x", pady=2)
        
#         # STATUS
#         status_frame = ttk.LabelFrame(parent, text="📈 Status", padding=10)
#         status_frame.pack(fill="x", pady=5)
        
#         ttk.Label(status_frame, text="Connection:").pack(anchor="w")
#         self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red")
#         self.status_label.pack(anchor="w", pady=2)
        
#         ttk.Label(status_frame, text="Packets:").pack(anchor="w")
#         self.packet_label = ttk.Label(status_frame, text="0")
#         self.packet_label.pack(anchor="w", pady=2)
        
#         ttk.Label(status_frame, text="Recording:").pack(anchor="w")
#         self.recording_label = ttk.Label(status_frame, text="❌ No", foreground="red")
#         self.recording_label.pack(anchor="w")

#     def _build_graph_panel(self, parent):
#         """Build right graph panel - FIXED: No overlapping labels"""
#         fig = Figure(figsize=(12, 8), dpi=100)
#         fig.subplots_adjust(left=0.06, right=0.98, top=0.96, bottom=0.08, hspace=0.35)
        
#         # Subplot 1: Channel 0
#         self.ax0 = fig.add_subplot(211)
#         # Use position to move title up and away from bottom subplot
#         self.ax0.set_title("📍 Channel 0 (EMG)", fontsize=12, fontweight='bold', pad=10)
#         self.ax0.set_xlabel("Time (seconds)")
#         self.ax0.set_ylabel("Amplitude (µV)")
#         self.ax0.grid(True, alpha=0.3)
#         y_limits = self.config.get("ui_settings", {}).get("y_axis_limits", [-2000, 2000])
#         self.ax0.set_ylim(y_limits[0], y_limits[1])
#         self.ax0.set_xlim(0, self.window_seconds)  # Set X-axis to start at 0
#         self.line0, = self.ax0.plot(self.time_axis, self.ch0_buffer,
#                                     color='red', linewidth=1.5, label='CH0')
#         self.ax0.legend(loc='upper right', fontsize=9)
        
#         # Subplot 2: Channel 1
#         self.ax1 = fig.add_subplot(212)
#         # Use position to move title down and away from top subplot
#         self.ax1.set_title("📍 Channel 1 (EOG)", fontsize=12, fontweight='bold', pad=10)
#         self.ax1.set_xlabel("Time (seconds)")
#         self.ax1.set_ylabel("Amplitude (µV)")
#         self.ax1.grid(True, alpha=0.3)
#         self.ax1.set_ylim(y_limits[0], y_limits[1])
#         self.ax1.set_xlim(0, self.window_seconds)  # Set X-axis to start at 0
#         self.line1, = self.ax1.plot(self.time_axis, self.ch1_buffer,
#                                     color='blue', linewidth=1.5, label='CH1')
#         self.ax1.legend(loc='upper right', fontsize=9)
        
#         # Create canvas
#         self.canvas = FigureCanvasTkAgg(fig, master=parent)
#         self.canvas.get_tk_widget().pack(fill="both", expand=True)
#         self.fig = fig

#     def update_port_list(self):
#         """Update available COM ports"""
#         try:
#             import serial.tools.list_ports
#             ports = []
#             for p, desc, hwid in serial.tools.list_ports.comports():
#                 ports.append(f"{p} - {desc}")
#             self.port_combo['values'] = ports if ports else ["No ports found"]
#             if ports:
#                 self.port_combo.current(0)
#         except Exception as e:
#             messagebox.showerror("Error", f"Failed to scan ports: {e}")

#     def connect_device(self):
#         """Connect to Arduino"""
#         if not self.port_var.get():
#             messagebox.showerror("Error", "Select a COM port")
#             return
        
#         port = self.port_var.get().split(" ")[0]
        
#         # Create serial reader
#         self.serial_reader = SerialPacketReader(port=port)
#         if not self.serial_reader.connect():
#             messagebox.showerror("Error", f"Failed to connect to {port}")
#             return
        
#         self.serial_reader.start()
#         self.is_connected = True
        
#         # Update UI
#         self.status_label.config(text="✅ Connected", foreground="green")
#         self.connect_btn.config(state="disabled")
#         self.disconnect_btn.config(state="normal")
#         self.start_btn.config(state="normal")
        
#         # Store channel types
#         self.ch0_type = self.ch0_var.get()
#         self.ch1_type = self.ch1_var.get()
        
#         # Create LSL outlets if available
#         if LSL_AVAILABLE:
#             ch_types = [self.ch0_type, self.ch1_type]
#             ch_labels = [f"{self.ch0_type}_0", f"{self.ch1_type}_1"]
#             self.lsl_raw_uV = LSLStreamer(
#                 "BioSignals-Raw-uV",
#                 channel_types=ch_types,
#                 channel_labels=ch_labels,
#                 channel_count=2,
#                 nominal_srate=float(self.config.get("sampling_rate", 512))
#             )
        
#     def disconnect_device(self):
#         """Disconnect from Arduino"""
#         if self.is_acquiring:
#             self.stop_acquisition()
        
#         self.is_connected = False
#         if self.serial_reader:
#             self.serial_reader.disconnect()
        
#         self.status_label.config(text="❌ Disconnected", foreground="red")
#         self.connect_btn.config(state="normal")
#         self.disconnect_btn.config(state="disabled")
#         self.start_btn.config(state="disabled")
#         self.stop_btn.config(state="disabled")

#     def start_acquisition(self):
#         """Start acquiring data"""
#         if not (self.serial_reader and self.is_connected):
#             messagebox.showerror("Error", "Device not connected")
#             return
        
#         self.serial_reader.send_command("START")
#         self.is_acquiring = True
#         self.is_recording = True
#         self.session_start_time = datetime.now()
#         self.packet_count = 0
#         self.session_data = []
#         self.last_packet_counter = None
        
#         # Clear buffers
#         self.ch0_buffer.fill(0)
#         self.ch1_buffer.fill(0)
#         self.buffer_ptr = 0
        
#         # Update UI
#         self.start_btn.config(state="disabled")
#         self.stop_btn.config(state="normal")
#         self.pause_btn.config(state="normal")
#         self.rec_btn.config(state="normal")
#         self.save_btn.config(state="normal")
#         self.recording_label.config(text="✅ Yes", foreground="green")

#     def stop_acquisition(self):
#         """Stop acquiring data"""
#         try:
#             if self.serial_reader:
#                 self.serial_reader.send_command("STOP")
#         except:
#             pass
        
#         self.is_acquiring = False
#         self.is_paused = False
#         self.is_recording = False
        
#         self.start_btn.config(state="normal")
#         self.stop_btn.config(state="disabled")
#         self.pause_btn.config(state="disabled")
#         self.rec_btn.config(state="disabled")
#         self.recording_label.config(text="❌ No", foreground="red")

#     def toggle_recording(self):
#         """Toggle recording"""
#         if not self.is_acquiring:
#             messagebox.showerror("Error", "Start acquisition first")
#             return
        
#         self.is_recording = not self.is_recording
#         if self.is_recording:
#             self.rec_btn.config(text="⚫ Stop Recording")
#             self.recording_label.config(text="✅ Yes", foreground="green")
#         else:
#             self.rec_btn.config(text="⚫ Start Recording")
#             self.recording_label.config(text="⏸️ Paused", foreground="orange")

#     def toggle_pause(self):
#         """Toggle pause/resume"""
#         if not self.is_acquiring:
#             return
        
#         self.is_paused = not self.is_paused
#         if self.is_paused:
#             if self.serial_reader:
#                 self.serial_reader.send_command("PAUSE")
#             self.pause_btn.config(text="▶️ Resume")
#             self.status_label.config(text="⏸️ Paused", foreground="orange")
#         else:
#             if self.serial_reader:
#                 self.serial_reader.send_command("RESUME")
#             self.pause_btn.config(text="⏸️ Pause")
#             self.status_label.config(text="✅ Connected", foreground="green")

#     def choose_save_path(self):
#         """Choose save directory"""
#         path = filedialog.askdirectory(
#             title="Select save directory",
#             initialdir=str(self.save_path)
#         )
#         if path:
#             self.save_path = Path(path)
#             self.path_label.config(text=str(self.save_path))

#     def save_session(self):
#         """Save session data"""
#         if not self.session_data:
#             messagebox.showwarning("Empty", "No data to save")
#             return
        
#         timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
#         self.save_path.mkdir(parents=True, exist_ok=True)
#         filepath = self.save_path / f"session_{timestamp}.json"
        
#         metadata = {
#             "session_info": {
#                 "timestamp": self.session_start_time.isoformat(),
#                 "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
#                 "total_packets": self.packet_count,
#                 "sampling_rate_hz": self.config.get("sampling_rate", 512),
#                 "channel_0_type": self.ch0_type,
#                 "channel_1_type": self.ch1_type
#             },
#             "sensor_config": self.config.get("sensor_mapping", {}),
#             "filters": self.config.get("filters", {}),
#             "data": self.session_data
#         }
        
#         with open(filepath, 'w') as f:
#             json.dump(metadata, f, indent=2)
        
#         messagebox.showinfo("Saved", f"Saved {len(self.session_data)} packets to {filepath}")

#     def main_loop(self):
#         """Main acquisition and update loop (Optimized)"""
#         try:
#             if self.is_acquiring and not self.is_paused and self.serial_reader:
#                 # 1. Collect all packets currently in queue
#                 batch_raw = []
#                 while True:
#                     pkt_bytes = self.serial_reader.get_packet(timeout=0)
#                     if pkt_bytes is None:
#                         break
#                     batch_raw.append(pkt_bytes)
                
#                 if batch_raw:
#                     # 2. Batch parse
#                     ctrs, r0, r1 = self.packet_parser.parse_batch(batch_raw)
                    
#                     # 3. Convert to uV
#                     u0 = adc_to_uv(r0)
#                     u1 = adc_to_uv(r1)
                    
#                     # 4. Push to LSL in chunk
#                     if LSL_AVAILABLE and self.lsl_raw_uV:
#                         chunk = np.column_stack((u0, u1)).tolist()
#                         self.lsl_raw_uV.push_chunk(chunk)
                    
#                     # 5. Update buffers efficiently
#                     n = len(u0)
#                     for i in range(n):
#                         # Simple duplicate check (last counter)
#                         if self.last_packet_counter == ctrs[i]:
#                             continue
#                         self.last_packet_counter = ctrs[i]
                        
#                         self.ch0_buffer[self.buffer_ptr] = u0[i]
#                         self.ch1_buffer[self.buffer_ptr] = u1[i]
#                         self.buffer_ptr = (self.buffer_ptr + 1) % self.buffer_size
                        
#                         if self.is_recording:
#                             # Still using dict for now, but batching parser already saved time
#                             self.session_data.append({
#                                 "packet_seq": int(ctrs[i]),
#                                 "ch0_raw_adc": int(r0[i]),
#                                 "ch1_raw_adc": int(r1[i]),
#                                 "ch0_uv": float(u0[i]),
#                                 "ch1_uv": float(u1[i])
#                             })
                        
#                         self.packet_count += 1

#             # Update UI labels
#             self.packet_label.config(text=str(self.packet_count))
            
#             # Update plots (every 30ms call, but update_plots itself is faster now)
#             self.update_plots()
        
#         except Exception as e:
#             print(f"Main loop error: {e}")
        
#         # Schedule next update
#         if self.root.winfo_exists():
#             self.root.after(30, self.main_loop)

#     def update_plots(self):
#         """Update the plot lines (Optimized)"""
#         try:
#             if not self.is_acquiring or self.is_paused:
#                 return

#             # Rotate buffers so latest data is on the right
#             ch0_rotated = np.roll(self.ch0_buffer, -self.buffer_ptr)
#             ch1_rotated = np.roll(self.ch1_buffer, -self.buffer_ptr)
            
#             # Update line data
#             self.line0.set_ydata(ch0_rotated)
#             self.line1.set_ydata(ch1_rotated)
            
#             # Redraw only when needed
#             self.canvas.draw_idle()
#         except Exception as e:
#             print(f"Plot update error: {e}")

#     def on_closing(self):
#         """Handle window closing"""
#         try:
#             if self.is_acquiring:
#                 self.stop_acquisition()
#             if self.serial_reader:
#                 self.serial_reader.disconnect()
#         finally:
#             self.root.destroy()

# def main():
#     root = tk.Tk()
#     app = AcquisitionApp(root)
#     app.update_port_list()
#     root.mainloop()

# if __name__ == "__main__":
#     main()


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
from queue import Queue, Empty

# Ensure we can import sibling packages
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

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
        self.session_start_time = None
        self.packet_count = 0
        self.last_packet_counter = None
        
        # Channel mapping
        self.ch0_type = "EMG"
        self.ch1_type = "EOG"
        
        # Data buffers for real-time plotting
        self.window_seconds = self.config.get("ui_settings", {}).get("window_seconds", 5.0)
        self.buffer_size = int(self.config.get("sampling_rate", 512) * self.window_seconds)
        
        # Ring buffers
        self.ch0_buffer = np.zeros(self.buffer_size)
        self.ch1_buffer = np.zeros(self.buffer_size)
        self.buffer_ptr = 0
        
        # Time axis
        self.time_axis = np.linspace(0, self.window_seconds, self.buffer_size)
        
        # Session data
        self.session_data = []
        self.latest_packet = {}

        self.data_queue = Queue(maxsize=1000)  # Bounded queue
        self.acquisition_thread = None
        self.thread_running = False
        
        # Build UI
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start Sync Thread
        self.start_sync_thread()

        # Start main loop
        self.main_loop()

    def _load_config(self) -> dict:
        """Load configuration from API or JSON file"""
        # Try API first
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
            print(f"[App] ⚠️ API load failed ({e}), falling back to file")

        # Fallback to local file
        project_root = Path(__file__).resolve().parent.parent.parent
        config_path = project_root / "config" / "sensor_config.json"
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[App] Error loading config: {e}")
                return self._default_config()
        return self._default_config()

    def _default_config(self) -> dict:
        """Default configuration"""
        return {
            "sampling_rate": 512,
            "channel_mapping": {
                "ch0": {"sensor": "EMG", "enabled": True, "label": "EMG Channel 0"},
                "ch1": {"sensor": "EOG", "enabled": True, "label": "EOG Channel 1"}
            },
            "filters": {
                "EMG": {"type": "high_pass", "cutoff": 70.0, "order": 4, "enabled": True},
                "EOG": {"type": "low_pass", "cutoff": 10.0, "order": 4, "enabled": True}
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
        """Save configuration to JSON file and API"""
        
        # UPDATE channel mapping from UI BEFORE saving
        self.config["channel_mapping"] = {
            "ch0": {"sensor": self.ch0_var.get(), "enabled": True},
            "ch1": {"sensor": self.ch1_var.get(), "enabled": True}
        }
        
        # 1. Save to Local File (Backup)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"[App] Config saved to {self.config_path}")
        except Exception as e:
            print(f"[App] Error saving config locally: {e}")
            messagebox.showerror("Error", f"Failed to save config: {e}")

        # 2. Push to API (Primary)
        def push_to_api(cfg):
            try:
                import urllib.request
                url = "http://localhost:5000/api/config"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(cfg).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=1) as response:
                    print(f"[App] 📤 Config pushed to API: {response.status}")
            except Exception as e:
                print(f"[App] ❌ Failed to push to API: {e}")
        
        threading.Thread(target=push_to_api, args=(self.config,), daemon=True).start()

    def start_sync_thread(self):
        """Poll API for config changes"""
        def loop():
            import urllib.request
            last_check = 0
            while True:
                time.sleep(2)
                try:
                    # Don't interrupt if we are actively recording/streaming to avoid jitter
                    # (optional trade-off)
                    
                    url = "http://localhost:5000/api/config"
                    with urllib.request.urlopen(url, timeout=1) as response:
                        if response.status == 200:
                            new_cfg = json.loads(response.read().decode())
                            
                            # Simple check if channel mapping changed
                            current_map = self.config.get("channel_mapping", {})
                            new_map = new_cfg.get("channel_mapping", {})
                            
                            if json.dumps(current_map, sort_keys=True) != json.dumps(new_map, sort_keys=True):
                                print(f"[App] 🔄 Remote config change detected!")
                                print(f"[App] Local: {current_map}")
                                print(f"[App] Remote: {new_map}")
                                self.root.after(0, self.update_config_from_remote, new_cfg)
                except Exception as e:
                    print(f"[App] Sync loop error: {e}")
        
        threading.Thread(target=loop, daemon=True).start()

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

    def _build_control_panel(self, parent):
        """Build left control panel"""
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
        if LSL_AVAILABLE:
            ch_types = [self.ch0_type, self.ch1_type]
            ch_labels = [f"{self.ch0_type}_0", f"{self.ch1_type}_1"]
            self.lsl_raw_uV = LSLStreamer(
                "BioSignals-Raw-uV",
                channel_types=ch_types,
                channel_labels=ch_labels,
                channel_count=2,
                nominal_srate=float(self.config.get("sampling_rate", 512))
            )
        
    def disconnect_device(self):
        """Disconnect from Arduino"""
        if self.is_acquiring:
            self.stop_acquisition()
        
        self.is_connected = False
        if self.serial_reader:
            self.serial_reader.disconnect()
        
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
        self.buffer_ptr = 0

        # Start acquisition in separate thread
        self.thread_running = True
        self.acquisition_thread = threading.Thread(
            target=self._acquisition_worker,
            daemon=True
        )
        self.acquisition_thread.start()
        
        # Update UI
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.pause_btn.config(state="normal")
        self.rec_btn.config(state="normal")
        self.save_btn.config(state="normal")
        self.recording_label.config(text="✅ Yes", foreground="green")

    def _acquisition_worker(self):
        """Separate thread for heavy data processing"""
        print("[Worker] 🧵 Acquisition worker started")
        
        while self.thread_running and self.is_acquiring:
            try:
                # Collect a SMALL batch (not ALL packets!)
                batch_raw = []
                batch_size = 10
                
                for _ in range(batch_size):
                    pkt_bytes = self.serial_reader.get_packet(timeout=0.01)
                    if pkt_bytes is None:
                        break
                    batch_raw.append(pkt_bytes)
                
                if not batch_raw:
                    continue  # No data yet, try again
                
                # Put data in queue for GUI thread to process
                self.data_queue.put(batch_raw)
                
            except Exception as e:
                print(f"[Worker] Error: {e}")
                break
        
        print("[Worker] 🧵 Acquisition worker stopped")

    def stop_acquisition(self):
        """Stop acquiring data"""
        self.thread_running = False 

        try:
            if self.serial_reader:
                self.serial_reader.send_command("STOP")
        except:
            pass
        
        self.is_acquiring = False
        self.is_paused = False
        self.is_recording = False

        # Wait for worker thread to finish
        if self.acquisition_thread and self.acquisition_thread.is_alive():
            self.acquisition_thread.join(timeout=1)
        
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

    # def main_loop(self):
    #     """Main acquisition and update loop (Optimized)"""
    #     try:
    #         if self.is_acquiring and not self.is_paused and self.serial_reader:
    #             # 1. Collect all packets currently in queue
    #             batch_raw = []
    #             while True:
    #                 pkt_bytes = self.serial_reader.get_packet(timeout=0)
    #                 if pkt_bytes is None:
    #                     break
    #                 batch_raw.append(pkt_bytes)
                
    #             if batch_raw:
    #                 # 2. Batch parse
    #                 ctrs, r0, r1 = self.packet_parser.parse_batch(batch_raw)
                    
    #                 # 3. Convert to uV
    #                 u0 = adc_to_uv(r0)
    #                 u1 = adc_to_uv(r1)
                    
    #                 # 4. Push to LSL in chunk
    #                 if LSL_AVAILABLE and self.lsl_raw_uV:
    #                     chunk = np.column_stack((u0, u1)).tolist()
    #                     self.lsl_raw_uV.push_chunk(chunk)
                    
    #                 # 5. Update buffers efficiently
    #                 n = len(u0)
    #                 for i in range(n):
    #                     # Simple duplicate check (last counter)
    #                     if self.last_packet_counter == ctrs[i]:
    #                         continue
    #                     self.last_packet_counter = ctrs[i]
                        
    #                     self.ch0_buffer[self.buffer_ptr] = u0[i]
    #                     self.ch1_buffer[self.buffer_ptr] = u1[i]
    #                     self.buffer_ptr = (self.buffer_ptr + 1) % self.buffer_size
                        
    #                     if self.is_recording:
    #                         # Still using dict for now, but batching parser already saved time
    #                         self.session_data.append({
    #                             "packet_seq": int(ctrs[i]),
    #                             "ch0_raw_adc": int(r0[i]),
    #                             "ch1_raw_adc": int(r1[i]),
    #                             "ch0_uv": float(u0[i]),
    #                             "ch1_uv": float(u1[i])
    #                         })
                        
    #                     self.packet_count += 1

    #         # Update UI labels
    #         self.packet_label.config(text=str(self.packet_count))
            
    #         # Update plots (every 30ms call, but update_plots itself is faster now)
    #         self.update_plots()
        
    #     except Exception as e:
    #         print(f"Main loop error: {e}")
        
    #     # Schedule next update
    #     if self.root.winfo_exists():
    #         self.root.after(30, self.main_loop)

    def main_loop(self):
        """GUI thread - stays responsive"""
        try:
            # Process queued data in small batches
            try:
                batch_raw = self.data_queue.get_nowait()  # Non-blocking!
            except:
                batch_raw = None
            
            if batch_raw and self.is_acquiring and not self.is_paused:
                # Parse, convert, update UI
                ctrs, r0, r1 = self.packet_parser.parse_batch(batch_raw)
                u0 = adc_to_uv(r0)
                u1 = adc_to_uv(r1)
                
                if LSL_AVAILABLE and self.lsl_raw_uV:
                    chunk = np.column_stack((u0, u1)).tolist()
                    self.lsl_raw_uV.push_chunk(chunk)
                
                # Update buffers
                n = len(u0)
                for i in range(n):
                    if self.last_packet_counter == ctrs[i]:
                        continue
                    
                    self.last_packet_counter = ctrs[i]
                    self.ch0_buffer[self.buffer_ptr] = u0[i]
                    self.ch1_buffer[self.buffer_ptr] = u1[i]
                    self.buffer_ptr = (self.buffer_ptr + 1) % self.buffer_size
                    
                    if self.is_recording:
                        self.session_data.append({
                            "packet_seq": int(ctrs[i]),
                            "ch0_raw_adc": int(r0[i]),
                            "ch1_raw_adc": int(r1[i]),
                            "ch0_uv": float(u0[i]),
                            "ch1_uv": float(u1[i])
                        })
                    
                    self.packet_count += 1
                
                # Update labels
                self.packet_label.config(text=str(self.packet_count))
                self.update_plots()
        
        except Exception as e:
            print(f"Main loop error: {e}")
        
        # Schedule next update
        if self.root.winfo_exists():
            self.root.after(30, self.main_loop)  # 30ms updates

    def update_plots(self):
        """Update the plot lines (Optimized)"""
        try:
            if not self.is_acquiring or self.is_paused:
                return

            # Rotate buffers so latest data is on the right
            ch0_rotated = np.roll(self.ch0_buffer, -self.buffer_ptr)
            ch1_rotated = np.roll(self.ch1_buffer, -self.buffer_ptr)
            
            # Update line data
            self.line0.set_ydata(ch0_rotated)
            self.line1.set_ydata(ch1_rotated)
            
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
