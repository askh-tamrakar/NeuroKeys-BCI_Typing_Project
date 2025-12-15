import collections
import numpy as np

class BlinkDetector:
    """
    Detects blinks from EOG signal using Slope and Amplitude thresholding.
    
    Logic:
    1. Calculate slope (derivative).
    2. Check if absolute amplitude > Threshold AND absolute slope > Slope Threshold.
    3. Enforce refractory period to avoid double counting.
    """
    
    def __init__(self, 
                 amp_threshold: float = 100.0, 
                 slope_threshold: float = 50.0, 
                 refractory_period_ms: float = 300.0,
                 sampling_rate: int = 512):
        
        self.amp_threshold = amp_threshold
        self.slope_threshold = slope_threshold
        self.refractory_samples = int((refractory_period_ms / 1000.0) * sampling_rate)
        
        self.last_blink_sample = -self.refractory_samples
        self.current_sample_idx = 0
        
        # Buffer for slope calculation (simple difference)
        self.prev_val = 0.0
        self.initialized = False

    def process(self, value: float) -> bool:
        """
        Process a single EOG sample.
        Returns True if a blink is detected.
        """
        self.current_sample_idx += 1
        
        if not self.initialized:
            self.prev_val = value
            self.initialized = True
            return False
        
        # Calculate Slope (simple difference for now, can be improved with window)
        slope = value - self.prev_val
        self.prev_val = value
        
        # Check Refractory Period
        if (self.current_sample_idx - self.last_blink_sample) < self.refractory_samples:
            return False
            
        # Detection Logic
        # EOG Blink = Large Amplitude Excursion + Steep Slope
        if abs(value) > self.amp_threshold and abs(slope) > self.slope_threshold:
            self.last_blink_sample = self.current_sample_idx
            return True
            
        return False

    def update_config(self, amp_thresh, slope_thresh):
        """Runtime update of thresholds."""
        if amp_thresh: self.amp_threshold = amp_thresh
        if slope_thresh: self.slope_threshold = slope_thresh
