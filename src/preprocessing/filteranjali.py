import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import requests
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from scipy.signal import butter, lfilter, iirnotch

# ==========================================
# SIGNAL PROCESSING LOGIC
# ==========================================

class SignalProcessor:
    @staticmethod
    def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
        if lowcut <= 0: lowcut = 0.01
        if highcut >= fs/2: highcut = (fs/2) - 1
        
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        y = lfilter(b, a, data)
        return y

    @staticmethod
    def notch_filter(data, notch_freq, quality_factor, fs):
        if notch_freq <= 0 or notch_freq >= fs/2:
            return data # Return raw if frequency is invalid
            
        nyq = 0.5 * fs
        freq = notch_freq / nyq
        b, a = iirnotch(freq, quality_factor)
        y = lfilter(b, a, data)
        return y

# ==========================================
# MAIN GUI APPLICATION
# ==========================================

class EOGAnalysisApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Signal Analyzer & Filter Tuner")
        self.root.geometry("1400x900")
        
        # Data Containers
        self.raw_data_ch0 = np.array([])
        self.raw_data_ch1 = np.array([])
        self.time_axis = np.array([])
        self.fs = 512.0  # Your specific sampling rate
        
        # UI Setup
        self.create_control_panel()
        self.create_plot_area()
        
        # Initial Status
        self.status_var.set("Ready. Load a JSON file or URL to begin.")

    def create_control_panel(self):
        # Top Frame: Data Loading
        load_frame = ttk.LabelFrame(self.root, text="Data Source", padding=10)
        load_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(load_frame, text="📂 Open JSON File", command=self.load_from_file).pack(side="left", padx=5)
        
        ttk.Label(load_frame, text="OR Load URL:").pack(side="left", padx=10)
        self.url_entry = ttk.Entry(load_frame, width=50)
        self.url_entry.pack(side="left", padx=5)
        ttk.Button(load_frame, text="⬇ Fetch URL", command=self.load_from_url).pack(side="left", padx=5)
        
        self.status_var = tk.StringVar()
        ttk.Label(load_frame, textvariable=self.status_var, foreground="blue").pack(side="right", padx=10)

        # Middle Frame: Filter Controls
        filter_frame = ttk.LabelFrame(self.root, text="Filter Settings (Real-time)", padding=10)
        filter_frame.pack(fill="x", padx=10, pady=5)
        
        # Grid layout for sliders
        # --- Bandpass Low Cut ---
        ttk.Label(filter_frame, text="Bandpass Low (Hz):").grid(row=0, column=0, sticky="w")
        self.bp_low_var = tk.DoubleVar(value=0.5)
        self.sl_low = ttk.Scale(filter_frame, from_=0.1, to=10.0, variable=self.bp_low_var, command=self.update_plot_event)
        self.sl_low.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(filter_frame, textvariable=self.bp_low_var).grid(row=0, column=2, padx=5)

        # --- Bandpass High Cut ---
        ttk.Label(filter_frame, text="Bandpass High (Hz):").grid(row=0, column=3, sticky="w", padx=10)
        self.bp_high_var = tk.DoubleVar(value=30.0)
        self.sl_high = ttk.Scale(filter_frame, from_=10.0, to=100.0, variable=self.bp_high_var, command=self.update_plot_event)
        self.sl_high.grid(row=0, column=4, sticky="ew", padx=5)
        ttk.Label(filter_frame, textvariable=self.bp_high_var).grid(row=0, column=5, padx=5)

        # --- Notch Frequency ---
        ttk.Label(filter_frame, text="Notch Freq (Hz):").grid(row=0, column=6, sticky="w", padx=10)
        self.notch_freq_var = tk.DoubleVar(value=50.0)
        self.sl_notch = ttk.Scale(filter_frame, from_=40.0, to=65.0, variable=self.notch_freq_var, command=self.update_plot_event)
        self.sl_notch.grid(row=0, column=7, sticky="ew", padx=5)
        ttk.Label(filter_frame, textvariable=self.notch_freq_var).grid(row=0, column=8, padx=5)

        filter_frame.columnconfigure(1, weight=1)
        filter_frame.columnconfigure(4, weight=1)
        filter_frame.columnconfigure(7, weight=1)

    def create_plot_area(self):
        # Matplotlib Figure
        self.fig, (self.ax0, self.ax1) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        self.fig.subplots_adjust(hspace=0.3)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        
        self.ax0.set_title("Channel 0 (Horizontal)")
        self.ax1.set_title("Channel 1 (Vertical)")
        self.ax1.set_xlabel("Time (seconds)")

    # ==========================================
    # DATA LOADING
    # ==========================================

    def load_from_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if path:
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                self.parse_json_data(data)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")

    def load_from_url(self):
        url = self.url_entry.get()
        if not url: return
        try:
            self.status_var.set("Downloading...")
            self.root.update()
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            self.parse_json_data(data)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download: {str(e)}")
            self.status_var.set("Download failed.")

    def parse_json_data(self, json_obj):
        # Handles the structure: { "data": [ { "ch0_voltage_uv": 123, ... }, ... ] }
        try:
            if "data" not in json_obj:
                raise ValueError("JSON missing 'data' key")
            
            raw_list = json_obj["data"]
            
            ch0 = []
            ch1 = []
            
            for pkt in raw_list:
                # Try to get voltage first (preferred)
                if "ch0_voltage_uv" in pkt:
                    ch0.append(pkt["ch0_voltage_uv"])
                    ch1.append(pkt["ch1_voltage_uv"])
                # Fallback to raw ADC if voltage not calculated
                elif "ch0_raw_adc" in pkt:
                    # Convert ADC (0-16383) to Voltage (µV) based on 5V ref
                    v0 = (pkt["ch0_raw_adc"] / 16384.0) * 5.0 * 1e6
                    v1 = (pkt["ch1_raw_adc"] / 16384.0) * 5.0 * 1e6
                    ch0.append(v0)
                    ch1.append(v1)

            self.raw_data_ch0 = np.array(ch0)
            self.raw_data_ch1 = np.array(ch1)
            
            # Create time axis
            duration = len(ch0) / self.fs
            self.time_axis = np.linspace(0, duration, len(ch0))
            
            self.status_var.set(f"Loaded {len(ch0)} samples. Duration: {duration:.2f}s")
            self.update_plot()
            
        except Exception as e:
            messagebox.showerror("Data Error", f"Could not parse JSON structure: {e}")

    # ==========================================
    # PLOTTING & UPDATING
    # ==========================================

    def update_plot_event(self, _=None):
        # Wrapper for slider events
        self.update_plot()

    def update_plot(self):
        if len(self.raw_data_ch0) == 0:
            return

        # 1. Get current settings from sliders
        low = self.bp_low_var.get()
        high = self.bp_high_var.get()
        notch = self.notch_freq_var.get()

        # 2. Process Data (Ch0)
        # Step A: Notch (remove mains noise)
        ch0_notched = SignalProcessor.notch_filter(self.raw_data_ch0, notch, 30.0, self.fs)
        # Step B: Bandpass (isolate signals)
        ch0_clean = SignalProcessor.butter_bandpass_filter(ch0_notched, low, high, self.fs)

        # 3. Process Data (Ch1)
        ch1_notched = SignalProcessor.notch_filter(self.raw_data_ch1, notch, 30.0, self.fs)
        ch1_clean = SignalProcessor.butter_bandpass_filter(ch1_notched, low, high, self.fs)

        # 4. Clear and Plot Ch0
        self.ax0.clear()
        self.ax0.plot(self.time_axis, self.raw_data_ch0, label='Raw', color='lightgray', alpha=0.6)
        self.ax0.plot(self.time_axis, ch0_clean, label='Filtered', color='blue', linewidth=1)
        self.ax0.set_title("Channel 0 (Horizontal)")
        self.ax0.legend(loc='upper right')
        self.ax0.grid(True, alpha=0.3)

        # 5. Clear and Plot Ch1
        self.ax1.clear()
        self.ax1.plot(self.time_axis, self.raw_data_ch1, label='Raw', color='lightgray', alpha=0.6)
        self.ax1.plot(self.time_axis, ch1_clean, label='Filtered', color='red', linewidth=1)
        self.ax1.set_title("Channel 1 (Vertical)")
        self.ax1.legend(loc='upper right')
        self.ax1.grid(True, alpha=0.3)
        
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    app = EOGAnalysisApp(root)
    root.mainloop()
