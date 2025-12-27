"""
EOG filter processor (Passive)

- Applies configurable low-pass filter (default 10 Hz, order 4)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
import numpy as np
from scipy.signal import butter, sosfilt, iirnotch, tf2sos

class EOGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512, channel_key: str = None):
        self.config = config
        self.sr = int(sr)
        self.channel_key = channel_key
        
        self._load_params()
        self._design_filters()
        
        # Initialize state (n_sections, 2)
        self.zi_lp = np.zeros((self.sos_lp.shape[0], 2))
        
        if self.notch_enabled:
            self.zi_notch = np.zeros((self.sos_notch.shape[0], 2))
        else:
            self.zi_notch = None

        if self.bp_enabled:
            self.zi_bp = np.zeros((self.sos_bp.shape[0], 2))
        else:
            self.zi_bp = None

    def _load_params(self):
        # 1. Default Global Config
        eog_cfg = self.config.get("filters", {}).get("EOG", {})
        
        # 2. Channel Specific Override?
        if self.channel_key:
            ch_cfg = self.config.get("filters", {}).get(self.channel_key, {})
            eog_cfg = {**eog_cfg, **ch_cfg}

        # Low Pass
        self.lp_cutoff = float(eog_cfg.get("cutoff", 10.0))
        self.lp_order = int(eog_cfg.get("order", 4))

        # Notch
        self.notch_enabled = eog_cfg.get("notch_enabled", False)
        self.notch_freq = float(eog_cfg.get("notch_freq", 50.0))
        self.notch_q = float(eog_cfg.get("notch_q", 30.0))

        # Bandpass
        self.bp_enabled = eog_cfg.get("bandpass_enabled", False)
        self.bp_low = float(eog_cfg.get("bandpass_low", 0.5))
        self.bp_high = float(eog_cfg.get("bandpass_high", 10.0))
        self.bp_order = int(eog_cfg.get("bandpass_order", 4))

    def _design_filters(self):
        nyq = self.sr / 2.0
        
        # 1. Low Pass
        wn = self.lp_cutoff / nyq
        self.sos_lp = butter(self.lp_order, wn, btype="low", output='sos', analog=False)

        # 2. Notch
        if self.notch_enabled:
            b_notch, a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)
            self.sos_notch = tf2sos(b_notch, a_notch)

        # 3. Bandpass
        if self.bp_enabled:
            low = self.bp_low / nyq
            high = self.bp_high / nyq
            if low <= 0 or high >= 1:
                print(f"[EOG] ⚠️ Invalid Bandpass freq: {self.bp_low}-{self.bp_high} Hz (Nyquist: {nyq}). Disabling.")
                self.bp_enabled = False
                self.sos_bp = None
            else:
                self.sos_bp = butter(self.bp_order, [low, high], btype="bandpass", output='sos', analog=False)

    def update_config(self, config: dict, sr: int):
        """Update filter parameters if config changed."""
        old_state = (self.lp_cutoff, self.notch_enabled, self.bp_enabled, self.bp_low, self.bp_high)
        
        self.config = config
        self.sr = int(sr)
        self._load_params()
        
        new_state = (self.lp_cutoff, self.notch_enabled, self.bp_enabled, self.bp_low, self.bp_high)
        
        if old_state != new_state:
            print(f"[EOG] Config changed -> Redesign filters")
            
            # Save old state if possible (shape check needed) Or just reset to 0
            # For robustness, let's reset to 0 on major config change
            self._design_filters()

            self.zi_lp = np.zeros((self.sos_lp.shape[0], 2))
            
            if self.notch_enabled:
                self.zi_notch = np.zeros((self.sos_notch.shape[0], 2))
            else:
                self.zi_notch = None

            if self.bp_enabled:
                self.zi_bp = np.zeros((self.sos_bp.shape[0], 2))
            else:
                self.zi_bp = None

    def process_sample(self, val: float) -> float:
        """Process a single sample value."""
        # sosfilt input must be array-like
        
        # 1. Low Pass (Standard EOG)
        out, self.zi_lp = sosfilt(self.sos_lp, [val], zi=self.zi_lp)
        
        # 2. Notch
        if self.notch_enabled and self.zi_notch is not None:
             out, self.zi_notch = sosfilt(self.sos_notch, out, zi=self.zi_notch)
             
        # 3. Bandpass
        if self.bp_enabled and self.zi_bp is not None:
             out, self.zi_bp = sosfilt(self.sos_bp, out, zi=self.zi_bp)

        return float(out[0])

