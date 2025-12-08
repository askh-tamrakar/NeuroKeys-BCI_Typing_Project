"""
EMG Acquisition App - OPTIMIZED v5.1
Performance improvements:
 - Unified single update loop instead of multiple after() calls
 - Batch updates every 100ms
 - Use draw_idle() instead of draw()
 - Fixed-size buffers (1024 samples max)
 - Queue-based packet processing
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
import sys
import os

# Ensure we can import sibling packages (like processing)
# Add 'src' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from processing.bridge import DataBridge

class EMGAcquisitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EMG Signal Acquisition - OPTIMIZED v5.1")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')

        # device / packet
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = 512.0
        self.BAUD_RATE = 230400
        self.NUM_CHANNELS = 2

        # state
        self.ser = None
        self.acquisition_active = False
        self.acquisition_thread = None
        self.is_recording = False

        # data
        self.session_data = []
        self.recorded_data = []
        self.session_start_time = None
        self.packet_count = 0
        self.bytes_received = 0

        # buffers (fixed size)
        self.graph_buffer_ch0 = deque(maxlen=1024)
        self.graph_buffer_ch1 = deque(maxlen=1024)
        self.graph_time_buffer = deque(maxlen=1024)
        self.graph_index = 0

        # Queue for thread-safe packet processing
        self.data_queue = queue.Queue()

        # Batch update variables
        self.pending_updates = 0
        self.last_update_time = time.time()
        self.update_interval = 0.1

        # save path
        self.save_path = Path("data/raw/session/emg")

        # latest packet
        self.latest_packet = {}

        self.setup_ui()
        self.update_port_list()

        # Bridge Integration
        self.bridge = DataBridge()
        self.bridge.start()
        
        # Single update loop
        self.root.after(30, self.main_update_loop)

    def make_scrollable_left_panel(self, parent):
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

    def setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        left_container = ttk.Frame(main_frame)
        left_container.pack(side="left", fill="y", expand=False)
        left_frame = self.make_scrollable_left_panel(left_container)
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)

        # Connection
        connection_frame = ttk.LabelFrame(left_frame, text="🔌 Connection", padding=10)
        connection_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(connection_frame, text="COM Port:").pack(anchor="w", padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=30, state="readonly")
        self.port_combo.pack(fill="x", padx=5, pady=2)
        ttk.Button(connection_frame, text="🔄 Refresh Ports", command=self.update_port_list).pack(fill="x", padx=5, pady=2)
        ttk.Label(connection_frame, text=f"Baud: {self.BAUD_RATE} | {int(self.SAMPLING_RATE)} Hz").pack(anchor="w", padx=5)

        # Status
        status_frame = ttk.LabelFrame(left_frame, text="📊 Status", padding=10)
        status_frame.pack(fill="x", pady=5, padx=5)
        ttk.Label(status_frame, text="Connection:").pack(anchor="w", padx=5)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial",10,"bold"))
        self.status_label.pack(anchor="w", padx=5, pady=2)
        ttk.Label(status_frame, text="Packets:").pack(anchor="w", padx=5)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.packet_label.pack(anchor="w", padx=5)
        ttk.Label(status_frame, text="Duration:").pack(anchor="w", padx=5)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial", 10, "bold"))
        self.duration_label.pack(anchor="w", padx=5)
        ttk.Label(status_frame, text="Rate (Hz):").pack(anchor="w", padx=5)
        self.rate_label = ttk.Label(status_frame, text="0 Hz")
        self.rate_label.pack(anchor="w", padx=5)
        ttk.Label(status_frame, text="Speed (KBps):").pack(anchor="w", padx=5)
        self.speed_label = ttk.Label(status_frame, text="0 KBps")
        self.speed_label.pack(anchor="w", padx=5)

        # Control
        control_frame = ttk.LabelFrame(left_frame, text="⚙️ Control", padding=10)
        control_frame.pack(fill="x", pady=5, padx=5)
        self.filter_btn = ttk.Button(control_frame, text="📡 Show Server Status", command=self.toggle_server)
        self.filter_btn.pack(fill="x", padx=2, pady=2)
        
        self.server_label = ttk.Label(control_frame, text="Server: Off", foreground="gray", font=("Consolas", 9))
        self.server_label.pack(fill="x", padx=5, pady=2)
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_arduino)
        self.connect_btn.pack(fill="x", padx=2, pady=2)
        self.disconnect_btn = ttk.Button(control_frame, text="❌ Disconnect", command=self.disconnect_arduino, state="disabled")
        self.disconnect_btn.pack(fill="x", padx=2, pady=2)
        self.start_btn = ttk.Button(control_frame, text="▶️ Start Acquisition", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", padx=2, pady=2)
        self.stop_btn = ttk.Button(control_frame, text="⏹️ Stop Acquisition", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", padx=2, pady=2)

        # Recording
        rec_frame = ttk.LabelFrame(left_frame, text="📝 Recording", padding=10)
        rec_frame.pack(fill="x", pady=5, padx=5)
        self.pause_rec_btn = ttk.Button(rec_frame, text="⏸️ Pause Recording", command=self.toggle_recording, state="disabled")
        self.pause_rec_btn.pack(fill="x", padx=2, pady=2)
        ttk.Label(rec_frame, text="Recording starts automatically when acquisition starts").pack(anchor="w", padx=5, pady=4)

        # Save
        save_frame = ttk.LabelFrame(left_frame, text="💾 Save / Export", padding=10)
        save_frame.pack(fill="x", pady=5, padx=5)
        ttk.Button(save_frame, text="📁 Choose Path", command=self.choose_save_path).pack(fill="x", padx=2, pady=2)
        self.path_label = ttk.Label(save_frame, text=str(self.save_path), wraplength=280, justify="left")
        self.path_label.pack(fill="x", padx=2, pady=4)
        self.save_btn = ttk.Button(save_frame, text="💾 Save Session JSON", command=self.save_session_data, state="disabled")
        self.save_btn.pack(fill="x", padx=2, pady=2)
        self.export_btn = ttk.Button(save_frame, text="📊 Export Graph PNG", command=self.export_graph, state="disabled")
        self.export_btn.pack(fill="x", padx=2, pady=2)

        # Stats
        stats_frame = ttk.LabelFrame(left_frame, text="📈 Stats", padding=10)
        stats_frame.pack(fill="both", expand=True, pady=5, padx=5)
        ttk.Label(stats_frame, text="Channel 0 (Flexor):").pack(anchor="w", padx=5)
        self.ch0_min_label = ttk.Label(stats_frame, text="Min: 0")
        self.ch0_min_label.pack(anchor="w", padx=10)
        self.ch0_max_label = ttk.Label(stats_frame, text="Max: 0")
        self.ch0_max_label.pack(anchor="w", padx=10)
        self.ch0_mean_label = ttk.Label(stats_frame, text="Mean: 0")
        self.ch0_mean_label.pack(anchor="w", padx=10, pady=4)
        ttk.Label(stats_frame, text="Channel 1 (Extensor):").pack(anchor="w", padx=5)
        self.ch1_min_label = ttk.Label(stats_frame, text="Min: 0")
        self.ch1_min_label.pack(anchor="w", padx=10)
        self.ch1_max_label = ttk.Label(stats_frame, text="Max: 0")
        self.ch1_max_label.pack(anchor="w", padx=10)
        self.ch1_mean_label = ttk.Label(stats_frame, text="Mean: 0")
        self.ch1_mean_label.pack(anchor="w", padx=10, pady=4)

        # Latest packet
        latest_frame = ttk.LabelFrame(left_frame, text="🧾 Latest packet detail", padding=8)
        latest_frame.pack(fill="x", pady=5, padx=5)
        self.latest_text = tk.Text(latest_frame, height=6, width=40, wrap="word")
        self.latest_text.insert("1.0", "No packet yet.")
        self.latest_text.configure(state="disabled")
        self.latest_text.pack(fill="both", expand=True)

        # Graph (right)
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EMG Signal (512 Hz)", padding=5)
        graph_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.fig = Figure(figsize=(10,6), dpi=100, facecolor='white')
        self.fig.patch.set_facecolor('#f0f0f0')
        self.ax_ch0 = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_ch0.plot([], [], linewidth=1.2, label='Ch0 (Flexor)', color='#0066cc')
        self.ax_ch0.set_ylabel('ADC Value')
        self.ax_ch0.set_ylim(0, 16384)
        self.ax_ch0.grid(True, alpha=0.3)
        self.ax_ch0.legend(loc='upper left', fontsize=9)
        self.ax_ch1 = self.fig.add_subplot(212)
        self.line_ch1, = self.ax_ch1.plot([], [], linewidth=1.2, label='Ch1 (Extensor)', color='#ff6600')
        self.ax_ch1.set_ylabel('ADC Value')
        self.ax_ch1.set_xlabel('Samples')
        self.ax_ch1.set_ylim(0, 16384)
        self.ax_ch1.grid(True, alpha=0.3)
        self.ax_ch1.legend(loc='upper left', fontsize=9)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # Serial / parsing
    def update_port_list(self):
        ports = []
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{port} - {desc}")
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)

    def connect_arduino(self):
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
            self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
            self.read_thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")
            self.status_label.config(text="❌ Failed", foreground="red")

    def disconnect_arduino(self):
        if self.acquisition_active:
            self.stop_acquisition()
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.status_label.config(text="❌ Disconnected", foreground="red")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.export_btn.config(state="disabled")
        self.pause_rec_btn.config(state="disabled")

    def read_loop(self):
        buffer = bytearray()
        while True:
            if self.ser is None or not getattr(self.ser, "is_open", False):
                time.sleep(0.1)
                continue
            try:
                if self.ser.in_waiting > 0:
                    chunk = self.ser.read(self.ser.in_waiting)
                    if chunk:
                        self.bytes_received += len(chunk)
                        buffer.extend(chunk)
                    while len(buffer) >= self.PACKET_LEN:
                        if buffer[0] == self.SYNC_BYTE_1 and buffer[1] == self.SYNC_BYTE_2:
                            if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                packet = bytes(buffer[:self.PACKET_LEN])
                                self.data_queue.put(packet)
                                del buffer[:self.PACKET_LEN]
                            else:
                                del buffer[0]
                        else:
                            del buffer[0]
                else:
                    time.sleep(0.001)
            except Exception as e:
                print("Read error:", e)
                time.sleep(0.1)

    def process_queue(self):
        """Process all queued packets at once."""
        try:
            while True:
                packet = self.data_queue.get_nowait()
                self.parse_and_store_packet(packet)
        except queue.Empty:
            pass

    def parse_and_store_packet(self, packet):
        try:
            # Packet: C7 7C CTR CH0H CH0L CH1H CH1L END
            counter = packet[2]
            # User specified: [3] Ch0_H, [4] Ch0_L -> Big Endian for channels?
            # Or standard Arduino analogRead (usually Sent as H/L). 
            # Previous code used (L << 8) | H which is wrong if [3]=H.
            # Assuming User is correct: [3]=High, [4]=Low.
            ch0_raw = (packet[3] << 8) | packet[4]
            ch1_raw = (packet[5] << 8) | packet[6]
            
            timestamp = datetime.now()
            elapsed = (timestamp - self.session_start_time).total_seconds() if self.session_start_time else 0.0
            data_entry = {
                "timestamp": timestamp.isoformat(),
                "elapsed_time_s": round(elapsed, 6),
                "packet_number": int(self.packet_count),
                "sequence_counter": int(counter),
                "ch0_raw_adc": int(ch0_raw),
                "ch1_raw_adc": int(ch1_raw)
            }
            self.session_data.append(data_entry)
            if self.is_recording:
                self.recorded_data.append(data_entry)
            self.packet_count += 1
            self.graph_buffer_ch0.append(ch0_raw)
            self.graph_buffer_ch1.append(ch1_raw)
            self.graph_time_buffer.append(self.graph_index)
            self.graph_index += 1
            self.latest_packet = data_entry
            self.pending_updates += 1
            
            # Broadcast to WebSocket
            # Format for LiveView: { "source": "EMG", "fs": 512, "timestamp": ts, "window": [ [ch0], [ch1] ] } or similar
            # LiveView expects window to be array of channels, each array of samples.
            # Sending one sample at a time:
            msg = {
                "source": "EMG",
                "fs": self.SAMPLING_RATE,
                "timestamp": int(time.time() * 1000),
                "window": [[ch0_raw], [ch1_raw]] 
            }
            if self.bridge.running:
                self.bridge.broadcast(msg)

        except Exception as e:
            print("Parse error:", e)

    # Main update loop
    def main_update_loop(self):
        """Single unified update loop."""
        try:
            self.process_queue()
            
            current_time = time.time()
            if current_time - self.last_update_time >= self.update_interval or self.pending_updates > 100:
                self.update_latest_packet_display()
                self.update_status_labels()
                self.update_graph_display()
                self.last_update_time = current_time
                self.pending_updates = 0
        except Exception as e:
            print("Update loop error:", e)

        if self.root.winfo_exists():
            self.root.after(30, self.main_update_loop)

    def update_latest_packet_display(self):
        if not self.latest_packet:
            return
        try:
            self.latest_text.configure(state="normal")
            self.latest_text.delete("1.0", "end")
            self.latest_text.insert("1.0", json.dumps(self.latest_packet, indent=2))
            self.latest_text.configure(state="disabled")
        except:
            pass

    # Controls
    def start_acquisition(self):
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Arduino not connected")
            return
        try:
            try:
                self.ser.write(b"START\n")
            except:
                pass
            self.session_data = []
            self.recorded_data = []
            self.packet_count = 0
            self.bytes_received = 0
            self.session_start_time = datetime.now()
            self.graph_buffer_ch0.clear()
            self.graph_buffer_ch1.clear()
            self.graph_time_buffer.clear()
            self.graph_index = 0
            self.acquisition_active = True
            self.is_recording = True
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="normal")
            self.pause_rec_btn.config(state="normal", text="⏸️ Pause Recording")
            self.save_btn.config(state="normal")
            self.export_btn.config(state="normal")
            self.status_label.config(text="✅ Connected", foreground="green")
        except Exception as e:
            messagebox.showerror("Error", f"Start failed: {e}")

    def stop_acquisition(self):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"STOP\n")
            except:
                pass
        self.acquisition_active = False
        self.is_recording = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.pause_rec_btn.config(state="disabled", text="⏸️ Pause Recording")

    def toggle_recording(self):
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.pause_rec_btn.config(text="⏸️ Pause Recording")
        else:
            self.pause_rec_btn.config(text="▶️ Resume Recording")

    def set_sampling_rate(self, rate):
        """Called by children (e.g. filter window) to update rate"""
        print(f"Acquisition: Setting sampling rate to {rate} Hz")
        self.SAMPLING_RATE = float(rate)
        # Update UI
        # self.baud_label.config... (if it existed separately)
        # Re-send start command or specific config command if Arduino supports it
        # For now, we just update the internal variable
        if self.ser and self.ser.is_open:
            try:
                # Example: send "RATE 500\n"
                cmd = f"RATE {int(rate)}\n"
                self.ser.write(cmd.encode())
            except Exception as e:
                print(f"Failed to send rate command: {e}")
        
        # Update integrated filter if open
        if self.filter_window and self.filter_window.winfo_exists():
            self.filter_window.fs = self.SAMPLING_RATE
            self.filter_window.buffer_size = int(self.filter_window.fs * self.filter_window.window_seconds)

    # Status / graph updates
    def update_status_labels(self):
        if self.session_start_time:
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

            if len(self.graph_buffer_ch0):
                ch0 = list(self.graph_buffer_ch0)
                self.ch0_min_label.config(text=f"Min: {min(ch0)}")
                self.ch0_max_label.config(text=f"Max: {max(ch0)}")
                self.ch0_mean_label.config(text=f"Mean: {int(np.mean(ch0))}")
            if len(self.graph_buffer_ch1):
                ch1 = list(self.graph_buffer_ch1)
                self.ch1_min_label.config(text=f"Min: {min(ch1)}")
                self.ch1_max_label.config(text=f"Max: {max(ch1)}")
                self.ch1_mean_label.config(text=f"Mean: {int(np.mean(ch1))}")

    def update_graph_display(self):
        if self.graph_index == 0:
            return
        try:
            x = list(self.graph_time_buffer)
            ch0 = list(self.graph_buffer_ch0)
            ch1 = list(self.graph_buffer_ch1)
            if len(x) > 1:
                self.line_ch0.set_data(x, ch0)
                self.ax_ch0.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                self.line_ch1.set_data(x, ch1)
                self.ax_ch1.set_xlim(max(0, self.graph_index - 1024), max(1024, self.graph_index))
                self.canvas.draw_idle()
        except Exception as e:
            print("Graph error:", e)

    # Save / export
    def choose_save_path(self):
        path = filedialog.askdirectory(title="Select save directory", initialdir=str(self.save_path.parent))
        if path:
            self.save_path = Path(path)
            self.path_label.config(text=str(self.save_path))

    def save_session_data(self):
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            folder = Path(self.save_path)
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"EMG_session_{timestamp}.json"
            filepath = folder / filename
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat() if self.session_start_time else datetime.now().isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0,
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.SAMPLING_RATE,
                    "channels": self.NUM_CHANNELS,
                    "device": "Arduino Uno R4",
                    "sensor_type": "EMG",
                    "channel_0": "Forearm Flexor (A0)",
                    "channel_1": "Forearm Extensor (A1)"
                },
                "data": self.session_data
            }
            with open(filepath, 'w') as f:
                json.dump(metadata, f, indent=2)
            messagebox.showinfo("Saved", f"Saved {len(self.session_data)} packets\nFile: {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")

    def export_graph(self):
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to export")
            return
        try:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            filename = f"EMG_graph_{timestamp}.png"
            filepath = filedialog.asksaveasfilename(defaultextension=".png", initialfile=filename)
            if filepath:
                self.fig.savefig(filepath, dpi=150, bbox_inches='tight')
                messagebox.showinfo("Success", f"Graph exported to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def toggle_server(self):
        # Server is started in __init__ now, but we can toggle broadcasting or just show status
        # For simplicity, we just update the label since it's always running in this new mode
        self.server_label.config(text="Server: ws://localhost:8765 (Active)", foreground="green")
        self.filter_btn.config(state="disabled")

def main():
    root = tk.Tk()
    app = EMGAcquisitionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
