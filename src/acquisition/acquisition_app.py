# src/acquisition/acquisition_app.py
"""
Integrated acquisition_app
- Imports SerialPacketReader, PacketParser, and LSLStreamer from local modules.
- Publishes BioSignals-Raw (raw ADC ints with channel metadata).
- Publishes BioSignals (processed µV floats).
- GUI simplified but functional and integrated.
- Run with: python -m src.acquisition.acquisition_app
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

# local imports (relative)
from .serial_reader import SerialPacketReader
from .packet_parser import PacketParser, Packet
from .lsl_streams import LSLStreamer, LSL_AVAILABLE

# optional scipy dependencies for realtime filtering in GUI
try:
    from scipy.signal import butter, sosfilt, sosfilt_zi, iirnotch, tf2sos
    SCIPY_AVAILABLE = True
except Exception:
    SCIPY_AVAILABLE = False

# ensure utf-8 on some platforms
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


# small helper for ADC->µV conversion (keeps original formula)
def adc_to_uv(adc_value: int, adc_bits: int = 14, vref: float = 3300.0) -> float:
    return ((adc_value / (2 ** adc_bits)) * vref) - (vref / 2.0)


class UnifiedAcquisitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Acquisition - Integrated")
        self.root.geometry("1200x800")

        # config & state
        self.config = {"sampling_rate": 512}
        self.save_path = Path("data/raw/session")
        self.serial_reader: SerialPacketReader = None
        self.packet_parser = PacketParser()
        self.lsl_raw: LSLStreamer = None
        self.lsl_processed: LSLStreamer = None

        # state
        self.is_connected = False
        self.is_acquiring = False
        self.is_recording = False
        self.session_start_time = None
        self.packet_count = 0
        self.last_packet_counter = None

        # channel mapping defaults used in LSL metadata
        self.channel_mapping = {0: "EEG", 1: "EOG"}  # user can change in UI

        # visualization buffers
        self.window_seconds = 4.0
        self.buffer_size = int(self.config.get("sampling_rate", 512) * self.window_seconds)
        self.vis_ch0 = np.zeros(self.buffer_size)
        self.vis_ch1 = np.zeros(self.buffer_size)
        self.vis_ptr = 0
        self.x_axis = np.linspace(0, self.window_seconds, self.buffer_size)

        # filter UI state (lightweight)
        self.filter_enabled_var = tk.BooleanVar(value=False)
        self.bp_low_var = tk.DoubleVar(value=0.5)
        self.bp_high_var = tk.DoubleVar(value=45.0)
        self.notch_freq_var = tk.DoubleVar(value=50.0)
        self.notch_q_var = tk.DoubleVar(value=30.0)
        self.sos = None
        self.zi_ch0 = None
        self.zi_ch1 = None

        # build UI
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # schedule loop
        self.pending_updates = 0
        self.last_update_time = time.time()
        self.update_interval = 0.1
        self.root.after(30, self.main_loop)

    # ---------------- UI ----------------
    def _build_ui(self):
        frame = ttk.Frame(self.root)
        frame.pack(fill="both", expand=True, padx=6, pady=6)

        left = ttk.Frame(frame, width=340)
        left.pack(side="left", fill="y")

        # port selection
        conn = ttk.LabelFrame(left, text="Connection")
        conn.pack(fill="x", pady=4)
        ttk.Label(conn, text="COM Port:").pack(anchor="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn, textvariable=self.port_var, width=30, state="readonly")
        self.port_combo.pack(fill="x", pady=2)
        ttk.Button(conn, text="Refresh", command=self.update_port_list).pack(fill="x", pady=2)

        # mapping controls
        mapf = ttk.LabelFrame(left, text="Channel Mapping")
        mapf.pack(fill="x", pady=4)
        ttk.Label(mapf, text="Channel 0:").pack(anchor="w")
        self.ch0_var = tk.StringVar(value=self.channel_mapping[0])
        ch0_combo = ttk.Combobox(mapf, textvariable=self.ch0_var, values=['EMG', 'EOG', 'EEG'], state="readonly")
        ch0_combo.pack(fill="x", pady=2)
        ttk.Label(mapf, text="Channel 1:").pack(anchor="w")
        self.ch1_var = tk.StringVar(value=self.channel_mapping[1])
        ch1_combo = ttk.Combobox(mapf, textvariable=self.ch1_var, values=['EMG', 'EOG', 'EEG'], state="readonly")
        ch1_combo.pack(fill="x", pady=2)

        # control buttons
        ctrl = ttk.LabelFrame(left, text="Control")
        ctrl.pack(fill="x", pady=4)
        self.connect_btn = ttk.Button(ctrl, text="Connect", command=self.connect_device)
        self.connect_btn.pack(fill="x", pady=2)
        self.disconnect_btn = ttk.Button(ctrl, text="Disconnect", command=self.disconnect_device, state="disabled")
        self.disconnect_btn.pack(fill="x", pady=2)
        self.start_btn = ttk.Button(ctrl, text="Start", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(fill="x", pady=2)
        self.stop_btn = ttk.Button(ctrl, text="Stop", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(fill="x", pady=2)

        # recording & save
        rec = ttk.LabelFrame(left, text="Recording")
        rec.pack(fill="x", pady=4)
        self.rec_btn = ttk.Button(rec, text="Start Recording", command=self.toggle_recording, state="disabled")
        self.rec_btn.pack(fill="x", pady=2)
        savef = ttk.LabelFrame(left, text="Save")
        savef.pack(fill="x", pady=4)
        ttk.Button(savef, text="Choose Path", command=self.choose_save_path).pack(fill="x", pady=2)
        self.path_label = ttk.Label(savef, text=str(self.save_path))
        self.path_label.pack(fill="x", pady=2)
        self.save_btn = ttk.Button(savef, text="Save Session", command=self.save_session, state="disabled")
        self.save_btn.pack(fill="x", pady=2)

        # status
        status = ttk.LabelFrame(left, text="Status")
        status.pack(fill="x", pady=4)
        ttk.Label(status, text="Connection:").pack(anchor="w")
        self.status_label = ttk.Label(status, text="Disconnected", foreground="red")
        self.status_label.pack(anchor="w")
        ttk.Label(status, text="Packets:").pack(anchor="w")
        self.packet_label = ttk.Label(status, text="0")
        self.packet_label.pack(anchor="w")

        # right side: simple plot area
        right = ttk.Frame(frame)
        right.pack(side="right", fill="both", expand=True)
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        fig = Figure(figsize=(8, 6), dpi=100)
        self.ax0 = fig.add_subplot(211)
        self.line0, = self.ax0.plot(self.x_axis, self.vis_ch0)
        self.ax1 = fig.add_subplot(212)
        self.line1, = self.ax1.plot(self.x_axis, self.vis_ch1)
        fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(fig, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------------- port utils ----------------
    def update_port_list(self):
        import serial.tools.list_ports
        ports = []
        for p, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{p} - {desc}")
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)

    # ---------------- device lifecycle ----------------
    def connect_device(self):
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        port = self.port_var.get().split(" ")[0]
        # instantiate SerialPacketReader
        self.serial_reader = SerialPacketReader(port=port)
        ok = self.serial_reader.connect()
        if not ok:
            messagebox.showerror("Error", f"Connection to {port} failed")
            return
        self.serial_reader.start()
        self.is_connected = True
        self.status_label.config(text="Connected", foreground="green")
        self.connect_btn.config(state="disabled")
        self.disconnect_btn.config(state="normal")
        self.start_btn.config(state="normal")
        # create LSL outlets (raw + processed) if pylsl available
        ch_types = [self.ch0_var.get(), self.ch1_var.get()]
        ch_labels = [f"{ch_types[0]}_0", f"{ch_types[1]}_1"]
        if LSL_AVAILABLE:
            self.lsl_raw = LSLStreamer("BioSignals-Raw", channel_types=ch_types, channel_labels=ch_labels, channel_count=2, nominal_srate=float(self.config.get("sampling_rate", 512)))
            self.lsl_processed = LSLStreamer("BioSignals", channel_types=ch_types, channel_labels=ch_labels, channel_count=2, nominal_srate=float(self.config.get("sampling_rate", 512)))
        messagebox.showinfo("Connected", f"Connected to {port}")

    def disconnect_device(self):
        if self.is_acquiring:
            self.stop_acquisition()
        self.is_connected = False
        if self.serial_reader:
            self.serial_reader.disconnect()
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Disconnected", foreground="red")

    def start_acquisition(self):
        if not (self.serial_reader and self.is_connected):
            messagebox.showerror("Error", "Device not connected")
            return
        # try send start
        self.serial_reader.send_command("START")
        self.is_acquiring = True
        self.is_recording = True
        self.session_start_time = datetime.now()
        self.packet_count = 0
        self.session_data = []
        self.last_packet_counter = None
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.rec_btn.config(state="normal")
        self.save_btn.config(state="normal")
        # reset vis buffers
        self.vis_ch0.fill(0)
        self.vis_ch1.fill(0)
        self.vis_ptr = 0

    def stop_acquisition(self):
        try:
            if self.serial_reader:
                self.serial_reader.send_command("STOP")
        except Exception:
            pass
        self.is_acquiring = False
        self.is_recording = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.rec_btn.config(state="disabled")

    def toggle_recording(self):
        if not self.is_acquiring:
            messagebox.showerror("Error", "Start acquisition first")
            return
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.rec_btn.config(text="Stop Recording")
        else:
            self.rec_btn.config(text="Start Recording")

    def choose_save_path(self):
        p = filedialog.askdirectory(title="Select save directory", initialdir=str(self.save_path))
        if p:
            self.save_path = Path(p)
            self.path_label.config(text=str(self.save_path))

    def save_session(self):
        if not hasattr(self, "session_data") or not self.session_data:
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
        with open(filepath, "w") as f:
            json.dump(metadata, f, indent=2)
        messagebox.showinfo("Saved", f"Saved {len(self.session_data)} packets to {filepath}")

    # ---------------- main loop ----------------
    def main_loop(self):
        try:
            if self.is_acquiring and self.serial_reader:
                # drain queued packets
                while True:
                    pkt_bytes = self.serial_reader.get_packet(timeout=0.001)
                    if pkt_bytes is None:
                        break
                    try:
                        pkt = self.packet_parser.parse(pkt_bytes)
                    except Exception as e:
                        print(f"[Acq] parse error: {e}")
                        continue
                    # duplicate suppression (simple)
                    if self.last_packet_counter is not None and pkt.counter == self.last_packet_counter:
                        # increment duplicate stat
                        self.serial_reader.duplicates += 1
                        continue
                    self.last_packet_counter = pkt.counter

                    # convert ADC->µV
                    ch0_uv = adc_to_uv(pkt.ch0_raw)
                    ch1_uv = adc_to_uv(pkt.ch1_raw)

                    # apply GUI-side filter if enabled (lightweight)
                    if SCIPY_AVAILABLE and self.filter_enabled_var.get():
                        if self.sos is None:
                            # design simple bandpass from UI values
                            fs = float(self.config.get("sampling_rate", 512))
                            nyq = 0.5 * fs
                            low = max(0.001, float(self.bp_low_var.get()))
                            high = min(nyq - 0.1, float(self.bp_high_var.get()))
                            try:
                                self.sos = butter(4, [low/nyq, high/nyq], btype="bandpass", output="sos")
                                self.zi_ch0 = sosfilt_zi(self.sos) * 0.0
                                self.zi_ch1 = sosfilt_zi(self.sos) * 0.0
                            except Exception:
                                self.sos = None
                        if self.sos is not None:
                            try:
                                y0, z0 = sosfilt(self.sos, [ch0_uv], zi=self.zi_ch0)
                                y1, z1 = sosfilt(self.sos, [ch1_uv], zi=self.zi_ch1)
                                ch0_uv = float(y0[0]); self.zi_ch0 = z0
                                ch1_uv = float(y1[0]); self.zi_ch1 = z1
                            except Exception as e:
                                print("[Acq] GUI filter error:", e)

                    # push LSL raw as ADC ints
                    if LSL_AVAILABLE and self.lsl_raw:
                        try:
                            self.lsl_raw.push_sample([float(pkt.ch0_raw), float(pkt.ch1_raw)], None)
                        except Exception as e:
                            print("[Acq] LSL raw push error:", e)

                    # push processed µV stream
                    if LSL_AVAILABLE and self.lsl_processed:
                        try:
                            self.lsl_processed.push_sample([float(ch0_uv), float(ch1_uv)], None)
                        except Exception as e:
                            print("[Acq] LSL processed push error:", e)

                    # update vis buffer
                    self.vis_ch0[self.vis_ptr] = ch0_uv
                    self.vis_ch1[self.vis_ptr] = ch1_uv
                    self.vis_ptr = (self.vis_ptr + 1) % self.buffer_size

                    # record
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
                    if self.is_recording:
                        if not hasattr(self, "session_data"):
                            self.session_data = []
                        self.session_data.append(entry)

                    self.packet_count += 1
                    self.pending_updates += 1

            # UI updates
            now = time.time()
            if (now - self.last_update_time >= self.update_interval) and self.pending_updates > 0:
                # update labels and plot
                self.packet_label.config(text=str(self.packet_count))
                # update plot lines
                try:
                    self.line0.set_ydata(self.vis_ch0)
                    self.line1.set_ydata(self.vis_ch1)
                    self.canvas.draw_idle()
                except Exception:
                    pass
                self.pending_updates = 0
                self.last_update_time = now

        except Exception as e:
            print("[Acq] main_loop error:", e)

        if self.root.winfo_exists():
            self.root.after(30, self.main_loop)

    def on_closing(self):
        try:
            if self.is_acquiring:
                self.stop_acquisition()
            if self.serial_reader:
                self.serial_reader.disconnect()
        finally:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = UnifiedAcquisitionApp(root)
    app.update_port_list()
    root.mainloop()


if __name__ == "__main__":
    main()
