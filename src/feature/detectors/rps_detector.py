import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

class RPSDetector:
    """
    Classifies EMG features into Rock, Paper, or Scissors gestures.
    Uses a pre-trained Random Forest model.
    
    Refactored to use a Candidate/State-based approach:
    - Buffers predictions while the gesture is active (not Rest).
    - Emits the most frequent prediction when the gesture returns to Rest.
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self.scaler = None
        
        # State tracking for candidate-based detection
        self.collecting_candidates = False
        self.candidates = []
        self.last_active_ts = 0.0
        
        # Configuration for state machine
        rps_cfg = config.get("features", {}).get("RPS", {})
        self.confidence_threshold = rps_cfg.get("confidence_threshold", 0.6)
        
        self._load_model()
        
    def _load_model(self):
        try:
            # Locate model paths relative to project root (assuming this file is in src/feature/detectors)
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            models_dir = project_root / "data" / "models"
            
            model_path = models_dir / "emg_rf.joblib"
            scaler_path = models_dir / "emg_scaler.joblib"
            
            if model_path.exists() and scaler_path.exists():
                self.model = joblib.load(model_path)
                self.scaler = joblib.load(scaler_path)
                print(f"[RPSDetector] [OK] Loaded ML Model from {model_path}")
            else:
                print(f"[RPSDetector] [WARN] Model not found at {model_path}")
                
        except Exception as e:
            print(f"[RPSDetector] [ERROR] Error loading model: {e}")
        
    def _predict_instant(self, features: dict) -> tuple[str, float]:
        """
        Helper: Make a single instant prediction from features.
        Returns: (Label, Confidence)
        """
        if not self.model or not self.scaler:
             return "Unknown", 0.0
             
        try:
            # 1. Prepare Feature Vector (Must match training order)
            # ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
            feature_cols = ['rms', 'mav', 'var', 'wl', 'peak', 'range', 'iemg', 'entropy', 'energy', 'kurtosis', 'skewness', 'ssc', 'wamp']
            
            row = []
            for col in feature_cols:
                val = features.get(col, 0.0)
                # handle potential missing 'range' vs 'rng' if any
                if col == 'range' and 'range' not in features and 'rng' in features:
                   val = features['rng']
                row.append(val)
            
            # 2. Scale
            X = pd.DataFrame([row], columns=feature_cols)
            X_scaled = self.scaler.transform(X)
            
            # 3. Predict PROBABILITY
            probs = self.model.predict_proba(X_scaled)[0]
            pred_idx = np.argmax(probs)
            confidence = probs[pred_idx]
            
            pred_label_int = self.model.classes_[pred_idx]
            
            # Map back to String
            # 0: Rest, 1: Rock, 2: Paper, 3: Scissors
            label_map = {0: 'Rest', 1: 'Rock', 2: 'Paper', 3: 'Scissors'}
            
            if isinstance(pred_label_int, str):
                 pred_label_str = pred_label_int
            else:
                 pred_label_str = label_map.get(int(pred_label_int), 'Unknown')

            return pred_label_str, confidence

        except Exception as e:
            print(f"[RPSDetector] Prediction Error: {e}")
            return "Error", 0.0

    def detect(self, features: dict) -> str | None:
        """
        Stateful detection logic:
        - If Rest -> Resolve any pending candidates.
        - If Gesture -> Add to candidates.
        """
        label, confidence = self._predict_instant(features)
        
        # Determine if this instant frame is "Active" (valid gesture) or "Rest"
        is_confident = confidence > self.confidence_threshold
        is_active = is_confident and label in ['Rock', 'Paper', 'Scissors']
        is_rest = is_confident and label == 'Rest'
        
        # State Machine
        if is_active:
            if not self.collecting_candidates:
                self.collecting_candidates = True
                self.candidates = []
                # print(f"[RPS] Starting gesture candidate collection... ({label})")
            
            self.candidates.append(label)
            return None # Don't emit yet
            
        elif is_rest:
            if self.collecting_candidates:
                # End of a gesture, resolve it!
                if self.candidates:
                    # Logic: Most frequent label
                    # Could also weigh by confidence if we stored it, but Mode is usually robust enough
                    counts = Counter(self.candidates)
                    most_common = counts.most_common(1)[0][0] # (Label, Count)
                    
                    # print(f"[RPS] Gesture Finished. Candidates: {counts}. Final: {most_common}")
                    
                    self.collecting_candidates = False
                    self.candidates = []
                    return most_common
                else:
                    self.collecting_candidates = False
                    return "Rest"
            else:
                # Already resting, ensure system knows
                return "Rest"
                
        else:
            # Low confidence or Unknown
            # If we are collecting, maybe tolerate a few dropped frames? 
            # For now, treat as noise/continue current state or ignore.
            # If we treat as "Rest", we might chop gestures too aggressively.
            # If we ignore, we rely on the next strong frame.
            return None
            
        return None

    def update_config(self, config: dict):
        self.config = config
        rps_cfg = config.get("features", {}).get("RPS", {})
        self.confidence_threshold = rps_cfg.get("confidence_threshold", 0.6)
        self._load_model()
