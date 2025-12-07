import numpy as np
from scipy.signal import butter, filtfilt

class EMGFilter:
    def __init__(self, sampling_rate=512):
        self.sampling_rate = sampling_rate
        
        # Design high-pass Butterworth filter
        # Cutoff at 70 Hz
        nyquist_freq = sampling_rate / 2
        normalized_cutoff = 70.0 / nyquist_freq
        
        self.b, self.a = butter(
            N=4,                          # 4th order
            Wn=normalized_cutoff,         # Normalized frequency
            btype='high'                  # High-pass
        )
    
    def filter_signal(self, signal):
        """
        Apply high-pass filter to EMG signal
        
        Args:
            signal: numpy array of EMG data
        
        Returns:
            filtered_signal: numpy array of filtered EMG
        """
        # Use filtfilt for zero-phase filtering
        filtered = filtfilt(self.b, self.a, signal)
        return filtered
    
    def get_filter_coefficients(self):
        """Return filter coefficients for analysis"""
        return {'b': self.b, 'a': self.a}


# Usage
emg_filter = EMGFilter(sampling_rate=512)
filtered_emg = emg_filter.filter_signal(raw_emg_data)
