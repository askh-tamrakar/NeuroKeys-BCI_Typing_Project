"""
EEG filter processor (Passive - Single Channel)

- Applies configurable notch filter (default 50 Hz) and bandpass (default 0.5-45 Hz)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
from scipy.signal import iirnotch, butter, sosfilt

class EEGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512, channel_key: str = None):
        self.config = config
        self.sr = int(sr)
        self.channel_key = channel_key
        
        # Load params
        self._load_params()
        
        # Initial design
        self._design_filters()
        
        # Initialize state (n_sections, 2)
        # SOS state shape is always (sections, 2) for standard IIR (filter_design usually output='sos' returns (sections, 6))
        self.zi_notch = np.zeros((self.sos_notch.shape[0], 2))
        self.zi_band = np.zeros((self.sos_band.shape[0], 2))

    def _load_params(self):
        # 1. Global EEG Config
        eeg_base = self.config.get("filters", {}).get("EEG", {})
        eeg_filters = eeg_base.get("filters", [])
        
        # 2. Channel Override?
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
        # iirnotch doesn't support output='sos' directly in older scipy? 
        # Actually it typically returns b, a. 
        # To get SOS for notch, easiest is to convert tf2sos, but iirnotch is precise.
        # Check if user has modern scipy from repro? Repro didn't check iirnotch sos.
        # Fallback: keep Notch as BA (it's usually stable as 2nd order) OR convert.
        # Let's try to keep Notch as BA if simple, but to be consistent let's convert tf2sos if needed.
        # Actually, standard iirnotch (b, a) is fine because it's always 2nd order (low order = stable).
        # The ISSUE is usually high order bandpass.
        # BUT for consistency, let's use SOS for everything if possible.
        # However, iirnotch returns (b, a). We can use tf2sos on it.
        from scipy.signal import tf2sos
        b_notch, a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)
        self.sos_notch = tf2sos(b_notch, a_notch)

        # Bandpass
        nyq = self.sr / 2.0
        low = self.bp_low / nyq
        high = self.bp_high / nyq
        self.sos_band = butter(self.bp_order, [low, high], btype="band", output='sos')

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
            self.zi_notch = np.zeros((self.sos_notch.shape[0], 2))
            self.zi_band = np.zeros((self.sos_band.shape[0], 2))

    def process_sample(self, val: float) -> float:
        """Process a single sample value: Notch -> Bandpass."""
        # 1. Notch
        # sosfilt expects array, we pass [val]. Returns array.
        notch_out, self.zi_notch = sosfilt(self.sos_notch, [val], zi=self.zi_notch)
        
        # 2. Bandpass
        band_out, self.zi_band = sosfilt(self.sos_band, notch_out, zi=self.zi_band)
        
        return float(band_out[0])

