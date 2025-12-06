import tkinter as tk
from tkinter import ttk
import numpy as np
from collections import deque
from scipy.signal import butter, filtfilt, lfilter

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

class EMGFilterWindow(tk.Toplevel):
    def __init__(self, parent, fs=250):
        super().__init__(parent)
        self.title("EMG Signal Processing")
        self.geometry("1000x800")
        
        self.fs = fs
        self.window_seconds = 10
        self.buffer_size = int(self.fs * self.window_seconds)
        
        # Buffers
        self.raw_ch0 = deque(maxlen=self.buffer_size)
        
        # Filter Settings (High Pass 70Hz)
        self.cutoff = 70.0
        self.order = 4
        self.b, self.a = self.calculate_coefficients()

        # Envelope Settings (RMS 100ms)
        self.rms_window_ms = 100
        
        self.setup_ui()
        
        # Animation
        self.running = True
        self.after(100, self.update_plot)
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def calculate_coefficients(self):
        nyq = 0.5 * self.fs
        normal_cutoff = self.cutoff / nyq
        if normal_cutoff >= 1.0: normal_cutoff = 0.99
        b, a = butter(self.order, normal_cutoff, btype='high', analog=False)
        return b, a

    def setup_ui(self):
        # Stats
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill="x", padx=5, pady=5)
        self.lbl_stats = ttk.Label(stats_frame, text="Waiting for data...")
        self.lbl_stats.pack()

        # Graphs
        self.fig = Figure(figsize=(10, 8), dpi=100)
        self.ax1 = self.fig.add_subplot(311)
        self.ax1.set_title("Raw Signal (Ch0)")
        self.line_raw, = self.ax1.plot([], [], 'b-', lw=0.5)
        
        self.ax2 = self.fig.add_subplot(312)
        self.ax2.set_title(f"Filtered (High-pass {self.cutoff}Hz)")
        self.line_filt, = self.ax2.plot([], [], 'g-', lw=0.5)
        
        self.ax3 = self.fig.add_subplot(313)
        self.ax3.set_title("RMS Envelope")
        self.line_env, = self.ax3.plot([], [], 'r-', lw=1.0)
        
        self.fig.tight_layout()
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def update_data(self, samples_ch0):
        """Called by main app to push new data"""
        if not self.running: return
        self.raw_ch0.extend(samples_ch0)

    def calculate_rms(self, signal):
        w_size = int((self.rms_window_ms / 1000.0) * self.fs)
        if len(signal) < w_size: return np.zeros_like(signal)
        window = np.ones(w_size) / float(w_size)
        return np.sqrt(np.convolve(signal**2, window, 'same'))

    def update_plot(self):
        if not self.running: return
        
        if len(self.raw_ch0) > self.fs:
            data = np.array(self.raw_ch0)
            
            # Filter
            filt = filtfilt(self.b, self.a, data)
            
            # Envelope
            env = self.calculate_rms(filt)
            
            # Plot
            x = np.arange(len(data))
            
            self.line_raw.set_data(x, data)
            self.ax1.set_xlim(0, len(data))
            self.ax1.set_ylim(min(data), max(data))
            
            self.line_filt.set_data(x, filt)
            self.ax2.set_xlim(0, len(data))
            self.ax2.set_ylim(min(filt), max(filt))
            
            self.line_env.set_data(x, env)
            self.ax3.set_xlim(0, len(data))
            self.ax3.set_ylim(0, max(env))
            
            self.lbl_stats.config(text=f"Current: {data[-1]:.0f} | Filt: {filt[-1]:.0f} | Env: {env[-1]:.0f}")
            self.canvas.draw_idle()
            
        self.after(100, self.update_plot)

    def on_close(self):
        self.running = False
        self.destroy()
