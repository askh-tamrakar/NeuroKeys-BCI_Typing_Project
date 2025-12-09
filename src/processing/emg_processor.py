"""
EMG filter processor (Passive)

- Applies configurable high-pass filter (default 70 Hz, order 4)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

class EMGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512):
        self.config = config
        self.sr = int(sr)
        
        # Load params from config or defaults
        emg_cfg = self.config.get("filters", {}).get("EMG", {})
        self.cutoff = float(emg_cfg.get("cutoff", 70.0))
        self.order = int(emg_cfg.get("order", 4))
        
        # Initial design
        self._design_filter()
        self.zi = lfilter_zi(self.b, self.a) * 0.0

    def _design_filter(self):
        nyq = self.sr / 2.0
        wn = self.cutoff / nyq
        # design high-pass Butterworth
        self.b, self.a = butter(self.order, wn, btype="high", analog=False)
        # print(f"[EMG] Designed high-pass: cutoff={self.cutoff} Hz order={self.order}")

    def update_config(self, config: dict, sr: int):
        """Update filter parameters if config changed."""
        self.config = config
        new_sr = int(sr)
        
        emg_cfg = self.config.get("filters", {}).get("EMG", {})
        new_cutoff = float(emg_cfg.get("cutoff", 70.0))
        new_order = int(emg_cfg.get("order", 4))
        
        if (new_cutoff != self.cutoff or 
            new_order != self.order or 
            new_sr != self.sr):
            
            print("[EMG] Config changed -> redesigning filter ({new_cutoff}Hz, order {new_order})")
            self.cutoff = new_cutoff
            self.order = new_order
            self.sr = new_sr
            self._design_filter()
            # Reset state on filter change to avoid instability
            self.zi = lfilter_zi(self.b, self.a) * 0.0

    def process_sample(self, val: float) -> float:
        """Process a single sample value."""
        filtered, self.zi = lfilter(self.b, self.a, [val], zi=self.zi)
        return float(filtered[0])

