class BlinkDetector:
    """
    Classifies EOG events (SingleBlink, DoubleBlink, Rest) based on configurable profiles.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self._load_config()
        
    def _load_config(self):
        # Expecting structure: {"EOG": {"SingleBlink": {...}, "DoubleBlink": {...}}}
        # Config merger puts feature_config content under 'features' key if using facade
        features = self.config.get("features", {})
        self.profiles = features.get("EOG", {})
        if not self.profiles:
            # Fallback for direct feature config usage
            self.profiles = self.config.get("EOG", {})
        
    def detect(self, features: dict) -> str | None:
        """
        Classify event based on multi-feature profiles (SingleBlink vs DoubleBlink).
        """
        if not features or not self.profiles:
            return None
            
        scores = {}
        # Threshold for validation (all ranges must match for a strict detector, or high % match)
        # For blinks, we usually want strict compliance with key metrics (duration, amplitude)
        
        candidates = []
        
        for event_name, profile in self.profiles.items():
            # Skip non-dict config items (like amp_threshold)
            if not isinstance(profile, dict):
                continue
                
            # if event_name == "Rest": continue - Enabled Rest for calibration detection
                
            match_count = 0
            total_features = 0
            mismatches = []
            
            for feat_name, range_val in profile.items():
                if feat_name in features and isinstance(range_val, list) and len(range_val) == 2:
                    total_features += 1
                    val = features[feat_name]
                    
                    # Handle None or NaN features if any
                    if val is None:
                        continue
                        
                    is_match = range_val[0] <= val <= range_val[1]
                    if is_match:
                        match_count += 1
                    else:
                        mismatches.append(f"{feat_name}={val:.2f} (Expected {range_val})")
            
            # Debug print
            print(f"[BlinkDetector] Checking {event_name}")
            print(f"[BlinkDetector] matches={match_count}/{total_features} | Misses: {mismatches}")

            # Strict Policy: All configured constraints must pass for a blink
            if total_features > 0:
                score = match_count / total_features
                if score == 1.0:
                    candidates.append(event_name)
                    print(f"[BlinkDetector] Matched {event_name}")
                else:
                    print(f"[BlinkDetector] Failed {event_name}: {', '.join(mismatches)}")
        
        if candidates:
            # Return the first candidate that passed all checks
            # Since strict matching requires score == 1.0, any candidate here is valid.
            # If multiple match (rare with good disjoint configs), taking the first is acceptable.
            best_candidate = candidates[0]
            print(f"[BlinkDetector] [OK] Detected: {best_candidate}")
            return best_candidate
            
        return None

    def update_config(self, config: dict):
        self.config = config
        self._load_config()

