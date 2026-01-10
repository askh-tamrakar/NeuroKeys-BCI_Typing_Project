"""
EMG filter processor (Passive)

- Applies configurable high-pass filter (default 70 Hz, order 4)
- Designed to be instantiated per-channel by filter_router.py
"""

import numpy as np
import numpy as np
from scipy.signal import butter, sosfilt, iirnotch, tf2sos

class EMGFilterProcessor:
    def __init__(self, config: dict, sr: int = 512, channel_key: str = None):
        self.config = config
        self.sr = int(sr)
        self.channel_key = channel_key
        
        self._load_params()
        self._design_filters()
        
<<<<<<< HEAD
        # Initialize state (sections, 2)
        self.zi_hp = np.zeros((self.sos_hp.shape[0], 2))
        
        if self.notch_enabled:
            self.zi_notch = np.zeros((self.sos_notch.shape[0], 2))
        else:
            self.zi_notch = None

        if self.bp_enabled:
            self.zi_bp = np.zeros((self.sos_bp.shape[0], 2))
        else:
            self.zi_bp = None
=======
        # Initialize state
        self.zi_hp = lfilter_zi(self.b_hp, self.a_hp) * 0.0
        self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0.0 if (self.notch_enabled and getattr(self, 'a_notch', None) is not None) else None
        self.zi_bp = lfilter_zi(self.b_bp, self.a_bp) * 0.0 if (self.bp_enabled and getattr(self, 'a_bp', None) is not None) else None
        self.zi_env = lfilter_zi(self.b_env, self.a_env) * 0.0 if self.envelope_enabled else None
>>>>>>> rps-implement

    def _load_params(self):
        # 1. Default Global Config
        emg_cfg = self.config.get("filters", {}).get("EMG", {})
        
        # 2. Channel Specific Override?
        if self.channel_key:
            ch_cfg = self.config.get("filters", {}).get(self.channel_key, {})
            # Merge simple keys
            emg_cfg = {**emg_cfg, **ch_cfg}

        # High Pass (Standard EMG)
        self.hp_cutoff = float(emg_cfg.get("cutoff", 70.0))
        self.hp_order = int(emg_cfg.get("order", 4))
        
        # Notch (Noise Filtering)
        self.notch_enabled = emg_cfg.get("notch_enabled", False)
        self.notch_freq = float(emg_cfg.get("notch_freq", 50.0))
        self.notch_q = float(emg_cfg.get("notch_q", 30.0))

        # Bandpass
        self.bp_enabled = emg_cfg.get("bandpass_enabled", False)
        self.bp_low = float(emg_cfg.get("bandpass_low", 20.0))
        self.bp_high = float(emg_cfg.get("bandpass_high", 450.0))
        self.bp_order = int(emg_cfg.get("bandpass_order", 4))

        # Envelope (Rectify + Low Pass)
        self.envelope_enabled = emg_cfg.get("envelope_enabled", True)
        self.envelope_cutoff = float(emg_cfg.get("envelope_cutoff", 10.0))
        self.envelope_order = int(emg_cfg.get("envelope_order", 4))

    def _design_filters(self):
        nyq = self.sr / 2.0
        
        # 1. High Pass
        wn_hp = self.hp_cutoff / nyq
        self.sos_hp = butter(self.hp_order, wn_hp, btype="high", output='sos', analog=False)

        # 2. Notch
<<<<<<< HEAD
        if self.notch_enabled:
            b_notch, a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)
            self.sos_notch = tf2sos(b_notch, a_notch)
=======
        if self.notch_enabled and self.notch_freq > 0:
            from scipy.signal import iirnotch
            self.b_notch, self.a_notch = iirnotch(self.notch_freq, self.notch_q, fs=self.sr)
        else:
             # If enabled but invalid freq, disable it implicitly for this run
             self.b_notch, self.a_notch = None, None
