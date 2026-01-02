from pathlib import Path

class BlinkDetector:
    """
    Classifies an event as a blink using robust heuristic rules.
    ML model has been removed in favor of signal processing metrics.
    """
    
    def __init__(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
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
            
        return None

    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        if not eog_cfg:
             eog_cfg = config.get("EOG", {})
             
        self.min_duration = eog_cfg.get("min_duration_ms", self.min_duration)
        self.max_duration = eog_cfg.get("max_duration_ms", self.max_duration)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", self.min_asymmetry)
        self.max_asymmetry = eog_cfg.get("max_asymmetry", self.max_asymmetry)
        self.min_kurtosis = eog_cfg.get("min_kurtosis", self.min_kurtosis)
