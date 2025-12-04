"""
EOG Signal Acquisition System
=============================
Professional EOG data acquisition from Arduino Uno R4
Sampling Rate: 512 Hz | Baud Rate: 230400 | 2-Channel EOG

Features:
- Real-time signal acquisition and filtering
- Live signal visualization (Graph)
- Automatic eye movement detection
- Data export and analysis
- Signal quality monitoring

Author: EOG Research Team
Version: 3.5 (Modified for Real-time Plotting)
Date: December 2024
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
from collections import deque
import struct

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not available - plotting disabled")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("Warning: NumPy not available - some features disabled")

try:
    from scipy.signal import butter, filtfilt, iirnotch
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: SciPy not available - filtering disabled")


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Application configuration constants"""
    
    # Serial communication
    BAUD_RATE = 230400
    SERIAL_TIMEOUT = 1.0
    
    # Packet format
    PACKET_LENGTH = 8
    SYNC_BYTE_1 = 0xC7
    SYNC_BYTE_2 = 0x7C
    END_BYTE = 0x01
    
    # Sampling
    SAMPLING_RATE = 512.0
    
    # Plotting
    PLOT_WINDOW_S = 5.0 # Visible window duration in seconds
    PLOT_MAX_SAMPLES = int(SAMPLING_RATE * PLOT_WINDOW_S)
    
    # Filtering
    FILTER_BUFFER_SIZE = 2048
    BANDPASS_LOW = 0.5
    BANDPASS_HIGH = 35.0
    NOTCH_QUALITY = 30
    
    # Display
    PREVIEW_PACKETS = 10 # Reduced for smaller log window
    UPDATE_INTERVAL_MS = 200
    DEBUG_MAX_LINES = 1000
    
    # Data
    OUTPUT_DIR = Path("data/eog_sessions")


# ============================================================================
# REAL-TIME FILTER
# ... (Class EOGFilter remains unchanged)
# ============================================================================

# ... (Class PacketParser remains unchanged)
# ============================================================================

# ============================================================================
# LIVE PLOT
# ============================================================================

class LivePlot:
    """Real-time Matplotlib plot integration for Tkinter"""
    
    def __init__(self, master_frame):
        # Use Figure size to make it slightly wider than tall
        self.fig, self.ax = plt.subplots(figsize=(8, 6), dpi=100)
        
        self.ax.set_title("Real-Time EOG Signal")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage ($\mu$V)")
        self.ax.grid(True, linestyle='--', alpha=0.6)
        
        # Initialize lines
        self.line_ch0, = self.ax.plot([], [], label='Channel 0 (Horizontal)', color='blue')
        self.line_ch1, = self.ax.plot([], [], label='Channel 1 (Vertical)', color='red')
        self.ax.legend(loc='upper right')
        
        # Initial axes limits (will be auto-scaled dynamically)
        self.ax.set_xlim(0, Config.PLOT_WINDOW_S)
        self.ax.set_ylim(-5000, 5000) # Initial guess for EOG data range
        
        # Integrate plot into Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=master_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill='both', expand=True)

    def update_plot(self, session_data, filter_enabled):
        """Update the plot with new data"""
        
        if not session_data:
            return
            
        # Select the last PLOT_MAX_SAMPLES data points
        data_to_plot = session_data[-Config.PLOT_MAX_SAMPLES:]
        
        if not data_to_plot:
            return

        # Use elapsed time (relative to the start of the current plot window)
        time_s = [d['elapsed_s'] for d in data_to_plot]
        
        # Choose between raw and filtered data
        if filter_enabled and 'ch0_filtered_uv' in data_to_plot[-1]:
            ch0_data = [d['ch0_filtered_uv'] for d in data_to_plot]
            ch1_data = [d['ch1_filtered_uv'] for d in data_to_plot]
            self.ax.set_title("Real-Time EOG Signal (Filtered)")
        else:
            ch0_data = [d['ch0_uv'] for d in data_to_plot]
            ch1_data = [d['ch1_uv'] for d in data_to_plot]
            self.ax.set_title("Real-Time EOG Signal (Raw)")
            
        # Update line data
        self.line_ch0.set_data(time_s, ch0_data)
        self.line_ch1.set_data(time_s, ch1_data)

        # Dynamic X-axis update
        t_max = time_s[-1] if time_s else Config.PLOT_WINDOW_S
        t_min = max(0, t_max - Config.PLOT_WINDOW_S)
        self.ax.set_xlim(t_min, t_max)
        
        # Dynamic Y-axis update (autoscale)
        min_y = min(min(ch0_data, default=0), min(ch1_data, default=0))
        max_y = max(max(ch0_data, default=0), max(ch1_data, default=0))
        
        # Add some margin
        margin = max(100, (max_y - min_y) * 0.1)
        self.ax.set_ylim(min_y - margin, max_y + margin)

        # Redraw
        self.canvas.draw_idle()

    def clear(self):
        """Clear the plot"""
        self.line_ch0.set_data([], [])
        self.line_ch1.set_data([], [])
        self.ax.set_xlim(0, Config.PLOT_WINDOW_S)
        self.ax.set_ylim(-5000, 5000)
        self.canvas.draw_idle()

    def cleanup(self):
        """Close the plot figure to free memory"""
        plt.close(self.fig)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class EOGAcquisitionApp:
    """Main EOG acquisition application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("EOG Signal Acquisition System v3.5")
        self.root.geometry("1500x950")
        
        # Serial connection
        self.serial_port = None
        self.is_acquiring = False
        self.acquisition_thread = None
        
        # Data structures
        self.parser = PacketParser()
        self.filter = EOGFilter()
        self.live_plot = None
        self.session_data = []
        self.session_start = None
        
        # UI variables
        self.port_var = tk.StringVar()
        self.filter_enabled = tk.BooleanVar(value=True)
        self.notch_freq = tk.IntVar(value=50)
        self.debug_enabled = tk.BooleanVar(value=True)
        
        # Statistics
        self.stats = {
            'packets': 0,
            'errors': 0,
            'duration': 0,
            'rate': 0
        }
        
        # Build UI
        self.create_ui()
        self.scan_ports()
        
        # Start update loop
        self.update_displays()
        
        # Bind cleanup function to window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        """Handle window close event"""
        if self.is_acquiring:
            self.stop_acquisition()
        if self.live_plot and MATPLOTLIB_AVAILABLE:
            self.live_plot.cleanup()
        self.root.destroy()
    
    def create_status_bar(self):