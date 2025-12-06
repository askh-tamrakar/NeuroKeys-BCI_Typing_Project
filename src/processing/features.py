import numpy as np

class EMGFeatureExtractor:
    def __init__(self):
        pass

    def extract(self, signal):
        """
        Extracts features from a 1D signal array.
        Returns a dict of features.
        """
        if len(signal) == 0:
            return {"rms": 0.0, "mav": 0.0, "max": 0.0}
            
        # Root Mean Square
        rms = np.sqrt(np.mean(signal**2))
        
        # Mean Absolute Value
        mav = np.mean(np.abs(signal))
        
        # Max Amplitude
        max_val = np.max(np.abs(signal))
        
        # Simple Zero Crossing Rate (very basic noise dependent)
        # zc = ((signal[:-1] * signal[1:]) < 0).sum()
        
        return {
            "rms": float(rms),
            "mav": float(mav),
            "max": float(max_val)
        }
