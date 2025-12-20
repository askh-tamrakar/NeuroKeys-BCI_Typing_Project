"""
EEG filter processor (Passive - Single Channel)

- Applies configurable notch filter (default 50 Hz) and bandpass (default 0.5-45 Hz)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
from scipy.signal import iirnotch, butter, lfilter, lfilter_zi

class EEGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512, channel_key: str = None):
        self.config = config
        self.sr = int(sr)
        self.channel_key = channel_key
        
        # Load params
        self._load_params()
        
        # Initial design
        self._design_filters()
        
        # Initialize state (0.0)
        self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0.0
        self.zi_band = lfilter_zi(self.b_band, self.a_band) * 0.0

    def _load_params(self):
        # 1. Global EEG Config
        eeg_base = self.config.get("filters", {}).get("EEG", {})
        eeg_filters = eeg_base.get("filters", [])
        
        # 2. Channel Override?
        # Note: EEG config is complex (list of filters), so deep merging is harder.
        # Simple strategy: If `filters.<channel_key>.filters` exists, use that instead.
        if self.channel_key:
            ch_cfg = self.config.get("filters", {}).get(self.channel_key, {})
            if "filters" in ch_cfg:
                eeg_filters = ch_cfg["filters"]

        notch_cfg = next((f for f in eeg_filters if f.get("type") == "notch"), {"freq": 50.0, "Q": 30})
        band_cfg = next((f for f in eeg_filters if f.get("type") == "bandpass"),
                        {"low": 0.5, "high": 45.0, "order": 4})

        self.notch_freq = float(notch_cfg.get("freq", 50.0))
        self.notch_q = float(notch_cfg.get("Q", 30.0))
        self.bp_low = float(band_cfg.get("low", 0.5))
        self.bp_high = float(band_cfg.get("high", 45.0))
        self.bp_order = int(band_cfg.get("order", 4))

    def _design_filters(self):
        # Notch
        self.b_notch, self.a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)
        # Bandpass
        nyq = self.sr / 2.0
        low = self.bp_low / nyq
        high = self.bp_high / nyq
        self.b_band, self.a_band = butter(self.bp_order, [low, high], btype="band")

    def update_config(self, config: dict, sr: int):
        """Update filter parameters if config changed."""
        old_params = (self.notch_freq, self.notch_q, self.bp_low, self.bp_high, self.bp_order, self.sr)
        
        self.config = config
        self.sr = int(sr)
        self._load_params()
        
        new_params = (self.notch_freq, self.notch_q, self.bp_low, self.bp_high, self.bp_order, self.sr)
        
        if old_params != new_params:
            print(f"[EEG] Config changed -> redesigning filters")
            self._design_filters()
            # Reset state
            self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0.0
            self.zi_band = lfilter_zi(self.b_band, self.a_band) * 0.0

    def process_sample(self, val: float) -> float:
        """Process a single sample value: Notch -> Bandpass."""
        # 1. Notch
        notch_out, self.zi_notch = lfilter(self.b_notch, self.a_notch, [val], zi=self.zi_notch)
        # 2. Bandpass
        band_out, self.zi_band = lfilter(self.b_band, self.a_band, notch_out, zi=self.zi_band)
        return float(band_out[0])

