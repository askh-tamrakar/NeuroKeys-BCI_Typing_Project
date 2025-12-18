"""
EOG filter processor (Passive)

- Applies configurable low-pass filter (default 10 Hz, order 4)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

class EOGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512):
        self.config = config
        self.sr = int(sr)
        
        # Load params from config or defaults
        eog_cfg = self.config.get("filters", {}).get("EOG", {})
        self.cutoff = float(eog_cfg.get("cutoff", 10.0))
        self.order = int(eog_cfg.get("order", 4))
        
        # Initial design
        self._design_filter()
        self.zi = lfilter_zi(self.b, self.a) * 0.0

    def _design_filter(self):
        nyq = self.sr / 2.0
        wn = self.cutoff / nyq
        self.b, self.a = butter(self.order, wn, btype="low", analog=False)

    def update_config(self, config: dict, sr: int):
        """Update filter parameters if config changed."""
        self.config = config
        new_sr = int(sr)
        
        eog_cfg = self.config.get("filters", {}).get("EOG", {})
        new_cutoff = float(eog_cfg.get("cutoff", 10.0))
        new_order = int(eog_cfg.get("order", 4))
        
        if (new_cutoff != self.cutoff or 
            new_order != self.order or 
            new_sr != self.sr):
            
            print(f"[EOG] Config changed -> redesigning filter ({new_cutoff}Hz, order {new_order})")
            self.cutoff = new_cutoff
            self.order = new_order
            self.sr = new_sr
            self._design_filter()
            # Reset state
            self.zi = lfilter_zi(self.b, self.a) * 0.0

    def process_sample(self, val: float) -> float:
        """Process a single sample value."""
        filtered, self.zi = lfilter(self.b, self.a, [val], zi=self.zi)
        #print(filtered)
        return float(filtered[0])

