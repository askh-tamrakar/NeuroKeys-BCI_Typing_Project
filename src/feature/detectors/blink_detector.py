class BlinkDetector:
    """
    Classifies an event as a blink based on extracted features.
    """
    
    def __init__(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        
        # Classification thresholds
        self.min_duration = eog_cfg.get("min_duration_ms", 100.0)
        self.max_duration = eog_cfg.get("max_duration_ms", 600.0)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", 0.05) 
        self.max_asymmetry = eog_cfg.get("max_asymmetry", 2.5) 
        self.min_kurtosis = eog_cfg.get("min_kurtosis", -3.0) 
        
    def detect(self, features: dict) -> bool:
        """
        Decision logic based on features.
        """
        if not features:
            return False
            
        dur = features["duration_ms"]
        asym = features["asymmetry"]
        kurt = features["kurtosis"]
        
        # Rule-based classification
        is_valid_duration = self.min_duration <= dur <= self.max_duration
        is_valid_asymmetry = self.min_asymmetry <= asym <= self.max_asymmetry
        is_valid_shape = kurt >= self.min_kurtosis
        
        if is_valid_duration and is_valid_asymmetry and is_valid_shape:
            return True
            
        return False

    def update_config(self, config: dict):
        eog_cfg = config.get("features", {}).get("EOG", {})
        self.min_duration = eog_cfg.get("min_duration_ms", self.min_duration)
        self.max_duration = eog_cfg.get("max_duration_ms", self.max_duration)
        self.min_asymmetry = eog_cfg.get("min_asymmetry", self.min_asymmetry)
        self.max_asymmetry = eog_cfg.get("max_asymmetry", self.max_asymmetry)
        self.min_kurtosis = eog_cfg.get("min_kurtosis", self.min_kurtosis)
