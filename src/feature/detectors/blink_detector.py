class BlinkDetector:
    """
    Classifies an event as a blink based on extracted features.
    Refactored to focus on robust amplitude and duration checks, removing brittle shape checks.
    """
    
    def __init__(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        
        # Simplified thresholds
        self.min_duration = eog_cfg.get("min_duration_ms", 50.0)    # Relaxed from 100
        self.max_duration = eog_cfg.get("max_duration_ms", 800.0)   # Relaxed from 600
        self.threshold_amp = eog_cfg.get("amp_threshold", 1.5)      # Primary detector
        
        # Debounce/Cooldown state
        self.last_detection_ts = 0.0
        self.cooldown_seconds = 0.5  # Ignore second phase of blink (biphasic)
        
    def detect(self, features: dict) -> bool:
        """
        Decision logic based on features.
        """
        if not features:
            return False
            
        dur = features.get("duration_ms", 0)
        amp = features.get("amplitude", 0)
        ts = features.get("timestamp", 0)
        
        # Cooldown Check
        if (ts - self.last_detection_ts) < self.cooldown_seconds:
             return False

        # Robust Logic:
        # 1. Amplitude must be significant (already checked by extractor, but verified here)
        # 2. Duration must be physiological (not a spike, not a drift)
        
        is_valid_amp = amp >= (self.threshold_amp * 0.8) # Allow slightly lower if extractor caught it
        is_valid_duration = self.min_duration <= dur <= self.max_duration
        
        if is_valid_amp and is_valid_duration:
            self.last_detection_ts = ts
            return True
            
        return False

    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        self.min_duration = eog_cfg.get("min_duration_ms", self.min_duration)
        self.max_duration = eog_cfg.get("max_duration_ms", self.max_duration)
        self.threshold_amp = eog_cfg.get("amp_threshold", self.threshold_amp)
