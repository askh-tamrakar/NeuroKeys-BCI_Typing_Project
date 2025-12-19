class EEGDetector:
    """
    Classifies EEG states based on configurable profiles.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._load_config()
        
    def _load_config(self):
        self.profiles = self.config.get("features", {}).get("EEG", {}).get("profiles", {})
        
    def detect(self, features: dict) -> str | None:
        """
        Classify state based on multi-feature profiles.
        """
        if not features or not self.profiles:
            return None
            
        scores = {}
        CONSENSUS_THRESHOLD = 0.6
        
        for state, profile in self.profiles.items():
            if state == "Rest":
                continue
                
            match_count = 0
            total_features = 0
            
            for feat_name, range_val in profile.items():
                if feat_name in features and isinstance(range_val, list) and len(range_val) == 2:
                    total_features += 1
                    val = features[feat_name]
                    is_match = range_val[0] <= val <= range_val[1]
                    if is_match:
                        match_count += 1
            
            if total_features > 0:
                scores[state] = match_count / total_features

        if not scores:
            return None
            
        best_state = max(scores, key=scores.get)
        
        if scores[best_state] >= CONSENSUS_THRESHOLD:
            print(f"[EEGDetector] Detected: {best_state.upper()}")
            return best_state.upper()
                
        return None

    def update_config(self, config: dict):
        self.config = config
        self._load_config()
