from pathlib import Path

class BlinkDetector:
    """
<<<<<<< HEAD
    Classifies an event as a blink using robust heuristic rules.
    ML model has been removed in favor of signal processing metrics.
=======
    Classifies an event as a blink based on extracted features.
    Refactored to focus on robust amplitude and duration checks, removing brittle shape checks.
>>>>>>> rps-implement
    """
    
    def __init__(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
<<<<<<< HEAD
        if not eog_cfg:
             eog_cfg = config.get("EOG", {})
        
        # Heuristic Thresholds
        self.min_duration = eog_cfg.get("min_duration_ms", 100.0)
        self.max_duration = eog_cfg.get("max_duration_ms", 800.0)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", 0.05) 
        self.max_asymmetry = eog_cfg.get("max_asymmetry", 3.5) 
        self.min_kurtosis = eog_cfg.get("min_kurtosis", -3.0) 
        
        print(f"[BlinkDetector] 📏 Initialized with Heuristics: Dur={self.min_duration}-{self.max_duration}ms")

    def detect(self, features: dict) -> str | None:
        """
        Classify event based on morphological features.
        """
        if not features:
            return None
        
        dur = features.get("duration_ms", 0)
        asym = features.get("asymmetry", 0)
        kurt = features.get("kurtosis", 0)
        
        # Check validity
        is_valid_duration = self.min_duration <= dur <= self.max_duration
        is_valid_asymmetry = self.min_asymmetry <= asym <= self.max_asymmetry
        is_valid_shape = kurt >= self.min_kurtosis

        if is_valid_duration and is_valid_asymmetry and is_valid_shape:
            # Classification Logic
            p_count = features.get("peak_count", 1)
            
            if p_count >= 2:
                print(f"[BlinkDetector] 🟢 DoubleBlink Detected (Peaks: {p_count}, Dur: {dur:.1f}ms)")
                return "DoubleBlink"
            else:
                print(f"[BlinkDetector] 🔵 SingleBlink Detected (Peaks: {p_count}, Dur: {dur:.1f}ms)")
                return "SingleBlink"
=======
        
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
>>>>>>> rps-implement
            
        return False

    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
<<<<<<< HEAD
        if not eog_cfg:
             eog_cfg = config.get("EOG", {})
             
        self.min_duration = eog_cfg.get("min_duration_ms", self.min_duration)
        self.max_duration = eog_cfg.get("max_duration_ms", self.max_duration)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", self.min_asymmetry)
        self.max_asymmetry = eog_cfg.get("max_asymmetry", self.max_asymmetry)
        self.min_kurtosis = eog_cfg.get("min_kurtosis", self.min_kurtosis)
=======
        self.min_duration = eog_cfg.get("min_duration_ms", self.min_duration)
        self.max_duration = eog_cfg.get("max_duration_ms", self.max_duration)
        self.threshold_amp = eog_cfg.get("amp_threshold", self.threshold_amp)
>>>>>>> rps-implement
