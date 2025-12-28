import numpy as np
import collections
from scipy import stats

class BlinkExtractor:
    """
    Feature Extractor for EOG blinks.
    Maintains a rolling buffer and detects peak candidates to extract features.
    """
    
    def __init__(self, 
                 channel_index: int, 
                 config: dict, 
                 sr: int):
        
        self.channel_index = channel_index
        self.sr = sr
        
        # Load thresholds from config
        eog_cfg = config.get("features", {}).get("EOG", {})
        # User reported ~3uV blinks, so 1.5 threshold is reasonable
        self.amp_threshold = eog_cfg.get("amp_threshold", 50.0) 
        self.min_duration_ms = eog_cfg.get("min_duration_ms", 100.0)
        self.max_duration_ms = eog_cfg.get("max_duration_ms", 800.0) # Increased for double blinks
        
        # Buffer for signal (approx 1 second of data)
        self.buffer_size = sr 
        self.buffer = collections.deque(maxlen=self.buffer_size)
        
        # Baseline estimation (rolling mean)
        self.baseline = 0.0
        self.alpha = 0.01 # Smoothing factor for baseline
        
        # State tracking
        self.is_collecting = False
        self.candidate_window = []
        self.start_idx = 0
        self.current_idx = 0
        self.cooldown_counter = 0
        
    def process(self, sample_val: float):
        """
        Process a single sample. 
        Returns a feature dictionary if a blink candidate window is finished, else None.
        """
        self.current_idx += 1
        
        # Update baseline (very slow moving average)
        if self.current_idx == 1:
            self.baseline = sample_val
        else:
            self.baseline = self.alpha * sample_val + (1 - self.alpha) * self.baseline
            
        # Zero-centered signal
        zero_centered = sample_val - self.baseline
        self.buffer.append(zero_centered)
        
        # Detection logic:
        # Start collecting when value exceeds threshold (relative to baseline)
        if not self.is_collecting:
            if abs(zero_centered) > self.amp_threshold:
                self.is_collecting = True
                self.candidate_window = [zero_centered]
                self.start_idx = self.current_idx
                self.cooldown_counter = 0
                
                print(f"[Extractor] Candidate start at {self.current_idx} (Val: {zero_centered:.2f})")
        else:
            self.candidate_window.append(zero_centered)
            
            # Check if signal is active (above cutoff)
            # We use a lower cutoff to sustain the window during valleys (like in double blinks)
            cutoff = self.amp_threshold / 4.0
            
            if abs(zero_centered) > cutoff:
                self.cooldown_counter = 0 # Signal is active, reset cooldown
            else:
                self.cooldown_counter += 1 # Signal is weak, count down
            
            # Stop conditions
            # 1. Max Duration Exceeded
            if len(self.candidate_window) > (self.max_duration_ms / 1000.0) * self.sr:
                features = self._extract_features(self.candidate_window)
                self.is_collecting = False
                self.candidate_window = []
                self.cooldown_counter = 0
                return features
            
            # 2. Cooldown Exceeded (Signal stayed low for too long)
            # Wait 150ms before giving up
            max_cooldown_samples = int(0.15 * self.sr)
            
            if self.cooldown_counter > max_cooldown_samples:
                # Signal has ended.
                # Check min duration
                if len(self.candidate_window) > (self.min_duration_ms / 1000.0) * self.sr:
                    features = self._extract_features(self.candidate_window)
                    self.is_collecting = False
                    self.candidate_window = []
                    self.cooldown_counter = 0
                    return features
                else:
                    # Too short, discard
                    self.is_collecting = False
                    self.candidate_window = []
                    self.cooldown_counter = 0
                
        return None

    @staticmethod
    def extract_features(data: list | np.ndarray, sr: int) -> dict:
        """
        Extract temporal and morphological features from a signal window.
        Static method for stateless usage.
        """
        if not len(data):
            return {}

        data = np.array(data)
        abs_data = np.abs(data)
        
        peak_idx = np.argmax(abs_data)
        peak_amp = abs_data[peak_idx]
        
        duration_ms = (len(data) / sr) * 1000.0
        rise_time_ms = (peak_idx / sr) * 1000.0
        fall_time_ms = ((len(data) - peak_idx) / sr) * 1000.0
        
        asymmetry = rise_time_ms / (fall_time_ms + 1e-6)
        
        # New Feature: Peak Counting (for Double Blink Detection)
        # Find peaks > 50% of max amplitude to ignore noise
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(abs_data, height=peak_amp * 0.5, distance=sr * 0.05) # 50ms distance
        peak_count = len(peaks)
        
        # Statistical features
        kurt = float(stats.kurtosis(data))
        skew = float(stats.skew(data))
        
        features = {
            "amplitude": float(peak_amp),
            "duration_ms": float(duration_ms),
            "rise_time_ms": float(rise_time_ms),
            "fall_time_ms": float(fall_time_ms),
            "asymmetry": float(asymmetry),
            "peak_count": int(peak_count),
            "kurtosis": kurt,
            "skewness": skew
        }
        
        return features

    def _extract_features(self, window):
        """
        Internal wrapper to maintain compatibility and add timestamp.
        """
        features = BlinkExtractor.extract_features(window, self.sr)
        features["timestamp"] = self.current_idx / self.sr
        return features

    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        self.amp_threshold = eog_cfg.get("amp_threshold", self.amp_threshold)
        self.min_duration_ms = eog_cfg.get("min_duration_ms", self.min_duration_ms)
        self.max_duration_ms = eog_cfg.get("max_duration_ms", self.max_duration_ms)
