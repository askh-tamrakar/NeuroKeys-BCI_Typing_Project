import numpy as np
import collections
from scipy import signal

class EEGExtractor:
    """
    Feature Extractor for EEG.
    Extracts frequency-domain features (Band Powers) from a sliding window.
    """
    
    def __init__(self, channel_index: int, config: dict, sr: int):
        self.channel_index = channel_index
        self.sr = sr
        
        # Window settings
        self.buffer_size = 512 
        self.stride = 64
        
        self.buffer = collections.deque(maxlen=self.buffer_size)
        self.sample_count = 0
        
        self._load_config(config)
        
    def _load_config(self, config):
        self.config = config
        eeg_cfg = self.config.get("features", {}).get("EEG", {})
        self.freq_bands = eeg_cfg.get("freq_bands", {
            "delta": [0.5, 4],
            "theta": [4, 8],
            "alpha": [8, 13],
            "beta": [13, 30]
        })
        
    def process(self, sample_val: float):
        """
        Process a single sample.
        Returns features if window is ready, else None.
        """
        self.buffer.append(sample_val)
        self.sample_count += 1
        
        if len(self.buffer) == self.buffer_size and self.sample_count % self.stride == 0:
            return self._extract_features(list(self.buffer))
            
        return None

    def _extract_features(self, window):
        data = np.array(window)
        # Simple Periodogram or Welch's method (nperseg=len(data) for 1s window is just fine)
        freqs, psd = signal.welch(data, self.sr, nperseg=len(data))
        
        features = {
            "timestamp": self.sample_count / self.sr
        }
        
        total_power = 0
        for band, (low, high) in self.freq_bands.items():
            idx = np.logical_and(freqs >= low, freqs <= high)
            power = np.sum(psd[idx])
            features[band] = float(power)
            total_power += power
            
        features["total_power"] = float(total_power)
        
        if total_power > 0:
            for band in self.freq_bands.keys():
                features[f"{band}_rel"] = features[band] / total_power
        
        return features

    def update_config(self, config: dict):
        self._load_config(config)