>>>>>>> rps-implement

        # 3. Bandpass
        if self.bp_enabled:
            low = self.bp_low / nyq
            if self.bp_high >= self.sr / 2.0:
                print(f"[EMG] ⚠️ Bandpass High ({self.bp_high} Hz) >= Nyquist. Capping to {self.sr/2.0 - 1.0} Hz.")
                self.bp_high = self.sr / 2.0 - 1.0
            
            high = self.bp_high / nyq
            
            if low <= 0 or high >= 1:
                # Fallback if invalid: Disable filter to avoid crash
                print(f"[EMG] ⚠️ Invalid Bandpass freq: {self.bp_low}-{self.bp_high} Hz (Nyquist: {nyq}). Disabling.")
                self.bp_enabled = False
                self.sos_bp = None
            else:
                self.sos_bp = butter(self.bp_order, [low, high], btype="bandpass", output='sos', analog=False)

        # 4. Envelope (Low Pass)
        if self.envelope_enabled:
            wn_env = self.envelope_cutoff / nyq
            self.b_env, self.a_env = butter(self.envelope_order, wn_env, btype="low", analog=False)
        else:
            self.b_env, self.a_env = [1.0], [1.0]

    def update_config(self, config: dict, sr: int):
        """Update filter parameters if config changed."""
        old_state = (self.hp_cutoff, self.notch_enabled, self.notch_freq, self.bp_enabled, self.bp_low, self.bp_high)
        
        self.config = config
        self.sr = int(sr)
        self._load_params()
        
        new_state = (self.hp_cutoff, self.notch_enabled, self.notch_freq, self.bp_enabled, self.bp_low, self.bp_high, self.envelope_enabled, self.envelope_cutoff)
        
        if old_state != new_state:
<<<<<<< HEAD
            print(f"[EMG] Config changed ({self.channel_key}) -> HP:{self.hp_cutoff} N:{self.notch_enabled} BP:{self.bp_enabled}")
            
            self._design_filters()
            
            # Reset
            self.zi_hp = np.zeros((self.sos_hp.shape[0], 2))

            if self.notch_enabled:
                self.zi_notch = np.zeros((self.sos_notch.shape[0], 2))
            else:
                self.zi_notch = None

            if self.bp_enabled:
                self.zi_bp = np.zeros((self.sos_bp.shape[0], 2))
            else:
                self.zi_bp = None
=======
            print(f"[EMG] Config changed ({self.channel_key}) -> HP:{self.hp_cutoff} Notch:{self.notch_enabled}({self.notch_freq}Hz) Env:{self.envelope_enabled} ({self.envelope_cutoff}Hz)")
            self._design_filters()
            
            # Reset states
            try:
                self.zi_hp = lfilter_zi(self.b_hp, self.a_hp) * 0.0
                self.zi_notch = lfilter_zi(self.b_notch, self.a_notch) * 0.0 if (self.notch_enabled and getattr(self, 'a_notch', None) is not None) else None
                self.zi_bp = lfilter_zi(self.b_bp, self.a_bp) * 0.0 if (self.bp_enabled and getattr(self, 'a_bp', None) is not None) else None
                self.zi_env = lfilter_zi(self.b_env, self.a_env) * 0.0 if self.envelope_enabled else None
            except Exception as e:
                print(f"[EMG] ⚠️ Filter state reset error: {e}")
                # Fallback to zeros (no steady state init)
                self.zi_hp = np.zeros(max(len(self.a_hp), len(self.b_hp)) - 1)
                if self.notch_enabled: self.zi_notch = np.zeros(max(len(self.a_notch), len(self.b_notch)) - 1)
                if self.bp_enabled: self.zi_bp = np.zeros(max(len(self.a_bp), len(self.b_bp)) - 1)
                if self.envelope_enabled: self.zi_env = np.zeros(max(len(self.a_env), len(self.b_env)) - 1)
>>>>>>> rps-implement

    def process_sample(self, val: float) -> float:
        """Process a single sample value."""
        # 1. High Pass
        # Returns array, take [0] only if we return scalar here, wait.
        # But sosfilt output preserves shape. If input is [val], output is [out].
        # But zi must be maintained.
        
        # Note: sosfilt([val], zi=zi) returns (filtered_array, new_zi)
        out, self.zi_hp = sosfilt(self.sos_hp, [val], zi=self.zi_hp)
        
        # 2. Notch
        if self.notch_enabled and self.zi_notch is not None:
             out, self.zi_notch = sosfilt(self.sos_notch, out, zi=self.zi_notch)
            
        # 3. Bandpass
        if self.bp_enabled and self.zi_bp is not None:
<<<<<<< HEAD
             out, self.zi_bp = sosfilt(self.sos_bp, out, zi=self.zi_bp)

        return float(out[0])
=======
             filtered, self.zi_bp = lfilter(self.b_bp, self.a_bp, [out], zi=self.zi_bp)
             filtered, self.zi_bp = lfilter(self.b_bp, self.a_bp, [out], zi=self.zi_bp)
             out = filtered[0]

        # 4. Envelope
        if self.envelope_enabled and self.zi_env is not None:
            # Rectify
            rectified = abs(out)
            # Low Pass
            enveloped, self.zi_env = lfilter(self.b_env, self.a_env, [rectified], zi=self.zi_env)
            out = enveloped[0]

        return float(out)
>>>>>>> rps-implement

