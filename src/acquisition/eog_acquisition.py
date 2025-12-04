"""
EOG Signal Acquisition Application - IMPROVED WITH DEBUG MODE
Connects to Arduino Uno R4 @ 230400 baud, 512 Hz sampling
2-Channel EOG data with correct 10-byte packet format
NOW WITH BETTER DEBUGGING AND START/STOP COMMANDS
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


class EOGAcquisitionApp:
    """Main application for EOG signal acquisition"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Signal Acquisition - Arduino Uno R4 (2-Channel)")
        self.root.geometry("1200x850")
        self.root.configure(bg='#f0f0f0')
        
        # Serial connection
        self.ser = None
        self.acquisition_active = False
        self.acquisition_thread = None
        self.debug_mode = tk.BooleanVar(value=True)
        
        # Data storage
        self.session_data = []
        self.session_start_time = None
        self.packet_count = 0
        self.last_debug_update = 0
        
        # Packet format constants
        self.PACKET_LEN = 8
        self.SYNC_BYTE_1 = 0xC7
        self.SYNC_BYTE_2 = 0x7C
        self.END_BYTE = 0x01
        self.SAMPLING_RATE = 512.0
        self.BAUD_RATE = 230400
        
        # Setup UI
        self.setup_ui()
        self.update_port_list()
        
    def setup_ui(self):
        """Create the user interface"""
        
        # Main frame with two columns
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # LEFT COLUMN: Controls
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # RIGHT COLUMN: Debug output
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=5)
        
        # ===== LEFT COLUMN: CONNECTION & CONTROL =====
        
        # Connection frame
        connection_frame = ttk.LabelFrame(left_frame, text="Connection Settings", padding="10")
        connection_frame.pack(fill="x", padx=0, pady=10)
        
        ttk.Label(connection_frame, text="COM Port:").grid(row=0, column=0, sticky="w", padx=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(connection_frame, textvariable=self.port_var, width=20, state="readonly")
        self.port_combo.grid(row=0, column=1, sticky="ew", padx=5)
        
        self.refresh_btn = ttk.Button(connection_frame, text="🔄 Refresh", command=self.update_port_list)
        self.refresh_btn.grid(row=0, column=2, padx=5)
        
        ttk.Label(connection_frame, text="Baud:").grid(row=1, column=0, sticky="w", padx=5)
        ttk.Label(connection_frame, text="230400 (Fixed)").grid(row=1, column=1, sticky="w", padx=5)
        
        connection_frame.columnconfigure(1, weight=1)
        
        # Status frame
        status_frame = ttk.LabelFrame(left_frame, text="Status", padding="10")
        status_frame.pack(fill="x", padx=0, pady=10)
        
        ttk.Label(status_frame, text="Connection:").grid(row=0, column=0, sticky="w", padx=5)
        self.status_label = ttk.Label(status_frame, text="❌ Disconnected", foreground="red", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=1, sticky="w", padx=5)
        
        ttk.Label(status_frame, text="Device:").grid(row=1, column=0, sticky="w", padx=5)
        self.device_label = ttk.Label(status_frame, text="Not Connected", font=("Arial", 9))
        self.device_label.grid(row=1, column=1, sticky="w", padx=5)
        
        ttk.Label(status_frame, text="Packets:").grid(row=2, column=0, sticky="w", padx=5)
        self.packet_label = ttk.Label(status_frame, text="0", font=("Arial", 9, "bold"))
        self.packet_label.grid(row=2, column=1, sticky="w", padx=5)
        
        ttk.Label(status_frame, text="Signal:").grid(row=3, column=0, sticky="w", padx=5)
        self.signal_label = ttk.Label(status_frame, text="Waiting...", font=("Arial", 9))
        self.signal_label.grid(row=3, column=1, sticky="w", padx=5)
        
        status_frame.columnconfigure(1, weight=1)
        
        # Control buttons
        control_frame = ttk.LabelFrame(left_frame, text="Acquisition Control", padding="10")
        control_frame.pack(fill="x", padx=0, pady=10)
        
        self.connect_btn = ttk.Button(control_frame, text="🔌 Connect", command=self.connect_arduino)
        self.connect_btn.pack(side="left", padx=5, pady=5)
        
        self.disconnect_btn = ttk.Button(control_frame, text="🔌 Disconnect", command=self.disconnect_arduino, state="disabled")
        self.disconnect_btn.pack(side="left", padx=5, pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="▶ Start", command=self.start_acquisition, state="disabled")
        self.start_btn.pack(side="left", padx=5, pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ Stop", command=self.stop_acquisition, state="disabled")
        self.stop_btn.pack(side="left", padx=5, pady=5)
        
        self.save_btn = ttk.Button(control_frame, text="💾 Save", command=self.save_session_data, state="disabled")
        self.save_btn.pack(side="left", padx=5, pady=5)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(left_frame, text="Latest Packets", padding="10")
        stats_frame.pack(fill="both", expand=True, padx=0, pady=10)
        
        self.stats_text = tk.Text(stats_frame, height=20, width=60, bg='#ffffff', font=("Courier", 8))
        self.stats_text.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=self.stats_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.stats_text.config(yscrollcommand=scrollbar.set)
        
        self.update_stats_display()
        
        # ===== RIGHT COLUMN: DEBUG OUTPUT =====
        
        # Debug control frame
        debug_ctrl_frame = ttk.LabelFrame(right_frame, text="Debug Options", padding="10")
        debug_ctrl_frame.pack(fill="x", padx=0, pady=10)
        
        ttk.Checkbutton(debug_ctrl_frame, text="Show Debug Output", variable=self.debug_mode).pack(anchor="w")
        
        clear_btn = ttk.Button(debug_ctrl_frame, text="Clear Debug", command=self.clear_debug)
        clear_btn.pack(side="left", padx=5)
        
        # Debug output frame
        debug_frame = ttk.LabelFrame(right_frame, text="Debug Console", padding="10")
        debug_frame.pack(fill="both", expand=True, padx=0, pady=10)
        
        self.debug_text = scrolledtext.ScrolledText(debug_frame, height=40, width=40, bg='#000000', fg='#00FF00', font=("Courier", 8))
        self.debug_text.pack(fill="both", expand=True)
        
        self.debug_log("EOG Acquisition v2 - Debug Ready ✓")
        self.debug_log("=" * 40)
        
    def debug_log(self, message):
        """Log debug message"""
        if not self.debug_mode.get():
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.debug_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.debug_text.see(tk.END)
        self.debug_text.update()
        
        # Limit size
        if int(self.debug_text.index('end-1c').split('.')[0]) > 500:
            self.debug_text.delete('1.0', '50.0')
    
    def clear_debug(self):
        """Clear debug output"""
        self.debug_text.delete('1.0', tk.END)
        self.debug_log("Debug cleared")
    
    def update_port_list(self):
        """Refresh the list of available COM ports"""
        ports = []
        for port, desc, hwid in serial.tools.list_ports.comports():
            ports.append(f"{port} - {desc}")
        
        self.port_combo['values'] = ports if ports else ["No ports found"]
        if ports:
            self.port_combo.current(0)
            self.debug_log(f"Found {len(ports)} COM port(s)")
    
    def connect_arduino(self):
        """Establish connection to Arduino"""
        if not self.port_var.get():
            messagebox.showerror("Error", "Select a COM port")
            return
        
        port_name = self.port_var.get().split(" ")[0]
        
        try:
            self.debug_log(f"Connecting to {port_name}...")
            self.ser = serial.Serial(port_name, self.BAUD_RATE, timeout=1)
            self.debug_log("Serial port opened")
            
            time.sleep(2)  # Arduino init time
            self.debug_log("Arduino initialized")
            
            # Clear buffer
            self.ser.reset_input_buffer()
            self.debug_log("Input buffer cleared")
            
            self.device_label.config(text="Arduino Uno R4 (2-Channel)")
            self.status_label.config(text="✅ Connected", foreground="green")
            
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.start_btn.config(state="normal")
            
            self.debug_log("✅ Connection successful")
            messagebox.showinfo("Success", f"Connected to {port_name}")
            
        except Exception as e:
            self.debug_log(f"❌ Connection failed: {e}")
            messagebox.showerror("Error", f"Connection failed: {e}")
            self.status_label.config(text="❌ Failed", foreground="red")
    
    def disconnect_arduino(self):
        """Close connection"""
        if self.acquisition_active:
            self.stop_acquisition()
        
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.debug_log("Disconnected from Arduino")
        
        self.status_label.config(text="❌ Disconnected", foreground="red")
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.device_label.config(text="Not Connected")
    
    def start_acquisition(self):
        """Start acquisition"""
        if not self.ser or not self.ser.is_open:
            messagebox.showerror("Error", "Arduino not connected")
            return
        
        self.debug_log("\n=== Starting Acquisition ===")
        
        # Reset data
        self.session_data = []
        self.packet_count = 0
        self.session_start_time = datetime.now()
        
        # Clear buffer
        self.ser.reset_input_buffer()
        self.debug_log("Buffer cleared, ready for data")
        
        self.acquisition_active = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.save_btn.config(state="disabled")
        
        self.acquisition_thread = threading.Thread(target=self.acquisition_loop, daemon=True)
        self.acquisition_thread.start()
        self.debug_log("Acquisition thread started")
    
    def acquisition_loop(self):
        """Read and parse packets"""
        buffer = bytearray()
        packets_since_update = 0
        bytes_read = 0
        debug_count = 0
        
        self.debug_log("Beginning to read from serial port...")
        
        while self.acquisition_active and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    byte = self.ser.read(1)
                    if byte:
                        buffer.extend(byte)
                        bytes_read += 1
                        debug_count += 1
                        
                        # Debug first 50 bytes
                        if debug_count <= 50:
                            self.debug_log(f"Byte {debug_count}: {byte.hex().upper()}", )
                        
                        # Check for complete packet
                        if len(buffer) >= self.PACKET_LEN:
                            if buffer[0] == self.SYNC_BYTE_1 and buffer[1] == self.SYNC_BYTE_2:
                                if buffer[self.PACKET_LEN - 1] == self.END_BYTE:
                                    # Valid packet
                                    self.parse_and_store_packet(buffer[:self.PACKET_LEN])
                                    packets_since_update += 1
                                    
                                    if packets_since_update >= 100:
                                        self.root.after(0, self.update_stats_display)
                                        packets_since_update = 0
                                    
                                    buffer = buffer[self.PACKET_LEN:]
                                else:
                                    buffer = buffer[1:]
                                    if debug_count <= 50:
                                        self.debug_log(f"  ^ Bad end byte (expected 0x01)")
                            else:
                                buffer = buffer[1:]
                else:
                    time.sleep(0.001)
                    
            except Exception as e:
                self.debug_log(f"❌ Error: {e}")
                break
        
        self.debug_log(f"Acquisition stopped. Total bytes read: {bytes_read}")
    
    def parse_and_store_packet(self, packet):
        """Parse 10-byte packet"""
        try:
            counter = packet[2]
            ch0_raw = (packet[3] << 8) | packet[4]
            ch1_raw = (packet[5] << 8) | packet[6]
            
            ch0_voltage = (ch0_raw / 16384.0) * 5.0 * 1e6
            ch1_voltage = (ch1_raw / 16384.0) * 5.0 * 1e6
            
            timestamp = datetime.now()
            elapsed_time = (timestamp - self.session_start_time).total_seconds()
            
            data_entry = {
                "timestamp": timestamp.isoformat(),
                "elapsed_time_s": round(elapsed_time, 6),
                "packet_number": self.packet_count,
                "sequence_counter": counter,
                "ch0_raw_adc": ch0_raw,
                "ch1_raw_adc": ch1_raw,
                "ch0_voltage_uv": round(ch0_voltage, 2),
                "ch1_voltage_uv": round(ch1_voltage, 2),
            }
            
            self.session_data.append(data_entry)
            self.packet_count += 1
            
            # Update packet label
            self.root.after(0, lambda: self.packet_label.config(text=str(self.packet_count)))
            
        except Exception as e:
            self.debug_log(f"Parse error: {e}")
    
    def stop_acquisition(self):
        """Stop acquisition"""
        self.acquisition_active = False
        time.sleep(0.5)
        
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.save_btn.config(state="normal")
        
        self.debug_log(f"=== Stopped: {self.packet_count} packets captured ===\n")
        self.update_stats_display()
    
    def update_stats_display(self):
        """Update statistics"""
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", tk.END)
        
        text = "ACQUISITION STATISTICS\n"
        text += "="*50 + "\n\n"
        
        if self.session_start_time:
            elapsed = (datetime.now() - self.session_start_time).total_seconds()
            text += f"Duration: {elapsed:.2f} sec\n"
        
        text += f"Packets: {self.packet_count}\n"
        text += f"Data points: {len(self.session_data)}\n"
        
        if self.packet_count > 0 and self.session_start_time:
            duration = (datetime.now() - self.session_start_time).total_seconds()
            rate = self.packet_count / duration if duration > 0 else 0
            text += f"Rate: {rate:.1f} Hz (target: 512)\n"
        
        text += "\n" + "="*50 + "\n"
        text += "LATEST 10 PACKETS:\n"
        text += "="*50 + "\n"
        text += f"{'#':<5} {'Ctr':<4} {'Ch0':<10} {'Ch1':<10}\n"
        text += "-"*50 + "\n"
        
        for entry in self.session_data[-10:]:
            pkt_num = entry['packet_number']
            ctr = entry['sequence_counter']
            ch0 = entry['ch0_voltage_uv']
            ch1 = entry['ch1_voltage_uv']
            text += f"{pkt_num:<5} {ctr:<4} {ch0:<10.0f} {ch1:<10.0f}\n"
        
        text += "\n" + "="*50 + "\n"
        text += "CHANNEL STATISTICS:\n"
        text += "="*50 + "\n"
        
        if len(self.session_data) > 0:
            ch0_vals = [e['ch0_voltage_uv'] for e in self.session_data]
            ch1_vals = [e['ch1_voltage_uv'] for e in self.session_data]
            
            text += f"Ch0 Min: {min(ch0_vals):.0f} µV\n"
            text += f"Ch0 Max: {max(ch0_vals):.0f} µV\n"
            text += f"Ch0 Mean: {sum(ch0_vals)/len(ch0_vals):.0f} µV\n\n"
            
            text += f"Ch1 Min: {min(ch1_vals):.0f} µV\n"
            text += f"Ch1 Max: {max(ch1_vals):.0f} µV\n"
            text += f"Ch1 Mean: {sum(ch1_vals)/len(ch1_vals):.0f} µV\n"
        
        self.stats_text.insert("1.0", text)
        self.stats_text.config(state="disabled")
    
    def save_session_data(self):
        """Save to JSON"""
        if not self.session_data:
            messagebox.showwarning("Empty", "No data to save")
            return
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir = Path("data/sessions")
            out_dir.mkdir(parents=True, exist_ok=True)
            
            filename = out_dir / f"eog_session_{timestamp}.json"
            
            metadata = {
                "session_info": {
                    "timestamp": self.session_start_time.isoformat(),
                    "duration_seconds": (datetime.now() - self.session_start_time).total_seconds(),
                    "total_packets": self.packet_count,
                    "sampling_rate_hz": self.SAMPLING_RATE,
                    "channels": 2,
                    "device": "Arduino Uno R4"
                },
                "data": self.session_data
            }
            
            with open(filename, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.debug_log(f"✅ Saved to {filename}")
            messagebox.showinfo("Success", f"Saved {len(self.session_data)} packets")
            
        except Exception as e:
            self.debug_log(f"❌ Save failed: {e}")
            messagebox.showerror("Error", f"Save failed: {e}")


def main():
    root = tk.Tk()
    app = EOGAcquisitionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
