"""
EOG filter processor (Passive)

- Applies configurable low-pass filter (default 10 Hz, order 4)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
from scipy.signal import butter, lfilter, lfilter_zi

class EOGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512, channel_key: str = None):
        self.config = config
        self.sr = int(sr)
        self.channel_key = channel_key
        
        self._load_params()
        self._design_filters()
        
        self.zi_lp = lfilter_zi(self.b_lp, self.a_lp) * 0.0
        self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0.0 if self.notch_enabled else None
        self.zi_bp = lfilter_zi(self.b_bp, self.a_bp) * 0.0 if self.bp_enabled else None

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
        self.b_lp, self.a_lp = butter(self.lp_order, wn, btype="low", analog=False)

        # 2. Notch
        if self.notch_enabled:
            from scipy.signal import iirnotch
            self.b_notch, self.a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)

        # 3. Bandpass
        if self.bp_enabled:
            low = self.bp_low / nyq
            high = self.bp_high / nyq
            if low <= 0 or high >= 1:
                self.b_bp, self.a_bp = [1.0], [1.0]
            else:
                self.b_bp, self.a_bp = butter(self.bp_order, [low, high], btype="bandpass", analog=False)

    def update_config(self, config: dict, sr: int):
        """Update filter parameters if config changed."""
        old_state = (self.lp_cutoff, self.notch_enabled, self.bp_enabled, self.bp_low, self.bp_high)
        
        self.config = config
        self.sr = int(sr)
        self._load_params()
        
        new_state = (self.lp_cutoff, self.notch_enabled, self.bp_enabled, self.bp_low, self.bp_high)
        
        if old_state != new_state:
            print(f"[EOG] Config changed -> Redesign filters")
            self._design_filters()
            # Reset state
            self.zi_lp = lfilter_zi(self.b_lp, self.a_lp) * 0.0
            self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0.0 if self.notch_enabled else None
            self.zi_bp = lfilter_zi(self.b_bp, self.a_bp) * 0.0 if self.bp_enabled else None

    def process_sample(self, val: float) -> float:
        """Process a single sample value."""
        # 1. Low Pass (Standard EOG)
        out, self.zi_lp = lfilter(self.b_lp, self.a_lp, [val], zi=self.zi_lp)
        out = out[0]
        
        # 2. Notch
        if self.notch_enabled and self.zi_notch is not None:
             filtered, self.zi_notch = lfilter(self.b_notch, self.a_notch, [out], zi=self.zi_notch)
             out = filtered[0]
             
        # 3. Bandpass
        if self.bp_enabled and self.zi_bp is not None:
             filtered, self.zi_bp = lfilter(self.b_bp, self.a_bp, [out], zi=self.zi_bp)
             out = filtered[0]

        return float(out)

