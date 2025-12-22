class RPSDetector:
    """
    Classifies EMG features into Rock, Paper, or Scissors gestures.
    Uses configurable thresholds.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._load_config()
        
    def _load_config(self):
        self.profiles = self.config.get("features", {}).get("EMG", {})
        
    def detect(self, features: dict) -> str | None:
        """
        Classify gesture based on multi-feature profiles and log values.
        """
        if not features or not self.profiles:
            return None
            
        # 1. Print all extracted values for the user
        # print(f"\n[RPSDetector] --- Features Extracted ---")
        # for feat, val in features.items():
        #     if feat != "timestamp":
        #         print(f"  > {feat:8}: {val:.4f}")
        
        scores = {}
        match_details = {}
        
        for gesture, profile in self.profiles.items():
            if gesture == "Rest":
                continue
                
            match_count = 0
            total_features = 0
            matches = []
            
            for feat_name, range_val in profile.items():
                if feat_name in features and isinstance(range_val, list) and len(range_val) == 2:
                    total_features += 1
                    val = features[feat_name]
                    is_match = range_val[0] <= val <= range_val[1]
                    if is_match:
                        match_count += 1
                        matches.append(feat_name)
            
            if total_features > 0:
                score = match_count / total_features
                scores[gesture] = score
                match_details[gesture] = f"{match_count}/{total_features} matches: {matches}"

        # Print match report
        # print(f"[RPSDetector] --- Match Report ---")
        # for gesture, detail in match_details.items():
        #     print(f"  {gesture:10}: {detail} (Score: {scores[gesture]:.2f})")

        # Threshold for detection (consensus)
        CONSENSUS_THRESHOLD = 0.6
        
        if not scores:
            return None
            
        best_gesture = max(scores, key=scores.get)
        
        if scores[best_gesture] >= CONSENSUS_THRESHOLD:
            print(f"[RPSDetector] [OK] Detected: {best_gesture.upper()}")
            return best_gesture.upper()
                
        # print(f"[RPSDetector] [SKIP] No consensus (Best: {best_gesture} @ {scores[best_gesture]:.2f})")
        return None

    def update_config(self, config: dict):
        self.config = config
        self._load_config()
