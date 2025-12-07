from scipy.signal import iirnotch

class NotchFilter50Hz:
    def __init__(self, sampling_rate=512):
        self.sampling_rate = sampling_rate
        
        # Design notch filter for 50 Hz power line noise
        self.b, self.a = iirnotch(
            w0=50.0,                      # Center frequency (Hz)
            Q=30,                         # Quality factor (narrowness)
            fs=sampling_rate              # Sampling frequency
        )
    
    def filter_signal(self, signal):
        """Remove 50 Hz power line interference"""
        from scipy.signal import lfilter
        filtered = lfilter(self.b, self.a, signal)
        return filtered
