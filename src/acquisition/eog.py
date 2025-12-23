"""
EOG Acquisition App
Merged/extended from user's eog_unified.py with the common UI upgrades:
 - Scrollable left control panel (same roomy layout as EEG)
 - Latest packet panel
 - Auto-start recording + Pause/Resume recording
 - Save naming: data/raw/session/eog/EOG_session_dd-mm-YYYY_HH-MM-SS.json
 - NOTE: No filter features included (as requested)
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

class EOGAcquisitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Signal Acquisition - v5.0")
        self.root.geometry("1600x950")
        self.root.configure(bg='#f0f0f0')

        # Packet config (same)
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = 512.0
        self.BAUD_RATE = 230400
        self.NUM_CHANNELS = 2

        # state/data
        self.ser = None
        self.acquisition_active = False
        self.acquisition_thread = None
        self.session_data = []
        self.recorded_data = []
        self.session_start_time = None
        self.packet_count = 0
        self.bytes_received = 0
        self.graph_buffer_ch0 = deque(maxlen=1024)
        self.graph_buffer_ch1 = deque(maxlen=1024)
        self.graph_time_buffer = deque(maxlen=1024)
        self.graph_index = 0
        self.last_graph_update_index = 0
        self.save_path = Path("data/raw/session/eog")
        self.latest_packet = {}
        self.is_recording = False

        self.setup_ui()
        self.update_port_list()
        self.root.after(30, self.update_graph_display)

    def make_scrollable_left_panel(self, parent):
        container = ttk.Frame(parent)
        container.pack(side="left", fill="y", expand=False, padx=5, pady=5)
        canvas = tk.Canvas(container, width=320, highlightthickness=0)
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
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial",10,"bold"))
        self.packet_label.pack(anchor="w", padx=5)
        ttk.Label(status_frame, text="Duration:").pack(anchor="w", padx=5)
        self.duration_label = ttk.Label(status_frame, text="00:00:00", font=("Arial",10,"bold"))
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
        ttk.Label(rec_frame, text="Recording starts automatically with acquisition").pack(anchor="w", padx=5, pady=4)

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
        ttk.Label(stats_frame, text="Channel 0 (Vertical):").pack(anchor="w", padx=5)
        self.ch0_min_label = ttk.Label(stats_frame, text="Min: 0")
        self.ch0_min_label.pack(anchor="w", padx=10)
        self.ch0_max_label = ttk.Label(stats_frame, text="Max: 0")
        self.ch0_max_label.pack(anchor="w", padx=10)
        self.ch0_mean_label = ttk.Label(stats_frame, text="Mean: 0")
        self.ch0_mean_label.pack(anchor="w", padx=10, pady=4)
        ttk.Label(stats_frame, text="Channel 1 (Horizontal):").pack(anchor="w", padx=5)
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
        graph_frame = ttk.LabelFrame(right_frame, text="📡 Real-Time EOG Signal (512 Hz)", padding=5)
        graph_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.fig = Figure(figsize=(10,6), dpi=100)
        self.fig.patch.set_facecolor('#f0f0f0')
        self.ax_ch0 = self.fig.add_subplot(211)
        self.line_ch0, = self.ax_ch0.plot([], [], linewidth=1.2, label='Ch0 (Vertical)')
        self.ax_ch0.set_ylabel('Voltage (µV)')
        self.ax_ch0.set_ylim(-100000, 100000)
        self.ax_ch0.grid(True, alpha=0.3)
        self.ax_ch1 = self.fig.add_subplot(212)
        self.line_ch1, = self.ax_ch1.plot([], [], linewidth=1.2, label='Ch1 (Horizontal)')
        self.ax_ch1.set_ylabel('Voltage (µV)')
        self.ax_ch1.set_xlabel('Samples')
        self.ax_ch1.set_ylim(-100000, 100000)
        self.ax_ch1.grid(True, alpha=0.3)
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # Serial read / parse
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
            self.read_thread = threading.Thread(target=self.acquisition_loop, daemon=True)
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

    def acquisition_loop(self):
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
                                self.root.after(0, self.parse_and_store_packet, packet)
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

    def parse_and_store_packet(self, packet):
        try:
            counter = packet[2]
            ch0_raw = (packet[4] << 8) | packet[3]
            ch1_raw = (packet[6] << 8) | packet[5]
            # convert to microvolts using original formula
            ch0_uv = (ch0_raw / 16384.0) * 5.0 * 1e6
            ch1_uv = (ch1_raw / 16384.0) * 5.0 * 1e6
            timestamp = datetime.now()
            elapsed = (timestamp - self.session_start_time).total_seconds() if self.session_start_time else 0.0
            data_entry = {
                "timestamp": timestamp.isoformat(),
                "elapsed_time_s": round(elapsed, 6),
                "packet_number": int(self.packet_count),
                "sequence_counter": int(counter),
                "ch0_adc": int(ch0_raw),
                "ch1_adc": int(ch1_raw),
                "ch0_uv": float(ch0_uv),
                "ch1_uv": float(ch1_uv)
            }
            self.session_data.append(data_entry)
            if self.is_recording:
                self.recorded_data.append(data_entry)
            self.packet_count += 1
            self.graph_buffer_ch0.append(ch0_uv)
            self.graph_buffer_ch1.append(ch1_uv)
            self.graph_time_buffer.append(self.graph_index)
            self.graph_index += 1
            self.latest_packet = data_entry
            self.latest_text.configure(state="normal")
            self.latest_text.delete("1.0", "end")
            self.latest_text.insert("1.0", json.dumps(self.latest_packet, indent=2))
            self.latest_text.configure(state="disabled")
            if self.packet_count % 50 == 0:
                self.update_status_labels()
        except Exception as e:
            print("Parse error:", e)

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
            self.is_recording = True  # start recording automatically
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

    # Status / graph
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
                self.ch0_min_label.config(text=f"Min: {min(ch0):.0f}")
                self.ch0_max_label.config(text=f"Max: {max(ch0):.0f}")
                self.ch0_mean_label.config(text=f"Mean: {np.mean(ch0):.0f}")
            if len(self.graph_buffer_ch1):
                ch1 = list(self.graph_buffer_ch1)
                self.ch1_min_label.config(text=f"Min: {min(ch1):.0f}")
                self.ch1_max_label.config(text=f"Max: {max(ch1):.0f}")
                self.ch1_mean_label.config(text=f"Mean: {np.mean(ch1):.0f}")

    def update_graph_display(self):
        if self.graph_index == self.last_graph_update_index:
            if self.root.winfo_exists():
                self.root.after(30, self.update_graph_display)
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
                self.last_graph_update_index = self.graph_index
        except Exception as e:
            print("Graph error:", e)
        if self.root.winfo_exists():
            self.root.after(30, self.update_graph_display)

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
            filename = f"EOG_session_{timestamp}.json"
            filepath = folder / filename
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat() if self.session_start_time else datetime.now().isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0,
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.SAMPLING_RATE,
                    "channels": self.NUM_CHANNELS,
                    "device": "Arduino Uno R4",
                    "sensor_type": "EOG",
                    "channel_0": "Vertical Eye Movement",
                    "channel_1": "Horizontal Eye Movement"
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
