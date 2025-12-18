class RPSDetector:
    """
    Classifies EMG features into Rock, Paper, or Scissors gestures.
    Uses configurable thresholds.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._load_config()
        
    def _load_config(self):
        emg_cfg = self.config.get("features", {}).get("EMG", {})
        
        # Thresholds (Default values based on heuristic estimation)
        # These need to be tuned based on actual signal levels
        self.rms_threshold_high = emg_cfg.get("rms_threshold_high", 1500.0) # Rock/Scissors vs Paper/Rest
        self.rms_threshold_low = emg_cfg.get("rms_threshold_low", 500.0)    # Paper vs Rest
        self.zcr_threshold = emg_cfg.get("zcr_threshold", 0.15)             # Scissors vs Rock
        
    def detect(self, features: dict) -> str | None:
        """
        Classify gesture based on features.
        Returns: "ROCK", "PAPER", "SCISSORS", or None (Rest/Unknown)
        """
        if not features:
            return None
            
        rms = features.get("rms", 0.0)
        zcr = features.get("zcr", 0.0)
        
        # 1. Check for Activity (vs Rest)
        if rms < self.rms_threshold_low:
            return None # Rest
            
        # 2. Check for High Intensity (Rock or Scissors)
        if rms > self.rms_threshold_high:
            # Distinguish Rock (Muscle tension) vs Scissors (Co-contraction/Dynamic)
            # Heuristic: Scissors often has higher frequency components (ZCR) or specific shape
            # NOTE: detailed separation usually requires ML. 
            # Simple heuristic: Scissors = High ZCR, Rock = Low ZCR
            if zcr > self.zcr_threshold:
                return "SCISSORS"
            else:
                return "ROCK"
                
        # 3. Medium Intensity -> Paper
        # (Opening hand requires some muscle, but less than fist)
        return "PAPER"

    def update_config(self, config: dict):
        self.config = config
        self._load_config()
