"""
Fixed Acquisition App - Dynamic Graphs
- Both graphs now load and update properly
- Smooth real-time animation
- Proper matplotlib integration
- Better error handling
"""

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

# Ensure we can import sibling packages (like processing)
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# local imports
from .serial_reader import SerialPacketReader
from .packet_parser import PacketParser, Packet
from .lsl_streams import LSLStreamer, LSL_AVAILABLE

# Bridge integration
from processing.bridge import DataBridge

# matplotlib imports
import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for Tkinter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation

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


class UnifiedAcquisitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EMG Signal Acquisition - OPTIMIZED v5.1 (Modular)")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')
        
        # Configuration
        self.config = {"sampling_rate": 512}
        self.save_path = Path("data/raw/session")
        
        # Serial reader & parser
        self.serial_reader = None
        self.packet_parser = PacketParser()
        
        # LSL streams
        self.lsl_raw = None
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
        self.channel_mapping = {0: "EMG", 1: "EOG"}
        
        # Data buffers for real-time plotting
        self.window_seconds = 5.0
        self.buffer_size = int(self.config.get("sampling_rate", 512) * self.window_seconds)
        
        # Ring buffers
        self.ch0_buffer = np.zeros(self.buffer_size)
        self.ch1_buffer = np.zeros(self.buffer_size)
        self.buffer_ptr = 0
        
        # Time axis
        self.time_axis = np.linspace(0, self.window_seconds, self.buffer_size)
        
        # Session data
        self.session_data = []
        
        # Latest packet for display
        self.latest_packet = {}
        
        # Bridge Integration
        self.bridge = DataBridge()
        self.bridge.start()
        
        # Build UI
        self._build_ui()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Start main loop
        self.main_loop()
    
    # ============ UI BUILDING ============
    
    def make_scrollable_left_panel(self, parent):
        """Create a scrollable frame for the left control panel"""
        container = ttk.Frame(parent)
        container.pack(side="left", fill="y", expand=False, padx=5, pady=5)
        canvas = tk.Canvas(container, width=320, highlightthickness=0, bg='white')
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable_frame, anchor="nw")
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
    
    def _build_ui(self):
        """Build the entire UI"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # LEFT PANEL (Controls) - Scrollable
        left_container = ttk.Frame(main_frame)
        left_container.pack(side="left", fill="y", expand=False)
        left_panel = self.make_scrollable_left_panel(left_container)
        
        self._build_control_panel(left_panel)
        
        # RIGHT PANEL (Graphs)
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True, padx=5)
        
        self._build_graph_panel(right_panel)
    
    def _build_control_panel(self, parent):
        """Build left control panel"""
        
        # CONNECTION SECTION
        conn_frame = ttk.LabelFrame(parent, text="Connection", padding=10)
        conn_frame.pack(fill="x", pady=5)
        
        ttk.Label(conn_frame, text="COM Port:").pack(anchor="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            conn_frame, 
            textvariable=self.port_var, 
            width=30, 
            state="readonly"
        )
        self.port_combo.pack(fill="x", pady=5)
        
        ttk.Button(conn_frame, text="Refresh Ports", command=self.update_port_list).pack(fill="x", pady=2)
        
        # CHANNEL MAPPING
        map_frame = ttk.LabelFrame(parent, text="Channel Mapping", padding=10)
        map_frame.pack(fill="x", pady=5)
        
        ttk.Label(map_frame, text="Channel 0:").pack(anchor="w")
        self.ch0_var = tk.StringVar(value="EMG")
        ttk.Combobox(map_frame, textvariable=self.ch0_var, 
                     values=['EMG', 'EOG', 'EEG'], 
                     state="readonly").pack(fill="x", pady=2)
        
        ttk.Label(map_frame, text="Channel 1:").pack(anchor="w")
        self.ch1_var = tk.StringVar(value="EOG")
        ttk.Combobox(map_frame, textvariable=self.ch1_var, 
                     values=['EMG', 'EOG', 'EEG'], 
                     state="readonly").pack(fill="x", pady=2)
        
        # CONTROL BUTTONS
        btn_frame = ttk.LabelFrame(parent, text="⚙️ Control", padding=10)
        btn_frame.pack(fill="x", pady=5)
        
        self.filter_btn = ttk.Button(
            btn_frame, 
            text="📡 Show Server Status", 
            command=self.toggle_server
        )
        self.filter_btn.pack(fill="x", padx=2, pady=2)
        
        self.server_label = ttk.Label(
            btn_frame, 
            text="Server: Off", 
            foreground="gray", 
            font=("Consolas", 9)
        )
        self.server_label.pack(fill="x", padx=5, pady=2)
        
        self.connect_btn = ttk.Button(
            btn_frame, 
            text="🔌 Connect", 
            command=self.connect_device
        )
        self.connect_btn.pack(fill="x", padx=2, pady=3)
        
        self.disconnect_btn = ttk.Button(
            btn_frame, 
            text="Disconnect", 
            command=self.disconnect_device,
            state="disabled"
        )
        self.disconnect_btn.pack(fill="x", pady=3)
        
        self.start_btn = ttk.Button(
            btn_frame, 
            text="Start Acquisition", 
            command=self.start_acquisition,
            state="disabled"
        )
        self.start_btn.pack(fill="x", pady=3)
        
        self.stop_btn = ttk.Button(
            btn_frame, 
            text="Stop Acquisition", 
            command=self.stop_acquisition,
            state="disabled"
        )
        self.stop_btn.pack(fill="x", pady=3)
        
        self.pause_btn = ttk.Button(
            btn_frame, 
            text="Pause", 
            command=self.toggle_pause,
            state="disabled"
        )
        self.pause_btn.pack(fill="x", pady=3)
        
        # RECORDING
        rec_frame = ttk.LabelFrame(parent, text="Recording", padding=10)
        rec_frame.pack(fill="x", pady=5)
        
        self.rec_btn = ttk.Button(
            rec_frame, 
            text="Start Recording", 
            command=self.toggle_recording,
            state="disabled"
        )
        self.rec_btn.pack(fill="x", pady=3)
        
        # SAVE
        save_frame = ttk.LabelFrame(parent, text="Save", padding=10)
        save_frame.pack(fill="x", pady=5)
        
        ttk.Button(save_frame, text="Choose Path", 
                   command=self.choose_save_path).pack(fill="x", pady=2)
        
        self.path_label = ttk.Label(save_frame, text=str(self.save_path), 
                                    wraplength=250)
        self.path_label.pack(fill="x", pady=2)
        
        self.save_btn = ttk.Button(
            save_frame, 
            text="Save Session", 
            command=self.save_session,
            state="disabled"
        )
        self.save_btn.pack(fill="x", pady=3)
        
        # STATUS
        status_frame = ttk.LabelFrame(parent, text="Status", padding=10)
        status_frame.pack(fill="x", pady=5)
        
        ttk.Label(status_frame, text="Connection:").pack(anchor="w")
        self.status_label = ttk.Label(status_frame, text="Disconnected", 
                                      foreground="red")
        self.status_label.pack(anchor="w", pady=2)
        
        ttk.Label(status_frame, text="Packets:").pack(anchor="w")
        self.packet_label = ttk.Label(status_frame, text="0")
        self.packet_label.pack(anchor="w", pady=2)
        
        ttk.Label(status_frame, text="Recording:").pack(anchor="w")
        self.recording_label = ttk.Label(status_frame, text="No", 
                                         foreground="red")
        self.recording_label.pack(anchor="w")
        
        # LATEST PACKET DISPLAY
        latest_frame = ttk.LabelFrame(parent, text="🧾 Latest Packet Detail", padding=8)
        latest_frame.pack(fill="x", pady=5, padx=5)
        self.latest_text = tk.Text(latest_frame, height=6, width=40, wrap="word")
        self.latest_text.insert("1.0", "No packet yet.")
        self.latest_text.configure(state="disabled")
        self.latest_text.pack(fill="both", expand=True)
    
    def _build_graph_panel(self, parent):
        """Build right graph panel"""
        
        # Create matplotlib figure with 2 subplots
        fig = Figure(figsize=(10, 8), dpi=100)
        fig.tight_layout(pad=3.0)
        
        # Subplot 1: Channel 0
        self.ax0 = fig.add_subplot(211)
        self.ax0.set_title("Channel 0 (EMG) - Real-time", fontsize=12, fontweight='bold')
        self.ax0.set_xlabel("Time (seconds)")
        self.ax0.set_ylabel("Amplitude (µV)")
        self.ax0.grid(True, alpha=0.3)
        self.ax0.set_ylim(-2000, 2000)
        self.line0, = self.ax0.plot(self.time_axis, self.ch0_buffer, 
                                     color='red', linewidth=1.5, label='CH0')
        self.ax0.legend(loc='upper right')
        
        # Subplot 2: Channel 1
        self.ax1 = fig.add_subplot(212)
        self.ax1.set_title("Channel 1 (EOG) - Real-time", fontsize=12, fontweight='bold')
        self.ax1.set_xlabel("Time (seconds)")
        self.ax1.set_ylabel("Amplitude (µV)")
        self.ax1.grid(True, alpha=0.3)
        self.ax1.set_ylim(-2000, 2000)
        self.line1, = self.ax1.plot(self.time_axis, self.ch1_buffer, 
                                     color='blue', linewidth=1.5, label='CH1')
        self.ax1.legend(loc='upper right')
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Store references
        self.fig = fig
    
    # ============ PORT MANAGEMENT ============
    
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
    
    # ============ DEVICE LIFECYCLE ============
    
    def connect_device(self):
        """Connect to Arduino"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        
        port = self.port_var.get().split(" ")[0]  # Extract just "COM7" from "COM7 - Description"
        
        # Create serial reader
        self.serial_reader = SerialPacketReader(port=port)
        if not self.serial_reader.connect():
            messagebox.showerror("Error", f"Failed to connect to {port}")
            return
        
        self.serial_reader.start()
        self.is_connected = True
        
        # Update UI
        self.status_label.config(text="Connected", foreground="green")
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="normal")
        self.start_btn.config(state="normal")
        
        # Create LSL outlets
        ch_types = [self.ch0_var.get(), self.ch1_var.get()]
        ch_labels = [f"{ch_types}_0", f"{ch_types}_1"]
        
        if LSL_AVAILABLE:
            self.lsl_raw = LSLStreamer(
                "BioSignals-Raw",
                channel_types=ch_types,
                channel_labels=ch_labels,
                channel_count=2,
                nominal_srate=float(self.config.get("sampling_rate", 512))
            )
            self.lsl_processed = LSLStreamer(
                "BioSignals",
                channel_types=ch_types,
                channel_labels=ch_labels,
                channel_count=2,
                nominal_srate=float(self.config.get("sampling_rate", 512))
            )
        
        messagebox.showinfo("Success", f"Connected to {port}")
    
    def disconnect_device(self):
        """Disconnect from Arduino"""
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
        
        # Update UI
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.pause_btn.config(state="normal")
        self.rec_btn.config(state="normal")
        self.save_btn.config(state="normal")
        self.recording_label.config(text="Yes", foreground="green")
    
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
        self.recording_label.config(text="No", foreground="red")
    
    def toggle_recording(self):
        """Toggle recording"""
        if not self.is_acquiring:
            messagebox.showerror("Error", "Start acquisition first")
            return
        
        self.is_recording = not self.is_recording
        
        if self.is_recording:
            self.rec_btn.config(text="Stop Recording")
            self.recording_label.config(text="Yes", foreground="green")
        else:
            self.rec_btn.config(text="Start Recording")
            self.recording_label.config(text="No", foreground="orange")
    
    def toggle_pause(self):
        """Toggle pause/resume acquisition"""
        if not self.is_acquiring:
            return
        
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            # Send PAUSE command to device
            if self.serial_reader:
                self.serial_reader.send_command("PAUSE")
            self.pause_btn.config(text="Resume")
            self.status_label.config(text="Paused", foreground="orange")
        else:
            # Send RESUME command to device
            if self.serial_reader:
                self.serial_reader.send_command("RESUME")
            self.pause_btn.config(text="Pause")
            self.status_label.config(text="Connected", foreground="green")
    
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
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.save_path.mkdir(parents=True, exist_ok=True)
        filepath = self.save_path / f"session_{timestamp}.json"
        
        metadata = {
            "session_info": {
                "timestamp": self.session_start_time.isoformat(),
                "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
                "total_packets": self.packet_count,
                "sampling_rate_hz": self.config.get("sampling_rate", 512),
                "channel_0_type": self.ch0_var.get(),
                "channel_1_type": self.ch1_var.get()
            },
            "data": self.session_data
        }
        
        with open(filepath, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        messagebox.showinfo("Saved", 
                          f"Saved {len(self.session_data)} packets to {filepath}")
    
    # ============ MAIN LOOP ============
    
    def main_loop(self):
        """Main acquisition and update loop"""
        try:
            if self.is_acquiring and not self.is_paused and self.serial_reader:
                # Drain queued packets
                while True:
                    pkt_bytes = self.serial_reader.get_packet(timeout=0.001)
                    if pkt_bytes is None:
                        break
                    
                    try:
                        pkt = self.packet_parser.parse(pkt_bytes)
                    except Exception as e:
                        print(f"Parse error: {e}")
                        continue
                    
                    # Duplicate check
                    if self.last_packet_counter is not None:
                        if pkt.counter == self.last_packet_counter:
                            continue
                    
                    self.last_packet_counter = pkt.counter
                    
                    # Convert to µV
                    ch0_uv = adc_to_uv(pkt.ch0_raw)
                    ch1_uv = adc_to_uv(pkt.ch1_raw)
                    
                    # Push to LSL
                    if LSL_AVAILABLE:
                        if self.lsl_raw:
                            self.lsl_raw.push_sample([ch0_uv, ch1_uv], None)
                        if self.lsl_processed:
                            self.lsl_processed.push_sample([ch0_uv, ch1_uv], None)
                    
                    # Add to circular buffers
                    self.ch0_buffer[self.buffer_ptr] = ch0_uv
                    self.ch1_buffer[self.buffer_ptr] = ch1_uv
                    self.buffer_ptr = (self.buffer_ptr + 1) % self.buffer_size
                    
                    # Record if recording
                    if self.is_recording:
                        entry = {
                            "timestamp": pkt.timestamp.isoformat(),
                            "packet_seq": int(pkt.counter),
                            "ch0_raw_adc": int(pkt.ch0_raw),
                            "ch1_raw_adc": int(pkt.ch1_raw),
                            "ch0_uv": float(ch0_uv),
                            "ch1_uv": float(ch1_uv),
                            "ch0_type": self.ch0_var.get(),
                            "ch1_type": self.ch1_var.get()
                        }
                        self.session_data.append(entry)
                        self.latest_packet = entry
                    
                    # Broadcast to WebSocket bridge
                    msg = {
                        "source": "EMG",
                        "fs": self.config.get("sampling_rate", 512),
                        "timestamp": int(time.time() * 1000),
                        "window": [[ch0_uv], [ch1_uv]]
                    }
                    if self.bridge.running:
                        self.bridge.broadcast(msg)
                    
                    self.packet_count += 1
            
            # Update UI labels
            self.packet_label.config(text=str(self.packet_count))
            
            # Update latest packet display
            self.update_latest_packet_display()
            
            # Update plots
            self.update_plots()
        
        except Exception as e:
            print(f"Main loop error: {e}")
        
        # Schedule next update (30ms = ~33Hz)
        if self.root.winfo_exists():
            self.root.after(30, self.main_loop)
    
    def update_plots(self):
        """Update the plot lines"""
        try:
            # Rotate buffers so latest data is on the right
            ch0_rotated = np.roll(self.ch0_buffer, -self.buffer_ptr)
            ch1_rotated = np.roll(self.ch1_buffer, -self.buffer_ptr)
            
            # Update line data
            self.line0.set_ydata(ch0_rotated)
            self.line1.set_ydata(ch1_rotated)
            
            # Redraw
            self.canvas.draw_idle()
        
        except Exception as e:
            print(f"Plot update error: {e}")
    
    def update_latest_packet_display(self):
        """Update the latest packet display widget"""
        if not self.latest_packet:
            return
        try:
            self.latest_text.configure(state="normal")
            self.latest_text.delete("1.0", "end")
            self.latest_text.insert("1.0", json.dumps(self.latest_packet, indent=2))
            self.latest_text.configure(state="disabled")
        except:
            pass
    
    def toggle_server(self):
        """Show WebSocket server status"""
        self.server_label.config(
            text="Server: ws://localhost:8765 (Active)", 
            foreground="green"
        )
        self.filter_btn.config(state="disabled")
    
    def on_closing(self):
        """Handle window closing"""
        try:
            if self.is_acquiring:
                self.stop_acquisition()
            if self.serial_reader:
                self.serial_reader.disconnect()
            if self.bridge:
                # Stop bridge if it has a stop method
                pass
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = UnifiedAcquisitionApp(root)
    app.update_port_list()
    root.mainloop()


if __name__ == "__main__":
    main()
